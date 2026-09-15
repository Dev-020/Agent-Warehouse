"""Keep a Changelog parsing and release edits (DESIGN §4.15)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .errors import UsageError
from .semver import Version

_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_BULLET_RE = re.compile(r"^\s*[-*] ")


@dataclass
class Section:
    name: str                 # "Unreleased" | "2.1.0"
    date: str | None
    start: int                # heading line index
    end: int                  # exclusive
    body: list[str] = field(default_factory=list)
    category_level: int = 4

    @property
    def version(self) -> Version | None:
        return Version.try_parse(self.name)


def _levels(is_document: bool) -> tuple[int, int, int]:
    return (2, 3, 4) if is_document else (1, 2, 3)


def _find_changelog_heading(lines: list[str], level: int) -> int | None:
    target = "#" * level + " Changelog"
    in_fence = False
    found = None
    for i, line in enumerate(lines):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence and line.rstrip() == target:
            found = i
    return found


def parse(text: str, *, is_document: bool) -> list[Section]:
    """Parse the changelog sections. Raises UsageError if the changelog heading is absent."""
    lines = text.split("\n")
    top, ver, cat = _levels(is_document)
    h = _find_changelog_heading(lines, top)
    if h is None:
        raise UsageError(f"no '{'#' * top} Changelog' heading")
    sec_re = re.compile(r"^" + "#" * ver + r" \[([^\]]+)\](?:\s+-\s+(\S+))?\s*$")
    stop_re = re.compile(r"^#{1," + str(top) + r"} ")
    sections: list[Section] = []
    in_fence = False
    end_of_region = len(lines)
    for i in range(h + 1, len(lines)):
        line = lines[i]
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = sec_re.match(line)
        if m:
            if sections:
                sections[-1].end = i
            sections.append(Section(m.group(1), m.group(2), i, len(lines), category_level=cat))
            continue
        if stop_re.match(line):
            end_of_region = i
            break
    if sections and sections[-1].end > end_of_region:
        sections[-1].end = end_of_region
    for s in sections:
        s.body = lines[s.start + 1:s.end]
    return sections


def validate(sections: list[Section]) -> list[str]:
    problems = []
    names = [s.name for s in sections]
    if "Unreleased" not in names:
        problems.append("[Unreleased] section missing")
    elif names[0] != "Unreleased":
        problems.append("[Unreleased] must be the first section")
    prev = None
    for s in sections:
        if s.name == "Unreleased":
            continue
        v = s.version
        if v is None:
            problems.append(f"bad version heading [{s.name}]")
            continue
        if s.date is None or not _DATE_RE.match(s.date):
            problems.append(f"[{s.name}] needs a YYYY-MM-DD date")
        if prev is not None and not v < prev:
            problems.append(f"versions not strictly descending at [{s.name}]")
        prev = v
    return problems


def unreleased(sections: list[Section]) -> Section:
    for s in sections:
        if s.name == "Unreleased":
            return s
    raise UsageError("[Unreleased] section missing")


def released(sections: list[Section]) -> list[Section]:
    return [s for s in sections if s.version is not None]


def bullets(section: Section) -> list[str]:
    return [line for line in section.body if _BULLET_RE.match(line)]


def entries_between(sections: list[Section], low: Version, high: Version) -> list[Section]:
    out = [s for s in sections if s.version is not None and low < s.version <= high]
    return sorted(out, key=lambda s: s.version, reverse=True)


def _bullet_blocks(section: Section) -> list[list[str]]:
    blocks: list[list[str]] = []
    cur: list[str] | None = None
    for line in section.body:
        if re.match(r"^[-*] ", line):
            cur = [line]
            blocks.append(cur)
        elif cur is not None and line.strip() and line[:1] in (" ", "\t"):
            cur.append(line)
        else:
            cur = None
    return blocks


def breaking(section: Section) -> list[str]:
    """Bullets containing 'BREAKING:' with their indented continuation lines, joined."""
    out = []
    for block in _bullet_blocks(section):
        if any("BREAKING:" in b for b in block):
            out.append("\n".join(block))
    return out


def categorized_bullets(section: Section) -> list[tuple[str, str]]:
    """(category, bullet text incl. continuation) for status display."""
    cat_re = re.compile(r"^#{" + str(section.category_level) + r"} (.+)$")
    starts = {id(b[0]): b for b in _bullet_blocks(section)}
    out, cat = [], ""
    for line in section.body:
        m = cat_re.match(line)
        if m:
            cat = m.group(1).strip()
        elif id(line) in starts:
            out.append((cat, " ".join(x.strip() for x in starts[id(line)])))
    return out


def release_edit(text: str, new: Version, today: str, *, is_document: bool) -> str:
    sections = parse(text, is_document=is_document)
    unrel = unreleased(sections)
    lines = text.split("\n")
    body = list(unrel.body)
    while body and not body[0].strip():
        body.pop(0)
    while body and not body[-1].strip():
        body.pop()
    _, ver, _ = _levels(is_document)
    has_following = unrel.end < len(lines) and any(l.strip() for l in lines[unrel.end:])
    new_block = [lines[unrel.start], "", "#" * ver + f" [{new}] - {today}", *body]
    rest = lines[unrel.end:]
    if has_following:
        new_block.append("")
        while rest and not rest[0].strip():
            rest.pop(0)
    else:
        rest = [""]
    out = lines[:unrel.start] + new_block + rest
    result = "\n".join(out)
    if not result.endswith("\n"):
        result += "\n"
    return result

def append_changed(text: str, msg: str, is_document: bool) -> str:
    sections = parse(text, is_document=is_document)
    unrel = unreleased(sections)
    lines = text.split("\n")
    
    top, ver, cat_level = _levels(is_document)
    cat_heading = "#" * cat_level + " Changed"
    
    body = lines[unrel.start + 1:unrel.end]
    cat_idx = None
    in_fence = False
    for i, line in enumerate(body):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
        if not in_fence and line.rstrip() == cat_heading:
            cat_idx = i
            break
            
    if cat_idx is not None:
        insert_idx = len(body)
        for i in range(cat_idx + 1, len(body)):
            if not in_fence and body[i].startswith("#" * cat_level + " "):
                insert_idx = i
                break
            if _FENCE_RE.match(body[i]):
                in_fence = not in_fence
        while insert_idx > cat_idx + 1 and not body[insert_idx - 1].strip():
            insert_idx -= 1
        body.insert(insert_idx, msg)
    else:
        while body and not body[-1].strip():
            body.pop()
        if body:
            body.append("")
        body.append(cat_heading)
        body.append(msg)
        body.append("")
        
    out = lines[:unrel.start + 1] + body + lines[unrel.end:]
    return "\n".join(out)
