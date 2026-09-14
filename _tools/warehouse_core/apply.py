"""Execute resolved actions in one project (DESIGN §4.2)."""
from __future__ import annotations

import sys
from pathlib import Path

from . import items
from . import lockfile
from . import readme as readme_mod
from .errors import GitError, UsageError
from .fsops import WriteGuard, atomic_write, cleanup_temp_files, delete_file, prune_empty_dirs
from .inspect import accepted_hashes, drifted, inspect_item, missing, present_clean, tracked_paths
from .lockfile import Lock, LockItem
from .render import effective_settings, normalize_stamp, render_release, settings_digest, sha256
from .resolve import ItemAction

FAILED_STATUSES = {"unfilled", "collision", "error", "missing-tag"}
import uuid
import contextlib

_probe_cache: dict[Path, bool] = {}

def is_case_insensitive(target_dir: Path) -> bool:
    d = target_dir
    while not d.exists() and d != d.parent:
        d = d.parent
    if d not in _probe_cache:
        test_name = f".case_probe_{uuid.uuid4().hex}"
        test_path = d / test_name
        try:
            test_path.write_text("")
            _probe_cache[d] = (d / test_name.upper()).exists()
        except OSError:
            _probe_cache[d] = sys.platform in ("win32", "darwin")
        finally:
            with contextlib.suppress(OSError):
                test_path.unlink()
    return _probe_cache[d]

def fold(path: str, case_insensitive: bool) -> str:
    """Path key for comparisons: case-folded on case-insensitive filesystems."""
    return path.casefold() if case_insensitive else path


def _order(actions: list[ItemAction], catalog) -> list[ItemAction]:
    adj = {a.id: [] for a in actions}
    in_degree = {a.id: 0 for a in actions}
    action_by_id = {a.id: a for a in actions}

    for a in actions:
        if a.to_v:
            try:
                meta = catalog.meta(a.id, a.to_v)
                for rid, _ in meta.requires:
                    if rid in action_by_id:
                        adj[rid].append(a.id)
                        in_degree[a.id] += 1
            except Exception:
                pass

    def tie_key(a_id):
        return (0 if items.kind_of(a_id) == "tool" else 1, a_id)

    zero_in = [a.id for a in actions if in_degree[a.id] == 0]
    zero_in.sort(key=tie_key, reverse=True)

    ordered = []
    while zero_in:
        curr = zero_in.pop()
        ordered.append(action_by_id[curr])
        for nxt in adj[curr]:
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                zero_in.append(nxt)
        zero_in.sort(key=tie_key, reverse=True)

    if len(ordered) < len(actions):
        cycle_ids = {a.id for a in actions} - {a.id for a in ordered}
        for cid in sorted(cycle_ids, key=tie_key):
            act = action_by_id[cid]
            act.kind = "error"
            act.reason = "dependency cycle"
            ordered.append(act)

    return ordered


def deprecation_note(catalog, item_id: str, v) -> str | None:
    try:
        meta = catalog.meta(item_id, v)
    except (GitError, UsageError):
        return None
    if meta.status != "deprecated":
        return None
    succ = catalog.successor(item_id)
    return f"deprecated: use {succ}" if succ else "deprecated"


def info_lines(report, pname: str, a: ItemAction) -> None:
    if a.blocked_newer:
        report.add(pname, "blocked", a.id, a.blocked_newer)
    if a.major:
        # a dependency-only item moves with the item that requires it
        via = a.via if getattr(a, "via", None) else (a.required_by[0] if a.source == "dependency" and a.required_by else a.id)
        report.add(pname, "major", a.id,
                   f"{a.to_v} ({a.major} available: warehouse pull {via} --major)")
    if a.narrowed:
        report.add(pname, "outside-pin", a.id, a.reason or "")
    elif a.outside_pin:
        report.add(pname, "outside-pin", a.id, f"{a.to_v} ({a.outside_pin} outside pin @{a.pin.text})")


