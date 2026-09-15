"""Command-line entry: argparse, global options, dispatch, exit codes."""
from __future__ import annotations

import argparse
import json
import sys

from . import TOOL_VERSION
from .commands import (add, check, impact, index_cmd, install_hook, pull, registry_cmd, release,
                       remove, status, sync, promote, discard, detach, template, bootstrap)
from .context import Context
from .errors import WarehouseError


def _globals(p: argparse.ArgumentParser, suppress: bool) -> None:
    d = argparse.SUPPRESS if suppress else None
    p.add_argument("--warehouse", default=d, help="warehouse root (default: from the tool's location)")
    p.add_argument("--config", default=d, help="config file (default: <warehouse>/warehouse.config.yml)")
    p.add_argument("--project", default=d, help="project directory (default: current directory)")
    p.add_argument("--json", action="store_true", default=argparse.SUPPRESS if suppress else False)
    p.add_argument("--verbose", action="store_true", default=argparse.SUPPRESS if suppress else False)
    p.add_argument("--today", default=d, help=argparse.SUPPRESS)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="warehouse", description="AI warehouse sync tool")
    parser.add_argument("--version", action="version", version=f"warehouse {TOOL_VERSION}")
    _globals(parser, suppress=False)
    sub = parser.add_subparsers(dest="command", required=True)

    def cmd(name, func, help_text):
        p = sub.add_parser(name, help=help_text)
        _globals(p, suppress=True)
        p.set_defaults(func=func)
        return p

    p = cmd("sync", sync.run, "propagate releases to projects")
    p.add_argument("--auto", action="store_true")
    p.add_argument("--if-new-tags", action="store_true")
    p.add_argument("--include-manual", action="store_true")
    p.add_argument("target_project", nargs="?", metavar="project")

    cmd("status", status.run, "current vs available versions for this project")

    p = cmd("pull", pull.run, "update items within their pins (--major to cross MAJOR)")
    p.add_argument("id", nargs="?")
    p.add_argument("--all", action="store_true")
    p.add_argument("--major", action="store_true")

    p = cmd("add", add.run, "add an item to the manifest and pull it")
    p.add_argument("spec", metavar="id[@pin]")
    p.add_argument("--major", action="store_true")

    p = cmd("remove", remove.run, "remove an item from the manifest and delete its copy")
    p.add_argument("id")
    p.add_argument("--prune", action="store_true")
    p.add_argument("--force", action="store_true")

    p = cmd("release", release.run, "release an item: changelog, version, commit, tag, sync")
    p.add_argument("id")
    p.add_argument("level", choices=["major", "minor", "patch", "initial"])
    p.add_argument("--no-sync", action="store_true")
    p.add_argument("--message")

    cmd("check", check.run, "read-only health report")

    p = cmd("impact", impact.run, "projects that use an item")
    p.add_argument("id")

    cmd("registry", registry_cmd.run, "regenerate _registry/projects.md")
    cmd("index", index_cmd.run, "regenerate 00_INDEX.md regions")

    p = cmd("install-hook", install_hook.run, "install the warehouse post-commit and post-merge hooks")
    p.add_argument("--force", action="store_true")

    p = cmd("promote", promote.run, "promote a drifted item back to the warehouse")
    p.add_argument("id")
    p.add_argument("--message")
    p.add_argument("--include-new", action="store_true")
    p.add_argument("--write-conflicts", action="store_true")

    p = cmd("discard", discard.run, "discard local drift or promoted state")
    p.add_argument("id")
    p.add_argument("--yes", action="store_true")
    p.add_argument("--pull", action="store_true")

    p = cmd("detach", detach.run, "remove an item from manifest/lock but keep it in the project")
    p.add_argument("id")
    p.add_argument("--force", action="store_true")

    p = cmd("template", template.run, "copy a template into the project")
    p.add_argument("id")
    p.add_argument("dest")
    p.add_argument("--set", action="append", default=[], help="name=value")

    p = cmd("bootstrap", bootstrap.run, "create a .warehouse.yml for an existing project")
    p.add_argument("--write", action="store_true")
    p.add_argument("--include-drafts", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code not in (0, None) else 0
    # sync's positional project
    args.project_positional = getattr(args, "target_project", None)
    try:
        ctx = Context(warehouse=args.warehouse, config=args.config, project=args.project, today=args.today,
                      json_out=args.json, verbose=args.verbose)
        if args.command == "sync":
            args.project = args.target_project
        return args.func(ctx, args)
    except WarehouseError as e:
        if getattr(args, "json", False):
            print(json.dumps({"command": args.command, "exit_code": e.code, "error": str(e)}))
        else:
            print(f"error: {e}", file=sys.stderr)
        return e.code
    except KeyboardInterrupt:
        return 130
