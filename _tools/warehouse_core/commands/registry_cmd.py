"""registry: regenerate _registry/projects.md (DESIGN §4.11). No commit."""
from __future__ import annotations

from .. import registry
from ..discovery import find_projects
from ..fsops import WriteGuard, atomic_write


def run(ctx, args) -> int:
    projects = find_projects(ctx.config, ctx.warehouse_root)
    data = registry.generate(projects, ctx.today)
    path = ctx.warehouse_root / "_registry" / "projects.md"
    guard = WriteGuard(ctx.warehouse_root, "_registry", allow_lock=False)
    if not path.is_file() or path.read_bytes() != data:
        atomic_write(guard, path, data)
    print(f"wrote _registry/projects.md ({len(projects)} projects)")
    return 0
