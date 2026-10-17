"""Command handlers for backlog CLI."""

from __future__ import annotations

import argparse
import datetime
import re
import subprocess
from pathlib import Path

from backlog_cli import TaskError
from backlog_cli.gitops import (
    BRANCH_PREFIX,
    CFG_ROOT,
    STALE_DAYS,
    MergeLock,
    branch_created_at,
    branch_exists,
    branch_last_activity,
    claim_branches,
    content_dirt,
    days_since,
    force_rmtree,
    git,
    git_dir,
    repo_root,
    staged_differs,
    worktree_list,
    write_atomic,
)
from backlog_cli.ids import find_next_id
from backlog_cli.layouts import PRIORITY_LEVELS, find_task_span, locate_section
from backlog_cli.settings import load_settings


def cmd_doctor(args: argparse.Namespace) -> int:
    """Check or initialize repository configuration and hooks."""
    cwd = Path.cwd()
    root = repo_root(cwd)
    problems: list[str] = []
    notes: list[str] = []

    if args.init:
        # Decision 6: doctor --init no longer writes backlog.file
        wroot = (root.parent / "worktrees").resolve()
        git("config", CFG_ROOT, str(wroot).replace("\\", "/"), cwd=root)
        wroot.mkdir(parents=True, exist_ok=True)
        notes.append(f"Configured {CFG_ROOT} = {wroot}")

    settings = load_settings(root)

    # Report layout
    notes.append(f"layout: {settings.layout} ({settings.sources['layout']})")

    # Backlog file or folder
    if settings.layout == "single":
        if settings.backlog_file.is_file():
            notes.append(f"backlog file: {settings.backlog_file} ({settings.sources['backlog_file']})")
        else:
            problems.append(
                f"Backlog file not found at {settings.backlog_file} ({settings.sources['backlog_file']}). Create one or run doctor --init."
            )
    else:  # split or folders
        if settings.backlog_dir.is_dir():
            notes.append(f"backlog folder: {settings.backlog_dir} ({settings.sources['backlog_dir']})")
        else:
            problems.append(
                f"Backlog folder not found at {settings.backlog_dir} ({settings.sources['backlog_dir']})."
            )

    # Worktree root
    if settings.worktree_root.is_dir():
        notes.append(f"worktree root: {settings.worktree_root} ({settings.sources['worktree_root']})")
    else:
        notes.append(
            f"worktree root: {settings.worktree_root} ({settings.sources['worktree_root']}) (does not exist yet)"
        )

    # Base branch
    notes.append(f"base branch: {settings.base_branch} ({settings.sources['base_branch']})")

    # Lock file check
    lock_file = git_dir(root) / "merge.lock"
    if lock_file.is_file():
        problems.append(f"Dangling merge.lock found at {lock_file}")

    for n in notes:
        print(f"  ok    {n}")
    for p in problems:
        print(f"  WARN  {p}")

    if not problems:
        print("  ok    setup is healthy and ready")
        return 0
    return 1


def cmd_status(args: argparse.Namespace) -> int:
    """Inspect active claims across git branch refs."""
    cwd = Path.cwd()
    root = repo_root(cwd)
    settings = load_settings(root)
    base = settings.base_branch
    trees = worktree_list(root)
    tree_by_branch = {t["branch"]: t for t in trees}

    claims = claim_branches(root)
    if not claims:
        print("No live claims in this repository.")
        return 0

    print(f"Live task claims ({len(claims)}):")
    for branch in claims:
        task_id = branch[len(BRANCH_PREFIX) :]
        created = branch_created_at(branch, cwd=root)
        active, ahead = branch_last_activity(branch, base, cwd=root)
        idle = days_since(active or created)
        stale_flag = " [STALE]" if idle and idle > STALE_DAYS else ""
        idle_str = f"idle={idle:.1f}d" if idle is not None else "idle=?"
        wt = tree_by_branch.get(branch, {}).get("path", "(no worktree attached)")

        print(f"  * {task_id:<12} (branch: {branch}) commits={ahead} {idle_str}{stale_flag}")
        print(f"      path: {wt}")

    return 0


