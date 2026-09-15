"""Create a .warehouse.yml for an existing project."""
from __future__ import annotations

import sys
from pathlib import Path

from .. import manifest, render, items
from ..discovery import load_project
from ..errors import UsageError


def run(ctx, args) -> int:
    proj_path = Path(args.project).resolve() if args.project else Path.cwd()
    
    types = set()
    if (proj_path / ".obsidian").is_dir():
        types.add("vault")
        
    codebase_markers = ["package.json", "pyproject.toml", "requirements.txt", "setup.py", "go.mod", "Cargo.toml", "pom.xml"]
    for marker in codebase_markers:
        if (proj_path / marker).is_file():
            types.add("codebase")
            break
    if not ("codebase" in types):
        if any(proj_path.glob("*.csproj")):
            types.add("codebase")

    if not types:
        print("warehouse bootstrap: neither vault nor codebase detected", file=sys.stderr)
        types.add("codebase") # default fallback

    C = ctx.catalog
    candidates = []
    
    include_drafts = getattr(args, "include_drafts", False)
    for iid in C._raw:
        if items.kind_of(iid) == "template":
            continue
        v = C.latest(iid)
        if not v:
            continue
        if v.is_draft and not include_drafts:
            continue
        meta = C.meta(iid, v)
        if meta.status == "deprecated":
            continue
        if not (meta.applies_to and set(meta.applies_to).intersection(types)):
            continue
        candidates.append((iid, v, meta))

    out = ["auto_sync: true", "target: warehouse/", "items:"]
    settings_needed = {}
    
    for iid, v, meta in sorted(candidates, key=lambda x: x[0]):
        pin = f"{v.major}" if not v.is_draft else f"0.{v.minor}"
        out.append(f"  - {iid}@{pin}")
        for s_name, spec in meta.settings.items():
            if not spec.has_default and s_name not in settings_needed:
                settings_needed[s_name] = spec.description

    if settings_needed:
        out.append("")
        out.append("settings:")
        for k, desc in sorted(settings_needed.items()):
            out.append(f"  {k}: \"\"  # {desc}")
            
    out_text = "\n".join(out) + "\n"
    
    if getattr(args, "write", False):
        manifest_path = proj_path / ".warehouse.yml"
        if manifest_path.exists():
            print(f"warehouse bootstrap: {manifest_path} already exists", file=sys.stderr)
            return 2
        manifest_path.write_text(out_text, encoding="utf-8")
        print(f"Created {manifest_path}")
    else:
        sys.stdout.write(out_text)

    return 0