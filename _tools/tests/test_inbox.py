import pytest
import json
from pathlib import Path

from warehouse_core.inbox import (
    InboxTicket,
    generate_ticket_id,
    create_ticket,
    get_ticket,
    list_tickets,
    update_ticket_status,
    triage_to_backlog
)

def test_generate_ticket_id():
    existing = set()
    id1 = generate_ticket_id("REQ", "hello world", existing, "20260916")
    assert id1 == "REQ-20260916-hello-world"
    existing.add(id1)
    
    id2 = generate_ticket_id("REQ", "hello world", existing, "20260916")
    assert id2 == "REQ-20260916-hello-world-2"

def test_create_ticket(tmp_path):
    ticket = create_ticket(
        warehouse_root=tmp_path,
        type="request",
        category="new-item",
        summary="A test request",
        details="Need this tool",
        project="some-project",
        priority="P1",
        date_str="2026-09-16T13:45:00"
    )
    
    assert ticket.id == "REQ-20260916-a-test-request"
    assert ticket.type == "request"
    assert ticket.category == "new-item"
    assert ticket.summary == "A test request"
    assert ticket.details == "Need this tool"
    assert ticket.project == "some-project"
    assert ticket.priority == "P1"
    assert ticket.status == "open"
    assert ticket.item is None
    
    p = tmp_path / "_inbox" / f"{ticket.id}.md"
    assert p.exists()
    content = p.read_text(encoding="utf-8")
    assert "id: REQ-20260916-a-test-request" in content
    assert "type: request" in content
    assert "category: new-item" in content
    assert "## Context / Why" in content
    assert "Need this tool" in content

def test_get_ticket(tmp_path):
    created = create_ticket(tmp_path, "issue", "bug", "Broken item", item="tool-foo")
    ticket = get_ticket(tmp_path, created.id)
    assert ticket is not None
    assert ticket.id == created.id
    assert ticket.type == "issue"
    assert ticket.category == "bug"
    assert ticket.item == "tool-foo"

def test_list_tickets(tmp_path):
    create_ticket(tmp_path, "issue", "bug", "A bug")
    create_ticket(tmp_path, "request", "new-item", "A request")
    create_ticket(tmp_path, "issue", "typo", "A typo")
    
    tickets = list_tickets(tmp_path)
    assert len(tickets) == 3
    
    issues = list_tickets(tmp_path, ticket_type="issue")
    assert len(issues) == 2
    
    requests = list_tickets(tmp_path, ticket_type="request")
    assert len(requests) == 1

def test_update_ticket_status(tmp_path):
    ticket = create_ticket(tmp_path, "issue", "bug", "A bug")
    updated = update_ticket_status(tmp_path, ticket.id, "resolved", "Fixed in PR #123")
    
    assert updated.status == "resolved"
    assert updated.resolution == "Fixed in PR #123"
    
    t = get_ticket(tmp_path, ticket.id)
    assert t.status == "resolved"
    assert t.resolution == "Fixed in PR #123"

def test_triage_to_backlog(tmp_path):
    ticket = create_ticket(tmp_path, "issue", "bug", "Need fix", details="It is broken")
    updated, tid = triage_to_backlog(tmp_path, ticket.id)
    
    assert updated.status == "triaged"
    
    backlog = tmp_path / "BACKLOG.md"
    assert backlog.exists()
    content = backlog.read_text(encoding="utf-8")
    
    assert "## 📌 Backlog (Open Tasks)" in content
    assert f"### [{tid}] Need fix" in content
    assert "- **Status**: `Open`" in content
    assert "It is broken" in content

# CLI TESTS
def test_cli_request(wh):
    code, out = wh.run("request", "Need a tool", "--reason", "Because", "--priority", "P1")
    assert code == 0
    assert "Request created: REQ-" in out

def test_cli_issue(wh):
    code, out = wh.run("issue", "nonexistent-item", "--summary", "Buggy", "--type", "bug", "--details", "Fix it")
    assert code == 0
    assert "Issue created: ISS-" in out
    assert "Warning: item 'nonexistent-item' not found" in out

def test_cli_inbox_list(wh):
    wh.run("request", "Tool A")
    code, out = wh.run("inbox", "list")
    assert code == 0
    assert "Tool A" in out

def test_cli_inbox_show(wh):
    wh.run("request", "Tool B", "--reason", "Testing show")
    code, out = wh.run("inbox", "list", "--json")
    data = json.loads(out)
    tid = data["tickets"][0]["id"]
    
    code, out = wh.run("inbox", "show", tid)
    assert code == 0
    assert tid in out
    assert "Testing show" in out

def test_cli_inbox_resolve(wh):
    wh.run("request", "Tool C")
    code, out = wh.run("inbox", "list", "--json")
    data = json.loads(out)
    tid = data["tickets"][0]["id"]
    
    code, out = wh.run("inbox", "resolve", tid, "--message", "Done")
    assert code == 0
    
    code, out = wh.run("inbox", "show", tid)
    assert "Status: resolved" in out
    assert "Done" in out

def test_cli_inbox_reject(wh):
    wh.run("request", "Tool D")
    code, out = wh.run("inbox", "list", "--json")
    data = json.loads(out)
    tid = data["tickets"][0]["id"]
    
    code, out = wh.run("inbox", "reject", tid, "--reason", "No")
    assert code == 0
    
    code, out = wh.run("inbox", "show", tid)
    assert "Status: rejected" in out

def test_cli_inbox_triage(wh):
    wh.run("request", "Tool E")
    code, out = wh.run("inbox", "list", "--json")
    data = json.loads(out)
    tid = data["tickets"][0]["id"]
    
    code, out = wh.run("inbox", "triage", tid)
    assert code == 0
    
    backlog = wh.root / "BACKLOG.md"
    assert backlog.exists()
    assert tid in backlog.read_text(encoding="utf-8")
