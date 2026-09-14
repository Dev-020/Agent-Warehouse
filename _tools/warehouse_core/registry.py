"""_registry/projects.md (DESIGN §2.7)."""
from __future__ import annotations

from . import lockfile
from .discovery import Project
from .errors import UsageError
from .inspect import drifted, inspect_item


def generate(projects: list[Project], today: str) -> bytes:
    prow = ["| Project | Auto-sync | Target | Items | Issues |", "|---|---|---|---|---|"]
    irow = ["| Item | Project | Pin | Installed | Source |", "|---|---|---|---|---|"]
    item_rows = []
    for p in sorted(projects, key=lambda p: p.name.lower()):
        if p.manifest is None:
            prow.append(f"| {p.name} | — | — | — | invalid manifest |")
            continue
        try:
            lock = lockfile.load(p.root)
        except UsageError:
            prow.append(f"| {p.name} | {'yes' if p.manifest.auto_sync else 'no'} | {p.manifest.target_display} | — | invalid lock |")
            continue
        n_drift = 0
        for iid, li in lock.items.items():
            if drifted(inspect_item(p.root / p.manifest.target, li)):
                n_drift += 1
            source = "manifest" if li.source == "manifest" else "required by " + ", ".join(li.required_by)
            item_rows.append((iid, p.name, f"@{li.pin}" if li.pin else "", li.version or "—", source))
        issues = f"{n_drift} drift" if n_drift else ""
        installed = sum(1 for li in lock.items.values() if li.version)
        prow.append(f"| {p.name} | {'yes' if p.manifest.auto_sync else 'no'} | {p.manifest.target_display} | "
                    f"{installed} | {issues} |")
    for r in sorted(item_rows):
        irow.append("| " + " | ".join(r) + " |")
    text = "\n".join([
        "<!-- warehouse:generated — `warehouse registry`. Do not edit. -->",
        "# Project registry",
        "",
        f"Generated {today} from {len(projects)} project{'s' if len(projects) != 1 else ''}.",
        "",
        "## Projects",
        "",
        *prow,
        "",
        "## Items",
        "",
        *irow,
        "",
    ])
    return text.encode("utf-8")
