import json
import sys

from ..inbox import (
    list_tickets,
    get_ticket,
    close_ticket,
    triage_to_backlog
)
from ..errors import UsageError

def run_list(ctx, args):
    tickets = list_tickets(ctx.warehouse_root, getattr(args, "status", None), getattr(args, "type", None))
    if ctx.json:
        print(json.dumps({"command": "inbox list", "tickets": [t.to_dict() for t in tickets]}, indent=2))
        return 0
        
    if not tickets:
        print("No tickets found.")
        return 0
        
    id_w = max(max(len(t.id) for t in tickets), 24)
    print(f"{'ID':<{id_w}} | {'TYPE':<10} | {'STATUS':<10} | {'PRIORITY':<8} | {'SUMMARY'}")
    print("-" * (id_w + 40))
    for t in tickets:
        print(f"{t.id:<{id_w}} | {t.type:<10} | {t.status:<10} | {t.priority:<8} | {t.summary}")
    return 0

def run_show(ctx, args):
    ticket = get_ticket(ctx.warehouse_root, args.ticket_id)
    if not ticket:
        raise UsageError(f"Ticket not found: {args.ticket_id}")
        
    if ctx.json:
        print(json.dumps({"command": "inbox show", "ticket": ticket.to_dict()}, indent=2))
        return 0
        
    print(f"ID: {ticket.id}")
    print(f"Type: {ticket.type}")
    print(f"Category: {ticket.category}")
    print(f"Status: {ticket.status}")
    print(f"Priority: {ticket.priority}")
    print(f"Created: {ticket.created}")
    print(f"Project: {ticket.project}")
    if ticket.item:
        print(f"Item: {ticket.item}")
    print(f"Summary: {ticket.summary}")
    print(f"\nDetails:\n{ticket.details}")
    if ticket.resolution:
        print(f"\nResolution Notes:\n{ticket.resolution}")
    return 0

def run_resolve(ctx, args):
    ticket = close_ticket(ctx.warehouse_root, args.ticket_id, "resolved", getattr(args, "message", None))
    if ctx.json:
        print(json.dumps({"command": "inbox resolve", "ticket": ticket.to_dict()}, indent=2))
    else:
        print(f"Ticket {ticket.id} marked as resolved.")
    return 0

def run_reject(ctx, args):
    ticket = close_ticket(ctx.warehouse_root, args.ticket_id, "rejected", getattr(args, "reason", None))
    if ctx.json:
        print(json.dumps({"command": "inbox reject", "ticket": ticket.to_dict()}, indent=2))
    else:
        print(f"Ticket {ticket.id} marked as rejected.")
    return 0

def run_triage(ctx, args):
    ticket, _ = triage_to_backlog(ctx.warehouse_root, args.ticket_id)
    if ctx.json:
        print(json.dumps({"command": "inbox triage", "ticket": ticket.to_dict()}, indent=2))
    else:
        print(f"Ticket {ticket.id} triaged to backlog.")
    return 0

def run(ctx, args) -> int:
    action = args.inbox_action
    if action == "list":
        return run_list(ctx, args)
    elif action == "show":
        return run_show(ctx, args)
    elif action == "resolve":
        return run_resolve(ctx, args)
    elif action == "reject":
        return run_reject(ctx, args)
    elif action == "triage":
        return run_triage(ctx, args)
    else:
        raise UsageError(f"Unknown inbox action: {action}")
