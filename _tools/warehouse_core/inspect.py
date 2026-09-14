"""Per-file state of installed items: clean | eol-only | missing | drift (DESIGN §4.2)."""
from __future__ import annotations

from pathlib import Path

from .lockfile import LockItem
from .render import sha256


def file_state(path: Path, expected: set[str]) -> str:
    if not path.is_file():
        return "missing"
    data = path.read_bytes()
    if sha256(data) in expected:
        return "clean"
    if b"\r\n" in data and sha256(data.replace(b"\r\n", b"\n")) in expected:
        return "eol-only"
    return "drift"


def accepted_hashes(li: LockItem) -> dict[str, set[str]]:
    """Every hash the tool wrote or planned for each path: lock files, the pending journal, and the hashes
    accepted from earlier interrupted generations (pending.accepted)."""
    out: dict[str, set[str]] = {}
    for rel, h in li.files.items():
        out.setdefault(rel, set()).add(h)
    pending = li.pending or {}
    for rel, h in (pending.get("files") or {}).items():
        out.setdefault(rel, set()).add(h)
    for rel, hs in (pending.get("accepted") or {}).items():
        out.setdefault(rel, set()).update(hs)
    return out


def tracked_paths(li: LockItem) -> set[str]:
    return set(accepted_hashes(li))


def inspect_item(target_dir: Path, li: LockItem) -> dict[str, str]:
    out = {}
    for rel, expected in sorted(accepted_hashes(li).items()):
        state = file_state(target_dir / rel, expected)
        # a path only planned by an interrupted run and never written is not a problem
        if state == "missing" and rel not in li.files:
            continue
        out[rel] = state
    return out


def present_clean(target_dir: Path, li: LockItem) -> list[str]:
    """Tracked paths that exist on disk and are clean (incl. pending-only ones)."""
    return [p for p, s in inspect_item(target_dir, li).items() if s in ("clean", "eol-only")]


def drifted(states: dict[str, str]) -> list[str]:
    return [p for p, s in states.items() if s == "drift"]


def missing(states: dict[str, str]) -> list[str]:
    return [p for p, s in states.items() if s == "missing"]
