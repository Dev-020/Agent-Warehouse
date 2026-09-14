"""One module per command; each exposes run(ctx, args) -> int."""
from __future__ import annotations

from .. import lockfile, manifest as manifest_mod
from ..discovery import Project


def current_project(ctx) -> tuple[Project, lockfile.Lock]:
    root = ctx.project_root()
    m = manifest_mod.load(root)
    return Project(root, m), lockfile.load(root)


def emit(ctx, report) -> int:
    print(report.render_json() if ctx.json else report.render_text(), end="")
    return report.exit_code()
