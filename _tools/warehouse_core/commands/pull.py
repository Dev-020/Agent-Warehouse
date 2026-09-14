"""pull <id> | --all [--major] (DESIGN §4.5)."""
from __future__ import annotations

from .. import changelog, items, lockfile, manifest as manifest_mod
from ..apply import apply_actions
from ..errors import GitError, UsageError
from ..fsops import WriteGuard, atomic_write
from ..report import Report
from ..resolve import ResolveError, effective_pin, resolve
from ..semver import Pin
from . import current_project, emit


def breaking_text(catalog, item_id, low, high) -> list[str]:
    latest = catalog.latest(item_id)
    try:
        secs = changelog.parse(catalog.changelog_text(item_id, latest), is_document=items.is_document(item_id))
    except (UsageError, GitError, KeyError):
        return []
    out = []
    for sec in changelog.entries_between(secs, low, high):
        for b in changelog.breaking(sec):
            out.append(f"  {sec.name}: " + " ".join(x.strip() for x in b.split("\n")))
    return out


def run(ctx, args) -> int:
    if bool(args.id) == bool(args.all):
        raise UsageError("give exactly one of <id> or --all")
    proj, lock = current_project(ctx)
    m = proj.manifest
    C = ctx.catalog
    label = "pull" + (f" {args.id}" if args.id else " --all") + (" --major" if args.major else "")
    report = Report(label, ctx.today, verbose=ctx.verbose)
    report.project(proj.name, "[auto]" if m.auto_sync else "[manual]")
    if args.id:
        if m.entry(args.id) is None and args.id not in lock.items:
            raise UsageError(f"{args.id} is not in .warehouse.yml or .warehouse.lock")
        ids = {args.id}
    else:
        ids = {e.id for e in m.entries} | set(lock.items)

    overrides: dict[str, Pin] = {}
    manifest_updates: dict[str, Pin] = {}
    if args.major:
        for iid in sorted(ids):
            li = lock.items.get(iid)
            inst = li.ver if li else None
            target = C.latest(iid)
            if inst is None or target is None:
                continue
            if target.line <= inst.line:
                # still resolved in major mode: its dependencies may need to cross a MAJOR line
                if args.id:
                    report.preamble.append(f"{iid}: {inst} is on the highest MAJOR line (unchanged unless "
                                           "a required item needs a MAJOR update)")
                continue
            for line in breaking_text(C, iid, inst, target):
                report.preamble.append(f"{iid} BREAKING {line.strip()}")
            entry = m.entry(iid)
            if entry is None:  # dependency-only
                bad = []
                for r in li.required_by:
                    rli = lock.items.get(r)
                    if rli is None or rli.ver is None:
                        continue
                    try:
                        for rid, rpin in C.meta(r, rli.ver).requires:
                            if rid == iid and not rpin.matches(target):
                                bad.append(f"{r}@{rpin.text}")
                    except (GitError, UsageError):
                        pass
                if bad and not all(b.split("@")[0] in ids for b in bad):
                    report.add(proj.name, "blocked", iid, f"{target} available but required by "
                               + ", ".join(bad) + "; pull the requiring item with --major instead")
                    ids.discard(iid)
                continue
            pin, _ = effective_pin(C, lock, iid, entry.pin)
            if pin is None:
                continue
            new_pin = pin.moved_to(target)
            overrides[iid] = new_pin
            manifest_updates[iid] = new_pin
        if not ids:
            return emit(ctx, report)

    try:
        before = {i: li.version for i, li in lock.items.items()}
        actions = resolve(C, m, lock, mode="major" if args.major else "pull", ids=ids, pin_overrides=overrides)
        apply_actions(ctx, proj, lock, actions, report, today=ctx.today)
    except ResolveError as e:
        report.add(proj.name, "error", None, str(e))
        return emit(ctx, report)

    written = {i: p for i, p in manifest_updates.items()
               if lock.items.get(i) and lock.items[i].version != before.get(i)
               and lock.items[i].ver and p.matches(lock.items[i].ver)}
    if written:
        text = m.raw
        cur = m
        for iid, pin in sorted(written.items()):
            text = manifest_mod.add_or_replace_entry(cur, iid, pin)
            cur = manifest_mod.load_text(text, m.path)
        guard = WriteGuard(proj.root, m.target, allow_manifest=True)
        atomic_write(guard, m.path, text.encode("utf-8"))
        for iid, pin in sorted(written.items()):
            report.preamble.append(f"manifest: {iid} pin moved to @{pin.text}")
    return emit(ctx, report)
