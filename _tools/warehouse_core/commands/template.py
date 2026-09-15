"""Copy a template into the project."""
from __future__ import annotations

import re
import sys
from pathlib import Path

from .. import items, render
from ..discovery import load_project
from ..errors import UsageError


def run(ctx, args) -> int:
    raw_id = args.id
    if "@" in raw_id:
        iid, ver_spec = raw_id.split("@", 1)
    else:
        iid = raw_id
        ver_spec = None

    if items.kind_of(iid) != "template":
        print(f"warehouse template: {iid} is not a template", file=sys.stderr)
        return 2

    dest = Path(args.dest).resolve()
    if dest.exists():
        print(f"warehouse template: destination {args.dest} already exists", file=sys.stderr)
        return 2

    if not dest.parent.exists():
        print(f"warehouse template: parent directory of {args.dest} does not exist", file=sys.stderr)
        return 2

    C = ctx.catalog
    if ver_spec:
        from ..semver import Version
        try:
            v = Version.parse(ver_spec)
        except Exception:
            print(f"warehouse template: invalid version '{ver_spec}'", file=sys.stderr)
            return 2
        if not C.has_tag(iid, v):
            print(f"warehouse template: tag {iid}@{v} does not exist", file=sys.stderr)
            return 3
    else:
        v = C.latest(iid)
        if not v:
            print(f"warehouse template: no releases found for {iid}", file=sys.stderr)
            return 3

    meta = C.meta(iid, v)
    
    proj = load_project(Path.cwd())
    
    settings = {}
    if proj.manifest:
        settings.update(proj.manifest.settings)
        
    for s in getattr(args, "set", []):
        if "=" in s:
            k, val = s.split("=", 1)
            settings[k] = val

    values, unfilled = render.effective_settings(meta, settings)
    for u in unfilled:
        print(f"warning: unfilled setting '{u}'", file=sys.stderr)

    files = C.files(iid, v)
    if not files:
        print(f"warehouse template: {iid}@{v} has no files", file=sys.stderr)
        return 1

    # Template is expected to be a single .md file (usually templates/name.md)
    template_rel = f"templates/{items.name_of(iid)}.md"
    if template_rel not in files:
        # Just grab the first file
        template_rel = list(files.keys())[0]

    data = files[template_rel]
    text = data.decode("utf-8", "replace")
    
    # Strip frontmatter
    text = re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.DOTALL)
    # Strip changelog
    text = re.sub(r"\n## Changelog\n.*$", "\n", text, flags=re.DOTALL)
    
    for k, val in values.items():
        if val:
            text = text.replace(f"{{{{{k}}}}}", val)
            
    header = f"<!-- from warehouse template {iid} v{v} -->\n"
    text = header + text
    
    dest.write_text(text, encoding="utf-8")
    return 0