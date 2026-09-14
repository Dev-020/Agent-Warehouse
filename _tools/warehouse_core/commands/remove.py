"""remove <id> [--prune] [--force] (DESIGN §4.7)."""
from __future__ import annotations

from .. import lockfile, manifest as manifest_mod
from ..apply import delete_files, write_readme
from ..errors import UsageError
from ..fsops import WriteGuard, atomic_write
from ..inspect import drifted, inspect_item, tracked_paths
from ..report import Report
from ..resolve import ResolveError, resolve
from . import current_project, emit


def run(ctx, args) -> int:
    iid = args.id
    proj, lock = current_project(ctx)
    m = proj.manifest
    report = Report(f"remove {iid}", ctx.today, verbose=ctx.verbose)
    report.project(proj.name, "[auto]" if m.auto_sync else "[manual]")
    li = lock.items.get(iid)
    if m.entry(iid) is None:
        if li is not None and li.source == "dependency":
            raise UsageError(f"{iid} is required by {', '.join(li.required_by) or 'another item'}; "
                             "remove that instead")
        raise UsageError(f"{iid} is not in .warehouse.yml")
    target_dir = proj.root / m.target
    guard = WriteGuard(proj.root, m.target, allow_manifest=True)

    if li is not None:
        requirers = [r for r in li.required_by if r in lock.items and r != iid]
        if requirers and not args.force:
            report.add(proj.name, "blocked", iid, "required by " + ", ".join(requirers) + " (use --force)")
            return emit(ctx, report)
        states = inspect_item(target_dir, li)
        d = drifted(states)
        if d and not args.force:
            report.add(proj.name, "drift", iid, f"{', '.join(d)} edited locally; use detach to keep your edits "
                                                "(or --force to delete)")
            return emit(ctx, report)

    text = manifest_mod.remove_entry(m, iid)
    atomic_write(guard, m.path, text.encode("utf-8"))
    proj.manifest = manifest_mod.load_text(text, m.path)

    if li is not None:
        delete_files(guard, target_dir, tracked_paths(li))
        del lock.items[iid]
    report.add(proj.name, "removed", iid, li.version if li else "not installed")

    try:
        actions = resolve(ctx.catalog, proj.manifest, lock, mode="sync")
    except ResolveError as e:
        actions = []
        report.add(proj.name, "error", None, str(e))
    for a in actions:
        if a.kind != "orphan":
            continue
        oli = lock.items[a.id]
        if iid not in oli.required_by:
            continue
        if args.prune:
            st = inspect_item(target_dir, oli)
            dd = drifted(st)
            if dd:
                report.add(proj.name, "drift", a.id, f"not pruned: {', '.join(dd)} edited locally")
                continue
            delete_files(guard, target_dir, tracked_paths(oli))
            del lock.items[a.id]
            report.add(proj.name, "removed", a.id, f"{oli.version} pruned (no longer required)")
        else:
            oli.required_by = [r for r in oli.required_by if r != iid and r in lock.items]
            report.add(proj.name, "orphan", a.id, "no longer required; kept (warehouse remove --prune to delete)")

    write_readme(ctx, proj, lock, guard, report)
    lockfile.save(proj.root, lock, guard)
    return emit(ctx, report)
