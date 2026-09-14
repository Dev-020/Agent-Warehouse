"""check [--project PATH]: read-only health report (DESIGN §4.9)."""
from __future__ import annotations

import os
from pathlib import Path

from .. import items, lockfile, software
from ..discovery import find_projects, load_project
from ..errors import GitError, UsageError
from ..inspect import drifted, inspect_item, tracked_paths
from ..render import effective_settings
from ..report import Report
from ..resolve import ResolveError, resolve
from . import emit


def check_warehouse(ctx, report: Report) -> None:
    C = ctx.catalog
    tree = items.discover_working_tree(ctx.warehouse_root)
    for iid in sorted(tree):
        for p in items.lint_item(ctx.warehouse_root, iid, catalog=C):
            report.add(None, "error", iid, f"{p.level} {p.code}: {p.msg}")
    for ref in C.malformed:
        report.add(None, "error", None, f"malformed tag {ref}")
    for iid in sorted(C._raw):
        C.versions(iid)
    for (iid, v), reason in sorted(C.invalid.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        report.add(None, "error", iid, f"tag {iid}@{v} ignored: {reason}")
    if tree and not C._raw:
        report.add(None, "missing-tag", None, "no tags found (git fetch --tags?)", info=True)
    if ctx.read_auto_state().get("needs_retry"):
        report.add(None, "needs-retry", None, "auto-sync requires a retry (see auto-sync.json)")


def check_project(ctx, report: Report, proj) -> None:
    C = ctx.catalog
    if proj.manifest is None:
        report.add(proj.name, "invalid-manifest", None, proj.error or "invalid manifest")
        return
    m = proj.manifest
    report.project(proj.name, "[auto]" if m.auto_sync else "[manual]")
    try:
        lock = lockfile.load(proj.root)
        actions = resolve(C, m, lock, mode="pull")
    except (UsageError, ResolveError) as e:
        report.add(proj.name, "error", None, str(e))
        return
    target_dir = proj.root / m.target
    for a in actions:
        li = lock.items.get(a.id)
        inst = li.ver if li else None
        if a.kind == "not-installable":
            report.add(proj.name, "not-installable", a.id, a.reason or "")
        if a.kind == "blocked" or a.blocked_newer:
            report.add(proj.name, "blocked", a.id, a.reason or a.blocked_newer)
        if a.kind == "orphan":
            report.add(proj.name, "orphan", a.id, a.reason or "")
        if a.kind == "remove":
            report.add(proj.name, "untracked", a.id, "removed from manifest; next sync deletes its copies", info=True)
        if li is not None:
            d = drifted(inspect_item(target_dir, li))
            if d:
                report.add(proj.name, "drift", a.id, ", ".join(d) + " edited locally")
            if li.state == "promoted":
                report.add(proj.name, "promoted", a.id, f"promoted from {li.version}")
        if inst is None:
            continue
        if not C.has_tag(a.id, inst):
            report.add(proj.name, "missing-tag", a.id, f"{a.id}@{inst} tag not found")
            continue
        vs = C.versions(a.id)
        if a.pin:
            comp = [v for v in vs if a.pin.matches(v) and v > inst and v.line == inst.line]
            if comp:
                report.add(proj.name, "compatible", a.id, f"{inst} -> {comp[-1]}"
                           + ("" if not m.auto_sync else " (next sync)"))
            outs = [v for v in vs if v.line == inst.line and not a.pin.matches(v) and v > inst]
            if outs:
                report.add(proj.name, "outside-pin", a.id, f"{outs[-1]} outside pin @{a.pin.text}")
        majors = [v for v in vs if v.line > inst.line]
        if majors:
            report.add(proj.name, "major", a.id, f"{inst} ({majors[-1]} available: warehouse pull {a.id} --major)")
        meta = C.meta(a.id, inst)
        _, unfilled = effective_settings(meta, m.settings)
        if unfilled:
            report.add(proj.name, "unfilled", a.id, "needs settings: " + ", ".join(unfilled))
        if meta.status == "deprecated":
            succ = C.successor(a.id)
            report.add(proj.name, "deprecated", a.id, f"deprecated: use {succ}" if succ else "deprecated")
        for req in meta.requires_software:
            res, detail = software.check(req)
            if res == "missing":
                report.add(proj.name, "missing-software", a.id, detail)
            elif res == "info":
                report.add(proj.name, "missing-software", a.id, detail, info=True)
        if not software.platform_ok(meta.platforms):
            report.add(proj.name, "platform", a.id,
                       f"supports {', '.join(meta.platforms)}; this is {software.current_platform()}")
    for a in actions:
        if a.kind == "not-installable" or a.to_v is None or lock.items.get(a.id) is not None:
            continue
        try:
            _, unfilled = effective_settings(C.meta(a.id, a.to_v), m.settings)
        except (GitError, UsageError):
            continue
        if unfilled:
            report.add(proj.name, "unfilled", a.id, "needs settings: " + ", ".join(unfilled))
    # check if needs retry
    if any(li.pending for li in lock.items.values()):
        report.add(proj.name, "needs-retry", None, "interrupted sync left pending journal entries")
    # untracked files in target
    known = {"README.md"}
    for li in lock.items.values():
        known |= tracked_paths(li)
    if target_dir.is_dir():
        for dp, _, files in os.walk(target_dir):
            for f in files:
                rel = (Path(dp) / f).relative_to(target_dir).as_posix()
                if rel in known or ".warehouse-tmp-" in f or f.lower() == "desktop.ini":
                    continue
                report.add(proj.name, "untracked", None, f"{m.target}/{rel}", info=True)


def run(ctx, args) -> int:
    report = Report("check", ctx.today, check_mode=True, verbose=ctx.verbose)
    check_warehouse(ctx, report)
    if ctx.project_arg:
        projects = [load_project(Path(ctx.project_arg).resolve())]
    else:
        projects = find_projects(ctx.config, ctx.warehouse_root)
    for proj in projects:
        check_project(ctx, report, proj)
    return emit(ctx, report)
