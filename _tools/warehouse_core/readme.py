"""<target>/README.md (DESIGN §2.5)."""
from __future__ import annotations

from . import items
from .lockfile import Lock

MARKER = "<!-- warehouse:generated — written by the warehouse sync tool. Do not edit; it is regenerated. -->"


def generate(lock: Lock, notes: dict[str, str]) -> bytes:
    rows = []
    for iid, li in sorted(lock.items.items()):
        if not li.version:
            continue
        if items.is_document(iid):
            p = items.target_rel_path(iid)
            link = f"[{p}]({p})"
        else:
            p = items.target_rel_path(iid)
            link = f"[{p}/]({p}/{items.main_file_name(iid)})"
        note_parts = []
        if li.source == "dependency" and li.required_by:
            note_parts.append("required by " + ", ".join(li.required_by))
        if notes.get(iid):
            note_parts.append(notes[iid])
        pin = f"@{li.pin}" if li.pin else ""
        rows.append(f"| {iid} | {li.version} | {pin} | {link} | {'; '.join(note_parts)} |")
    text = "\n".join([
        MARKER,
        "# Warehouse items",
        "",
        "This project uses items from the AI warehouse. The files in this folder are synced copies. They may be",
        "updated automatically (`auto_sync: true`) or with `warehouse pull`. Do not edit them here: change them in",
        "the warehouse, or run `warehouse promote <id>` to send a local change upstream.",
        "",
        "| Item | Version | Pin | Path | Notes |",
        "|---|---|---|---|---|",
        *rows,
        "",
        "Manifest: `.warehouse.yml` at the project root.",
        "",
    ])
    return text.encode("utf-8")


def has_marker(data: bytes) -> bool:
    return data.replace(b"\r\n", b"\n").split(b"\n", 1)[0].decode("utf-8", "replace").startswith(
        "<!-- warehouse:generated")
