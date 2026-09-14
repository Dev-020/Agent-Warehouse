"""sync [--auto] [--if-new-tags] [--include-manual] [project] (DESIGN §4.3)."""
from __future__ import annotations

from pathlib import Path

from .. import lockfile
from ..apply import apply_actions
from ..discovery import Project, find_projects, load_project, target_contains_project
from ..errors import UsageError
from ..manifest import MANIFEST_NAME
from ..report import Report
from ..resolve import ResolveError, resolve
from . import emit


def sync_projects(ctx, report: Report, projects: list[Project], *, explicit: bool, include_manual: bool) -> None:
    for proj in projects:
        if proj.manifest is None:
            report.add(proj.name, "invalid-manifest", None, proj.error or "invalid manifest")
            continue
        mode = "[auto]" if proj.manifest.auto_sync else "[manual]"
        if not explicit and not proj.manifest.auto_sync and not include_manual:
            report.project(proj.name, f"{mode}  skipped: auto_sync is false")
            report.skipped_projects += 1
            continue
        report.project(proj.name, mode)
        sync_one(ctx, report, proj, mode="sync")


def sync_one(ctx, report: Report, proj: Project, *, mode: str = "sync") -> None:
    if target_contains_project(proj):
        report.add(proj.name, "error", None, "target contains another project; not synced")
        return
    try:
        lock = lockfile.load(proj.root)
        actions = resolve(ctx.catalog, proj.manifest, lock, mode=mode)
        apply_actions(ctx, proj, lock, actions, report, today=ctx.today)
    except (ResolveError, UsageError) as e:
        report.add(proj.name, "error", None, str(e))
    except Exception as e:  # never let one project abort the run for the others
        report.add(proj.name, "error", None, f"{type(e).__name__}: {e}")


def run(ctx, args) -> int:
    with ctx.run_lock() as acquired:
        if not acquired:
            if args.auto:
                return 0
            raise ctx.busy_error()
        digest = ctx.catalog.tags_digest()
        state = ctx.read_auto_state()
        if args.if_new_tags and state.get("tags_digest") == digest and not state.get("needs_retry"):
            return 0
        label = "sync" + (" --auto" if args.auto else "")
        report = Report(label, ctx.today, verbose=ctx.verbose)
        for w in ctx.config.warnings:
            report.preamble.append(f"warning: {w}")
        if args.project:
            root = Path(args.project).resolve()
            if not (root / MANIFEST_NAME).is_file():
                raise UsageError(f"no {MANIFEST_NAME} in {root}")
            projects = [load_project(root)]
            explicit = True
        else:
            projects = find_projects(ctx.config, ctx.warehouse_root)
            explicit = False
        sync_projects(ctx, report, projects, explicit=explicit, include_manual=args.include_manual)
        code = emit(ctx, report)
        if args.auto:
            ctx.write_auto_state(digest, needs_retry=report.needs_retry)
        return code
