from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from . import frontmatter
from .errors import UsageError

@dataclass
class InboxTicket:
    id: str
    type: str
    category: str
    summary: str
    details: str
    project: str
    created: str
    priority: str = "P2"
    status: str = "open"
    item: str | None = None
    resolution: str | None = None
    file_path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "category": self.category,
            "item": self.item,
            "summary": self.summary,
            "details": self.details,
            "project": self.project,
            "created": self.created,
            "priority": self.priority,
            "status": self.status,
            "resolution": self.resolution,
            "file_path": str(self.file_path) if self.file_path else None
        }

def generate_ticket_id(prefix: str, slug: str, existing_ids: set[str], date_str: str | None = None) -> str:
    if date_str is None:
        date_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d")
    
    clean_slug = re.sub(r'[^a-z0-9]+', '-', slug.lower()).strip('-')
    clean_slug = clean_slug[:50].rstrip('-')
    if not clean_slug:
        clean_slug = "ticket"
        
    base_id = f"{prefix}-{date_str}-{clean_slug}"
    candidate = base_id
    counter = 2
    
    while candidate in existing_ids:
        candidate = f"{base_id}-{counter}"
        counter += 1
        
    return candidate

def _write_ticket(file_path: Path, ticket: InboxTicket) -> None:
    data = {
        "id": ticket.id,
        "type": ticket.type,
        "category": ticket.category,
        "item": ticket.item,
        "project": ticket.project,
        "created": ticket.created,
        "status": ticket.status,
        "priority": ticket.priority,
        "summary": ticket.summary
    }
    
    fm = yaml.safe_dump(data, sort_keys=False).strip()
    
    lines = [
        "---",
        fm,
        "---",
        "",
        f"# {ticket.summary}",
        "",
        "## Context / Why",
        ticket.details.strip() if ticket.details else "",
        "",
        "## Resolution Notes"
    ]
    if ticket.resolution:
        lines.append(ticket.resolution.strip())
    else:
        lines.append("")
        
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

def create_ticket(warehouse_root: Path, type: str, category: str, summary: str, details: str = "", item: str | None = None, project: str = "", priority: str = "P2", date_str: str | None = None) -> InboxTicket:
    inbox_dir = warehouse_root / "_inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    
    existing_ids = {p.stem for p in inbox_dir.glob("*.md")}
    
    if date_str is None:
        now = datetime.datetime.now(datetime.timezone.utc)
        d_str = now.strftime("%Y%m%d")
        created = now.strftime("%Y-%m-%dT%H:%M:%S")
    else:
        d_str = date_str[:10].replace("-", "") if "-" in date_str else date_str[:8]
        created = date_str
        
    prefix = "REQ" if type == "request" else "ISS"
    ticket_id = generate_ticket_id(prefix, summary, existing_ids, d_str)
    
    ticket = InboxTicket(
        id=ticket_id,
        type=type,
        category=category,
        item=item,
        summary=summary,
        details=details,
        project=project,
        created=created,
        priority=priority,
        status="open",
        resolution=None,
        file_path=inbox_dir / f"{ticket_id}.md"
    )
    
    _write_ticket(ticket.file_path, ticket)
    return ticket

def _parse_ticket_file(path: Path) -> InboxTicket | None:
    text = path.read_text(encoding="utf-8")
    try:
        fm = frontmatter.parse(text)
    except UsageError:
        return None
        
    if "id" not in fm or "type" not in fm:
        return None
        
    _, body = frontmatter.split(text)
    
    details = ""
    resolution = None
    
    body = body.strip()
    
    context_match = re.search(r'## Context / Why\n(.*?)(\n##|$)', body, re.DOTALL)
    if context_match:
        details = context_match.group(1).strip()
        
    resolution_match = re.search(r'## Resolution Notes\n(.*)', body, re.DOTALL)
    if resolution_match:
        res = resolution_match.group(1).strip()
        if res:
            resolution = res
            
    return InboxTicket(
        id=fm.get("id", path.stem),
        type=fm.get("type", ""),
        category=fm.get("category", ""),
        summary=fm.get("summary", ""),
        details=details,
        project=fm.get("project", ""),
        created=fm.get("created", ""),
        priority=fm.get("priority", "P2"),
        status=fm.get("status", "open"),
        item=fm.get("item"),
        resolution=resolution,
        file_path=path
    )

def list_tickets(warehouse_root: Path, status: str | None = None, ticket_type: str | None = None) -> list[InboxTicket]:
    inbox_dir = warehouse_root / "_inbox"
    if not inbox_dir.exists():
        return []
        
    tickets = []
    for p in inbox_dir.glob("*.md"):
        if p.name == "README.md":
            continue
        ticket = _parse_ticket_file(p)
        if ticket:
            if status and ticket.status != status and status != "all":
                continue
            if ticket_type and ticket.type != ticket_type:
                continue
            tickets.append(ticket)
            
    tickets.sort(key=lambda t: t.created, reverse=True)
    return tickets

def get_ticket(warehouse_root: Path, ticket_id: str) -> InboxTicket | None:
    if not ticket_id or Path(ticket_id).name != ticket_id or ".." in ticket_id:
        return None
    p = warehouse_root / "_inbox" / f"{ticket_id}.md"
    if p.exists():
        return _parse_ticket_file(p)
    return None

def update_ticket_status(warehouse_root: Path, ticket_id: str, new_status: str, message: str | None = None) -> InboxTicket:
    ticket = get_ticket(warehouse_root, ticket_id)
    if not ticket:
        raise UsageError(f"Ticket not found: {ticket_id}")
        
    ticket.status = new_status
    if message:
        if ticket.resolution:
            ticket.resolution += f"\n\n{message}"
        else:
            ticket.resolution = message
            
    _write_ticket(ticket.file_path, ticket)
    return ticket

