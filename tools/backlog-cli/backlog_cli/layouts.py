"""Layout implementations for single-file, split-files, and item-folders backlogs."""

from __future__ import annotations

import datetime
import os
import re
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from backlog_cli import TaskError
from backlog_cli.gitops import write_atomic
from backlog_cli.ids import id_matches, parse_task_id
from backlog_cli.model import Item

PRIORITY_LEVELS = ("P1", "P2", "P3")
PRIORITY_RANK = {"P1": 1, "P2": 2, "P3": 3}


def make_slug(title: str) -> str:
    """Generate a slug from title: lowercase, non-alphanumerics to -, cut to at most 50 chars at - (F12)."""
    s = title.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if len(s) > 50:
        s = s[:50]
        if "-" in s:
            s = s.rsplit("-", 1)[0]
    if not s:
        s = "item"
    return s


def yaml_escape_string(val: str) -> str:
    """Escape backslash and double quote for YAML double-quoted string (F6)."""
    return val.replace("\\", "\\\\").replace('"', '\\"')


def parse_labels_list(val: Any) -> list[str]:
    """Parse labels from string or list into a list of clean label strings (F10)."""
    if not val:
        return []
    if isinstance(val, list):
        res: list[str] = []
        for x in val:
            res.extend(parse_labels_list(x))
        return res
    if isinstance(val, str):
        parts = [p.strip().strip("`").strip("'\"") for p in val.split(",") if p.strip()]
        return [p for p in parts if p]
    return [str(val).strip()]


def render_labels_markdown(labels: Any) -> str:
    """Render labels for markdown entry line per convention §4.5 (F10)."""
    lbls = parse_labels_list(labels)
    if not lbls:
        return ""
    return ", ".join(f"`{l}`" for l in lbls)


def format_yaml_value(key: str, val: Any) -> str:
    """Format a value for YAML frontmatter per ruling F6."""
    if key in ("title", "id"):
        return f'"{yaml_escape_string(str(val))}"'
    if key == "labels" or isinstance(val, list):
        items = parse_labels_list(val) if key == "labels" else [str(x) for x in val]
        quoted_items = [f'"{yaml_escape_string(x)}"' for x in items]
        return f"[{', '.join(quoted_items)}]"

    sval = str(val)
    if (
        ": " in sval
        or " #" in sval
        or (sval and sval[0] in "[]{}!&*->%@#?,`|'\"")
        or sval != sval.strip()
        or sval.lower() in ("true", "false", "yes", "no", "on", "off", "null", "~", "")
    ):
        return f'"{yaml_escape_string(sval)}"'

    try:
        float(sval)
        return f'"{yaml_escape_string(sval)}"'
    except ValueError:
        pass

    return sval


def unescape_yaml_string(s: str) -> str:
    """Unescape a quoted YAML string per ruling F6."""
    s = s.strip()
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        quote_char = s[0]
        inner = s[1:-1]
        if quote_char == "'":
            return inner.replace("''", "'")
        res = []
        i = 0
        while i < len(inner):
            if inner[i] == "\\" and i + 1 < len(inner):
                nxt = inner[i + 1]
                if nxt == '"':
                    res.append('"')
                    i += 2
                elif nxt == "\\":
                    res.append("\\")
                    i += 2
                elif nxt == "n":
                    res.append("\n")
                    i += 2
                elif nxt == "t":
                    res.append("\t")
                    i += 2
                else:
                    res.append(inner[i : i + 2])
                    i += 2
            else:
                res.append(inner[i])
                i += 1
        return "".join(res)
    return s


def split_lines_exact(text: str) -> list[str]:
    """Split lines strictly on \n, stripping a preceding \r if present (F8)."""
    return [line[:-1] if line.endswith("\r") else line for line in text.split("\n")]


def split_lines_keepends(text: str) -> list[str]:
    """Split text on \n keeping line endings, without splitting on other unicode breaks (F8)."""
    parts = text.split("\n")
    result = [p + "\n" for p in parts[:-1]]
    if parts[-1]:
        result.append(parts[-1])
    return result


def read_text_preserving(path: Path) -> tuple[str, str, bool, str]:
    """Read file content and detect line ending (LF/CRLF), UTF-8 BOM, and exact tail (F7)."""
    raw = path.read_bytes()
    has_bom = raw.startswith(b"\xef\xbb\xbf")
    line_ending = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8-sig")
    tail_len = len(text) - len(text.rstrip("\r\n"))
    tail = text[len(text) - tail_len :]
    return text, line_ending, has_bom, tail


def write_text_preserving(
    path: Path,
    lines_or_text: list[str] | str,
    line_ending: str,
    has_bom: bool,
    tail: str | None = None,
) -> None:
    """Write text preserving original line ending, BOM, and exact tail (F7, F8)."""
    if isinstance(lines_or_text, str):
        tail_len = len(lines_or_text) - len(lines_or_text.rstrip("\r\n"))
        body = lines_or_text[:-tail_len] if tail_len else lines_or_text
        lines = split_lines_exact(body) if body else []
        if tail is None:
            tail = lines_or_text[len(lines_or_text) - tail_len :] if tail_len else line_ending
    else:
        lines = lines_or_text
        if tail is None:
            tail = line_ending

    content = line_ending.join(lines) + tail
    encoded = content.encode("utf-8")
    if has_bom:
        encoded = b"\xef\xbb\xbf" + encoded
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(encoded)
    os.replace(tmp, path)


