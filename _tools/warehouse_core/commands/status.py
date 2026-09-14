"""status: current vs available versions for this project (DESIGN §4.4). Read-only."""
from __future__ import annotations

import json
import re

from .. import changelog, items
from ..apply import deprecation_note
from ..errors import GitError, UsageError
from ..inspect import drifted, inspect_item
from ..render import effective_settings
from ..resolve import resolve
from . import current_project


def _clean(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^[-*]\s+", "", s)
    return s.replace("**", "")


def changelog_lines(catalog, item_id, low, high, *, breaking_only: bool) -> list[str]:
    latest = catalog.latest(item_id)
    if latest is None:
        return []
    try:
        secs = changelog.parse(catalog.changelog_text(item_id, latest), is_document=items.is_document(item_id))
    except (UsageError, GitError, KeyError):
        return []
    out = []
    for sec in changelog.entries_between(secs, low, high):
        if breaking_only:
            for b in changelog.breaking(sec):
                parts = [_clean(x) for x in b.split("\n")]
                out.append(f"  {sec.name} — " + "  ".join(parts))
        else:
            for cat, text in changelog.categorized_bullets(sec):
                out.append(f"  {sec.name} — {cat + ': ' if cat else ''}{_clean(text)}")
    return out


def run(ctx, args) -> int:
    proj, lock = current_project(ctx)
    C = ctx.catalog
    m = proj.manifest
    actions = resolve(C, m, lock, mode="pull")
    target_dir = proj.root / m.target
    out = [f"warehouse status — {ctx.today}", f"{proj.name}  [{'auto' if m.auto_sync else 'manual'}]"]
    data = []
    width = max([len(a.id) for a in actions] + [20]) + 2
    for a in actions:
        li = lock.items.get(a.id)
        inst = li.ver if li else None
        row = {"id": a.id, "installed": str(inst) if inst else None, "pin": a.pin.text if a.pin else None,
               "flags": []}
        if inst is None:
            if a.kind == "not-installable":
                line = f"{a.id:<{width}}not installable: {a.reason}"
            elif a.kind == "blocked":
                line = f"{a.id:<{width}}not installable: {a.reason}"
            else:
                line = f"{a.id:<{width}}not installed  (run warehouse sync . or warehouse pull {a.id})"
            out.append(line)
            data.append(row)
            continue
        parts = [f"{a.id:<{width}}installed {inst}"]
        if a.pin:
            parts.append(f"pin @{a.pin.text}")
        detail_lines = []
        comp, outside, major = a.compatible, a.outside_pin, a.major
        # compatible relative to the installed version
        vs = C.versions(a.id)
        if a.pin:
            cands = [v for v in vs if a.pin.matches(v) and v > inst and v.line == inst.line]
            comp = cands[-1] if cands else None
            outs = [v for v in vs if v.line == inst.line and not a.pin.matches(v) and v > inst]
            outside = outs[-1] if outs else None
        majors = [v for v in vs if v.line > inst.line]
        major = majors[-1] if majors else None
        if comp:
            parts.append(f"compatible {comp}")
            detail_lines += changelog_lines(C, a.id, inst, comp, breaking_only=False)
        if major:
            parts.append(f"major {major}")
            detail_lines += changelog_lines(C, a.id, inst, major, breaking_only=True)
        if not comp and not major:
            parts.append("up to date")
        if outside:
            parts.append(f"({outside} outside pin)")
        if li.source == "dependency" and li.required_by:
            parts.append("required by " + ", ".join(li.required_by))
        states = inspect_item(target_dir, li)
        d = drifted(states)
        if d:
            parts.append("drift: " + ", ".join(d))
        if li.state == "promoted":
            parts.append("promoted")
        if a.kind in ("blocked", "orphan") or a.blocked_newer:
            parts.append(f"{'blocked' if a.kind != 'orphan' else 'orphan'}: {a.reason or a.blocked_newer}")
        if a.kind == "pin-moved":
            parts.append(a.reason)
        try:
            meta = C.meta(a.id, inst)
            _, unfilled = effective_settings(meta, m.settings)
            if unfilled:
                parts.append("unfilled: " + ", ".join(unfilled))
            note = deprecation_note(C, a.id, inst)
            if note:
                parts.append(note)
        except (GitError, UsageError):
            parts.append("missing-tag")
        out.append("  ".join(parts))
        out.extend(detail_lines)
        row.update(compatible=str(comp) if comp else None, major=str(major) if major else None,
                   outside_pin=str(outside) if outside else None, drift=d, changelog=detail_lines)
        data.append(row)
    if ctx.json:
        print(json.dumps({"command": "status", "date": ctx.today, "project": proj.name, "items": data}, indent=2))
    else:
        print("\n".join(out))
    return 0
