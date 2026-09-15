"""Discard local drift or promoted state."""
from __future__ import annotations

import difflib
import sys
from pathlib import Path

from .. import fsops, inspect, lockfile, render
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
        print(f"warehouse discard: {iid} is not in the project lock", file=sys.stderr)
        return 1

    target_dir = proj.root / proj.manifest.target
    states = inspect.inspect_item(target_dir, li)
    drift = inspect.drifted(states)
    
    if not drift and li.state != "promoted":
        print(f"warehouse discard: {iid} has no drift and is not promoted", file=sys.stderr)
        return 0

    v = li.ver
    if not v:
        print(f"warehouse discard: {iid} has no locked version", file=sys.stderr)
        return 1

    C = ctx.catalog
    if not C.has_tag(iid, v):
        print(f"warehouse discard: tag {iid}@{v} does not exist", file=sys.stderr)
        return 3

    meta = C.meta(iid, v)
    files = C.files(iid, v)
    rendered = render.render_release(meta, files, proj.manifest.settings, li.synced or ctx.today, exclude=ctx.config.sync_exclude)

    if not getattr(args, "yes", False):
        import difflib
        diffs = []
        for rel in drift:
            d_bytes = (target_dir / rel).read_bytes() if (target_dir / rel).is_file() else b""
            b_bytes = rendered.files.get(rel, b"")
            d_lines = d_bytes.decode("utf-8", "replace").splitlines(keepends=True)
            b_lines = b_bytes.decode("utf-8", "replace").splitlines(keepends=True)
            
            diff = list(difflib.unified_diff(
                b_lines, d_lines,
                fromfile=f"{rel} (rendered)", tofile=f"{rel} (disk)",
                n=3
            ))
            diffs.extend(diff)
            
        if diffs:
            sys.stdout.writelines(diffs)
            
        return 10

    # with --yes:
    guard = fsops.WriteGuard(proj.root, proj.manifest.target)
    stale = [rel for rel in list(li.files) if rel not in rendered.files]
    for rel in stale:
        p = target_dir / rel
        if p.is_file():
            p.unlink()
        del li.files[rel]

    for rel, data in rendered.files.items():
        p = target_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        fsops.atomic_write(guard, p, data)
        li.files[rel] = render.sha256(data)
        
    li.state = "ok"
    li.promoted = None
    li.pending = None
    lockfile.save(proj.root, lock, guard)

    if getattr(args, "pull", False):
        from . import pull
        args.major = False
        args.all = False
        return pull.run(ctx, args)

    return 0