def parse_markdown_entries(lines: list[str]) -> list[tuple[int, int, str, str]]:
    """Locate all entry spans [start, end) outside code blocks."""
    in_code_block = False
    entries: list[tuple[int, int, str, str]] = []
    current_start: int | None = None
    current_id: str | None = None
    current_title: str | None = None

    for i, line in enumerate(lines):
        sline = line.strip()
        if sline.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        if line.startswith("## ") or line.startswith("### "):
            if current_start is not None:
                entries.append((current_start, i, current_id or "", current_title or ""))
                current_start = None
                current_id = None
                current_title = None

            if line.startswith("### "):
                tid = parse_task_id(line)
                if tid:
                    current_start = i
                    current_id = tid
                    m = re.match(r"^###\s+\[([^\]]+)\]\s*(.*)$", line)
                    current_title = m.group(2).strip() if m else ""

    if current_start is not None:
        entries.append((current_start, len(lines), current_id or "", current_title or ""))

    return entries


def find_sections(lines: list[str]) -> dict[str, tuple[int, int]]:
    """Map section names ('in progress', 'backlog', 'completed', 'icebox') to line spans (F11)."""
    in_code_block = False
    all_headings: list[tuple[int, str | None]] = []
    for i, line in enumerate(lines):
        sline = line.strip()
        if sline.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if line.startswith("## "):
            clean = re.sub(r"[^\w\s\(\)/-]", "", line[3:]).strip().lower()
            norm = None
            if "in progress" in clean:
                norm = "in progress"
            elif "backlog" in clean:
                norm = "backlog"
            elif "completed" in clean:
                norm = "completed"
            elif "icebox" in clean:
                norm = "icebox"
            all_headings.append((i, norm))

    result: dict[str, tuple[int, int]] = {}
    for idx, (line_idx, norm) in enumerate(all_headings):
        if norm:
            next_idx = all_headings[idx + 1][0] if idx + 1 < len(all_headings) else len(lines)
            result[norm] = (line_idx, next_idx)
    return result


def item_from_entry_lines(
    entry_lines: list[str],
    path: Path | None = None,
    span: tuple[int, int] | None = None,
    line_ending: str = "\n",
) -> Item:
    """Parse an Item from entry lines."""
    title_line = entry_lines[0]
    tid = parse_task_id(title_line) or ""
    m = re.match(r"^#{1,3}\s+\[([^\]]+)\]\s*(.*)$", title_line)
    title = m.group(2).strip() if m else ""

    status = "Open"
    priority = "P2"
    fields: dict[str, Any] = {}
    body_lines: list[str] = []

    metadata_done = False
    for line in entry_lines[1:]:
        if not metadata_done and line.startswith("- **"):
            parts = [p.strip() for p in line.lstrip("- ").split("|")]
            for p in parts:
                if "**Status**:" in p:
                    m_st = re.search(r"\*\*Status\*\*:\s*`?([^`*]+)`?", p)
                    if m_st:
                        status = m_st.group(1).strip()
                if "**Priority**:" in p:
                    m_pr = re.search(r"\*\*Priority\*\*:\s*`?([^`*]+)`?", p)
                    if m_pr:
                        priority = m_pr.group(1).strip()
                if "**Labels**:" in p:
                    m_lb = re.search(r"\*\*Labels\*\*:\s*(.*)$", p)
                    if m_lb:
                        fields["labels"] = parse_labels_list(m_lb.group(1).strip())
                if "**Created**:" in p:
                    m_cr = re.search(r"\*\*Created\*\*:\s*([0-9-]+)", p)
                    if m_cr:
                        fields["created"] = m_cr.group(1).strip()
                if "**Resolved**:" in p:
                    m_rs = re.search(r"\*\*Resolved\*\*:\s*([0-9-]+)", p)
                    if m_rs:
                        fields["resolved"] = m_rs.group(1).strip()
        else:
            if line.strip():
                metadata_done = True
            body_lines.append(line)

    raw = line_ending.join(entry_lines)
    body = "\n".join(body_lines)
    return Item(
        id=tid,
        title=title,
        status=status,
        priority=priority,
        fields=fields,
        body=body,
        raw=raw,
        path=path,
        span=span,
    )


def render_entry_lines(item: Item, style: str = "full", h_prefix: str = "###") -> list[str]:
    """Render entry lines adhering to decision 14."""
    today = item.fields.get("created") or datetime.date.today().isoformat()
    lbl_rendered = render_labels_markdown(item.fields.get("labels"))
    labels_part = f" | **Labels**: {lbl_rendered}" if lbl_rendered else ""
    meta_status = f"- **Status**: `{item.status}` | **Priority**: `{item.priority}`{labels_part}"
    meta_created = f"- **Created**: {today}"

    lines = [f"{h_prefix} [{item.id}] {item.title}", meta_status, meta_created]
    if item.fields.get("resolved"):
        lines.append(f"- **Resolved**: {item.fields['resolved']}")

    sub_h = "####" if h_prefix == "###" else "##"
    why = item.fields.get("why", "")
    wanted = item.fields.get("wanted", "")
    criteria = item.fields.get("criteria", [])

    if style == "full":
        lines.append("")
        lines.append(f"{sub_h} Why")
        if why:
            lines.append(why)
        lines.append("")
        lines.append(f"{sub_h} Wanted")
        if wanted:
            lines.append(wanted)
        lines.append("")
        lines.append(f"{sub_h} Acceptance Criteria")
        for idx, crit in enumerate(criteria, start=1):
            lines.append(f"- [ ] #{idx} {crit}")
        lines.append("")
        lines.append(f"{sub_h} Outcome")
        lines.append("(Filled on completion.)")
    else:  # compact
        lines.append("")
        if why:
            lines.append(why)
            lines.append("")
        if wanted:
            lines.append(f"*Wanted:* {wanted}")
            lines.append("")
        if criteria:
            lines.append(f"*Done when:* {criteria[0]}")

    return lines


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str, str]:
    """Parse frontmatter from markdown file. Returns (fields, body, raw_frontmatter)."""
    lines = split_lines_keepends(text)
    if not lines or lines[0].strip() != "---":
        return {}, text, ""
    end_idx = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx == -1:
        return {}, text, ""

    fields: dict[str, Any] = {}
    for line in lines[1:end_idx]:
        sline = line.strip()
        if not sline or sline.startswith("#"):
            continue
        if ":" in sline:
            k, _, v = sline.partition(":")
            k = k.strip()
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                items = [unescape_yaml_string(x.strip()) for x in v[1:-1].split(",") if x.strip()]
                fields[k] = items
            else:
                fields[k] = unescape_yaml_string(v)

    body = "".join(lines[end_idx + 1 :])
    raw_fm = "".join(lines[: end_idx + 1])
    return fields, body, raw_fm