def cmd_open(args: argparse.Namespace) -> int:
    """Create a new backlog item and allocate next ID."""
    cwd = Path.cwd()
    root = repo_root(cwd)
    settings = load_settings(root)
    if settings.layout != "single":
        raise TaskError(f"layout '{settings.layout}' is not supported yet")
    bpath = settings.backlog_file
    if not bpath.is_file():
        raise TaskError(f"Backlog file does not exist at {bpath}")

    prefix = args.prefix or "TASK"
    priority = args.priority.upper()
    if priority not in PRIORITY_LEVELS:
        raise TaskError(f"Invalid priority {priority!r}. Must be one of {PRIORITY_LEVELS}")

    text = bpath.read_text(encoding="utf-8")
    task_id = find_next_id(prefix, text)
    today = datetime.date.today().isoformat()

    entry_lines = [
        f"### [{task_id}] {args.title.strip()}",
        f"- **Status**: `Open` | **Priority**: `{priority}` | **Labels**: `{args.labels or 'Task'}`",
        f"- **Created**: {today}",
        "",
        "#### Why",
        args.why or "Task objective and background context.",
        "",
        "#### Wanted",
        args.wanted or "Desired outcome and deliverables.",
        "",
        "#### Acceptance Criteria",
        "- [ ] #1 Implementation complete and verified.",
        "",
        "#### Outcome",
        "- (Pending completion)",
        "",
    ]

    lines = text.splitlines()
    loc = locate_section(lines, r"Backlog|Open Tasks")
    if loc is None:
        # Fallback: append before Completed or at end
        loc = locate_section(lines, r"Completed")
        if loc is None:
            lines.extend(["", "## 📌 Backlog (Open Tasks)", ""])
            loc = len(lines) - 1

    # Insert under backlog section
    insert_at = loc + 1
    while insert_at < len(lines) and (not lines[insert_at].strip() or lines[insert_at].startswith("<!--")):
        insert_at += 1

    lines[insert_at:insert_at] = [""] + entry_lines
    write_atomic(bpath, "\n".join(lines).rstrip() + "\n")
    try:
        rel_bpath = bpath.relative_to(root).as_posix()
        git("add", rel_bpath, cwd=root)
        git("commit", "-m", f"{task_id}: open — {args.title.strip()}", cwd=root)
    except Exception:
        pass
    print(f"Created backlog item [{task_id}]: {args.title}")

    if args.claim:
        return cmd_claim(argparse.Namespace(id=task_id, backlog_path=str(bpath)))
    return 0


def cmd_claim(args: argparse.Namespace) -> int:
    """Atomically claim a task and provision its worktree."""
    cwd = Path.cwd()
    root = repo_root(cwd)
    custom_backlog = getattr(args, "backlog_path", None)
    settings = load_settings(root, backlog_path=custom_backlog)
    if settings.layout != "single":
        raise TaskError(f"layout '{settings.layout}' is not supported yet")
    bpath = settings.backlog_file
    task_id = args.id.lstrip("#")
    branch = f"{BRANCH_PREFIX}{task_id}"

    if branch_exists(branch, cwd=root):
        raise TaskError(f"Task [{task_id}] is already claimed: branch {branch} exists.")

    wroot = settings.worktree_root
    wroot.mkdir(parents=True, exist_ok=True)
    target_dir = (wroot / task_id).resolve()

    if target_dir.exists():
        raise TaskError(f"Directory {target_dir} already exists on disk but has no claim branch.")

    # Atomic step: create branch and worktree
    try:
        git("worktree", "add", str(target_dir), "-b", branch, cwd=root)
    except TaskError as exc:
        raise TaskError(f"Could not create worktree for [{task_id}]:\n{exc}")

    # Update status inside worktree
    try:
        wt_bpath = target_dir / bpath.relative_to(root)
        if wt_bpath.is_file():
            content = wt_bpath.read_text(encoding="utf-8")
            lines = content.splitlines()
            span = find_task_span(lines, task_id)
            if span:
                start, end = span
                block = lines[start:end]
                # Update status
                for idx, bl in enumerate(block):
                    if "**Status**:" in bl:
                        block[idx] = re.sub(r"`Open`", "`In Progress`", bl)
                # Move to In Progress section if present
                in_prog_idx = locate_section(lines, r"In Progress")
                if in_prog_idx is not None:
                    del lines[start:end]
                    ins = in_prog_idx + 1
                    while ins < len(lines) and (not lines[ins].strip() or lines[ins].startswith("<!--")):
                        ins += 1
                    lines[ins:ins] = [""] + block
                else:
                    lines[start:end] = block
                write_atomic(wt_bpath, "\n".join(lines).rstrip() + "\n")
                git("add", str(wt_bpath), cwd=target_dir)
                git("commit", "-m", f"{task_id}: claim", "--no-verify", cwd=target_dir)
    except Exception:
        # Roll back on error
        git("worktree", "remove", "--force", str(target_dir), cwd=root, check=False)
        git("branch", "-D", branch, cwd=root, check=False)
        raise

    print(f"Claimed [{task_id}]:")
    print(f"  Branch:   {branch}")
    print(f"  Worktree: {target_dir}")
    print(f"\nWork in the worktree path above. To complete:\n  python task.py close {task_id} --outcome 'Summary'")
    return 0


def cmd_adopt(args: argparse.Namespace) -> int:
    """Locate the worktree path of an existing claim."""
    cwd = Path.cwd()
    root = repo_root(cwd)
    settings = load_settings(root)
    task_id = args.id.lstrip("#")
    branch = f"{BRANCH_PREFIX}{task_id}"

    if not branch_exists(branch, cwd=root):
        raise TaskError(f"Task [{task_id}] is not claimed (branch {branch} does not exist).")

    for t in worktree_list(root):
        if t["branch"] == branch:
            print(f"Existing worktree for [{task_id}]:\n{t['path']}")
            return 0

    wroot = settings.worktree_root
    recreated = (wroot / task_id).resolve()
    raise TaskError(
        f"Branch {branch} exists but has no active worktree.\n"
        f"Recreate it with: git worktree add {recreated} {branch}"
    )


