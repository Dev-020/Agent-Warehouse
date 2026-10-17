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
    """Generate a slug from title: lowercase, non-alphanumerics to -, cut to at most 50 chars at -."""
    s = title.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if len(s) > 50:
        s = s[:50]
        if "-" in s:
            s = s.rsplit("-", 1)[0]
    return s


def read_text_preserving(path: Path) -> tuple[str, str, bool]:
    """Read file content and detect line ending (LF/CRLF) and UTF-8 BOM."""
    raw = path.read_bytes()
    has_bom = raw.startswith(b"\xef\xbb\xbf")
    line_ending = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8-sig")
    return text, line_ending, has_bom


def write_text_preserving(path: Path, text: str, line_ending: str, has_bom: bool) -> None:
    """Write text preserving original line ending and BOM."""
    # Normalize to desired line ending
    lines = text.splitlines()
    content = line_ending.join(lines) + line_ending
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
    """Map section names ('in progress', 'backlog', 'completed', 'icebox') to line spans."""
    in_code_block = False
    headings: list[tuple[int, str]] = []
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
            if norm:
                headings.append((i, norm))

    result: dict[str, tuple[int, int]] = {}
    for idx, (line_idx, norm) in enumerate(headings):
        next_idx = headings[idx + 1][0] if idx + 1 < len(headings) else len(lines)
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
                    m_lb = re.search(r"\*\*Labels\*\*:\s*`?([^`*]+)`?", p)
                    if m_lb:
                        fields["labels"] = m_lb.group(1).strip()
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
    labels_part = f" | **Labels**: `{item.fields['labels']}`" if item.fields.get("labels") else ""
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
    lines = text.splitlines(keepends=True)
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
                items = [x.strip().strip("'\"") for x in v[1:-1].split(",") if x.strip()]
                fields[k] = items
            elif (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                fields[k] = v[1:-1]
            else:
                fields[k] = v

    body = "".join(lines[end_idx + 1 :])
    raw_fm = "".join(lines[: end_idx + 1])
    return fields, body, raw_fm


def update_frontmatter(text: str, updates: dict[str, Any]) -> str:
    """Update frontmatter fields surgically. New fields go at the end before ---."""
    lines = text.splitlines(keepends=True)
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
            if matched == "id":
                new_fm_lines.append(f'id: "{val}"{le}')
            elif isinstance(val, list):
                new_fm_lines.append(f'{matched}: [{", ".join(str(x) for x in val)}]{le}')
            else:
                new_fm_lines.append(f"{matched}: {val}{le}")
        else:
            new_fm_lines.append(line)

    for k, val in remaining.items():
        if k == "id":
            new_fm_lines.append(f'id: "{val}"{le}')
        elif isinstance(val, list):
            new_fm_lines.append(f'{k}: [{", ".join(str(x) for x in val)}]{le}')
        else:
            new_fm_lines.append(f"{k}: {val}{le}")

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
    def add(self, item: Item, style: str = "full") -> list[Path]:
        pass

    @abstractmethod
    def set_status(self, task_id: str, status: str) -> list[Path]:
        pass

    @abstractmethod
    def close(self, task_id: str, status: str, outcome: str) -> list[Path]:
        pass

    @abstractmethod
    def append_note(self, task_id: str, text: str) -> list[Path]:
        pass

    @abstractmethod
    def header(self) -> str:
        pass

    @abstractmethod
    def paths_for(self, task_id: str | None = None) -> list[Path]:
        pass


# ---------------------------------------------------------------------------
# Single File Layout
# ---------------------------------------------------------------------------


class SingleFileLayout(BaseLayout):
    def __init__(self, backlog_file: Path):
        self.file = Path(backlog_file)

    def header(self) -> str:
        if not self.file.is_file():
            return ""
        text, _, _ = read_text_preserving(self.file)
        # Header is block between top of file and first ## section
        lines = text.splitlines()
        hdr_lines: list[str] = []
        for line in lines:
            if line.startswith("## "):
                break
            hdr_lines.append(line)
        return "\n".join(hdr_lines)

    def paths_for(self, task_id: str | None = None) -> list[Path]:
        return [self.file]

    def _load(self) -> tuple[list[str], str, bool, dict[str, tuple[int, int]]]:
        if not self.file.is_file():
            raise TaskError(f"Backlog file does not exist at {self.file}")
        text, le, bom = read_text_preserving(self.file)
        lines = text.splitlines()
        sections = find_sections(lines)
        for req in ("in progress", "backlog", "completed", "icebox"):
            if req not in sections:
                raise TaskError(f"Section '{req}' not found in {self.file}")
        return lines, le, bom, sections

    def items(self) -> list[Item]:
        if not self.file.is_file():
            return []
        lines, le, bom, _ = self._load()
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

    def add(self, item: Item, style: str = "full") -> list[Path]:
        lines, le, bom, sections = self._load()
        b_start, b_end = sections["backlog"]

        # Priority placement (Decision 15)
        new_rank = PRIORITY_RANK.get(item.priority, 2)
        entries = parse_markdown_entries(lines)
        backlog_entries = [
            (s, e, item_from_entry_lines(lines[s:e])) for s, e, _, _ in entries if s >= b_start and e <= b_end
        ]

        same_prio = [e for e in backlog_entries if PRIORITY_RANK.get(e[2].priority, 2) == new_rank]
        lower_prio = [e for e in backlog_entries if PRIORITY_RANK.get(e[2].priority, 2) > new_rank]

        if same_prio:
            ins = same_prio[-1][1]
        elif lower_prio:
            ins = lower_prio[0][0]
        else:
            ins = b_end
            while ins > b_start + 1 and not lines[ins - 1].strip():
                ins -= 1

        entry_lines = render_entry_lines(item, style=style, h_prefix="###")
        # Ensure clean spacing around entry
        to_insert = [""] + entry_lines if ins > 0 and lines[ins - 1].strip() else entry_lines
        lines[ins:ins] = to_insert

        write_text_preserving(self.file, "\n".join(lines), le, bom)
        return [self.file]

    def set_status(self, task_id: str, status: str) -> list[Path]:
        lines, le, bom, sections = self._load()
        target = self.find(task_id)
        if not target or not target.span:
            raise TaskError(f"Task [{task_id}] not found in {self.file}")

        start, end = target.span
        entry_lines = list(lines[start:end])
        del lines[start:end]

        today = datetime.date.today().isoformat()
        # Update status line
        for i, l in enumerate(entry_lines):
            if l.startswith("- **Status**:"):
                entry_lines[i] = re.sub(r"`(Open|In Progress|Closed|Rejected|Cancelled)`", f"`{status}`", l)
                break

        if status in ("Rejected", "Cancelled"):
            # Add Resolved metadata line if not present
            has_resolved = any(l.startswith("- **Resolved**:") for l in entry_lines)
            if not has_resolved:
                for idx in range(len(entry_lines) - 1, -1, -1):
                    if entry_lines[idx].startswith("- **"):
                        entry_lines.insert(idx + 1, f"- **Resolved**: {today}")
                        break

        # Re-parse sections after deletion
        sections = find_sections(lines)
        if status == "In Progress":
            target_sec = "in progress"
        elif status in ("Rejected", "Cancelled"):
            target_sec = "icebox"
        elif status == "Closed":
            target_sec = "completed"
        else:
            target_sec = "backlog"

        sec_start, sec_end = sections[target_sec]
        ins = sec_end
        while ins > sec_start + 1 and not lines[ins - 1].strip():
            ins -= 1

        to_insert = [""] + entry_lines if ins > 0 and lines[ins - 1].strip() else entry_lines
        lines[ins:ins] = to_insert

        write_text_preserving(self.file, "\n".join(lines), le, bom)
        return [self.file]

    def close(self, task_id: str, status: str, outcome: str) -> list[Path]:
        lines, le, bom, sections = self._load()
        target = self.find(task_id)
        if not target or not target.span:
            raise TaskError(f"Task [{task_id}] not found in {self.file}")

        start, end = target.span
        entry_lines = list(lines[start:end])
        del lines[start:end]

        today = datetime.date.today().isoformat()
        # 1. Status: Closed
        for i, l in enumerate(entry_lines):
            if l.startswith("- **Status**:"):
                entry_lines[i] = re.sub(r"`(Open|In Progress|Closed)`", f"`{status}`", l)
                break

        # 2. Resolved line (Decision 19 / D5)
        has_resolved = False
        last_meta_idx = -1
        for i, l in enumerate(entry_lines):
            if l.startswith("- **"):
                last_meta_idx = i
            if l.startswith("- **Resolved**:"):
                has_resolved = True
                entry_lines[i] = f"- **Resolved**: {today}"
                break
        if not has_resolved and last_meta_idx != -1:
            entry_lines.insert(last_meta_idx + 1, f"- **Resolved**: {today}")

        # 3. Outcome (Decision 19)
        outcome_idx = None
        for i, l in enumerate(entry_lines):
            if l.strip() == "#### Outcome":
                outcome_idx = i
                break

        if outcome_idx is not None:
            # Full style
            # If placeholder in parentheses, replace it; otherwise add paragraph below
            next_idx = outcome_idx + 1
            while next_idx < len(entry_lines) and not entry_lines[next_idx].strip():
                next_idx += 1
            if next_idx < len(entry_lines) and re.match(r"^\s*\(.*\)\s*$", entry_lines[next_idx]):
                entry_lines[next_idx] = outcome
            else:
                entry_lines.append("")
                entry_lines.append(outcome)
        else:
            # Compact style: add *Outcome (<date>):* <text> at end
            entry_lines.append("")
            entry_lines.append(f"*Outcome ({today}):* {outcome}")

        # 4. Move to bottom of Completed section
        sections = find_sections(lines)
        c_start, c_end = sections["completed"]
        ins = c_end
        while ins > c_start + 1 and not lines[ins - 1].strip():
            ins -= 1

        to_insert = [""] + entry_lines if ins > 0 and lines[ins - 1].strip() else entry_lines
        lines[ins:ins] = to_insert

        write_text_preserving(self.file, "\n".join(lines), le, bom)
        return [self.file]

    def append_note(self, task_id: str, text: str) -> list[Path]:
        lines, le, bom, sections = self._load()
        target = self.find(task_id)
        if not target or not target.span:
            raise TaskError(f"Task [{task_id}] not found in {self.file}")

        start, end = target.span
        entry_lines = list(lines[start:end])
        today = datetime.date.today().isoformat()
        note_line = f"- {today}: {text}"

        is_full = any(l.strip().startswith("#### ") for l in entry_lines)
        if is_full:
            notes_idx = None
            outcome_idx = None
            for i, l in enumerate(entry_lines):
                if l.strip() == "#### Notes":
                    notes_idx = i
                if l.strip() == "#### Outcome":
                    outcome_idx = i

            if notes_idx is not None:
                # Append under #### Notes
                ins = notes_idx + 1
                while ins < len(entry_lines) and not entry_lines[ins].strip().startswith("#### "):
                    ins += 1
                entry_lines.insert(ins, note_line)
            else:
                # Create #### Notes just before #### Outcome or at end
                insert_before = outcome_idx if outcome_idx is not None else len(entry_lines)
                entry_lines[insert_before:insert_before] = ["#### Notes", note_line, ""]
        else:
            # Compact: add at end of prose before *Wanted:*
            wanted_idx = None
            for i, l in enumerate(entry_lines):
                if l.strip().startswith("*Wanted:*"):
                    wanted_idx = i
                    break
            if wanted_idx is not None:
                entry_lines.insert(wanted_idx, note_line)
                entry_lines.insert(wanted_idx + 1, "")
            else:
                entry_lines.append(note_line)

        lines[start:end] = entry_lines
        write_text_preserving(self.file, "\n".join(lines), le, bom)
        return [self.file]


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
        text, _, _ = read_text_preserving(self.header_file)
        return text

    def paths_for(self, task_id: str | None = None) -> list[Path]:
        return [self.open_file, self.closed_file]

    def _load_open(self) -> tuple[list[str], str, bool, dict[str, tuple[int, int]]]:
        if not self.open_file.is_file():
            raise TaskError(f"Backlog file does not exist at {self.open_file}")
        text, le, bom = read_text_preserving(self.open_file)
        lines = text.splitlines()
        sections = find_sections(lines)
        for req in ("in progress", "backlog"):
            if req not in sections:
                raise TaskError(f"Section '{req}' not found in {self.open_file}")
        return lines, le, bom, sections

    def _load_closed(self) -> tuple[list[str], str, bool, dict[str, tuple[int, int]]]:
        if not self.closed_file.is_file():
            raise TaskError(f"Backlog file does not exist at {self.closed_file}")
        text, le, bom = read_text_preserving(self.closed_file)
        lines = text.splitlines()
        sections = find_sections(lines)
        for req in ("completed", "icebox"):
            if req not in sections:
                raise TaskError(f"Section '{req}' not found in {self.closed_file}")
        return lines, le, bom, sections

    def items(self) -> list[Item]:
        res: list[Item] = []
        if self.open_file.is_file():
            lines, le, bom, _ = self._load_open()
            for s, e, _, _ in parse_markdown_entries(lines):
                res.append(item_from_entry_lines(lines[s:e], self.open_file, (s, e), line_ending=le))
        if self.closed_file.is_file():
            lines, le, bom, _ = self._load_closed()
            for s, e, _, _ in parse_markdown_entries(lines):
                res.append(item_from_entry_lines(lines[s:e], self.closed_file, (s, e), line_ending=le))
        return res

    def find(self, task_id: str) -> Item | None:
        for it in self.items():
            if id_matches(it.id, task_id):
                return it
        return None

    def add(self, item: Item, style: str = "full") -> list[Path]:
        lines, le, bom, sections = self._load_open()
        b_start, b_end = sections["backlog"]

        new_rank = PRIORITY_RANK.get(item.priority, 2)
        entries = parse_markdown_entries(lines)
        backlog_entries = [
            (s, e, item_from_entry_lines(lines[s:e])) for s, e, _, _ in entries if s >= b_start and e <= b_end
        ]

        same_prio = [e for e in backlog_entries if PRIORITY_RANK.get(e[2].priority, 2) == new_rank]
        lower_prio = [e for e in backlog_entries if PRIORITY_RANK.get(e[2].priority, 2) > new_rank]

        if same_prio:
            ins = same_prio[-1][1]
        elif lower_prio:
            ins = lower_prio[0][0]
        else:
            ins = b_end
            while ins > b_start + 1 and not lines[ins - 1].strip():
                ins -= 1

        entry_lines = render_entry_lines(item, style=style, h_prefix="###")
        to_insert = [""] + entry_lines if ins > 0 and lines[ins - 1].strip() else entry_lines
        lines[ins:ins] = to_insert

        write_text_preserving(self.open_file, "\n".join(lines), le, bom)
        return [self.open_file]

    def set_status(self, task_id: str, status: str) -> list[Path]:
        target = self.find(task_id)
        if not target or not target.span or not target.path:
            raise TaskError(f"Task [{task_id}] not found in backlog")

        if target.path == self.open_file and status in ("Open", "In Progress"):
            lines, le, bom, sections = self._load_open()
            start, end = target.span
            entry_lines = list(lines[start:end])
            del lines[start:end]

            for i, l in enumerate(entry_lines):
                if l.startswith("- **Status**:"):
                    entry_lines[i] = re.sub(r"`(Open|In Progress)`", f"`{status}`", l)
                    break

            sections = find_sections(lines)
            target_sec = "in progress" if status == "In Progress" else "backlog"
            sec_start, sec_end = sections[target_sec]
            ins = sec_end
            while ins > sec_start + 1 and not lines[ins - 1].strip():
                ins -= 1

            to_insert = [""] + entry_lines if ins > 0 and lines[ins - 1].strip() else entry_lines
            lines[ins:ins] = to_insert

            write_text_preserving(self.open_file, "\n".join(lines), le, bom)
            return [self.open_file]

        # Moving from Open.md to Closed.md (Icebox / Completed)
        open_lines, o_le, o_bom, _ = self._load_open()
        closed_lines, c_le, c_bom, _ = self._load_closed()

        start, end = target.span
        entry_lines = list(open_lines[start:end])
        del open_lines[start:end]

        today = datetime.date.today().isoformat()
        for i, l in enumerate(entry_lines):
            if l.startswith("- **Status**:"):
                entry_lines[i] = re.sub(r"`(Open|In Progress)`", f"`{status}`", l)
                break

        has_resolved = any(l.startswith("- **Resolved**:") for l in entry_lines)
        if not has_resolved:
            for idx in range(len(entry_lines) - 1, -1, -1):
                if entry_lines[idx].startswith("- **"):
                    entry_lines.insert(idx + 1, f"- **Resolved**: {today}")
                    break

        c_sections = find_sections(closed_lines)
        target_sec = "completed" if status == "Closed" else "icebox"
        sec_start, sec_end = c_sections[target_sec]
        ins = sec_end
        while ins > sec_start + 1 and not closed_lines[ins - 1].strip():
            ins -= 1

        to_insert = [""] + entry_lines if ins > 0 and closed_lines[ins - 1].strip() else entry_lines
        closed_lines[ins:ins] = to_insert

        write_text_preserving(self.open_file, "\n".join(open_lines), o_le, o_bom)
        write_text_preserving(self.closed_file, "\n".join(closed_lines), c_le, c_bom)
        return [self.open_file, self.closed_file]

    def close(self, task_id: str, status: str, outcome: str) -> list[Path]:
        target = self.find(task_id)
        if not target or not target.span or not target.path:
            raise TaskError(f"Task [{task_id}] not found in backlog")

        open_lines, o_le, o_bom, _ = self._load_open()
        closed_lines, c_le, c_bom, _ = self._load_closed()

        start, end = target.span
        entry_lines = list(open_lines[start:end])
        del open_lines[start:end]

        today = datetime.date.today().isoformat()
        for i, l in enumerate(entry_lines):
            if l.startswith("- **Status**:"):
                entry_lines[i] = re.sub(r"`(Open|In Progress)`", f"`{status}`", l)
                break

        has_resolved = False
        last_meta_idx = -1
        for i, l in enumerate(entry_lines):
            if l.startswith("- **"):
                last_meta_idx = i
            if l.startswith("- **Resolved**:"):
                has_resolved = True
                entry_lines[i] = f"- **Resolved**: {today}"
                break
        if not has_resolved and last_meta_idx != -1:
            entry_lines.insert(last_meta_idx + 1, f"- **Resolved**: {today}")

        outcome_idx = None
        for i, l in enumerate(entry_lines):
            if l.strip() == "#### Outcome":
                outcome_idx = i
                break

        if outcome_idx is not None:
            next_idx = outcome_idx + 1
            while next_idx < len(entry_lines) and not entry_lines[next_idx].strip():
                next_idx += 1
            if next_idx < len(entry_lines) and re.match(r"^\s*\(.*\)\s*$", entry_lines[next_idx]):
                entry_lines[next_idx] = outcome
            else:
                entry_lines.append("")
                entry_lines.append(outcome)
        else:
            entry_lines.append("")
            entry_lines.append(f"*Outcome ({today}):* {outcome}")

        c_sections = find_sections(closed_lines)
        c_start, c_end = c_sections["completed"]
        ins = c_end
        while ins > c_start + 1 and not closed_lines[ins - 1].strip():
            ins -= 1

        to_insert = [""] + entry_lines if ins > 0 and closed_lines[ins - 1].strip() else entry_lines
        closed_lines[ins:ins] = to_insert

        write_text_preserving(self.open_file, "\n".join(open_lines), o_le, o_bom)
        write_text_preserving(self.closed_file, "\n".join(closed_lines), c_le, c_bom)
        return [self.open_file, self.closed_file]

    def append_note(self, task_id: str, text: str) -> list[Path]:
        target = self.find(task_id)
        if not target or not target.span or not target.path:
            raise TaskError(f"Task [{task_id}] not found in backlog")

        target_file = target.path
        text_content, le, bom = read_text_preserving(target_file)
        lines = text_content.splitlines()
        start, end = target.span
        entry_lines = list(lines[start:end])
        today = datetime.date.today().isoformat()
        note_line = f"- {today}: {text}"

        is_full = any(l.strip().startswith("#### ") for l in entry_lines)
        if is_full:
            notes_idx = None
            outcome_idx = None
            for i, l in enumerate(entry_lines):
                if l.strip() == "#### Notes":
                    notes_idx = i
                if l.strip() == "#### Outcome":
                    outcome_idx = i

            if notes_idx is not None:
                ins = notes_idx + 1
                while ins < len(entry_lines) and not entry_lines[ins].strip().startswith("#### "):
                    ins += 1
                entry_lines.insert(ins, note_line)
            else:
                insert_before = outcome_idx if outcome_idx is not None else len(entry_lines)
                entry_lines[insert_before:insert_before] = ["#### Notes", note_line, ""]
        else:
            wanted_idx = None
            for i, l in enumerate(entry_lines):
                if l.strip().startswith("*Wanted:*"):
                    wanted_idx = i
                    break
            if wanted_idx is not None:
                entry_lines.insert(wanted_idx, note_line)
                entry_lines.insert(wanted_idx + 1, "")
            else:
                entry_lines.append(note_line)

        lines[start:end] = entry_lines
        write_text_preserving(target_file, "\n".join(lines), le, bom)
        return [target_file]


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
        text, _, _ = read_text_preserving(self.header_file)
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
                    text, _, _ = read_text_preserving(file_to_read)
                    fields, body, _ = parse_frontmatter(text)
                    tid = str(fields.get("id", ""))
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
                text, _, _ = read_text_preserving(p)
                fields, body, _ = parse_frontmatter(text)
                tid = str(fields.get("id", ""))
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
        filename = f"{clean_id}-{slug}.md" if slug else f"{clean_id}.md"
        target_path = self.open_dir / filename

        today = item.fields.get("created") or datetime.date.today().isoformat()
        fm_lines = [
            "---",
            f'id: "{item.id}"',
            f"title: {item.title}",
            f"status: {item.status}",
            f"priority: {item.priority}",
        ]
        if item.fields.get("labels"):
            lbls = item.fields["labels"]
            if isinstance(lbls, list):
                fm_lines.append(f"labels: [{', '.join(lbls)}]")
            else:
                fm_lines.append(f"labels: [{lbls}]")
        fm_lines.append(f"created: {today}")
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
        return [target_path]

    def set_status(self, task_id: str, status: str) -> list[Path]:
        target = self.find(task_id)
        if not target or not target.path:
            raise TaskError(f"Task [{task_id}] not found in backlog")

        file_path = target.path
        text, le, bom = read_text_preserving(file_path)
        updates: dict[str, Any] = {"status": status}
        today = datetime.date.today().isoformat()
        if status in ("Rejected", "Cancelled"):
            updates["resolved"] = today

        new_text = update_frontmatter(text, updates)
        write_text_preserving(file_path, new_text, le, bom)

        if status in ("Rejected", "Cancelled") and self.open_dir in file_path.parents:
            # Move to closed/
            self.closed_dir.mkdir(parents=True, exist_ok=True)
            if file_path.parent == self.open_dir:
                dest = self.closed_dir / file_path.name
                shutil.move(str(file_path), str(dest))
                return [file_path, dest]
            else:
                folder = file_path.parent
                dest = self.closed_dir / folder.name
                shutil.move(str(folder), str(dest))
                return [folder, dest]

        return [file_path]

    def close(self, task_id: str, status: str, outcome: str) -> list[Path]:
        target = self.find(task_id)
        if not target or not target.path:
            raise TaskError(f"Task [{task_id}] not found in backlog")

        file_path = target.path
        text, le, bom = read_text_preserving(file_path)
        today = datetime.date.today().isoformat()

        # Update frontmatter: status and resolved
        updates = {"status": status, "resolved": today}
        text_with_fm = update_frontmatter(text, updates)

        # Update outcome in body
        lines = text_with_fm.splitlines()
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

        write_text_preserving(file_path, "\n".join(lines), le, bom)

        # Move to closed/
        self.closed_dir.mkdir(parents=True, exist_ok=True)
        if file_path.parent == self.open_dir:
            dest = self.closed_dir / file_path.name
            shutil.move(str(file_path), str(dest))
            return [file_path, dest]
        else:
            folder = file_path.parent
            dest = self.closed_dir / folder.name
            shutil.move(str(folder), str(dest))
            return [folder, dest]

    def append_note(self, task_id: str, text: str) -> list[Path]:
        target = self.find(task_id)
        if not target or not target.path:
            raise TaskError(f"Task [{task_id}] not found in backlog")

        file_path = target.path
        content, le, bom = read_text_preserving(file_path)
        lines = content.splitlines()
        today = datetime.date.today().isoformat()
        note_line = f"- {today}: {text}"

        is_full = any(l.strip().startswith("## ") for l in lines)
        if is_full:
            notes_idx = None
            outcome_idx = None
            for i, l in enumerate(lines):
                if l.strip() == "## Notes":
                    notes_idx = i
                if l.strip() == "## Outcome":
                    outcome_idx = i

            if notes_idx is not None:
                ins = notes_idx + 1
                while ins < len(lines) and not lines[ins].strip().startswith("## "):
                    ins += 1
                lines.insert(ins, note_line)
            else:
                insert_before = outcome_idx if outcome_idx is not None else len(lines)
                lines[insert_before:insert_before] = ["## Notes", note_line, ""]
        else:
            wanted_idx = None
            for i, l in enumerate(lines):
                if l.strip().startswith("*Wanted:*"):
                    wanted_idx = i
                    break
            if wanted_idx is not None:
                lines.insert(wanted_idx, note_line)
                lines.insert(wanted_idx + 1, "")
            else:
                lines.append(note_line)

        write_text_preserving(file_path, "\n".join(lines), le, bom)
        return [file_path]


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
