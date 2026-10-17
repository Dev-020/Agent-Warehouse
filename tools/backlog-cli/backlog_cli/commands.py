"""Command handlers for backlog CLI."""

from __future__ import annotations

import argparse
import datetime
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable

from backlog_cli import TaskError
from backlog_cli.gitops import (
    BRANCH_PREFIX,
    CFG_ROOT,
    STALE_DAYS,
    MergeLock,
    Restorable,
    branch_created_at,
    branch_exists,
    branch_last_activity,
    check_no_git_dir_env,
    claim_branches,
    content_dirt,
    days_since,
    force_rmtree,
    git,
    git_dir,
    repo_root,
    worktree_list,
)
from backlog_cli.ids import allocate_id, collect_branch_ids
from backlog_cli.layouts import PRIORITY_LEVELS, get_layout
from backlog_cli.model import Item
from backlog_cli.settings import load_settings


def safe_commit(
    root: Path,
    message: str,
    pre_check_paths: list[Path],
    action_fn: Callable[[], list[Path]],
) -> None:
    """Safely execute action_fn and commit only the written paths adhering to Decision 17.

    Refuses if any path has uncommitted changes.
    Restores files and deletes newly created files if commit fails.
    """
    existing_paths = [p for p in pre_check_paths if p.exists()]
    dirt = content_dirt(root, *[str(p) for p in existing_paths])
    if dirt.strip():
        raise TaskError(f"Cannot modify backlog: uncommitted changes in target paths:\n{dirt}")

    with Restorable(existing_paths):
        paths_before = set(existing_paths)
        written_paths = action_fn()
        created_paths = [p for p in written_paths if p not in paths_before and p.exists()]

        try:
            rel_paths: list[str] = []
            for p in written_paths:
                try:
                    rel_paths.append(p.relative_to(root).as_posix())
                except ValueError:
                    rel_paths.append(str(p))
            for p in paths_before:
                if not p.exists():
                    try:
                        rel_paths.append(p.relative_to(root).as_posix())
                    except ValueError:
                        rel_paths.append(str(p))

            git("add", "--", *rel_paths, cwd=root)
            trailer = "Co-Authored-By: Gemini 3.8 Flash High (Antigravity) <noreply@google.com>"
            summary = message[:72]
            git("commit", "-m", summary, "-m", trailer, "--", *rel_paths, cwd=root)
        except Exception as exc:
            if rel_paths:
                git("reset", "-q", "--", *rel_paths, cwd=root, check=False)
            for p in created_paths:
                if p.exists():
                    if p.is_dir():
                        shutil.rmtree(p, ignore_errors=True)
                    else:
                        try:
                            p.unlink()
                        except OSError:
                            pass
            err_str = str(exc)
            if "git commit" in err_str or "git add" in err_str:
                raise TaskError(err_str)
            raise


def detect_git_discovery(root: Path) -> str:
    """Report how git was found adhering to Decision 26."""
    if "GIT_DIR" in os.environ or "GIT_WORK_TREE" in os.environ:
        return "GIT_DIR/GIT_WORK_TREE environment"
    dot_git = root / ".git"
    if dot_git.is_file():
        target = ""
        try:
            text = dot_git.read_text(encoding="utf-8").strip()
            if text.startswith("gitdir:"):
                target = text[len("gitdir:") :].strip()
        except OSError:
            pass
        if not target:
            try:
                target = git("rev-parse", "--git-dir", cwd=root, check=False)
            except Exception:
                pass
        return f".git pointer file -> {target}" if target else ".git pointer file"
    return ".git folder"


