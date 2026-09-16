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

def triage_to_backlog(warehouse_root: Path, ticket_id: str) -> tuple[InboxTicket, str]:
    ticket = get_ticket(warehouse_root, ticket_id)
    if not ticket:
        raise UsageError(f"Ticket not found: {ticket_id}")
        
    if ticket.status != "open":
        raise UsageError(f"Ticket {ticket_id} is not open (status: {ticket.status})")
        
    backlog_path = warehouse_root / "BACKLOG.md"
    
    if not backlog_path.exists():
        lines = [
            "# Warehouse Backlog",
            "",
            "## 📋 In Progress",
            "",
            "## 📌 Backlog (Open Tasks)",
            "",
            "## ✅ Completed",
            "",
            "## 🧊 Icebox",
            ""
        ]
        backlog_path.write_text("\n".join(lines), encoding="utf-8")
        
    content = backlog_path.read_text(encoding="utf-8")
    
    item_str = f"- **Item**: {ticket.item}" if ticket.item else ""
    if item_str:
        header_lines = f"- **Created**: {ticket.created[:10]}\n- **Project**: {ticket.project or 'N/A'}\n{item_str}"
    else:
        header_lines = f"- **Created**: {ticket.created[:10]}\n- **Project**: {ticket.project or 'N/A'}"
        
    task_text = f"### [{ticket_id}] {ticket.summary}\n"
    task_text += f"- **Status**: `Open` | **Priority**: `{ticket.priority}` | **Labels**: `{ticket.category.title()}`, `Inbox`\n"
    task_text += f"{header_lines}\n\n"
    task_text += "#### Why\n"
    task_text += f"{ticket.details or ticket.summary}\n\n"
    task_text += "#### Wanted\n"
    task_text += f"Address {ticket.type} submitted via warehouse inbox.\n\n"
    task_text += "#### Acceptance Criteria\n"
    task_text += f"- [ ] #1 Investigate and resolve {ticket_id}.\n"
    task_text += "- [ ] #2 Verify and release fix if applicable.\n"
    
    marker = "## 📌 Backlog (Open Tasks)"
    if marker not in content:
        content += f"\n{marker}\n\n{task_text}"
    else:
        parts = content.split(marker, 1)
        content = parts[0] + marker + "\n\n" + task_text + parts[1]
        
    backlog_path.write_text(content, encoding="utf-8")
    
    updated_ticket = update_ticket_status(warehouse_root, ticket_id, "triaged", "Triaged to BACKLOG.md")
    
    return updated_ticket, ticket_id
