# Agent Inbox & Feedback System

This directory (`_inbox/`) stores requests and issues filed against the AI Agent Warehouse. It serves as an intake queue for human and agent workflows to track bugs, requested features, enhancements, and typos safely without immediately polluting the backlog or modifying project code directly.

## Ticket Lifecycle

- **Open**: The ticket has been filed and awaits review.
- **Triaged**: The ticket has been reviewed and moved into the main `BACKLOG.md` for scheduling.
- **Resolved**: The ticket was addressed and fixed.
- **Rejected**: The ticket will not be addressed (with reasons provided).

These four are the only statuses. **Every ticket goes through `BACKLOG.md`:** triage it first, do the
work against its backlog entry, and move the entry to Completed (or to the Icebox, if rejected) with
its Outcome. Only then mark the ticket resolved or rejected. A ticket is never resolved straight from
the inbox, even when the fix is quick.

## Ticket Structure

Tickets are Markdown files named with an ID like `REQ-YYYYMMDD-slug.md` or `ISS-YYYYMMDD-slug.md`. They contain YAML frontmatter holding the ticket metadata and a markdown body detailing the context and resolution.

```markdown
---
id: REQ-20260916-new-feature
type: request
category: new-item
item: null
project: some-project
created: "2026-09-16T13:45:00"
status: open
priority: P2
summary: New feature request
---

# New feature request

## Context / Why
User requested a new feature to handle XYZ.

## Resolution Notes
```

## CLI Commands

You can manage the inbox using the `warehouse` CLI:
- `warehouse request <summary> [--reason <reason>]`
- `warehouse issue <item_id> --summary <summary> [--type bug|typo...]`
- `warehouse inbox list`
- `warehouse inbox show <ticket_id>`
- `warehouse inbox triage <ticket_id>`
- `warehouse inbox resolve <ticket_id> --message <msg>`
- `warehouse inbox reject <ticket_id> --reason <reason>`