def update_frontmatter(text: str, updates: dict[str, Any]) -> str:
    """Update frontmatter fields surgically. New fields go at the end before ---."""
    lines = split_lines_keepends(text)
    if not lines or lines[0].strip() != "---":
        return text
    end_idx = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx == -1:
        return text

    le = "\r\n" if "\r\n" in text else "\n"
    remaining = dict(updates)
    new_fm_lines: list[str] = []

    for line in lines[1:end_idx]:
        sline = line.strip()
        matched = None
        if ":" in sline:
            k = sline.split(":", 1)[0].strip()
            if k in remaining:
                matched = k
        if matched:
            val = remaining.pop(matched)
            formatted = format_yaml_value(matched, val)
            new_fm_lines.append(f"{matched}: {formatted}{le}")
        else:
            new_fm_lines.append(line)

    for k, val in remaining.items():
        formatted = format_yaml_value(k, val)
        new_fm_lines.append(f"{k}: {formatted}{le}")

    return lines[0] + "".join(new_fm_lines) + "".join(lines[end_idx:])


# ---------------------------------------------------------------------------
# Base Layout Interface
# ---------------------------------------------------------------------------


class BaseLayout(ABC):
    @abstractmethod
    def items(self) -> list[Item]:
        pass

    @abstractmethod
    def find(self, task_id: str) -> Item | None:
        pass

    @abstractmethod
    def add(self, item: Item, style: str = "full") -> tuple[list[Path], list[tuple[Path, Path]]]:
        pass

    @abstractmethod
    def set_status(self, task_id: str, status: str) -> tuple[list[Path], list[tuple[Path, Path]]]:
        pass

    @abstractmethod
    def close(self, task_id: str, status: str, outcome: str) -> tuple[list[Path], list[tuple[Path, Path]]]:
        pass

    @abstractmethod
    def append_note(self, task_id: str, text: str) -> tuple[list[Path], list[tuple[Path, Path]]]:
        pass

    @abstractmethod
    def header(self) -> str:
        pass

    @abstractmethod
    def paths_for(self, task_id: str | None = None) -> list[Path]:
        pass


# ---------------------------------------------------------------------------
# Shared Entry & File Helpers (Decision 22)
# ---------------------------------------------------------------------------


def entry_get_metadata_span(entry_lines: list[str]) -> tuple[int, int]:
    """Return the [start, end) index span of the metadata block directly following the heading."""
    end = 1
    while end < len(entry_lines) and entry_lines[end].startswith("- **"):
        end += 1
    return 1, end


def entry_set_status(entry_lines: list[str], new_status: str, resolved_date: str | None = None) -> None:
    """Update status and optionally insert/update resolved date in the metadata block."""
    meta_start, meta_end = entry_get_metadata_span(entry_lines)
    for i in range(meta_start, meta_end):
        if entry_lines[i].startswith("- **Status**:"):
            entry_lines[i] = re.sub(r"`(Open|In Progress|Closed|Rejected|Cancelled)`", f"`{new_status}`", entry_lines[i])
            break

    if resolved_date:
        has_resolved = False
        for i in range(meta_start, meta_end):
            if entry_lines[i].startswith("- **Resolved**:"):
                has_resolved = True
                entry_lines[i] = f"- **Resolved**: {resolved_date}"
                break
        if not has_resolved:
            # Insert right after the last metadata line (Fixes B1: never past metadata block)
            entry_lines.insert(meta_end, f"- **Resolved**: {resolved_date}")


def entry_set_outcome(entry_lines: list[str], outcome: str, today: str) -> None:
    """Update or append outcome in entry_lines."""
    outcome_idx = None
    for i, l in enumerate(entry_lines):
        if l.strip() == "#### Outcome":
            outcome_idx = i
            break

    if outcome_idx is not None:
        # Full style: replace parenthesized placeholder, or append paragraph below
        next_idx = outcome_idx + 1
        while next_idx < len(entry_lines) and not entry_lines[next_idx].strip():
            next_idx += 1
        if next_idx < len(entry_lines) and re.match(r"^\s*\(.*\)\s*$", entry_lines[next_idx]):
            entry_lines[next_idx] = outcome
        else:
            entry_lines.append("")
            entry_lines.append(outcome)
    else:
        # Compact style: append *Outcome (<date>):* <text>
        entry_lines.append("")
        entry_lines.append(f"*Outcome ({today}):* {outcome}")


