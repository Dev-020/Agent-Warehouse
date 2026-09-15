"""Remove an item from manifest/lock but keep it in the project."""
from __future__ import annotations

import sys
from pathlib import Path

from .. import fsops, items, lockfile, manifest, readme, render
from ..discovery import load_project
from ..errors import GitError, UsageError


def run(ctx, args) -> int:
    proj_path = Path(args.project).resolve() if args.project else Path.cwd()
    proj = load_project(proj_path)
    if not proj.manifest:
        raise UsageError(proj.error or "invalid manifest")

    lock = lockfile.load(proj.root)
    iid = args.id
    li = lock.items.get(iid)
    if not li:
        print(f"warehouse detach: {iid} is not in the project lock", file=sys.stderr)
        return 1

    if li.required_by and not getattr(args, "force", False):
        print(f"warehouse detach: {iid} is required by {', '.join(li.required_by)}; use --force to detach anyway", file=sys.stderr)
        return 1
        
    if li.source == "dependency" and not getattr(args, "force", False):
        print(f"warehouse detach: {iid} is a dependency-only item; use --force to detach anyway", file=sys.stderr)
        return 1

    target_dir = proj.root / proj.manifest.target

    # Strip header from main file
    main_file = items.kind_of(iid) + "s/" + items.name_of(iid) + "/SKILL.md"
    if items.kind_of(iid) == "protocol":
        main_file = items.name_of(iid) + ".md"
    elif items.kind_of(iid) == "tool":
        main_file = "tools/" + items.name_of(iid) + "/TOOL.md"
    elif items.kind_of(iid) == "convention":
        main_file = "conventions/" + items.name_of(iid) + "/CONVENTION.md"
    elif items.kind_of(iid) == "architecture":
        main_file = "architecture/" + items.name_of(iid) + "/ARCHITECTURE.md"
        
    p = target_dir / main_file
    if p.is_file():
        text = p.read_text(encoding="utf-8")
        stripped = render.strip_header(text)
        guard = fsops.WriteGuard(proj.root, proj.manifest.target)
        fsops.atomic_write(guard, p, stripped.encode("utf-8"))

    # Remove from manifest
    if li.source == "manifest":
        new_text = manifest.remove_entry(proj.manifest, iid)
        proj.manifest.path.write_text(new_text, encoding="utf-8")

    # Remove from lock
    del lock.items[iid]
    
    # Regenerate README
    guard = fsops.WriteGuard(proj.root, proj.manifest.target)
    readme_path = target_dir / "README.md"
    if lock.items:
        notes = {}
        for xid, xli in lock.items.items():
            if xli.ver:
                try:
                    meta = ctx.catalog.meta(xid, xli.ver)
                    if meta.status == "deprecated":
                        succ = ctx.catalog.successor(xid)
                        notes[xid] = f"deprecated: use {succ}" if succ else "deprecated"
                except Exception:
                    pass
        data = readme.generate(lock, notes)
        fsops.atomic_write(guard, readme_path, data)
        lock.readme = render.sha256(data)
    else:
        if readme_path.is_file() and readme.has_marker(readme_path.read_bytes()):
            readme_path.unlink()
        lock.readme = None
        
    lockfile.save(proj.root, lock, guard)
    print(f"warehouse detach: {iid} detached; files remain in {proj.manifest.target} (move out of {proj.manifest.target} if you like)")
    return 0