def cmd_doctor(args: argparse.Namespace) -> int:
    """Check or initialize repository configuration and hooks."""
    cwd = Path.cwd()
    problems: list[str] = []
    notes: list[str] = []
    warnings: list[str] = []

    try:
        root = repo_root(cwd)
    except TaskError as exc:
        problems.append(str(exc))
        for p in problems:
            print(f"  WARN  {p}")
        return 1

    # Report git detection (Decision 26)
    git_source = detect_git_discovery(root)
    notes.append(f"git: {git_source}")

    if args.init:
        # Decision 6: doctor --init no longer writes backlog.file
        wroot = (root.parent / "worktrees").resolve()
        git("config", CFG_ROOT, str(wroot).replace("\\", "/"), cwd=root)
        wroot.mkdir(parents=True, exist_ok=True)
        notes.append(f"Configured {CFG_ROOT} = {wroot}")

    settings = load_settings(root)

    # Report layout
    notes.append(f"layout: {settings.layout} ({settings.sources['layout']})")

    # Backlog file or folder (Decision 11)
    if settings.layout == "single":
        if settings.backlog_file.is_file():
            notes.append(f"backlog file: {settings.backlog_file} ({settings.sources['backlog_file']})")
        else:
            problems.append(
                f"Backlog file not found at {settings.backlog_file} ({settings.sources['backlog_file']}). Create one or run doctor --init."
            )
    elif settings.layout == "split":
        bdir = settings.backlog_dir
        hdr = bdir / "00_BACKLOG.md"
        opn = bdir / "Open.md"
        cls = bdir / "Closed.md"
        missing = [p for p in (hdr, opn, cls) if not p.is_file()]
        if not missing:
            notes.append(f"backlog folder: {settings.backlog_dir} ({settings.sources['backlog_dir']})")
        else:
            for p in missing:
                problems.append(f"Backlog file not found at {p} ({settings.sources['backlog_dir']}).")

        # Warn but don't fail if .gitattributes has no merge=union line for Closed.md
        gitattrs = root / ".gitattributes"
        has_union = False
        if gitattrs.is_file():
            text = gitattrs.read_text(encoding="utf-8")
            for line in text.splitlines():
                if "Closed.md" in line and "merge=union" in line:
                    has_union = True
                    break
        if not has_union:
            warnings.append(".gitattributes has no merge=union line for Closed.md")
    else:  # folders
        bdir = settings.backlog_dir
        hdr = bdir / "00_BACKLOG.md"
        opn = bdir / "open"
        cls = bdir / "closed"
        missing = []
        if not hdr.is_file():
            missing.append(hdr)
        if not opn.is_dir():
            missing.append(opn)
        if not cls.is_dir():
            missing.append(cls)
        if not missing:
            notes.append(f"backlog folder: {settings.backlog_dir} ({settings.sources['backlog_dir']})")
        else:
            for p in missing:
                problems.append(f"Backlog file or folder not found at {p} ({settings.sources['backlog_dir']}).")

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
    for w in warnings:
        print(f"  WARN  {w}")
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
    if args.claim:
        check_no_git_dir_env()
    cwd = Path.cwd()
    root = repo_root(cwd)
    trees = worktree_list(root)
    current_branch = git("branch", "--show-current", cwd=root, check=False).strip()

    is_secondary_worktree = False
    try:
        gd = git("rev-parse", "--git-dir", cwd=root, check=False)
        gcd = git("rev-parse", "--git-common-dir", cwd=root, check=False)
        if Path(gd).resolve() != Path(gcd).resolve():
            is_secondary_worktree = True
    except Exception:
        pass

    # Decision 16 (S9): Inside claim/* worktree, write and commit there; otherwise primary worktree
    if current_branch.startswith(BRANCH_PREFIX) or not is_secondary_worktree:
        target_root = root
    else:
        primary_candidate = Path(trees[0]["path"]).resolve() if trees else root
        if (primary_candidate / "objects").is_dir() and not (primary_candidate / ".git").exists():
            target_root = root
        else:
            target_root = primary_candidate

    settings = load_settings(target_root)
    layout = get_layout(settings)

    # Decision 14: Entry style from header or --style
    hdr = layout.header()
    header_style = "full"
    m_style = re.search(r"[-*]\s*\*\*Entry style:\*\*\s*(.+)", hdr, re.IGNORECASE)
    if m_style:
        s_val = m_style.group(1).strip().lower()
        if "compact" in s_val and "full" not in s_val:
            header_style = "compact"
    style = args.style or header_style

    criteria = args.criterion or []
    if style == "compact" and len(criteria) > 1:
        raise TaskError("compact style allows at most one --criterion ('Done when')")

    priority = args.priority.upper()
    if priority not in PRIORITY_LEVELS:
        raise TaskError(f"Invalid priority {priority!r}. Must be one of {PRIORITY_LEVELS}")

    # Decision 23 (D1): Collect every ID from target tree, base branch tip, and claim/* branches
    existing_ids = collect_branch_ids(root, target_root, settings)
    task_id = allocate_id(existing_ids, prefix=args.prefix, new_prefix=args.new_prefix)

    today = datetime.date.today().isoformat()
    fields: dict[str, Any] = {
        "created": today,
        "why": args.why.strip() if args.why else "",
        "wanted": args.wanted.strip() if args.wanted else "",
        "criteria": criteria,
    }
    if args.labels and args.labels != "Task":
        fields["labels"] = args.labels.strip()

    item = Item(
        id=task_id,
        title=args.title.strip(),
        status="Open",
        priority=priority,
        fields=fields,
    )

    commit_msg = f"chore(backlog): open [{task_id}] {args.title.strip()}"[:72]
    pre_paths = layout.paths_for()

    def do_add():
        return layout.add(item, style=style)

    safe_commit(target_root, commit_msg, pre_paths, do_add)
    print(f"Created backlog item [{task_id}]: {args.title.strip()}")

    if args.claim:
        return cmd_claim(argparse.Namespace(id=task_id, backlog_path=None))
    return 0