def entry_append_note(entry_lines: list[str], text: str, today: str, h_prefix: str = "####") -> None:
    """Append dated note to entry_lines right after last note line, ensuring single blank line before next heading."""
    note_line = f"- {today}: {text}"
    notes_heading = f"{h_prefix} Notes"
    outcome_heading = f"{h_prefix} Outcome"

    is_full = any(l.strip().startswith(f"{h_prefix} ") for l in entry_lines)
    if is_full:
        notes_idx = None
        outcome_idx = None
        for i, l in enumerate(entry_lines):
            s = l.strip()
            if s == notes_heading:
                notes_idx = i
            elif s == outcome_heading:
                outcome_idx = i

        if notes_idx is not None:
            last_note_idx = None
            for i in range(notes_idx + 1, len(entry_lines)):
                s = entry_lines[i].strip()
                if s.startswith(f"{h_prefix} "):
                    break
                if s.startswith("- "):
                    last_note_idx = i

            if last_note_idx is not None:
                insert_idx = last_note_idx + 1
            else:
                insert_idx = notes_idx + 1

            entry_lines.insert(insert_idx, note_line)

            next_idx = insert_idx + 1
            if next_idx < len(entry_lines) and entry_lines[next_idx].strip().startswith(f"{h_prefix} "):
                entry_lines.insert(next_idx, "")
        else:
            insert_before = outcome_idx if outcome_idx is not None else len(entry_lines)
            entry_lines[insert_before:insert_before] = [notes_heading, note_line, ""]
    else:
        wanted_idx = None
        for i, l in enumerate(entry_lines):
            if l.strip().startswith("*Wanted:*"):
                wanted_idx = i
                break
        if wanted_idx is not None:
            last_note_idx = None
            for i in range(wanted_idx):
                s = entry_lines[i].strip()
                if s.startswith("- ") and not s.startswith("- **"):
                    last_note_idx = i

            if last_note_idx is not None:
                entry_lines.insert(last_note_idx + 1, note_line)
            else:
                ins = wanted_idx - 1 if wanted_idx > 0 and not entry_lines[wanted_idx - 1].strip() else wanted_idx
                entry_lines.insert(ins, note_line)
                if ins + 1 < len(entry_lines) and entry_lines[ins + 1].strip():
                    entry_lines.insert(ins + 1, "")
        else:
            entry_lines.append(note_line)


def file_find_entry(
    lines: list[str], task_id: str, path: Path | None = None, line_ending: str = "\n"
) -> tuple[int, int, Item] | None:
    """Find entry matching task_id in lines."""
    for s, e, tid, _ in parse_markdown_entries(lines):
        if id_matches(tid, task_id):
            return s, e, item_from_entry_lines(lines[s:e], path=path, span=(s, e), line_ending=line_ending)
    return None


def file_extract_entry(lines: list[str], task_id: str) -> tuple[list[str], Item]:
    """Extract entry matching task_id from lines, removing it and returning clean entry lines."""
    for s, e, tid, _ in parse_markdown_entries(lines):
        if id_matches(tid, task_id):
            raw_entry = lines[s:e]
            clean_entry = list(raw_entry)
            while clean_entry and not clean_entry[-1].strip():
                clean_entry.pop()
            it = item_from_entry_lines(clean_entry)
            del lines[s:e]
            return clean_entry, it
    raise TaskError(f"Task [{task_id}] not found in backlog")


def file_insert_entry_at_bottom(
    lines: list[str],
    sections: dict[str, tuple[int, int]],
    entry_lines: list[str],
    section_name: str,
) -> None:
    """Insert entry at the bottom of a section, ensuring exact 1-blank-line separation (Fixes B3)."""
    while entry_lines and not entry_lines[0].strip():
        entry_lines.pop(0)
    while entry_lines and not entry_lines[-1].strip():
        entry_lines.pop()

    sec_start, sec_end = sections[section_name]
    last_idx = sec_start
    for i in range(sec_start + 1, sec_end):
        if lines[i].strip():
            last_idx = i

    if sec_end < len(lines):
        lines[last_idx + 1 : sec_end] = ["", *entry_lines, ""]
    else:
        lines[last_idx + 1 : sec_end] = ["", *entry_lines]


def file_insert_entry_by_priority(
    lines: list[str],
    sections: dict[str, tuple[int, int]],
    entry_lines: list[str],
) -> None:
    """Insert entry into backlog section by priority (P1, P2, P3)."""
    while entry_lines and not entry_lines[0].strip():
        entry_lines.pop(0)
    while entry_lines and not entry_lines[-1].strip():
        entry_lines.pop()

    b_start, b_end = sections["backlog"]
    item = item_from_entry_lines(entry_lines)
    new_rank = PRIORITY_RANK.get(item.priority, 2)
    entries = parse_markdown_entries(lines)
    backlog_entries = [
        (s, e, item_from_entry_lines(lines[s:e])) for s, e, _, _ in entries if s >= b_start and e <= b_end
    ]

    same_prio = [e for e in backlog_entries if PRIORITY_RANK.get(e[2].priority, 2) == new_rank]
    lower_prio = [e for e in backlog_entries if PRIORITY_RANK.get(e[2].priority, 2) > new_rank]

    if same_prio:
        target_idx = same_prio[-1][1]
        lines[target_idx:target_idx] = [*entry_lines, ""]
    elif lower_prio:
        target_idx = lower_prio[0][0]
        lines[target_idx:target_idx] = [*entry_lines, ""]
    else:
        file_insert_entry_at_bottom(lines, sections, entry_lines, "backlog")


# ---------------------------------------------------------------------------
# Single File Layout
# ---------------------------------------------------------------------------


