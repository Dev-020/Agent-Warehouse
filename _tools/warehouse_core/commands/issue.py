import json
import sys

from ..inbox import create_ticket
from ..errors import UsageError
from . import current_project

def run(ctx, args) -> int:
    try:
        proj, _ = current_project(ctx)
        project_name = proj.name if proj else ""
    except Exception:
        project_name = getattr(args, "project", "")
        
    item_id = args.item_id
    if item_id not in ctx.catalog.all_ids():
        print(f"Warning: item '{item_id}' not found in catalog.", file=sys.stderr)
        
    ticket = create_ticket(
        warehouse_root=ctx.warehouse_root,
        type="issue",
        category=args.type,
        summary=args.summary,
        details=getattr(args, "details", "") or "",
        item=item_id,
        project=project_name,
        priority=args.priority
    )
    
    if ctx.json:
        print(json.dumps({"command": "issue", "ticket": ticket.to_dict()}, indent=2))
    else:
        print(f"Issue created: {ticket.id}")
    return 0