def delete_files(guard: WriteGuard, target_dir: Path, paths) -> None:
    for rel in sorted(paths):
        p = target_dir / rel
        delete_file(guard, p)
        prune_empty_dirs(guard, p.parent)


def write_readme(ctx, project, lock: Lock, guard: WriteGuard, report) -> None:
    target_dir = project.root / project.manifest.target
    path = target_dir / "README.md"
    installed = {i: li for i, li in lock.items.items() if li.version}
    existing = path.read_bytes() if path.is_file() else None
    if existing is not None and not readme_mod.has_marker(existing):
        if installed:
            report.add(project.name, "collision", None,
                       f"{project.manifest.target}/README.md exists and is not generated; not written")
        return
    if not installed:
        if existing is not None:
            delete_file(guard, path)
        lock.readme = None
        return
    notes = {}
    for iid, li in installed.items():
        n = deprecation_note(ctx.catalog, iid, li.ver) if li.ver else None
        if n:
            notes[iid] = n
    data = readme_mod.generate(lock, notes)
    if existing != data:
        atomic_write(guard, path, data)
    lock.readme = sha256(data)


def _exclude(ctx) -> list[str]:
    return ctx.config.sync_exclude


def _failed_requirement(ctx, lock: Lock, a: ItemAction, failed: dict[str, str]) -> str | None:
    """#14: a changed item whose required item ended unfilled/collision/error is not installed."""
    if a.kind not in ("install", "update", "downgrade") or a.to_v is None:
        return None
    try:
        reqs = ctx.catalog.meta(a.id, a.to_v).requires
    except (GitError, UsageError):
        return None
    for rid, rpin in reqs:
        if failed and rid in failed:
            return f"{a.id} {a.to_v} needs {rid}, which was not synced ({failed[rid]})"
        l_item = lock.items.get(rid)
        l_ver = l_item.version if l_item else ""
        l_ver_obj = l_item.ver if l_item else None
        if not l_ver_obj or not rpin.matches(l_ver_obj):
            return f"{a.id} {a.to_v} needs {rid}@{rpin.text} (project has {l_ver or 'none'})"
    return None


def apply_actions(ctx, project, lock: Lock, actions: list[ItemAction], report, *, today: str) -> None:
    root = project.root
    m = project.manifest
    pname = project.name
    guard = WriteGuard(root, m.target)
    cleanup_temp_files(guard)
    target_dir = root / m.target
    failed: dict[str, str] = {}

    for a in _order(actions, ctx.catalog):
        li = lock.items.get(a.id)
        start = len(report.lines)
        try:
            if a.kind == "not-installable":
                report.add(pname, "not-installable", a.id, a.reason or "")
            elif a.kind == "blocked":
                report.add(pname, "blocked", a.id, a.reason or "")
            elif a.kind == "error":
                report.add(pname, "error", a.id, a.reason or "")
            elif a.kind == "pin-moved":
                report.add(pname, "major", a.id, a.reason or "")
            elif a.kind == "orphan":
                if li is not None:  # drop requirers that are no longer installed
                    li.required_by = [r for r in li.required_by if r in lock.items and r != a.id]
                report.add(pname, "orphan", a.id, a.reason or "")
            elif a.kind == "remove":
                _remove_hand_removed(guard, target_dir, lock, a, report, pname)
            else:
                why = _failed_requirement(ctx, lock, a, failed)
                if why:
                    report.add(pname, "blocked", a.id, why)
                else:
                    _apply_one(ctx, project, lock, a, li, guard, target_dir, report, today)
        except Exception as e:  # per item: report and continue (GuardError, OSError, bad release content ...)
            if isinstance(e, GitError) and "missing-tag" in str(e):
                report.add(pname, "missing-tag", a.id, str(e))
            else:
                report.add(pname, "error", a.id, f"{type(e).__name__}: {e}")
                import traceback
                if getattr(ctx, "verbose", False):
                    traceback.print_exc()
                try:
                    ctx.state_dir.mkdir(parents=True, exist_ok=True)
                    with open(ctx.state_dir / "hook.log", "a", encoding="utf-8") as f:
                        f.write(f"Traceback for {a.id} in {pname}:\n")
                        traceback.print_exc(file=f)
                except Exception:
                    pass
            try:
                lockfile.save(root, lock, guard)
            except Exception:
                pass
        for ln in report.lines[start:]:
            if ln.id == a.id and ln.status in FAILED_STATUSES and not ln.info:
                failed.setdefault(a.id, ln.status)

    write_readme(ctx, project, lock, guard, report)
    lockfile.save(root, lock, guard)
    if any(li.pending for li in lock.items.values()):
        report.needs_retry = True


