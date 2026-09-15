"""Promote a drifted item back to the warehouse."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from .. import changelog, fsops, inspect, items, lockfile, merge, render
from ..discovery import load_project
from ..errors import GitError, UsageError
from . import emit
from ..report import Report


def run(ctx, args) -> int:
    report = Report("promote", ctx.today, verbose=ctx.verbose)
    proj_path = Path(args.project).resolve() if args.project else Path.cwd()
    proj = load_project(proj_path)
    if not proj.manifest:
        raise UsageError(proj.error or "invalid manifest")

    lock = lockfile.load(proj.root)
    iid = args.id
    li = lock.items.get(iid)
    if not li:
        print(f"warehouse promote: {iid} is not in the project lock", file=sys.stderr)
        return 1

    target_dir = proj.root / proj.manifest.target
    states = inspect.inspect_item(target_dir, li)
    drift = inspect.drifted(states)

    has_new = False
    if not items.is_document(iid):
        item_folder = target_dir / items.target_rel_path(iid)
        if item_folder.is_dir():
            for dp, _, filenames in os.walk(item_folder):
                for fn in filenames:
                    if fn in ("desktop.ini", ".DS_Store"):
                        continue
                    p = Path(dp) / fn
                    rel = p.relative_to(target_dir).as_posix()
                    if rel not in li.files:
                        has_new = True
                        break
                if has_new:
                    break

    if not drift and not (has_new and getattr(args, "include_new", False)):
        print(f"warehouse promote: {iid} has no drift; nothing to promote", file=sys.stderr)
        return 0

    v = li.ver
    if not v:
        print(f"warehouse promote: {iid} has no locked version", file=sys.stderr)
        return 1

    C = ctx.catalog
    if not C.has_tag(iid, v):
        print(f"warehouse promote: tag {iid}@{v} does not exist", file=sys.stderr)
        return 3

    meta = C.meta(iid, v)
    settings, _ = render.effective_settings(meta, proj.manifest.settings)

    files = C.files(iid, v)
    rendered = render.render_release(meta, files, proj.manifest.settings, li.synced or ctx.today, exclude=ctx.config.sync_exclude)

    new_master_files = {}
    conflicts = []

    def _warn(msg):
        print(f"warning: {msg}", file=sys.stderr)

    master_base = ctx.warehouse_root

    for rel in drift:
        if items.is_document(iid):
            rel_in_item = rel
        else:
            prefix = items.target_rel_path(iid) + "/"
            if rel.startswith(prefix):
                rel_in_item = rel[len(prefix):]
            else:
                rel_in_item = rel

        t_bytes = files.get(rel_in_item)
        if t_bytes is None:
            continue
        b_bytes = rendered.files.get(rel, b"")
        d_bytes = (target_dir / rel).read_bytes()
        
        # CRLF to LF, strip header
        d_bytes = d_bytes.replace(b"\r\n", b"\n")
        d_text = render.strip_header(d_bytes.decode("utf-8", "replace"))
        
        t_text = render.strip_header(t_bytes.decode("utf-8", "replace"))
        b_text = render.strip_header(b_bytes.decode("utf-8", "replace"))
        
        if rel.endswith(".md"):
            p_bytes = merge.reverse_substitute(t_text.encode("utf-8"), b_text.encode("utf-8"), d_text.encode("utf-8"), settings, _warn)
        else:
            p_bytes = d_text.encode("utf-8")
            
        ours_path = master_base / items.item_rel_path(iid) if items.is_document(iid) else master_base / items.item_rel_path(iid) / rel_in_item
        ours = ours_path.read_bytes().replace(b"\r\n", b"\n") if ours_path.is_file() else b""
        base = t_text.encode("utf-8")
        theirs = p_bytes
        
        if ours == base:
            result = theirs
        else:
            try:
                result, n_conflicts = C.git.merge_file(ours, base, theirs)
                if n_conflicts > 0:
                    conflicts.append((rel, result))
            except Exception:
                conflicts.append((rel, theirs))
                result = theirs
        
        new_master_files[rel_in_item] = result

    # Check for deleted files in project
    for rel in li.files:
        if not (target_dir / rel).is_file():
            print(f"warehouse promote: {rel} was deleted in project; kept in master", file=sys.stderr)

    if not items.is_document(iid):
        item_folder = target_dir / items.target_rel_path(iid)
        if item_folder.is_dir():
            for dp, _, filenames in os.walk(item_folder):
                for fn in filenames:
                    if fn in ("desktop.ini", ".DS_Store"):
                        continue
                    p = Path(dp) / fn
                    rel = p.relative_to(target_dir).as_posix()
                    prefix = items.target_rel_path(iid) + "/"
                    rel_in_item = rel[len(prefix):] if rel.startswith(prefix) else rel
                    if rel not in li.files:
                        if getattr(args, "include_new", False):
                            new_master_files[rel_in_item] = p.read_bytes()
                            li.files[rel] = render.sha256(p.read_bytes())
                        else:
                            print(f"warehouse promote: untracked file {rel} ignored (use --include-new to promote)", file=sys.stderr)

    if conflicts:
        if not getattr(args, "write_conflicts", False):
            for rel, _ in conflicts:
                print(f"conflict in {rel}", file=sys.stderr)
            return 4
        else:
            print("warning: writing conflicts", file=sys.stderr)

    for rel_in_item, data in new_master_files.items():
        if items.is_document(iid):
            p = master_base / items.item_rel_path(iid)
        else:
            p = master_base / items.item_rel_path(iid) / rel_in_item
        p.parent.mkdir(parents=True, exist_ok=True)
        guard = fsops.WriteGuard(master_base, None, extra_files=[p])
        fsops.atomic_write(guard, p, data)

    # Changelog
    ch_path = master_base / items.changelog_file(iid)
    if ch_path.is_file():
        ch_text = ch_path.read_text(encoding="utf-8")
        msg = getattr(args, "message", None) or f"local edits to {', '.join(drift)}"
        bullet = f"- Promoted from {proj.name}: {msg}"
        new_ch = changelog.append_changed(ch_text, bullet, items.is_document(iid))
        guard = fsops.WriteGuard(master_base, None, extra_files=[ch_path])
        fsops.atomic_write(guard, ch_path, new_ch.encode("utf-8"))

    # Diff
    cp = C.git.run("diff", "--", str(master_base), check=False)
    sys.stdout.write(cp.stdout.decode("utf-8", "replace"))

    current_disk_hashes = {}
    for rel in li.files:
        p = target_dir / rel
        if p.is_file():
            current_disk_hashes[rel] = render.sha256(p.read_bytes())

    li.state = "promoted"
    li.promoted = {"from_version": str(v), "files": current_disk_hashes}
    lockfile.save(proj.root, lock, fsops.WriteGuard(proj.root, ""))

    return 0