def cmd_close(args: argparse.Namespace) -> int:
    """Record completion, gate, merge to base branch, and tear down worktree."""
    cwd = Path.cwd()
    root = repo_root(cwd)
    settings = load_settings(root)
    if settings.layout != "single":
        raise TaskError(f"layout '{settings.layout}' is not supported yet")
    base = settings.base_branch
    task_id = args.id.lstrip("#")
    branch = f"{BRANCH_PREFIX}{task_id}"

    if not branch_exists(branch, cwd=root):
        raise TaskError(f"Task [{task_id}] is not claimed (branch {branch} does not exist).")

    # Locate worktree
    wt_path = None
    for t in worktree_list(root):
        if t["branch"] == branch:
            wt_path = Path(t["path"])
            break

    if not wt_path or not wt_path.is_dir():
        raise TaskError(f"Worktree for [{task_id}] not found. Run adopt first.")

    # Guard against uncommitted work in worktree
    dirt = content_dirt(wt_path, worktree_root=settings.worktree_root)
    if dirt:
        raise TaskError(
            f"Worktree {wt_path} contains uncommitted work:\n{dirt}\n"
            "Commit all changes inside the worktree before running close."
        )

    bpath_rel = settings.backlog_file.relative_to(root)
    wt_bpath = wt_path / bpath_rel

    today = datetime.date.today().isoformat()
    if wt_bpath.is_file():
        content = wt_bpath.read_text(encoding="utf-8")
        lines = content.splitlines()
        span = find_task_span(lines, task_id)
        if span:
            start, end = span
            block = lines[start:end]
            # Update status and outcome
            for idx, bl in enumerate(block):
                if "**Status**:" in bl:
                    block[idx] = re.sub(r"`In Progress`|`Open`", "`Closed`", bl)
                    if "**Resolved**:" not in block[idx]:
                        block[idx] += f" | **Resolved**: {today}"
                if "#### Outcome" in bl and idx + 1 < len(block):
                    block[idx + 1] = f"- {args.outcome.strip()} ({today})"

            # Move to Completed section
            comp_idx = locate_section(lines, r"Completed")
            if comp_idx is not None:
                del lines[start:end]
                # Append-only: find end of Completed section
                ins = comp_idx + 1
                while ins < len(lines) and not lines[ins].startswith("## "):
                    ins += 1
                lines[ins:ins] = [""] + block
            else:
                lines[start:end] = block
            write_atomic(wt_bpath, "\n".join(lines).rstrip() + "\n")
            git("add", str(wt_bpath), cwd=wt_path)
            if staged_differs(wt_path):
                git("commit", "-m", f"{task_id}: close — {args.outcome.strip()}", "--no-verify", cwd=wt_path)

    # Sync base branch into worktree
    merged = subprocess.run(
        ["git", "merge", base, "-m", f"{task_id}: sync with {base}"],
        cwd=str(wt_path),
        capture_output=True,
        text=True,
    )
    if merged.returncode != 0:
        raise TaskError(
            f"{base} does not merge cleanly into {branch}.\n"
            f"Resolve conflicts in {wt_path}, commit, and re-run close."
        )

    # Check for primary tree dirt
    main_dirt = content_dirt(root, worktree_root=settings.worktree_root)
    if main_dirt:
        raise TaskError(
            f"Primary tree {root} has uncommitted changes:\n{main_dirt}\n"
            "Commit them in the primary tree first. Never stash, as these may belong to another session."
        )

    # Atomic merge under lock
    lock_file = git_dir(root) / "merge.lock"
    with MergeLock(lock_file):
        git("merge", "--no-ff", branch, "-m", f"Merge {branch}: {args.outcome.strip()}", cwd=root)
        try:
            force_rmtree(wt_path)
            git("worktree", "prune", cwd=root, check=False)
        except Exception as exc:
            print(f"Warning: Merged, but could not remove worktree {wt_path}: {exc}")
        git("branch", "-d", branch, cwd=root)

    print(f"Successfully closed and merged [{task_id}] into {base}.")
    return 0


def cmd_abandon(args: argparse.Namespace) -> int:
    """Release a claim without merging."""
    cwd = Path.cwd()
    root = repo_root(cwd)
    settings = load_settings(root)
    task_id = args.id.lstrip("#")
    branch = f"{BRANCH_PREFIX}{task_id}"

    if not branch_exists(branch, cwd=root):
        raise TaskError(f"Task [{task_id}] is not claimed.")

    wt_path = None
    for t in worktree_list(root):
        if t["branch"] == branch:
            wt_path = Path(t["path"])
            break

    if wt_path and wt_path.is_dir():
        if not args.force:
            dirt = content_dirt(wt_path, worktree_root=settings.worktree_root)
            if dirt:
                raise TaskError(
                    f"Worktree {wt_path} contains uncommitted work:\n{dirt}\n"
                    "Pass --force to discard uncommitted changes."
                )
        force_rmtree(wt_path)
        git("worktree", "prune", cwd=root, check=False)

    git("branch", "-D", branch, cwd=root)
    print(f"Abandoned claim [{task_id}] (deleted branch {branch}).")
    return 0
