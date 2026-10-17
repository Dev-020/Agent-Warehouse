"""Layout helpers for sections and spans."""

from __future__ import annotations

import re

from backlog_cli.ids import parse_task_id

PRIORITY_LEVELS = ("P1", "P2", "P3")


def locate_section(lines: list[str], heading_pattern: str) -> int | None:
    """Find line index of section heading matching pattern."""
    regex = re.compile(heading_pattern, re.IGNORECASE)
    for i, line in enumerate(lines):
        if line.startswith("## ") and regex.search(line):
            return i
    return None


def find_task_span(lines: list[str], task_id: str) -> tuple[int, int] | None:
    """Find [start, end) line range for task entry."""
    start = None
    for i, line in enumerate(lines):
        tid = parse_task_id(line)
        if tid == task_id or tid == f"#{task_id}" or (task_id.startswith("#") and tid == task_id[1:]):
            start = i
            break
    if start is None:
        return None

    end = len(lines)
    for j in range(start + 1, len(lines)):
        line = lines[j]
        if line.startswith("## ") or line.startswith("### ") or (line.startswith("- [") and "**" in line):
            end = j
            break
    return start, end
