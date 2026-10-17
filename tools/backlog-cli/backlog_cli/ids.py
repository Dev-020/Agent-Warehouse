"""Task ID parsing, extraction, and generation."""

from __future__ import annotations

import re


def parse_task_id(header_line: str) -> str | None:
    """Extract ID from ### [ID] or - [ ] **ID**."""
    line = header_line.strip()
    # Format: ### [ID] or ### [#ID]
    m = re.match(r"^###\s+\[#?([^\]]+)\]", line)
    if m:
        return m.group(1).strip()
    # Format: - [ ] **ID** or - [/] **ID**
    m2 = re.search(r"[-*]\s*\[[ x/\-]\]\s*\*\*([^*]+)\*\*", line)
    if m2:
        return m2.group(1).strip()
    return None


def extract_all_ids(text: str) -> list[str]:
    ids = []
    for line in text.splitlines():
        tid = parse_task_id(line)
        if tid:
            ids.append(tid)
    return ids


def find_next_id(prefix: str, text: str) -> str:
    """Allocate next ID matching prefix."""
    used = []
    for tid in extract_all_ids(text):
        if prefix.lower() == "num" or prefix == "#":
            clean = tid.lstrip("#")
            if clean.isdigit():
                used.append(int(clean))
        elif tid.startswith(prefix + "-"):
            tail = tid[len(prefix) + 1 :]
            if tail.isdigit():
                used.append(int(tail))
        elif tid.startswith(prefix):
            tail = tid[len(prefix) :].lstrip("-#")
            if tail.isdigit():
                used.append(int(tail))

    nxt = (max(used) + 1) if used else 1
    if prefix.lower() in ("num", "#"):
        return f"#{nxt:03d}"
    return f"{prefix}-{nxt}"
