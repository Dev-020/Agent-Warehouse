"""impact <id> (DESIGN §4.10)."""
from __future__ import annotations

import json

from .. import items, lockfile
from ..discovery import find_projects
from ..errors import GitError, UsageError


def run(ctx, args) -> int:
    iid = args.id
    C = ctx.catalog
    tree = items.discover_working_tree(ctx.warehouse_root)
    if not C.versions(iid) and iid not in tree:
        raise UsageError(f"unknown item {iid}")
    latest = C.latest(iid)
    rows = []
    for proj in find_projects(ctx.config, ctx.warehouse_root):
        if proj.manifest is None:
            continue
        try:
            lock = lockfile.load(proj.root)
        except UsageError:
            continue
        entry = proj.manifest.entry(iid)
        li = lock.items.get(iid)
        if entry is None and li is None:
            continue
        pin = entry.pin.text if entry and entry.pin else (li.pin if li else None)
        source = "manifest" if entry else "required by " + ", ".join(li.required_by)
        rows.append({"project": proj.name, "auto_sync": proj.manifest.auto_sync, "pin": pin,
                     "installed": li.version if li else None, "source": source,
                     "next_major": "report only"})
    dependents = []
    for other in C.all_ids():
        lv = C.latest(other)
        try:
            if any(rid == iid for rid, _ in C.meta(other, lv).requires):
                pins = [f"@{p.text}" for rid, p in C.meta(other, lv).requires if rid == iid]
                dependents.append(f"{other} {lv} requires {iid}{pins[0]}")
        except (GitError, UsageError):
            pass
    if ctx.json:
        print(json.dumps({"command": "impact", "id": iid, "latest": str(latest) if latest else None,
                          "projects": rows, "dependents": dependents}, indent=2))
        return 0
    print(f"warehouse impact {iid} — latest release {latest or 'none'}")
    print("| Project | auto_sync | Pin | Installed | Source | Next MAJOR would |")
    print("|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['project']} | {'true' if r['auto_sync'] else 'false'} | "
              f"{'@' + r['pin'] if r['pin'] else ''} | {r['installed'] or '—'} | {r['source']} | report only |")
    print("Warehouse items that require it:" if dependents else "No warehouse items require it.")
    for d in dependents:
        print(f"  {d}")
    return 0
