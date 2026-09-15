"""Create a .warehouse.yml for an existing project."""
from __future__ import annotations

import sys
from pathlib import Path

from .. import manifest, render, items, profiles
from ..discovery import load_project
from ..errors import UsageError
from ..semver import Pin


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

    profile_name = getattr(args, "profile", "starter") or "starter"

    if profile_name == "all":
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
    else:
        prof = profiles.get_profile(ctx.warehouse_root, profile_name)
        if not prof:
            raise UsageError(f"profile '{profile_name}' not found")

        out = ["auto_sync: true", "target: warehouse/", "items:"]
        for it in prof.items:
            out.append(f"  - {it}")

        settings_dict = dict(prof.settings)
        settings_comments = {}

        C = ctx.catalog
        for it in prof.items:
            mm = manifest.ENTRY_RE.match(it)
            if not mm:
                continue
            iid = mm.group("id")
            pin_str = mm.group("pin")
            pin = Pin.parse(pin_str) if pin_str else None
            try:
                v = C.latest(iid, pin)
                if v:
                    meta = C.meta(iid, v)
                    for s_name, spec in meta.settings.items():
                        if not spec.has_default and s_name not in settings_dict:
                            settings_dict[s_name] = ""
                            settings_comments[s_name] = spec.description
            except Exception:
                pass

        if settings_dict:
            out.append("")
            out.append("settings:")
            for k, v in sorted(settings_dict.items()):
                if k in settings_comments:
                    desc = settings_comments[k]
                    out.append(f"  {k}: \"\"  # {desc}")
                else:
                    out.append(f"  {k}: \"{v}\"")
            
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