def _remove_hand_removed(guard, target_dir, lock, a, report, pname) -> None:
    li = lock.items[a.id]
    states = inspect_item(target_dir, li)
    drift = drifted(states)
    delete_files(guard, target_dir, present_clean(target_dir, li))  # incl. files only in the pending journal
    if drift:
        known = accepted_hashes(li)
        li.files = {p: li.files.get(p) or sorted(known[p])[0] for p in drift}
        li.pending = None
        report.add(pname, "drift", a.id, "entry removed from .warehouse.yml; kept edited file(s): " + ", ".join(drift))
    else:
        del lock.items[a.id]
        report.add(pname, "removed", a.id, "removed from .warehouse.yml")


def _apply_one(ctx, project, lock, a: ItemAction, li: LockItem | None, guard, target_dir, report, today) -> None:
    pname = project.name
    m = project.manifest
    C = ctx.catalog
    to_v = a.to_v
    root = project.root

    meta = C.meta(a.id, to_v) if C.has_tag(a.id, to_v) else None
    if meta is None:
        # installed version whose tag is gone: nothing can be rendered
        if li is not None and a.kind == "keep":
            states = inspect_item(target_dir, li)
            if drifted(states):
                report.add(pname, "drift", a.id, f"{li.version} skipped: {', '.join(drifted(states))} edited locally")
            elif missing(states):
                report.add(pname, "missing-tag", a.id, f"{a.id}@{to_v} tag missing; cannot restore {', '.join(missing(states))}")
            else:
                report.add(pname, "unchanged", a.id, f"{li.version} (tag missing)")
            info_lines(report, pname, a)
            return
        raise GitError(f"missing-tag: {a.id}@{to_v} does not exist")

    values, unfilled = effective_settings(meta, m.settings)
    if unfilled:
        report.add(pname, "unfilled", a.id, "needs settings: " + ", ".join(unfilled))
        return
    digest = settings_digest(values)
    files = C.files(a.id, to_v)

    if li is not None and a.kind == "keep" and digest == li.settings_digest and not li.pending:
        # metadata only (source/pin/required_by), no file writes
        li.source = a.source
        li.required_by = list(a.required_by)
        if a.pin is not None:
            li.pin = a.pin.text
        states = inspect_item(target_dir, li)
        drift = drifted(states)
        miss = missing(states)
        if drift:
            report.add(pname, "drift", a.id, f"{li.version} skipped: {', '.join(drift)} edited locally")
        elif miss:
            rendered = render_release(meta, files, m.settings, li.synced or today, exclude=_exclude(ctx))
            restored, unrestorable = [], []
            for rel in miss:
                data = rendered.files.get(rel)
                if data is None or sha256(data) != li.files.get(rel):
                    unrestorable.append(rel)
                    continue
                atomic_write(guard, target_dir / rel, data)
                restored.append(rel)
            lockfile.save(root, lock, guard)
            if restored:
                report.add(pname, "restored", a.id, f"{li.version} restored: {', '.join(restored)}")
            if unrestorable:
                report.add(pname, "error", a.id, f"{li.version} cannot restore {', '.join(unrestorable)}: "
                                                 "the release no longer renders the same bytes")
        else:
            report.add(pname, "unchanged", a.id, li.version)
        _post(ctx, report, pname, a, li.ver or to_v)
        return

    rendered = render_release(meta, files, m.settings, today, exclude=_exclude(ctx))
    tracked = tracked_paths(li) if li else set()
    states: dict[str, str] = {}
    if li is not None:
        states = inspect_item(target_dir, li)
        drift = drifted(states)
        if drift:
            report.add(pname, "drift", a.id, f"{li.version} skipped: {', '.join(drift)} edited locally")
            _post(ctx, report, pname, a, li.ver)
            return
    tracked_by_fold = {fold(t, is_case_insensitive(target_dir)): t for t in tracked}

    adopted: dict[str, str] = {}
    for rel, data in rendered.files.items():
        p = target_dir / rel
        if fold(rel, is_case_insensitive(target_dir)) in tracked_by_fold or not p.is_file():
            continue
        disk = p.read_bytes()
        if normalize_stamp(disk.replace(b"\r\n", b"\n")) == normalize_stamp(data):
            adopted[rel] = sha256(disk)
        else:
            report.add(pname, "collision", a.id,
                       f"{m.target}/{rel} exists and is not a warehouse copy; item skipped")
            return

    new_hashes = {rel: sha256(d) for rel, d in rendered.files.items()}
    if li is None:
        li = LockItem(version="", source=a.source)
        lock.items[a.id] = li
    # journal: keep every hash accepted so far per path, so a second interruption can't turn files written
    # by the first one into false drift
    accepted = {rel: sorted(hs) for rel, hs in accepted_hashes(li).items()}
    li.pending = {"version": str(to_v), "files": new_hashes, "synced": today, "settings_digest": digest,
                  "accepted": accepted}
    lockfile.save(root, lock, guard)

    # stale tracked paths (incl. case-only renames and pending-only leftovers) go first, only if clean
    stale = [t for t in tracked if t not in rendered.files and states.get(t) in ("clean", "eol-only")]
    delete_files(guard, target_dir, stale)

    final_hashes = {}
    for rel, data in rendered.files.items():
        p = target_dir / rel
        if rel in adopted:
            final_hashes[rel] = adopted[rel]
            continue
        if p.is_file():
            disk = p.read_bytes()
            if disk == data:
                final_hashes[rel] = new_hashes[rel]
                continue
            if states.get(rel) == "eol-only" and disk.replace(b"\r\n", b"\n") == data:
                final_hashes[rel] = new_hashes[rel]
                continue
        atomic_write(guard, p, data)
        final_hashes[rel] = new_hashes[rel]

    from_v = li.ver
    old_digest = li.settings_digest
    lock.items[a.id] = LockItem(version=str(to_v), pin=a.pin.text if a.pin else None, source=a.source,
                                required_by=list(a.required_by), settings_digest=digest, synced=today,
                                state="ok", files=final_hashes, promoted=None, pending=None)
    lockfile.save(root, lock, guard)

    if from_v is None:
        if adopted and len(adopted) == len(rendered.files):
            report.add(pname, "adopted", a.id, f"{to_v} (existing files match)")
        else:
            report.add(pname, "installed", a.id, str(to_v))
    elif to_v > from_v:
        report.add(pname, "updated", a.id, f"{from_v} -> {to_v}")
    elif to_v < from_v:
        report.add(pname, "downgraded", a.id, f"{from_v} -> {to_v}")
    else:
        report.add(pname, "updated", a.id, f"{to_v} settings changed" if old_digest != digest
                   else f"{to_v} completed interrupted update")
    _post(ctx, report, pname, a, to_v)


def _post(ctx, report, pname, a: ItemAction, v) -> None:
    if v is not None:
        note = deprecation_note(ctx.catalog, a.id, v)
        if note:
            report.add(pname, "deprecated", a.id, note)
    info_lines(report, pname, a)
