"""profile [list|show|save|delete|apply] (Progressive Context Disclosure)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from .. import fsops, manifest as manifest_mod, profiles
from ..errors import UsageError
from ..semver import Pin
from . import current_project


def _list(ctx, args) -> int:
    profs = profiles.list_profiles(ctx.warehouse_root)
    if getattr(args, "json", False) or ctx.json:
        print(json.dumps([p.to_dict() for p in profs], indent=2))
        return 0

    if not profs:
        print("No profiles found.")
        return 0

    name_w = max(max(len(p.name) for p in profs), 4)
    tier_w = 4
    items_w = max(max(len(str(len(p.items))) for p in profs), 5)
    applies_w = max(max(len(", ".join(p.applies_to)) for p in profs), 10)

    header = f"{'Name':<{name_w}}  {'Tier':<{tier_w}}  {'Items':<{items_w}}  {'Applies-to':<{applies_w}}  Description"
    sep = f"{'-'*name_w}  {'-'*tier_w}  {'-'*items_w}  {'-'*applies_w}  {'-'*11}"
    lines = [header, sep]
    for p in profs:
        applies_str = ", ".join(p.applies_to)
        lines.append(f"{p.name:<{name_w}}  {p.tier:<{tier_w}}  {len(p.items):<{items_w}}  {applies_str:<{applies_w}}  {p.description}")
    print("\n".join(lines))
    return 0


def _show(ctx, args) -> int:
    prof = profiles.get_profile(ctx.warehouse_root, args.name)
    if not prof:
        raise UsageError(f"profile '{args.name}' not found")

    if getattr(args, "json", False) or ctx.json:
        print(json.dumps(prof.to_dict(), indent=2))
        return 0

    lines = [
        f"Name: {prof.name}",
        f"Tier: {prof.tier}",
        f"Applies-to: {', '.join(prof.applies_to)}",
        f"Description: {prof.description}",
        f"Items ({len(prof.items)}):",
    ]
    for item in prof.items:
        lines.append(f"  - {item}")
    if prof.settings:
        lines.append("Settings:")
        for k, v in sorted(prof.settings.items()):
            lines.append(f"  {k}: {v}")
    else:
        lines.append("Settings: (none)")
    print("\n".join(lines))
    return 0


def _save(ctx, args) -> int:
    existing = profiles.get_profile(ctx.warehouse_root, args.name)

    if getattr(args, "description", None) is not None:
        desc = args.description
    elif existing:
        desc = existing.description
    else:
        desc = ""

    if getattr(args, "tier", None) is not None:
        tier = int(args.tier)
    elif existing:
        tier = existing.tier
    else:
        tier = 0

    if getattr(args, "applies_to", None) is not None:
        applies_to = [x.strip() for x in args.applies_to.split(",") if x.strip()]
    elif existing:
        applies_to = list(existing.applies_to)
    else:
        applies_to = ["vault", "codebase"]

    items = None
    settings = None

    if getattr(args, "from_manifest", False):
        proj, lock = current_project(ctx)
        m = proj.manifest
        items = [f"{e.id}@{e.pin.text}" if e.pin else e.id for e in m.entries]
        settings = dict(m.settings)

    if getattr(args, "items", None) is not None:
        items = [x.strip() for x in args.items.split(",") if x.strip()]

    if items is None:
        if existing:
            items = list(existing.items)
        else:
            items = []

    if settings is None:
        if existing:
            settings = dict(existing.settings)
        else:
            settings = {}

    prof = profiles.Profile(
        name=args.name,
        description=desc,
        tier=tier,
        applies_to=applies_to,
        items=items,
        settings=settings,
    )
    saved_path = profiles.save_profile(ctx.warehouse_root, prof)
    print(f"Saved profile {args.name} ({saved_path})")
    return 0


def _delete(ctx, args) -> int:
    prof = profiles.get_profile(ctx.warehouse_root, args.name)
    if not prof:
        raise UsageError(f"profile '{args.name}' not found")

    if not getattr(args, "yes", False):
        if sys.stdin.isatty():
            ans = input(f"Delete profile '{args.name}'? [y/N] ").strip().lower()
            if ans not in ("y", "yes"):
                print("Aborted.")
                return 0
        else:
            raise UsageError(f"use --yes to confirm deletion of profile '{args.name}'")

    deleted = profiles.delete_profile(ctx.warehouse_root, args.name)
    if deleted:
        print(f"Deleted profile {args.name}")
        return 0
    raise UsageError(f"profile '{args.name}' not found")


def _ensure_settings_dict(m: manifest_mod.Manifest, settings: dict[str, str]) -> str:
    missing = {k: v for k, v in settings.items() if k not in m.settings}
    if not missing:
        return m.raw
    lines = manifest_mod._split(m.raw)
    s_idx = None
    for i, line in enumerate(lines):
        if re.match(r"^settings\s*:", line):
            s_idx = i
            break
    new_lines = [f'  {k}: "{v}"' for k, v in sorted(missing.items())]
    if s_idx is None:
        lines += ["settings:", *new_lines]
    else:
        rest = lines[s_idx][lines[s_idx].index(":") + 1:].split("#")[0].strip()
        if rest in ("{}",):
            lines[s_idx] = "settings:"
        last = s_idx
        for j in range(s_idx + 1, len(lines)):
            if lines[j][:1].isspace() and lines[j].strip():
                last = j
            elif not lines[j].strip():
                continue
            else:
                break
        lines[last + 1:last + 1] = new_lines
    return manifest_mod._validated(manifest_mod._join(lines), m)


def _apply(ctx, args) -> int:
    prof = profiles.get_profile(ctx.warehouse_root, args.name)
    if not prof:
        raise UsageError(f"profile '{args.name}' not found")

    proj, lock = current_project(ctx)
    m = proj.manifest

    added_items = []
    text = m.raw

    for it in prof.items:
        mm = manifest_mod.ENTRY_RE.match(it)
        if not mm:
            raise UsageError(f"invalid item entry in profile '{prof.name}': {it}")
        iid = mm.group("id")
        pin_str = mm.group("pin")
        pin = Pin.parse(pin_str) if pin_str is not None else None

        entry = m.entry(iid)
        if entry is None or entry.pin != pin:
            text = manifest_mod.add_or_replace_entry(m, iid, pin)
            m = manifest_mod.load_text(text, m.path)
            added_items.append(it)

    if prof.settings:
        text = _ensure_settings_dict(m, prof.settings)
        m = manifest_mod.load_text(text, m.path)

    C = ctx.catalog
    for it in prof.items:
        mm = manifest_mod.ENTRY_RE.match(it)
        if not mm:
            continue
        iid = mm.group("id")
        pin_str = mm.group("pin")
        pin = Pin.parse(pin_str) if pin_str else None
        try:
            latest = C.latest(iid, pin)
            if latest:
                meta = C.meta(iid, latest)
                required = {n: s.description for n, s in meta.settings.items() if not s.has_default}
                if required:
                    text = manifest_mod.ensure_settings_keys(m, required)
                    m = manifest_mod.load_text(text, m.path)
        except Exception:
            pass

    guard = fsops.WriteGuard(proj.root, m.target, allow_manifest=True)
    fsops.atomic_write(guard, m.path, m.raw.encode("utf-8"))

    if getattr(args, "json", False) or ctx.json:
        print(json.dumps({"command": "profile apply", "profile": args.name, "added": added_items}))
    else:
        if added_items:
            print(f"Applied profile '{args.name}' to {m.path.name}:")
            for it in added_items:
                print(f"  + {it}")
        else:
            print(f"Profile '{args.name}' items are already present in {m.path.name}.")
    return 0


def run(ctx, args) -> int:
    action = getattr(args, "profile_action", None)
    if action == "list":
        return _list(ctx, args)
    elif action == "show":
        return _show(ctx, args)
    elif action == "save":
        return _save(ctx, args)
    elif action == "delete":
        return _delete(ctx, args)
    elif action == "apply":
        return _apply(ctx, args)
    else:
        raise UsageError("subcommand required: list, show, save, delete, apply")
