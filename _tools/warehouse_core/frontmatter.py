"""Split, parse and line-edit YAML frontmatter."""
from __future__ import annotations

import re

import yaml

from .errors import UsageError


def _bounds(text: str) -> tuple[int, int] | None:
    """Return (block_start, block_end_offset_after_closing_fence) or None."""
    if not text.startswith("---\n"):
        return None
    pos = 4
    while True:
        nl = text.find("\n", pos)
        line = text[pos:] if nl == -1 else text[pos:nl]
        if line.rstrip() == "---":
            end = len(text) if nl == -1 else nl + 1
            return 4, end
        if nl == -1:
            return None
        pos = nl + 1


def split(text: str) -> tuple[str | None, str]:
    b = _bounds(text)
    if b is None:
        return None, text
    start, end = b
    closing = text.rfind("---", start, end)
    return text[4:closing], text[end:]


def end_offset(text: str) -> int | None:
    """Offset just after the closing '---\\n' line."""
    b = _bounds(text)
    return None if b is None else b[1]


def parse(text: str) -> dict:
    block, _ = split(text)
    if block is None:
        raise UsageError("no frontmatter (file must start with '---' and have a closing '---' line)")
    try:
        data = yaml.safe_load(block) if block.strip() else {}
    except yaml.YAMLError as e:
        raise UsageError(f"frontmatter is not valid YAML: {e}") from None
    if not isinstance(data, dict):
        raise UsageError("frontmatter must be a mapping")
    return data


def set_scalar(text: str, key: str, value: str) -> str:
    b = _bounds(text)
    if b is None:
        raise UsageError("no frontmatter")
    start, end = b
    block = text[start:end]
    pat = re.compile(rf"^{re.escape(key)}:.*$", re.M)
    if not pat.search(block):
        raise UsageError(f"frontmatter has no '{key}:' line")
    new_block = pat.sub(lambda m: f"{key}: {value}", block, count=1)
    return text[:start] + new_block + text[end:]