class SingleFileLayout(BaseLayout):
    def __init__(self, backlog_file: Path):
        self.file = Path(backlog_file)

    def header(self) -> str:
        if not self.file.is_file():
            return ""
        text, _, _, _ = read_text_preserving(self.file)
        lines = split_lines_exact(text.rstrip("\r\n")) if text else []
        hdr_lines: list[str] = []
        for line in lines:
            if line.startswith("## "):
                break
            hdr_lines.append(line)
        return "\n".join(hdr_lines)

    def paths_for(self, task_id: str | None = None) -> list[Path]:
        return [self.file]

    def _load(self) -> tuple[list[str], str, bool, str, dict[str, tuple[int, int]]]:
        if not self.file.is_file():
            raise TaskError(f"Backlog file does not exist at {self.file}")
        text, le, bom, tail = read_text_preserving(self.file)
        lines = split_lines_exact(text[: len(text) - len(tail)] if tail else text) if text else []
        sections = find_sections(lines)
        for req in ("in progress", "backlog", "completed", "icebox"):
            if req not in sections:
                raise TaskError(f"Section '{req}' not found in {self.file}")
        return lines, le, bom, tail, sections

    def items(self) -> list[Item]:
        if not self.file.is_file():
            return []
        lines, le, bom, tail, _ = self._load()
        entries = parse_markdown_entries(lines)
        return [
            item_from_entry_lines(lines[start:end], self.file, (start, end), line_ending=le)
            for start, end, _, _ in entries
        ]

    def find(self, task_id: str) -> Item | None:
        for it in self.items():
            if id_matches(it.id, task_id):
                return it
        return None

    def add(self, item: Item, style: str = "full") -> tuple[list[Path], list[tuple[Path, Path]]]:
        lines, le, bom, tail, sections = self._load()
        entry_lines = render_entry_lines(item, style=style, h_prefix="###")
        file_insert_entry_by_priority(lines, sections, entry_lines)
        write_text_preserving(self.file, lines, le, bom, tail=tail)
        return [self.file], []

    def set_status(self, task_id: str, status: str) -> tuple[list[Path], list[tuple[Path, Path]]]:
        lines, le, bom, tail, sections = self._load()
        entry_lines, _ = file_extract_entry(lines, task_id)
        today = datetime.date.today().isoformat()
        entry_set_status(entry_lines, status, resolved_date=(today if status in ("Rejected", "Cancelled") else None))
        sections = find_sections(lines)
        if status == "In Progress":
            target_sec = "in progress"
        elif status in ("Rejected", "Cancelled"):
            target_sec = "icebox"
        elif status == "Closed":
            target_sec = "completed"
        else:
            target_sec = "backlog"
        file_insert_entry_at_bottom(lines, sections, entry_lines, target_sec)
        write_text_preserving(self.file, lines, le, bom, tail=tail)
        return [self.file], []

    def close(self, task_id: str, status: str, outcome: str) -> tuple[list[Path], list[tuple[Path, Path]]]:
        lines, le, bom, tail, sections = self._load()
        entry_lines, _ = file_extract_entry(lines, task_id)
        today = datetime.date.today().isoformat()
        entry_set_status(entry_lines, status, resolved_date=today)
        entry_set_outcome(entry_lines, outcome, today)
        sections = find_sections(lines)
        file_insert_entry_at_bottom(lines, sections, entry_lines, "completed")
        write_text_preserving(self.file, lines, le, bom, tail=tail)
        return [self.file], []

    def append_note(self, task_id: str, text: str) -> tuple[list[Path], list[tuple[Path, Path]]]:
        lines, le, bom, tail, _ = self._load()
        res = file_find_entry(lines, task_id, path=self.file, line_ending=le)
        if not res:
            raise TaskError(f"Task [{task_id}] not found in {self.file}")
        start, end, _ = res
        entry_lines = list(lines[start:end])
        today = datetime.date.today().isoformat()
        entry_append_note(entry_lines, text, today, h_prefix="####")
        lines[start:end] = entry_lines
        write_text_preserving(self.file, lines, le, bom, tail=tail)
        return [self.file], []


# ---------------------------------------------------------------------------
# Split Files Layout
# ---------------------------------------------------------------------------


