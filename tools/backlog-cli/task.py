#!/usr/bin/env python3
"""CLI backlog manager with atomic git worktree claims, ID allocation, and structured sections.

Adheres to convention/backlog and protocol/worktree-claims.
Provides multi-agent concurrency control, atomic branch reservations (claim/<ID>),
conflict avoidance, and lifecycle transitions.

Usage:
    python task.py doctor [--init]
    python task.py status [--write]
    python task.py open "Task title" [--prefix INF] [--priority P2] [--claim]
    python task.py claim <ID>
    python task.py adopt <ID>
    python task.py close <ID> --outcome "Summary of implementation"
    python task.py abandon <ID> [--force]
"""

from __future__ import annotations

import argparse
import sys

from backlog_cli import TaskError
from backlog_cli.commands import (
    cmd_abandon,
    cmd_adopt,
    cmd_claim,
    cmd_close,
    cmd_doctor,
    cmd_open,
    cmd_status,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    # doctor
    p_doc = sub.add_parser("doctor", help="Check or initialize git and backlog settings")
    p_doc.add_argument("--init", action="store_true", help="Initialize git config defaults")
    p_doc.set_defaults(func=cmd_doctor)

    # status
    p_stat = sub.add_parser("status", help="List active claims across branch refs")
    p_stat.set_defaults(func=cmd_status)

    # open
    p_open = sub.add_parser("open", help="Create a new task entry in the backlog")
    p_open.add_argument("title", help="Task title")
    p_open.add_argument("--prefix", default="TASK", help="ID prefix (e.g. INF, TASK, #)")
    p_open.add_argument("--priority", default="P2", help="P1 | P2 | P3")
    p_open.add_argument("--labels", default="Task", help="Comma-separated labels")
    p_open.add_argument("--why", default="", help="Description of motivation")
    p_open.add_argument("--wanted", default="", help="Description of desired outcome")
    p_open.add_argument("--claim", action="store_true", help="Claim immediately after creation")
    p_open.set_defaults(func=cmd_open)

    # claim
    p_claim = sub.add_parser("claim", help="Claim a task and create an isolated worktree")
    p_claim.add_argument("id", help="Task ID to claim")
    p_claim.add_argument("--backlog-path", help="Path to backlog file")
    p_claim.set_defaults(func=cmd_claim)

    # adopt
    p_adopt = sub.add_parser("adopt", help="Locate worktree of an active claim")
    p_adopt.add_argument("id", help="Task ID")
    p_adopt.set_defaults(func=cmd_adopt)

    # close
    p_close = sub.add_parser("close", help="Record completion, gate, and merge task")
    p_close.add_argument("id", help="Task ID to close")
    p_close.add_argument("--outcome", required=True, help="One-line outcome summary")
    p_close.set_defaults(func=cmd_close)

    # abandon
    p_aban = sub.add_parser("abandon", help="Release claim without merging")
    p_aban.add_argument("id", help="Task ID")
    p_aban.add_argument("--force", action="store_true", help="Discard uncommitted changes")
    p_aban.set_defaults(func=cmd_abandon)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except TaskError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
