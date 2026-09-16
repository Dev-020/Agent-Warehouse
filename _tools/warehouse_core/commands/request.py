import json

from ..inbox import create_ticket
from ..errors import UsageError
from . import current_project

def run(ctx, args) -> int:
    try:
        proj, _ = current_project(ctx)
        project_name = proj.name if proj else ""
    except Exception:
        project_name = getattr(args, "project", "")
        
    ticket = create_ticket(
        warehouse_root=ctx.warehouse_root,
        type="request",
        category="new-item",
        summary=args.summary,
        details=getattr(args, "reason", "") or "",
        project=project_name,
        priority=args.priority
    )
    
    if ctx.json:
        print(json.dumps({"command": "request", "ticket": ticket.to_dict()}, indent=2))
    else:
        print(f"Request created: {ticket.id}")
    return 0