def cmd_claim(args: argparse.Namespace) -> int:
    """Atomically claim a task and provision its worktree."""
    check_no_git_dir_env()
    cwd = Path.cwd()
    root = repo_root(cwd)
    custom_backlog = getattr(args, "backlog_path", None)
    settings = load_settings(root, backlog_path=custom_backlog)
    layout = get_layout(settings)

    task_id = args.id.strip().strip("'\"").strip("[]")
    # Decision 18: Refuse before creating branch if not found or not Open
    item = layout.find(task_id)
    if not item:
        raise TaskError(f"Task [{task_id}] not found in backlog.")
    if item.status != "Open":
        raise TaskError(f"Task [{task_id}] has status '{item.status}', expected 'Open'.")

    clean_id = task_id.lstrip("#")
    branch = f"{BRANCH_PREFIX}{clean_id}"

    if branch_exists(branch, cwd=root):
        raise TaskError(f"Task [{task_id}] is already claimed: branch {branch} exists.")

    wroot = settings.worktree_root
    wroot.mkdir(parents=True, exist_ok=True)
    target_dir = (wroot / clean_id).resolve()

    if target_dir.exists():
        raise TaskError(f"Directory {target_dir} already exists on disk but has no claim branch.")

    try:
        git("worktree", "add", str(target_dir), "-b", branch, cwd=root)
    except TaskError as exc:
        raise TaskError(f"Could not create worktree for [{task_id}]:\n{exc}")

    try:
        wt_settings = load_settings(target_dir)
        wt_layout = get_layout(wt_settings)

        def do_claim():
            return wt_layout.set_status(task_id, "In Progress")

        summary = f"chore(backlog): claim [{task_id}]"[:72]
        safe_commit(target_dir, summary, wt_layout.paths_for(task_id), do_claim)
    except Exception:
        # Decision 25: remove worktree, delete branch only if it has no commits of its own
        try:
            git("worktree", "remove", "--force", str(target_dir), cwd=root)
        except Exception:
            force_rmtree(target_dir)
            git("worktree", "prune", cwd=root, check=False)
        base = settings.base_branch
        commits_ahead = git(
            "log",
            "--no-merges",
            "--format=%h",
            f"{base}..{branch}",
            cwd=root,
            check=False,
        ).splitlines()
        has_own_commits = any(c.strip() for c in commits_ahead)
        if not has_own_commits:
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
    task_id = args.id.strip().strip("'\"").strip("[]")
    clean_id = task_id.lstrip("#")
    branch = f"{BRANCH_PREFIX}{clean_id}"

    if not branch_exists(branch, cwd=root):
        raise TaskError(f"Task [{task_id}] is not claimed (branch {branch} does not exist).")

    for t in worktree_list(root):
        if t["branch"] == branch:
            print(f"Existing worktree for [{task_id}]:\n{t['path']}")
            return 0

    wroot = settings.worktree_root
    recreated = (wroot / clean_id).resolve()
    raise TaskError(
        f"Branch {branch} exists but has no active worktree.\n"
        f"Recreate it with: git worktree add {recreated} {branch}"
    )