class SplitFilesLayout(BaseLayout):
    def __init__(self, backlog_dir: Path):
        self.dir = Path(backlog_dir)
        self.header_file = self.dir / "00_BACKLOG.md"
        self.open_file = self.dir / "Open.md"
        self.closed_file = self.dir / "Closed.md"

    def header(self) -> str:
        if not self.header_file.is_file():
            return ""
        text, _, _, _ = read_text_preserving(self.header_file)
        return text

    def paths_for(self, task_id: str | None = None) -> list[Path]:
        return [self.open_file, self.closed_file]

    def _load_open(self) -> tuple[list[str], str, bool, str, dict[str, tuple[int, int]]]:
        if not self.open_file.is_file():
            raise TaskError(f"Backlog file does not exist at {self.open_file}")
        text, le, bom, tail = read_text_preserving(self.open_file)
        lines = split_lines_exact(text[: len(text) - len(tail)] if tail else text) if text else []
        sections = find_sections(lines)
        for req in ("in progress", "backlog"):
            if req not in sections:
                raise TaskError(f"Section '{req}' not found in {self.open_file}")
        return lines, le, bom, tail, sections

    def _load_closed(self) -> tuple[list[str], str, bool, str, dict[str, tuple[int, int]]]:
        if not self.closed_file.is_file():
            raise TaskError(f"Backlog file does not exist at {self.closed_file}")
        text, le, bom, tail = read_text_preserving(self.closed_file)
        lines = split_lines_exact(text[: len(text) - len(tail)] if tail else text) if text else []
        sections = find_sections(lines)
        for req in ("completed", "icebox"):
            if req not in sections:
                raise TaskError(f"Section '{req}' not found in {self.closed_file}")
        return lines, le, bom, tail, sections

    def items(self) -> list[Item]:
        res: list[Item] = []
        if self.open_file.is_file():
            lines, le, bom, tail, _ = self._load_open()
            for s, e, _, _ in parse_markdown_entries(lines):
                res.append(item_from_entry_lines(lines[s:e], self.open_file, (s, e), line_ending=le))
        if self.closed_file.is_file():
            lines, le, bom, tail, _ = self._load_closed()
            for s, e, _, _ in parse_markdown_entries(lines):
                res.append(item_from_entry_lines(lines[s:e], self.closed_file, (s, e), line_ending=le))
        return res

    def find(self, task_id: str) -> Item | None:
        for it in self.items():
            if id_matches(it.id, task_id):
                return it
        return None

    def add(self, item: Item, style: str = "full") -> tuple[list[Path], list[tuple[Path, Path]]]:
        lines, le, bom, tail, sections = self._load_open()
        entry_lines = render_entry_lines(item, style=style, h_prefix="###")
        file_insert_entry_by_priority(lines, sections, entry_lines)
        write_text_preserving(self.open_file, lines, le, bom, tail=tail)
        return [self.open_file], []

    def set_status(self, task_id: str, status: str) -> tuple[list[Path], list[tuple[Path, Path]]]:
        target = self.find(task_id)
        if not target or not target.span or not target.path:
            raise TaskError(f"Task [{task_id}] not found in backlog")

        today = datetime.date.today().isoformat()
        is_closing = status in ("Closed", "Rejected", "Cancelled")

        if target.path == self.open_file and not is_closing:
            lines, le, bom, tail, sections = self._load_open()
            entry_lines, _ = file_extract_entry(lines, task_id)
            entry_set_status(entry_lines, status)
            sections = find_sections(lines)
            target_sec = "in progress" if status == "In Progress" else "backlog"
            file_insert_entry_at_bottom(lines, sections, entry_lines, target_sec)
            write_text_preserving(self.open_file, lines, le, bom, tail=tail)
            return [self.open_file], []

        if target.path == self.open_file:
            open_lines, o_le, o_bom, o_tail, _ = self._load_open()
            entry_lines, _ = file_extract_entry(open_lines, task_id)
            entry_set_status(entry_lines, status, resolved_date=(today if is_closing else None))
            write_text_preserving(self.open_file, open_lines, o_le, o_bom, tail=o_tail)

            closed_lines, c_le, c_bom, c_tail, sections = self._load_closed()
            target_sec = "completed" if status == "Closed" else "icebox"
            file_insert_entry_at_bottom(closed_lines, sections, entry_lines, target_sec)
            write_text_preserving(self.closed_file, closed_lines, c_le, c_bom, tail=c_tail)
            return [self.open_file, self.closed_file], []
        else:
            closed_lines, c_le, c_bom, c_tail, sections = self._load_closed()
            entry_lines, _ = file_extract_entry(closed_lines, task_id)
            entry_set_status(entry_lines, status, resolved_date=(today if is_closing else None))
            sections = find_sections(closed_lines)
            target_sec = "completed" if status == "Closed" else "icebox"
            file_insert_entry_at_bottom(closed_lines, sections, entry_lines, target_sec)
            write_text_preserving(self.closed_file, closed_lines, c_le, c_bom, tail=c_tail)
            return [self.closed_file], []

    def close(self, task_id: str, status: str, outcome: str) -> tuple[list[Path], list[tuple[Path, Path]]]:
        target = self.find(task_id)
        if not target or not target.span or not target.path:
            raise TaskError(f"Task [{task_id}] not found in backlog")

        today = datetime.date.today().isoformat()
        if target.path == self.open_file:
            open_lines, o_le, o_bom, o_tail, _ = self._load_open()
            entry_lines, _ = file_extract_entry(open_lines, task_id)
            entry_set_status(entry_lines, status, resolved_date=today)
            entry_set_outcome(entry_lines, outcome, today)
            write_text_preserving(self.open_file, open_lines, o_le, o_bom, tail=o_tail)

            closed_lines, c_le, c_bom, c_tail, sections = self._load_closed()
            file_insert_entry_at_bottom(closed_lines, sections, entry_lines, "completed")
            write_text_preserving(self.closed_file, closed_lines, c_le, c_bom, tail=c_tail)
            return [self.open_file, self.closed_file], []
        else:
            closed_lines, c_le, c_bom, c_tail, sections = self._load_closed()
            entry_lines, _ = file_extract_entry(closed_lines, task_id)
            entry_set_status(entry_lines, status, resolved_date=today)
            entry_set_outcome(entry_lines, outcome, today)
            sections = find_sections(closed_lines)
            file_insert_entry_at_bottom(closed_lines, sections, entry_lines, "completed")
            write_text_preserving(self.closed_file, closed_lines, c_le, c_bom, tail=c_tail)
            return [self.closed_file], []

    def append_note(self, task_id: str, text: str) -> tuple[list[Path], list[tuple[Path, Path]]]:
        target = self.find(task_id)
        if not target or not target.span or not target.path:
            raise TaskError(f"Task [{task_id}] not found in backlog")

        target_file = target.path
        text_content, le, bom, tail = read_text_preserving(target_file)
        lines = split_lines_exact(text_content[: len(text_content) - len(tail)] if tail else text_content) if text_content else []
        res = file_find_entry(lines, task_id, path=target_file, line_ending=le)
        if not res:
            raise TaskError(f"Task [{task_id}] not found in {target_file}")
        start, end, _ = res
        entry_lines = list(lines[start:end])
        today = datetime.date.today().isoformat()
        entry_append_note(entry_lines, text, today, h_prefix="####")
        lines[start:end] = entry_lines
        write_text_preserving(target_file, lines, le, bom, tail=tail)
        return [target_file], []