OPEN_MARKER = "## 📌 Backlog (Open Tasks)"

NEW_BACKLOG = """# Warehouse Backlog

> **How this backlog is run** (`convention/backlog`)
> - **Layout:** single file
> - **IDs:** imported from `_inbox/` tickets (`[REQ-…]`, `[ISS-…]`). Never reused.
> - **Entry style:** full
> - **Writes:** by hand, one writer at a time. `warehouse inbox triage <id>` adds the entry for a ticket.
> - **Extra fields:** `**Project**` and `**Item**`, after `**Created**`.

## 📋 In Progress

## 📌 Backlog (Open Tasks)

## ✅ Completed

## 🧊 Icebox (Not Doing / Rejected)
"""

_ENTRY = re.compile(r"^### \[([^\]]+)\]")
_PRIORITY = re.compile(r"\*\*Priority\*\*:\s*`P(\d)`")


def _priority_rank(priority: str | None) -> int:
    m = re.fullmatch(r"P(\d)", priority or "")
    return int(m.group(1)) if m else 2


def _entry_lines(ticket: InboxTicket) -> list[str]:
    lines = [
        f"### [{ticket.id}] {ticket.summary}",
        f"- **Status**: `Open` | **Priority**: `{ticket.priority}` | **Labels**: `{ticket.category.title()}`, `Inbox`",
        f"- **Created**: {ticket.created[:10]}",
    ]
    if ticket.project:
        lines.append(f"- **Project**: {ticket.project}")
    if ticket.item:
        lines.append(f"- **Item**: {ticket.item}")
    lines += [
        "",
        "#### Why",
        ticket.details or ticket.summary,
        "",
        "#### Wanted",
        f"Address {ticket.type} submitted via warehouse inbox.",
        "",
        "#### Acceptance Criteria",
        f"- [ ] #1 Investigate and resolve {ticket.id}.",
        "- [ ] #2 Verify and release fix if applicable.",
        "",
        "#### Outcome",
        "(Filled on completion.)",
    ]
    return lines


def _insert_by_priority(content: str, entry: list[str], priority: str) -> str:
    """Insert after the last open task of the same or higher priority (convention/backlog §4.3)."""
    lines = content.split("\n")
    if OPEN_MARKER not in lines:
        return content.rstrip("\n") + "\n\n" + OPEN_MARKER + "\n\n" + "\n".join(entry) + "\n"
    start = lines.index(OPEN_MARKER)
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    starts = [i for i in range(start + 1, end) if _ENTRY.match(lines[i])]

    rank = _priority_rank(priority)
    at = starts[0] if starts else end
    for n, s in enumerate(starts):
        e = starts[n + 1] if n + 1 < len(starts) else end
        m = next((m for m in map(_PRIORITY.search, lines[s:e]) if m), None)
        if m is None or int(m.group(1)) <= rank:
            at = e

    # Back up over trailing blank lines so the entry sits right after the previous one.
    while at > start + 1 and lines[at - 1].strip() == "":
        at -= 1
    block = [""] + entry
    if at >= len(lines) or lines[at].strip() != "":
        block.append("")  # keep one blank line before whatever follows
    return "\n".join(lines[:at] + block + lines[at:])


def triage_to_backlog(warehouse_root: Path, ticket_id: str) -> tuple[InboxTicket, str]:
    ticket = get_ticket(warehouse_root, ticket_id)
    if not ticket:
        raise UsageError(f"Ticket not found: {ticket_id}")

    if ticket.status != "open":
        raise UsageError(f"Ticket {ticket_id} is not open (status: {ticket.status})")

    backlog_path = warehouse_root / "BACKLOG.md"
    if not backlog_path.exists():
        backlog_path.write_text(NEW_BACKLOG, encoding="utf-8")

    content = backlog_path.read_text(encoding="utf-8")
    content = _insert_by_priority(content, _entry_lines(ticket), ticket.priority)
    backlog_path.write_text(content, encoding="utf-8")

    updated_ticket = update_ticket_status(warehouse_root, ticket_id, "triaged", "Triaged to BACKLOG.md")

    return updated_ticket, ticket_id


def backlog_section(warehouse_root: Path, ticket_id: str) -> str | None:
    """The `## ` heading of the BACKLOG.md section holding the ticket's entry, or None."""
    backlog_path = warehouse_root / "BACKLOG.md"
    if not backlog_path.exists():
        return None
    section = None
    for line in backlog_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
        elif line.startswith(f"### [{ticket_id}]"):
            return section
    return None


def close_ticket(warehouse_root: Path, ticket_id: str, new_status: str, message: str | None = None) -> InboxTicket:
    """Resolve or reject a ticket, but only once its backlog entry has been closed.

    Every ticket goes through BACKLOG.md: a resolved ticket's entry must be under
    Completed, a rejected ticket's under the Icebox.
    """
    wanted = {"resolved": "Completed", "rejected": "Icebox"}[new_status]
    if not get_ticket(warehouse_root, ticket_id):
        raise UsageError(f"Ticket not found: {ticket_id}")
    section = backlog_section(warehouse_root, ticket_id)
    if section is None:
        raise UsageError(
            f"Ticket {ticket_id} has no entry in BACKLOG.md. Triage it first "
            f"(warehouse inbox triage {ticket_id}), and move the entry to {wanted} when it is done."
        )
    if wanted not in section:
        raise UsageError(
            f"The BACKLOG.md entry for {ticket_id} is under '{section}'. "
            f"Move it to {wanted}, with its Outcome, before marking the ticket {new_status}."
        )
    return update_ticket_status(warehouse_root, ticket_id, new_status, message)