def cmd_close(args: argparse.Namespace) -> int:
    """Record completion, gate, merge to base branch, and tear down worktree."""
    check_no_git_dir_env()
    cwd = Path.cwd()
    root = repo_root(cwd)
    settings = load_settings(root)
    base = settings.base_branch
    task_id = args.id.strip().strip("'\"").strip("[]")
    clean_id = task_id.lstrip("#")
    branch = f"{BRANCH_PREFIX}{clean_id}"

    if not branch_exists(branch, cwd=root):
        raise TaskError(f"Task [{task_id}] is not claimed (branch {branch} does not exist).")

    wt_path = None
    for t in worktree_list(root):
        if t["branch"] == branch:
            wt_path = Path(t["path"])
            break

    if not wt_path or not wt_path.is_dir():
        raise TaskError(f"Worktree for [{task_id}] not found. Run adopt first.")

    dirt = content_dirt(wt_path, worktree_root=settings.worktree_root)
    if dirt:
        raise TaskError(
            f"Worktree {wt_path} contains uncommitted work:\n{dirt}\n"
            "Commit all changes inside the worktree before running close."
        )

    wt_settings = load_settings(wt_path)
    wt_layout = get_layout(wt_settings)

    def do_close():
        return wt_layout.close(task_id, "Closed", args.outcome.strip())

    summary = f"chore(backlog): close [{task_id}]"[:72]
    safe_commit(wt_path, summary, wt_layout.paths_for(task_id), do_close)

    # Sync base branch into worktree
    merged = subprocess.run(
        ["git", "merge", base, "-m", f"{clean_id}: sync with {base}"],
        cwd=str(wt_path),
        capture_output=True,
        text=True,
    )
    if merged.returncode != 0:
        unmerged = git("ls-files", "-u", cwd=wt_path, check=False).strip()
        if unmerged:
            raise TaskError(
                f"{base} does not merge cleanly into {branch}.\n"
                f"Resolve conflicts in {wt_path}, commit, and re-run close."
            )
        git("merge", "--abort", cwd=wt_path, check=False)
        err = (merged.stderr or merged.stdout).strip()
        raise TaskError(f"Sync merge of {base} into {branch} failed:\n{err}")

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
        merge_res = subprocess.run(
            ["git", "merge", "--no-ff", branch, "-m", f"Merge {branch}: {args.outcome.strip()}"],
            cwd=str(root),
            capture_output=True,
            text=True,
        )
        if merge_res.returncode != 0:
            git("merge", "--abort", cwd=root, check=False)
            err = (merge_res.stderr or merge_res.stdout).strip()
            raise TaskError(f"Merge into {base} failed:\n{err}")

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
    check_no_git_dir_env()
    cwd = Path.cwd()
    root = repo_root(cwd)
    settings = load_settings(root)
    base = settings.base_branch
    task_id = args.id.strip().strip("'\"").strip("[]")
    clean_id = task_id.lstrip("#")
    branch = f"{BRANCH_PREFIX}{clean_id}"

    if not branch_exists(branch, cwd=root):
        raise TaskError(f"Task [{task_id}] is not claimed.")

    wt_path = None
    for t in worktree_list(root):
        if t["branch"] == branch:
            wt_path = Path(t["path"])
            break

    if not args.force:
        if wt_path and wt_path.is_dir():
            dirt = content_dirt(wt_path, worktree_root=settings.worktree_root)
            if dirt:
                raise TaskError(
                    f"Worktree {wt_path} contains uncommitted work:\n{dirt}\n"
                    "Pass --force to discard uncommitted changes."
                )

        log_out = git(
            "log",
            "--no-merges",
            "--format=%h %s",
            f"{base}..{branch}",
            cwd=root,
            check=False,
        )
        claim_subjects = {
            f"chore(backlog): claim [{task_id}]",
            f"chore(backlog): claim [#{clean_id}]",
            f"chore(backlog): claim [{clean_id}]",
        }
        remaining_commits: list[str] = []
        for line in log_out.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(" ", 1)
            subject = parts[1] if len(parts) > 1 else ""
            if subject in claim_subjects:
                continue
            remaining_commits.append(line)

        if remaining_commits:
            commits_list = "\n".join(f"  {c}" for c in remaining_commits)
            raise TaskError(
                f"Branch {branch} has commits not on {base}:\n{commits_list}\n"
                "Pass --force to abandon and delete the branch."
            )

    tip_hash = git("rev-parse", "--short", branch, cwd=root).strip()

    if args.force:
        print(f"Branch {branch} tip was {tip_hash}. To restore it:\n  git branch {branch} {tip_hash}")

    if wt_path and wt_path.is_dir():
        force_rmtree(wt_path)
        git("worktree", "prune", cwd=root, check=False)

    git("branch", "-D", branch, cwd=root)
    print(f"Abandoned claim [{task_id}] (deleted branch {branch}).")
    return 0