# ---------------------------------------------------------------------------
# Item Folders Layout
# ---------------------------------------------------------------------------


class ItemFoldersLayout(BaseLayout):
    def __init__(self, backlog_dir: Path):
        self.dir = Path(backlog_dir)
        self.header_file = self.dir / "00_BACKLOG.md"
        self.open_dir = self.dir / "open"
        self.closed_dir = self.dir / "closed"

    def header(self) -> str:
        if not self.header_file.is_file():
            return ""
        text, _, _, _ = read_text_preserving(self.header_file)
        return text

    def paths_for(self, task_id: str | None = None) -> list[Path]:
        if task_id:
            it = self.find(task_id)
            if it and it.path:
                return [it.path]
        return [self.open_dir, self.closed_dir]

    def _find_item_path(self, base_dir: Path, clean_id: str) -> Path | None:
        if not base_dir.is_dir():
            return None
        # Check files directly in base_dir
        for p in base_dir.iterdir():
            if p.is_file() and p.suffix == ".md":
                prefix = p.stem.split("-", 1)[0]
                if prefix.lower() == clean_id.lower() or p.stem.lower() == clean_id.lower():
                    return p
            elif p.is_dir():
                prefix = p.name.split("-", 1)[0]
                if prefix.lower() == clean_id.lower() or p.name.lower() == clean_id.lower():
                    main_file = p / f"{p.name}.md"
                    if main_file.is_file():
                        return main_file
        return None

    def items(self) -> list[Item]:
        res: list[Item] = []
        for d in (self.open_dir, self.closed_dir):
            if not d.is_dir():
                continue
            for p in d.iterdir():
                file_to_read = None
                if p.is_file() and p.suffix == ".md" and p.name != ".gitkeep":
                    file_to_read = p
                elif p.is_dir():
                    main_file = p / f"{p.name}.md"
                    if main_file.is_file():
                        file_to_read = main_file

                if file_to_read:
                    text, _, _, _ = read_text_preserving(file_to_read)
                    fields, body, _ = parse_frontmatter(text)
                    tid = str(fields.get("id", "")).strip()
                    if not tid:
                        fname = file_to_read.stem
                        m = re.match(r"^(\d+|[A-Za-z]+-\d+)(?:-|\.md$|/|$)", fname)
                        if m:
                            tid = f"#{m.group(1)}" if m.group(1).isdigit() else m.group(1)
                    title = str(fields.get("title", ""))
                    status = str(fields.get("status", "Open"))
                    priority = str(fields.get("priority", "P2"))
                    res.append(
                        Item(
                            id=tid,
                            title=title,
                            status=status,
                            priority=priority,
                            fields=fields,
                            body=body,
                            raw=text,
                            path=file_to_read,
                        )
                    )
        return res

    def find(self, task_id: str) -> Item | None:
        clean_id = task_id.lstrip("#").strip("[]")
        # Try quick path lookup in open and closed
        for base in (self.open_dir, self.closed_dir):
            p = self._find_item_path(base, clean_id)
            if p:
                text, _, _, _ = read_text_preserving(p)
                fields, body, _ = parse_frontmatter(text)
                tid = str(fields.get("id", "")).strip()
                if not tid:
                    fname = p.stem
                    m = re.match(r"^(\d+|[A-Za-z]+-\d+)(?:-|\.md$|/|$)", fname)
                    if m:
                        tid = f"#{m.group(1)}" if m.group(1).isdigit() else m.group(1)
                if id_matches(tid, task_id):
                    return Item(
                        id=tid,
                        title=str(fields.get("title", "")),
                        status=str(fields.get("status", "Open")),
                        priority=str(fields.get("priority", "P2")),
                        fields=fields,
                        body=body,
                        raw=text,
                        path=p,
                    )

        # Fallback: scan all items by frontmatter id
        for it in self.items():
            if id_matches(it.id, task_id):
                return it
        return None

    def add(self, item: Item, style: str = "full") -> list[Path]:
        self.open_dir.mkdir(parents=True, exist_ok=True)
        clean_id = item.id.lstrip("#").strip("[]")
        slug = make_slug(item.title)
        filename = f"{clean_id}-{slug}.md"
        target_path = self.open_dir / filename

        today = item.fields.get("created") or datetime.date.today().isoformat()
        fm_lines = [
            "---",
            f"id: {format_yaml_value('id', item.id)}",
            f"title: {format_yaml_value('title', item.title)}",
            f"status: {format_yaml_value('status', item.status)}",
            f"priority: {format_yaml_value('priority', item.priority)}",
        ]
        if item.fields.get("labels"):
            lbls = format_yaml_value("labels", item.fields["labels"])
            fm_lines.append(f"labels: {lbls}")
        fm_lines.append(f"created: {format_yaml_value('created', today)}")
        fm_lines.append("---")
        fm_lines.append("")

        body_lines = [f"# [{item.id}] {item.title}"]
        sub_h = "##"
        why = item.fields.get("why", "")
        wanted = item.fields.get("wanted", "")
        criteria = item.fields.get("criteria", [])

        if style == "full":
            body_lines.append("")
            body_lines.append(f"{sub_h} Why")
            if why:
                body_lines.append(why)
            body_lines.append("")
            body_lines.append(f"{sub_h} Wanted")
            if wanted:
                body_lines.append(wanted)
            body_lines.append("")
            body_lines.append(f"{sub_h} Acceptance Criteria")
            for idx, crit in enumerate(criteria, start=1):
                body_lines.append(f"- [ ] #{idx} {crit}")
            body_lines.append("")
            body_lines.append(f"{sub_h} Outcome")
            body_lines.append("(Filled on completion.)")
        else:  # compact
            body_lines.append("")
            if why:
                body_lines.append(why)
                body_lines.append("")
            if wanted:
                body_lines.append(f"*Wanted:* {wanted}")
                body_lines.append("")
            if criteria:
                body_lines.append(f"*Done when:* {criteria[0]}")

        content = "\n".join(fm_lines + body_lines) + "\n"
        write_atomic(target_path, content)
        return [target_path], []

    def set_status(self, task_id: str, status: str) -> tuple[list[Path], list[tuple[Path, Path]]]:
        target = self.find(task_id)
        if not target or not target.path:
            raise TaskError(f"Task [{task_id}] not found in backlog")

        file_path = target.path
        text, le, bom, tail = read_text_preserving(file_path)
        updates: dict[str, Any] = {"status": status}
        today = datetime.date.today().isoformat()
        if status in ("Rejected", "Cancelled"):
            updates["resolved"] = today

        new_text = update_frontmatter(text, updates)
        write_text_preserving(file_path, new_text, le, bom, tail=tail)

        if status in ("Rejected", "Cancelled") and self.open_dir in file_path.parents:
            # Move to closed/
            self.closed_dir.mkdir(parents=True, exist_ok=True)
            if file_path.parent == self.open_dir:
                dest = self.closed_dir / file_path.name
                shutil.move(str(file_path), str(dest))
                return [dest], [(file_path, dest)]
            else:
                folder = file_path.parent
                dest = self.closed_dir / folder.name
                shutil.move(str(folder), str(dest))
                main_file = dest / file_path.name
                return [main_file], [(folder, dest)]

        return [file_path], []

    def close(self, task_id: str, status: str, outcome: str) -> tuple[list[Path], list[tuple[Path, Path]]]:
        target = self.find(task_id)
        if not target or not target.path:
            raise TaskError(f"Task [{task_id}] not found in backlog")

        file_path = target.path
        text, le, bom, tail = read_text_preserving(file_path)
        today = datetime.date.today().isoformat()

        # Update frontmatter: status and resolved
        updates = {"status": status, "resolved": today}
        text_with_fm = update_frontmatter(text, updates)

        # Update outcome in body
        lines = split_lines_exact(text_with_fm[: len(text_with_fm) - len(tail)] if tail else text_with_fm) if text_with_fm else []
        outcome_idx = None
        for i, l in enumerate(lines):
            if l.strip() == "## Outcome":
                outcome_idx = i
                break

        if outcome_idx is not None:
            next_idx = outcome_idx + 1
            while next_idx < len(lines) and not lines[next_idx].strip():
                next_idx += 1
            if next_idx < len(lines) and re.match(r"^\s*\(.*\)\s*$", lines[next_idx]):
                lines[next_idx] = outcome
            else:
                lines.append("")
                lines.append(outcome)
        else:
            lines.append("")
            lines.append(f"*Outcome ({today}):* {outcome}")

        write_text_preserving(file_path, lines, le, bom, tail=tail)

        # Move to closed/
        self.closed_dir.mkdir(parents=True, exist_ok=True)
        if file_path.parent == self.open_dir:
            dest = self.closed_dir / file_path.name
            shutil.move(str(file_path), str(dest))
            return [dest], [(file_path, dest)]
        else:
            folder = file_path.parent
            dest = self.closed_dir / folder.name
            shutil.move(str(folder), str(dest))
            main_file = dest / file_path.name
            return [main_file], [(folder, dest)]

    def append_note(self, task_id: str, text: str) -> tuple[list[Path], list[tuple[Path, Path]]]:
        target = self.find(task_id)
        if not target or not target.path:
            raise TaskError(f"Task [{task_id}] not found in backlog")

        file_path = target.path
        content, le, bom, tail = read_text_preserving(file_path)
        lines = split_lines_exact(content[: len(content) - len(tail)] if tail else content) if content else []
        today = datetime.date.today().isoformat()
        entry_append_note(lines, text, today, h_prefix="##")
        write_text_preserving(file_path, lines, le, bom, tail=tail)
        return [file_path], []


# ---------------------------------------------------------------------------
# Layout Factory & Legacy helpers
# ---------------------------------------------------------------------------


def get_layout(settings: Any) -> BaseLayout:
    """Instantiate the layout class for the configured layout."""
    if settings.layout == "single":
        return SingleFileLayout(settings.backlog_file)
    elif settings.layout == "split":
        return SplitFilesLayout(settings.backlog_dir)
    elif settings.layout == "folders":
        return ItemFoldersLayout(settings.backlog_dir)
    else:
        raise TaskError(f"Unsupported layout '{settings.layout}'")


def locate_section(lines: list[str], heading_pattern: str) -> int | None:
    """Legacy helper: find line index of section heading matching pattern."""
    regex = re.compile(heading_pattern, re.IGNORECASE)
    for i, line in enumerate(lines):
        if line.startswith("## ") and regex.search(line):
            return i
    return None


def find_task_span(lines: list[str], task_id: str) -> tuple[int, int] | None:
    """Legacy helper: find [start, end) line range for task entry."""
    for s, e, tid, _ in parse_markdown_entries(lines):
        if id_matches(tid, task_id):
            return s, e
    return None
