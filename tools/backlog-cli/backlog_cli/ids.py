"""Task ID parsing, classification, and allocation."""

from __future__ import annotations

import re


def parse_task_id(header_line: str) -> str | None:
    """Extract ID from ### [ID] or # [ID]. Drops legacy - [ ] **ID**."""
    line = header_line.strip()
    m = re.match(r"^#{1,3}\s+\[([^\]]+)\]", line)
    if m:
        return m.group(1).strip()
    return None


def id_matches(a: str, b: str) -> bool:
    """Check if two IDs match, ignoring quotes, brackets, and leading # differences."""
    clean_a = a.strip().strip("'\"").strip("[]")
    clean_b = b.strip().strip("'\"").strip("[]")
    if clean_a == clean_b:
        return True
    return clean_a.lstrip("#") == clean_b.lstrip("#")


def classify_id(raw_id: str) -> tuple[str, str, int, int]:
    """Classify an ID into (scheme_type, prefix_or_symbol, number, width).

    scheme_type is 'sequential', 'prefixed', or 'other'.
    """
    clean = raw_id.strip().strip("'\"").strip("[]")
    if clean.startswith("#") and clean[1:].isdigit():
        return ("sequential", "#", int(clean[1:]), len(clean[1:]))
    m = re.match(r"^([A-Za-z]+)-(\d+)$", clean)
    if m:
        return ("prefixed", m.group(1), int(m.group(2)), len(m.group(2)))
    return ("other", clean, 0, 0)


def extract_all_ids(text: str) -> list[str]:
    """Extract all task IDs from a text string."""
    ids = []
    for line in text.splitlines():
        tid = parse_task_id(line)
        if tid:
            ids.append(tid)
    return ids


def allocate_id(
    existing_ids: list[str],
    prefix: str | None = None,
    new_prefix: bool = False,
) -> str:
    """Allocate the next task ID adhering to decision 13 (S7)."""
    from backlog_cli import TaskError

    seq_nums: list[int] = []
    seq_widths: list[int] = []
    prefix_map: dict[str, list[int]] = {}

    for raw_id in existing_ids:
        stype, pfix, num, width = classify_id(raw_id)
        if stype == "sequential":
            seq_nums.append(num)
            seq_widths.append(width)
        elif stype == "prefixed":
            prefix_map.setdefault(pfix, []).append(num)

    known_prefixes = sorted(prefix_map.keys())
    schemes_in_use: list[str] = []
    if seq_nums:
        schemes_in_use.append("#")
    schemes_in_use.extend(known_prefixes)

    if prefix is not None:
        p = prefix.strip()
        if p == "#":
            if not seq_nums and not new_prefix:
                prefixes_disp = ", ".join(schemes_in_use) or "none"
                raise TaskError(
                    f"Sequential ID scheme '#' is not in use. Prefixes in use: {prefixes_disp}. Use --new-prefix to introduce it."
                )
            nxt = (max(seq_nums) + 1) if seq_nums else 1
            width = max(max(seq_widths), 3) if seq_widths else 3
            return f"#{nxt:0{width}d}"
        else:
            if p not in prefix_map and not new_prefix:
                prefixes_disp = ", ".join(known_prefixes) or "none"
                raise TaskError(
                    f"Prefix '{p}' is not in use. Prefixes in use: {prefixes_disp}. Use --new-prefix to introduce it."
                )
            nxt = (max(prefix_map[p]) + 1) if p in prefix_map else 1
            return f"{p}-{nxt}"

    # Without --prefix
    if not schemes_in_use:
        return "#001"
    if len(schemes_in_use) == 1:
        scheme = schemes_in_use[0]
        if scheme == "#":
            nxt = max(seq_nums) + 1
            width = max(max(seq_widths), 3)
            return f"#{nxt:0{width}d}"
        else:
            nxt = max(prefix_map[scheme]) + 1
            return f"{scheme}-{nxt}"

    schemes_disp = ", ".join(schemes_in_use)
    raise TaskError(
        f"Multiple ID schemes in use: {schemes_disp}. Specify --prefix to allocate a new ID."
    )


def find_next_id(prefix: str, text: str) -> str:
    """Legacy helper: allocate next ID matching prefix from text."""
    existing = extract_all_ids(text)
    return allocate_id(existing, prefix=prefix, new_prefix=True)
