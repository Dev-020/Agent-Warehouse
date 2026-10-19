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
    git_ok,
    primary_tree,
    repo_root,
    worktree_list,
)
from backlog_cli.ids import allocate_id, collect_branch_ids, id_matches
from backlog_cli.layouts import (
    PRIORITY_LEVELS,
    SingleFileLayout,
    SplitFilesLayout,
    file_extract_entry,
    file_find_entry,
    file_insert_entry_at_bottom,
    file_insert_entry_by_priority,
    find_sections,
    get_layout,
    item_from_entry_lines,
    normalize_item_fields,
    parse_frontmatter,
    parse_markdown_entries,
    read_text_preserving,
    split_lines_exact,
    write_text_preserving,
)
from backlog_cli.model import Item
from backlog_cli.settings import load_settings


def find_item_on_branch(root: Path, branch: str, task_id: str, settings: Any) -> Item | None:
    """Read and find an item on a branch ref without checking it out (Decision 18, F4)."""
    layout_type = settings.layout
    if layout_type == "single":
        try:
            rel = settings.backlog_file.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            rel = settings.backlog_file.name
        proc = subprocess.run(
            ["git", "show", f"{branch}:{rel}"],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode != 0:
            return None
        lines = [l[:-1] if l.endswith("\r") else l for l in proc.stdout.split("\n")]
        res = file_find_entry(lines, task_id)
        return res[2] if res else None

    elif layout_type == "split":
        try:
            rel_dir = settings.backlog_dir.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            rel_dir = settings.backlog_dir.name
        proc = subprocess.run(
            ["git", "show", f"{branch}:{rel_dir}/Open.md"],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode == 0:
            lines = [l[:-1] if l.endswith("\r") else l for l in proc.stdout.split("\n")]
            res = file_find_entry(lines, task_id)
            if res:
                return res[2]
        proc_cls = subprocess.run(
            ["git", "show", f"{branch}:{rel_dir}/Closed.md"],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc_cls.returncode == 0:
            lines = [l[:-1] if l.endswith("\r") else l for l in proc_cls.stdout.split("\n")]
            res = file_find_entry(lines, task_id)
            if res:
                return res[2]
        return None

    elif layout_type == "folders":
        try:
            rel_dir = settings.backlog_dir.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            rel_dir = settings.backlog_dir.name
        proc_ls = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", branch, "--", f"{rel_dir}/open", f"{rel_dir}/closed"],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc_ls.returncode != 0:
            return None
        md_paths = [
            l.strip()
            for l in proc_ls.stdout.splitlines()
            if l.strip().endswith(".md") and not l.strip().endswith("00_BACKLOG.md")
        ]
        clean_id = task_id.lstrip("#").strip("[]")
        for md_path in md_paths:
            proc_show = subprocess.run(
                ["git", "show", f"{branch}:{md_path}"],
                cwd=str(root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if proc_show.returncode == 0:
                fields, body, _ = parse_frontmatter(proc_show.stdout)
                tid = str(fields.get("id", ""))
                if tid and id_matches(tid, task_id):
                    return Item(
                        id=tid,
                        title=str(fields.get("title", "")),
                        status=str(fields.get("status", "Open")),
                        priority=str(fields.get("priority", "P2")),
                        fields=fields,
                        body=body,
                        path=Path(md_path),
                    )
                elif not tid:
                    fname = Path(md_path).name
                    m = re.match(r"^(\d+|[A-Za-z]+-\d+)(?:-|\.md$|/|$)", fname)
                    if m:
                        val = f"#{m.group(1)}" if m.group(1).isdigit() else m.group(1)
                        if id_matches(val, task_id):
                            return Item(
                                id=val,
                                title=str(fields.get("title", fname)),
                                status=str(fields.get("status", "Open")),
                                priority=str(fields.get("priority", "P2")),
                                fields=fields,
                                body=body,
                                path=Path(md_path),
                            )
        return None


def find_all_items_on_branch(root: Path, branch: str, settings: Any) -> list[Item]:
    """Read all items on a branch ref without checking it out (Decision 39)."""
    layout_type = settings.layout
    items: list[Item] = []
    if layout_type == "single":
        try:
            rel = settings.backlog_file.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            rel = settings.backlog_file.name
        proc = subprocess.run(
            ["git", "show", f"{branch}:{rel}"],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode == 0 and proc.stdout:
            lines = split_lines_exact(proc.stdout)
            for s, e, tid, _ in parse_markdown_entries(lines):
                it = item_from_entry_lines(lines[s:e], settings.backlog_file)
                items.append(it)
        return items

    elif layout_type == "split":
        try:
            rel_dir = settings.backlog_dir.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            rel_dir = settings.backlog_dir.name
        for fname in ("Open.md", "Closed.md"):
            proc = subprocess.run(
                ["git", "show", f"{branch}:{rel_dir}/{fname}"],
                cwd=str(root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if proc.returncode == 0 and proc.stdout:
                lines = split_lines_exact(proc.stdout)
                for s, e, tid, _ in parse_markdown_entries(lines):
                    it = item_from_entry_lines(lines[s:e], settings.backlog_dir / fname)
                    items.append(it)
        return items

    elif layout_type == "folders":
        try:
            rel_dir = settings.backlog_dir.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            rel_dir = settings.backlog_dir.name
        proc_ls = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", branch, "--", f"{rel_dir}/open", f"{rel_dir}/closed"],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc_ls.returncode != 0:
            return items
        md_paths = [
            l.strip()
            for l in proc_ls.stdout.splitlines()
            if l.strip().endswith(".md") and not l.strip().endswith("00_BACKLOG.md")
        ]
        for md_path in md_paths:
            proc_show = subprocess.run(
                ["git", "show", f"{branch}:{md_path}"],
                cwd=str(root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if proc_show.returncode == 0 and proc_show.stdout:
                fields, body, _ = parse_frontmatter(proc_show.stdout)
                fields = normalize_item_fields(fields)
                tid = str(fields.get("id", "")).strip()
                if not tid:
                    fname = Path(md_path).stem
                    m = re.match(r"^(\d+|[A-Za-z]+-\d+)(?:-|\.md$|/|$)", fname)
                    if m:
                        tid = f"#{m.group(1)}" if m.group(1).isdigit() else m.group(1)
                items.append(
                    Item(
                        id=tid,
                        title=str(fields.get("title", "")),
                        status=str(fields.get("status", "Open")),
                        priority=str(fields.get("priority", "P2")),
                        fields=fields,
                        body=body,
                        raw=proc_show.stdout,
                        path=Path(md_path),
                    )
                )
        return items

    return items



def safe_commit(
    root: Path,
    message: str,
    pre_check_paths: list[Path],
    action_fn: Callable[[], list[Path] | tuple[list[Path], list[tuple[Path, Path]]]],
) -> None:
    """Safely execute action_fn and commit only the written paths adhering to Decision 17.

    Refuses if any path has uncommitted changes.
    Restores files and moves if commit fails (F3).
    """
    existing_paths = [p for p in pre_check_paths if p.exists()]
    dirt = content_dirt(root, *[str(p) for p in existing_paths])
    if dirt.strip():
        raise TaskError(f"Cannot modify backlog: uncommitted changes in target paths:\n{dirt}")

    with Restorable(existing_paths):
        paths_before = set(existing_paths)
        res = action_fn()
        if isinstance(res, tuple) and len(res) == 2 and isinstance(res[1], list):
            written_paths, moves = res
        else:
            written_paths, moves = res, []

        created_paths = [
            p
            for p in written_paths
            if p not in paths_before
            and p.exists()
            and not any(dest == p or dest in p.parents for _, dest in moves)
        ]

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
            for src, dest in moves:
                try:
                    rel_paths.append(src.relative_to(root).as_posix())
                except ValueError:
                    rel_paths.append(str(src))
                try:
                    rel_paths.append(dest.relative_to(root).as_posix())
                except ValueError:
                    rel_paths.append(str(dest))

            rel_paths = list(dict.fromkeys(rel_paths))

            git("add", "--", *rel_paths, cwd=root)
            summary = message[:72]
            # F14: no Co-Authored-By trailer in tool commits
            git("commit", "-m", summary, "--", *rel_paths, cwd=root)
        except Exception as exc:
            if rel_paths:
                git("reset", "-q", "--", *rel_paths, cwd=root, check=False)
            # F3: Move each destination back to its source first, then Restorable restores bytes
            for src, dest in reversed(moves):
                if dest.exists():
                    shutil.move(str(dest), str(src))
            for p in created_paths:
                if p.exists() and not any(src == p or src in p.parents for src, _ in moves):
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

    # Report main tree (Decision 27)
    try:
        main_t = primary_tree(root)
        notes.append(f"main tree: {main_t}")
    except TaskError:
        notes.append("main tree: unknown from here (run from the main tree)")


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
    if "\r" in args.title or "\n" in args.title:
        raise TaskError("title cannot contain newlines")

    if args.criterion:
        for c in args.criterion:
            if "\r" in c or "\n" in c:
                raise TaskError("--criterion cannot contain newlines")

    if getattr(args, "labels", None) and args.labels:
        if "\r" in args.labels or "\n" in args.labels:
            raise TaskError("--labels cannot contain newlines")

    if getattr(args, "why", None) and args.why:
        for line in args.why.splitlines():
            if line.strip().startswith("#"):
                raise TaskError("--why cannot contain lines starting with '#'")

    if getattr(args, "wanted", None) and args.wanted:
        for line in args.wanted.splitlines():
            if line.strip().startswith("#"):
                raise TaskError("--wanted cannot contain lines starting with '#'")

    if args.claim:
        check_no_git_dir_env()
    cwd = Path.cwd()
    root = repo_root(cwd)
    current_branch = git("branch", "--show-current", cwd=root, check=False).strip()

    # Decision 27 (S9): Inside claim/* worktree, write and commit there; otherwise primary_tree(root)
    if current_branch.startswith(BRANCH_PREFIX):
        target_root = root
    else:
        target_root = primary_tree(root)

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
    base = settings.base_branch

    # F5: check base branch exists at the start
    if not git_ok("show-ref", "--verify", "--quiet", f"refs/heads/{base}", cwd=root):
        raise TaskError(f"base branch '{base}' not found; set backlog.baseBranch")

    task_id = args.id.strip().strip("'\"").strip("[]")
    # F4 / Decision 18: Read item from <base> without checking out
    item = find_item_on_branch(root, base, task_id, settings)
    if not item:
        raise TaskError(f"Task [{task_id}] not found in backlog on branch '{base}'.")
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
        # F4: branch from <base>
        git("worktree", "add", str(target_dir), "-b", branch, base, cwd=root)
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
    # F15: quote task_id in hint
    print(f"\nWork in the worktree path above. To complete:\n  python task.py close '{task_id}' --outcome 'Summary'")
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


def resolve_sync_conflicts(wt_path: Path, task_id: str, base: str, branch: str, wt_settings: Any) -> None:
    """Resolve backlog-only conflicts during sync merge in close (Decisions 34, 35)."""
    if wt_settings.layout not in ("single", "split"):
        raise TaskError(
            f"{base} does not merge cleanly into {branch}.\n"
            f"Resolve conflicts in {wt_path}, commit, and re-run close."
        )

    conflicted_raw = git("diff", "--name-only", "--diff-filter=U", cwd=wt_path, check=False).splitlines()
    conflicted_paths = {p.strip().replace("\\", "/") for p in conflicted_raw if p.strip()}
    if not conflicted_paths:
        unmerged = git("ls-files", "-u", cwd=wt_path, check=False).strip()
        if unmerged:
            raise TaskError(
                f"{base} does not merge cleanly into {branch}.\n"
                f"Resolve conflicts in {wt_path}, commit, and re-run close."
            )
        return

    if wt_settings.layout == "single":
        rel_bf = wt_settings.backlog_file.resolve().relative_to(wt_path.resolve()).as_posix()
        allowed_paths = {rel_bf}
    else:
        rel_bd = wt_settings.backlog_dir.resolve().relative_to(wt_path.resolve()).as_posix()
        allowed_paths = {
            f"{rel_bd}/Open.md",
            f"{rel_bd}/Closed.md",
            f"{rel_bd}/00_BACKLOG.md",
        }

    if not conflicted_paths.issubset(allowed_paths):
        raise TaskError(
            f"{base} does not merge cleanly into {branch}.\n"
            f"Resolve conflicts in {wt_path}, commit, and re-run close."
        )

    mb_res = subprocess.run(
        ["git", "merge-base", "HEAD", "MERGE_HEAD"],
        cwd=str(wt_path),
        capture_output=True,
        text=True,
    )
    if mb_res.returncode != 0 or not mb_res.stdout.strip():
        raise TaskError(
            f"{base} does not merge cleanly into {branch}.\n"
            f"Resolve conflicts in {wt_path}, commit, and re-run close."
        )
    mb = mb_res.stdout.strip()

    def _norm_tid(tid: str) -> str:
        return tid.strip().strip("'\"").strip("[]").lstrip("#")

    def _clean_entry_lines(raw: list[str]) -> list[str]:
        lines = [l.rstrip("\r\n") for l in raw]
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        return lines

    def _read_entries_from_ref(ref: str) -> dict[str, tuple[str, list[str]]]:
        entries: dict[str, tuple[str, list[str]]] = {}
        if wt_settings.layout == "single":
            paths_to_read = [rel_bf]
        else:
            paths_to_read = [f"{rel_bd}/Open.md", f"{rel_bd}/Closed.md", f"{rel_bd}/00_BACKLOG.md"]

        for rel_p in paths_to_read:
            proc = subprocess.run(
                ["git", "show", f"{ref}:{rel_p}"],
                cwd=str(wt_path),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if proc.returncode == 0 and proc.stdout:
                lines = split_lines_exact(proc.stdout)
                for s, e, tid, _ in parse_markdown_entries(lines):
                    clean_lines = list(lines[s:e])
                    while clean_lines and not clean_lines[-1].strip():
                        clean_lines.pop()
                    entries[_norm_tid(tid)] = (tid, clean_lines)
        return entries

    head_entries = _read_entries_from_ref("HEAD")
    mb_entries = _read_entries_from_ref(mb)

    norm_task_id = _norm_tid(task_id)

    # Check if the branch changed any other entry (compare HEAD with merge base)
    for norm_id, (raw_tid, mb_lines) in mb_entries.items():
        if norm_id == norm_task_id:
            continue
        if norm_id not in head_entries:
            raise TaskError(
                f"Branch changed entry [{raw_tid}] not owned by claim [{task_id}].\n"
                f"Resolve conflicts in {wt_path}, commit, and re-run close."
            )
        _, head_lines = head_entries[norm_id]
        if _clean_entry_lines(mb_lines) != _clean_entry_lines(head_lines):
            raise TaskError(
                f"Branch changed entry [{raw_tid}] not owned by claim [{task_id}].\n"
                f"Resolve conflicts in {wt_path}, commit, and re-run close."
            )

    if norm_task_id not in head_entries:
        raise TaskError(f"Task [{task_id}] not found in HEAD of claim branch.")

    _, claimed_entry_lines = head_entries[norm_task_id]
    new_branch_items = [
        norm_id for norm_id in head_entries if norm_id != norm_task_id and norm_id not in mb_entries
    ]

    # Start each conflicted file from the base branch's version (MERGE_HEAD)
    for p in conflicted_paths:
        git("checkout", "MERGE_HEAD", "--", p, cwd=wt_path, check=True)

    if wt_settings.layout == "single":
        text, le, bom, tail = read_text_preserving(wt_settings.backlog_file)
        lines = split_lines_exact(text[: len(text) - len(tail)] if tail else text) if text else []

        if file_find_entry(lines, task_id):
            file_extract_entry(lines, task_id)

        claimed_item = item_from_entry_lines(claimed_entry_lines)
        sections = find_sections(lines)
        if claimed_item.status == "In Progress":
            file_insert_entry_at_bottom(lines, sections, claimed_entry_lines, "in progress")
        elif claimed_item.status == "Open":
            file_insert_entry_by_priority(lines, sections, claimed_entry_lines)
        elif claimed_item.status in ("Rejected", "Cancelled"):
            file_insert_entry_at_bottom(lines, sections, claimed_entry_lines, "icebox")
        elif claimed_item.status == "Closed":
            file_insert_entry_at_bottom(lines, sections, claimed_entry_lines, "completed")

        for norm_id in new_branch_items:
            _, new_lines = head_entries[norm_id]
            new_item = item_from_entry_lines(new_lines)
            sections = find_sections(lines)
            if new_item.status == "Open":
                file_insert_entry_by_priority(lines, sections, new_lines)
            elif new_item.status == "In Progress":
                file_insert_entry_at_bottom(lines, sections, new_lines, "in progress")
            elif new_item.status in ("Rejected", "Cancelled"):
                file_insert_entry_at_bottom(lines, sections, new_lines, "icebox")
            elif new_item.status == "Closed":
                file_insert_entry_at_bottom(lines, sections, new_lines, "completed")

        write_text_preserving(wt_settings.backlog_file, lines, le, bom, tail=tail)
        git("add", "--", rel_bf, cwd=wt_path, check=True)

    else:
        open_file = wt_settings.backlog_dir / "Open.md"
        closed_file = wt_settings.backlog_dir / "Closed.md"

        o_text, o_le, o_bom, o_tail = read_text_preserving(open_file)
        open_lines = split_lines_exact(o_text[: len(o_text) - len(o_tail)] if o_tail else o_text) if o_text else []
        c_text, c_le, c_bom, c_tail = read_text_preserving(closed_file)
        closed_lines = split_lines_exact(c_text[: len(c_text) - len(c_tail)] if c_tail else c_text) if c_text else []

        if file_find_entry(open_lines, task_id):
            file_extract_entry(open_lines, task_id)
        if file_find_entry(closed_lines, task_id):
            file_extract_entry(closed_lines, task_id)

        claimed_item = item_from_entry_lines(claimed_entry_lines)
        if claimed_item.status in ("In Progress", "Open"):
            open_sections = find_sections(open_lines)
            if claimed_item.status == "In Progress":
                file_insert_entry_at_bottom(open_lines, open_sections, claimed_entry_lines, "in progress")
            else:
                file_insert_entry_by_priority(open_lines, open_sections, claimed_entry_lines)
        else:
            closed_sections = find_sections(closed_lines)
            target_sec = "completed" if claimed_item.status == "Closed" else "icebox"
            file_insert_entry_at_bottom(closed_lines, closed_sections, claimed_entry_lines, target_sec)

        for norm_id in new_branch_items:
            _, new_lines = head_entries[norm_id]
            new_item = item_from_entry_lines(new_lines)
            if new_item.status in ("In Progress", "Open"):
                open_sections = find_sections(open_lines)
                if new_item.status == "Open":
                    file_insert_entry_by_priority(open_lines, open_sections, new_lines)
                else:
                    file_insert_entry_at_bottom(open_lines, open_sections, new_lines, "in progress")
            else:
                closed_sections = find_sections(closed_lines)
                target_sec = "completed" if new_item.status == "Closed" else "icebox"
                file_insert_entry_at_bottom(closed_lines, closed_sections, new_lines, target_sec)

        write_text_preserving(open_file, open_lines, o_le, o_bom, tail=o_tail)
        write_text_preserving(closed_file, closed_lines, c_le, c_bom, tail=c_tail)
        git("add", "--", f"{rel_bd}/Open.md", f"{rel_bd}/Closed.md", cwd=wt_path, check=True)
        if f"{rel_bd}/00_BACKLOG.md" in conflicted_paths:
            git("add", "--", f"{rel_bd}/00_BACKLOG.md", cwd=wt_path, check=True)

    # Finish the merge commit
    proc = subprocess.run(["git", "commit", "--no-edit"], cwd=str(wt_path), capture_output=True, text=True)
    if proc.returncode != 0:
        git("merge", "--abort", cwd=wt_path, check=False)
        err = (proc.stderr or proc.stdout).strip()
        raise TaskError(f"Merge commit failed:\n{err}")


def cmd_close(args: argparse.Namespace) -> int:
    """Record completion, gate, merge to base branch, and tear down worktree."""
    check_no_git_dir_env()
    outcome = args.outcome.strip() if getattr(args, "outcome", None) else ""
    if not outcome:
        raise TaskError("--outcome is required")
    if "\r" in args.outcome or "\n" in args.outcome:
        raise TaskError("--outcome cannot contain newlines")

    cwd = Path.cwd()
    root = repo_root(cwd)
    settings = load_settings(root)
    base = settings.base_branch
    task_id = args.id.strip().strip("'\"").strip("[]")
    clean_id = task_id.lstrip("#")
    branch = f"{BRANCH_PREFIX}{clean_id}"

    # F5: check base branch exists at the start
    if not git_ok("show-ref", "--verify", "--quiet", f"refs/heads/{base}", cwd=root):
        raise TaskError(f"base branch '{base}' not found; set backlog.baseBranch")

    # Decision 27 / F9: Primary tree must be found via primary_tree(root) and be on base branch
    primary_path = primary_tree(root)
    primary_branch = git("branch", "--show-current", cwd=primary_path, check=False).strip()
    if primary_branch != base:
        raise TaskError(f"Primary tree {primary_path} is on branch '{primary_branch}', expected base branch '{base}'.")
    trees = worktree_list(root)

    if not branch_exists(branch, cwd=root):
        raise TaskError(f"Task [{task_id}] is not claimed (branch {branch} does not exist).")

    wt_path = None
    for t in trees:
        if t["branch"] == branch:
            wt_path = Path(t["path"]).resolve()
            break

    if not wt_path or not wt_path.is_dir():
        raise TaskError(f"Worktree for [{task_id}] not found. Run adopt first.")

    # F1: If cwd is inside the claim worktree, refuse cleanly before touching anything
    try:
        cwd_resolved = cwd.resolve()
        if cwd_resolved == wt_path or wt_path in cwd_resolved.parents:
            raise TaskError(
                f"Cannot close from inside the claim worktree; run this command from the primary tree ({primary_path})."
            )
    except ValueError:
        pass

    # F2: Check uncommitted changes in BOTH trees before any write
    wt_dirt = content_dirt(wt_path, worktree_root=settings.worktree_root)
    if wt_dirt:
        raise TaskError(
            f"Worktree {wt_path} contains uncommitted work:\n{wt_dirt}\n"
            "Commit all changes inside the worktree before running close."
        )

    main_dirt = content_dirt(primary_path, worktree_root=settings.worktree_root)
    if main_dirt:
        raise TaskError(
            f"Primary tree {primary_path} has uncommitted changes:\n{main_dirt}\n"
            "Commit them in the primary tree first. Never stash, as these may belong to another session."
        )

    wt_settings = load_settings(wt_path)
    wt_layout = get_layout(wt_settings)
    item = wt_layout.find(task_id)
    if not item:
        raise TaskError(f"Task [{task_id}] not found in worktree backlog.")

    # Decision 34: Unless the item is already Closed on the branch (F2), sync base into claim worktree
    if item.status != "Closed":
        # Step 2: Sync base branch into worktree
        merged = subprocess.run(
            ["git", "merge", base, "-m", f"{clean_id}: sync with {base}"],
            cwd=str(wt_path),
            capture_output=True,
            text=True,
        )
        if merged.returncode != 0:
            unmerged = git("ls-files", "-u", cwd=wt_path, check=False).strip()
            if unmerged:
                resolve_sync_conflicts(wt_path, task_id, base, branch, wt_settings)
            else:
                git("merge", "--abort", cwd=wt_path, check=False)
                err = (merged.stderr or merged.stdout).strip()
                raise TaskError(f"Sync merge of {base} into {branch} failed:\n{err}")

        # Step 3: The close write and its commit, on the merged tree
        wt_layout_merged = get_layout(wt_settings)
        def do_close():
            return wt_layout_merged.close(task_id, "Closed", args.outcome.strip())

        summary = f"chore(backlog): close [{task_id}]"[:72]
        safe_commit(wt_path, summary, wt_layout_merged.paths_for(task_id), do_close)

    # Atomic merge under lock in primary tree
    lock_file = git_dir(primary_path) / "merge.lock"
    with MergeLock(lock_file):
        merge_res = subprocess.run(
            ["git", "merge", "--no-ff", branch, "-m", f"Merge {branch}: {args.outcome.strip()}"],
            cwd=str(primary_path),
            capture_output=True,
            text=True,
        )
        if merge_res.returncode != 0:
            git("merge", "--abort", cwd=primary_path, check=False)
            err = (merge_res.stderr or merge_res.stdout).strip()
            raise TaskError(f"Merge into {base} failed:\n{err}")

        try:
            force_rmtree(wt_path)
            git("worktree", "prune", cwd=primary_path, check=False)
        except Exception as exc:
            print(f"Warning: Merged, but could not remove worktree {wt_path}: {exc}")
        git("branch", "-d", branch, cwd=primary_path)

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

    # F5: check base branch exists at the start
    if not git_ok("show-ref", "--verify", "--quiet", f"refs/heads/{base}", cwd=root):
        raise TaskError(f"base branch '{base}' not found; set backlog.baseBranch")

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

        # F5: run git log with check=True
        log_out = git(
            "log",
            "--no-merges",
            "--format=%h %s",
            f"{base}..{branch}",
            cwd=root,
            check=True,
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


def _handle_reject_or_cancel(args: argparse.Namespace, new_status: str) -> int:
    check_no_git_dir_env()
    reason = args.reason.strip() if getattr(args, "reason", None) else ""
    if not reason:
        raise TaskError(f"--reason is required for {new_status.lower()}")
    if "\r" in args.reason or "\n" in args.reason:
        raise TaskError("--reason cannot contain newlines")

    cwd = Path.cwd()
    root = repo_root(cwd)
    settings = load_settings(root)
    base = settings.base_branch

    # F5: check base branch exists at the start
    if not git_ok("show-ref", "--verify", "--quiet", f"refs/heads/{base}", cwd=root):
        raise TaskError(f"base branch '{base}' not found; set backlog.baseBranch")

    # Decision 27: Written in primary tree
    primary_path = primary_tree(root)

    # F9: Primary tree must be on the base branch
    primary_branch = git("branch", "--show-current", cwd=primary_path, check=False).strip()
    if primary_branch != base:
        raise TaskError(f"Primary tree {primary_path} is on branch '{primary_branch}', expected base branch '{base}'.")

    task_id = args.id.strip().strip("'\"").strip("[]")
    clean_id = task_id.lstrip("#")
    branch = f"{BRANCH_PREFIX}{clean_id}"

    # Decision 29: The item must have no claim/<ID> branch
    if branch_exists(branch, cwd=root):
        raise TaskError(f"[{task_id}] is claimed; abandon or close the claim first")

    primary_settings = load_settings(primary_path)
    primary_layout = get_layout(primary_settings)
    item = primary_layout.find(task_id)
    if not item:
        raise TaskError(f"Task [{task_id}] not found in backlog on branch '{base}'.")

    # Decision 29: The item must be Open
    if item.status != "Open":
        raise TaskError(f"[{task_id}] is {item.status}; only Open items can be rejected or cancelled")

    # Dependents (convention §4.6, Decision 36):
    # Separate unclaimed dependents (noted on main in the main commit)
    # from claimed dependents (noted in their claim worktrees after the main commit).
    unclaimed_dependents: list[Item] = []
    claimed_dependents: list[Item] = []
    for it in primary_layout.items():
        if it.status in ("Open", "In Progress") and not id_matches(it.id, item.id):
            deps = it.fields.get("depends_on", [])
            if any(id_matches(d, item.id) for d in deps):
                dep_clean_id = it.id.lstrip("#").strip("[]")
                dep_branch = f"{BRANCH_PREFIX}{dep_clean_id}"
                if branch_exists(dep_branch, cwd=root):
                    claimed_dependents.append(it)
                else:
                    unclaimed_dependents.append(it)

    # Warning for items on claim branches (Decision 29, Decision 39)
    for cb in claim_branches(root):
        branch_items = find_all_items_on_branch(root, cb, primary_settings)
        for cb_item in branch_items:
            deps = cb_item.fields.get("depends_on", [])
            if any(id_matches(d, item.id) for d in deps):
                if not primary_layout.find(cb_item.id):
                    print(f"Warning: item [{cb_item.id}] on branch {cb} depends on [{item.id}]")

    verb = "rejected" if new_status == "Rejected" else "cancelled"
    dep_note = (
        f"Depends on [{item.id}], which was {verb}: {reason}. "
        "Check whether this item is still blocked or needs rethinking."
    )

    pre_paths = set(primary_layout.paths_for(item.id))
    for dep in unclaimed_dependents:
        pre_paths.update(primary_layout.paths_for(dep.id))

    def do_action():
        written_paths = []
        all_moves = []
        w_paths, moves = primary_layout.close(item.id, new_status, reason)
        written_paths.extend(w_paths)
        all_moves.extend(moves)
        for dep in unclaimed_dependents:
            w_paths, moves = primary_layout.append_note(dep.id, dep_note)
            written_paths.extend(w_paths)
            all_moves.extend(moves)
        return written_paths, all_moves

    action_verb = "reject" if new_status == "Rejected" else "cancel"
    commit_msg = f"chore(backlog): {action_verb} [{item.id}]"[:72]
    safe_commit(primary_path, commit_msg, list(pre_paths), do_action)

    # Decision 36: While an item is claimed, only its claim branch edits its entry.
    # Note claimed dependents in their worktrees after the main commit has succeeded.
    trees = worktree_list(root)
    for dep in claimed_dependents:
        dep_clean_id = dep.id.lstrip("#").strip("[]")
        dep_branch = f"{BRANCH_PREFIX}{dep_clean_id}"
        wt_path = None
        for t in trees:
            if t["branch"] == dep_branch:
                wt_path = Path(t["path"]).resolve()
                break

        cmd_hint = f"python task.py amend '{dep.id}' --note '{dep_note}'"
        if not wt_path or not wt_path.is_dir():
            print(f"Warning: claimed dependent [{dep.id}] has no worktree. Run instead:\n  {cmd_hint}")
        else:
            try:
                wt_settings = load_settings(wt_path)
                wt_layout = get_layout(wt_settings)
                def do_dep_note():
                    return wt_layout.append_note(dep.id, dep_note)

                dep_commit_msg = f"chore(backlog): note [{dep.id}]"[:72]
                safe_commit(wt_path, dep_commit_msg, wt_layout.paths_for(dep.id), do_dep_note)
            except Exception as exc:
                print(f"Warning: could not update claimed dependent [{dep.id}]: {exc}\nRun instead:\n  {cmd_hint}")

    print(f"{new_status} [{item.id}]: {reason}")
    return 0


def cmd_reject(args: argparse.Namespace) -> int:
    """Reject an open backlog task with a reason (Decision 29)."""
    return _handle_reject_or_cancel(args, "Rejected")


def cmd_cancel(args: argparse.Namespace) -> int:
    """Cancel an open backlog task with a reason (Decision 29)."""
    return _handle_reject_or_cancel(args, "Cancelled")


def cmd_amend(args: argparse.Namespace) -> int:
    """Amend a backlog task with notes or priority updates (Decision 30)."""
    check_no_git_dir_env()
    if getattr(args, "note", None) is not None and ("\r" in args.note or "\n" in args.note):
        raise TaskError("--note cannot contain newlines")
    task_id = args.id.strip().strip("'\"").strip("[]")
    note = args.note.strip() if getattr(args, "note", None) else None
    priority = args.priority.upper() if getattr(args, "priority", None) else None

    if not note and not priority:
        raise TaskError("amend requires at least one of --note or --priority")

    if priority and not note:
        raise TaskError("--priority requires --note with the reason")

    if priority and priority not in PRIORITY_LEVELS:
        raise TaskError(f"Invalid priority {priority!r}. Must be one of {PRIORITY_LEVELS}")

    cwd = Path.cwd()
    root = repo_root(cwd)
    settings = load_settings(root)
    base = settings.base_branch

    # F5: base branch must exist
    if not git_ok("show-ref", "--verify", "--quiet", f"refs/heads/{base}", cwd=root):
        raise TaskError(f"base branch '{base}' not found; set backlog.baseBranch")

    clean_id = task_id.lstrip("#")
    branch = f"{BRANCH_PREFIX}{clean_id}"

    # Where to write (Decision 30):
    if branch_exists(branch, cwd=root):
        wt_path = None
        for t in worktree_list(root):
            if t["branch"] == branch:
                wt_path = Path(t["path"]).resolve()
                break
        if not wt_path or not wt_path.is_dir():
            raise TaskError(f"run adopt '{task_id}' first")
        target_tree = wt_path
    else:
        primary_path = primary_tree(root)
        primary_branch = git("branch", "--show-current", cwd=primary_path, check=False).strip()
        if primary_branch != base:
            raise TaskError(f"Primary tree {primary_path} is on branch '{primary_branch}', expected base branch '{base}'.")
        target_tree = primary_path

    target_settings = load_settings(target_tree)
    target_layout = get_layout(target_settings)
    item = target_layout.find(task_id)
    if not item:
        raise TaskError(f"Task [{task_id}] not found in backlog at {target_tree}.")

    if item.status in ("Closed", "Rejected", "Cancelled"):
        raise TaskError(f"[{item.id}] is {item.status}; only open or in-progress items can be amended")

    if priority and item.priority == priority:
        raise TaskError(f"[{item.id}] is already {priority}")

    commit_msg = f"chore(backlog): amend [{item.id}]"[:72]
    pre_paths = target_layout.paths_for(item.id)

    def do_amend():
        written_paths = []
        all_moves = []
        if priority:
            old_prio = item.priority
            w_paths, moves = target_layout.set_priority(item.id, priority)
            written_paths.extend(w_paths)
            all_moves.extend(moves)
            note_content = f"priority {old_prio} → {priority}: {note}"
        else:
            note_content = note

        w_paths, moves = target_layout.append_note(item.id, note_content)
        written_paths.extend(w_paths)
        all_moves.extend(moves)
        return written_paths, all_moves

    safe_commit(target_tree, commit_msg, pre_paths, do_amend)
    print(f"Amended [{item.id}]")
    return 0


def select_list_items(
    items: list[Item],
    claims: list[str],
    status_filter: str | None = None,
    priority_filter: str | None = None,
    is_folders_layout: bool = False,
) -> list[tuple[int, str, Any, Item, str, str]]:
    """Pure selection and sorting function for backlog list (Decision 31, Decision 43)."""
    valid_statuses = {"open", "in progress", "in-progress", "closed", "completed", "rejected", "cancelled", "all"}
    if status_filter:
        if status_filter.lower() not in valid_statuses:
            raise TaskError(
                f"Invalid status {status_filter!r}. Must be one of: Open, In Progress, Closed, Rejected, Cancelled, all"
            )

    valid_priorities = {"P1", "P2", "P3"}
    if priority_filter:
        if priority_filter.upper() not in valid_priorities:
            raise TaskError(
                f"Invalid priority {priority_filter!r}. Must be one of: P1, P2, P3"
            )
        priority_filter = priority_filter.upper()

    matched_entries = []

    for idx, item in enumerate(items):
        claim_match = None
        for branch in claims:
            branch_id = branch[len(BRANCH_PREFIX) :]
            if id_matches(item.id, branch_id):
                claim_match = branch
                break

        if claim_match:
            display_status = f"In Progress ({claim_match})"
        else:
            display_status = item.status

        # Priority filter
        if priority_filter:
            if (item.priority or "").upper() != priority_filter:
                continue

        # Status filter
        if status_filter:
            if status_filter.lower() == "all":
                pass
            elif status_filter.lower() in ("in progress", "in-progress"):
                if not display_status.startswith("In Progress"):
                    continue
            elif status_filter.lower() in ("closed", "completed"):
                if display_status not in ("Closed", "Completed"):
                    continue
            else:
                if display_status.lower() != status_filter.lower():
                    continue
        else:
            # Default: Open and In Progress
            if display_status != "Open" and not display_status.startswith("In Progress"):
                continue

        prio_rank = {"P1": 1, "P2": 2, "P3": 3}.get((item.priority or "").upper(), 99)
        created = item.fields.get("created") or ""
        sort_created = created if created else "9999-99-99"

        if is_folders_layout:
            pos = item.path.name if item.path else item.id
        else:
            pos = idx

        matched_entries.append((prio_rank, sort_created, pos, item, display_status, created))

    matched_entries.sort(key=lambda x: (x[0], x[1], x[2]))
    return matched_entries


def select_next_item(
    items: list[Item],
    claims: list[str],
    is_folders_layout: bool = False,
) -> tuple[Item | None, int]:
    """Pure selection function for next ready item (Decision 32, Decision 43)."""
    ready_items = []
    blocked_count = 0

    for idx, item in enumerate(items):
        if item.status != "Open":
            continue

        is_claimed = False
        for branch in claims:
            branch_id = branch[len(BRANCH_PREFIX) :]
            if id_matches(item.id, branch_id):
                is_claimed = True
                break

        if is_claimed:
            continue

        deps = item.fields.get("depends_on", [])
        is_blocked = False
        if deps:
            for dep_id in deps:
                dep_item = next((it for it in items if id_matches(it.id, dep_id)), None)
                if not dep_item or dep_item.status not in ("Closed", "Completed"):
                    is_blocked = True
                    break

        if is_blocked:
            blocked_count += 1
        else:
            prio_rank = {"P1": 1, "P2": 2, "P3": 3}.get((item.priority or "").upper(), 99)
            created = item.fields.get("created") or ""
            sort_created = created if created else "9999-99-99"
            if is_folders_layout:
                pos = item.path.name if item.path else item.id
            else:
                pos = idx
            ready_items.append((prio_rank, sort_created, pos, item, created))

    if not ready_items:
        return None, blocked_count

    ready_items.sort(key=lambda x: (x[0], x[1], x[2]))
    return ready_items[0][3], blocked_count


def cmd_list(args: argparse.Namespace) -> int:
    """List backlog items with optional status and priority filtering (Decision 31)."""
    cwd = Path.cwd()
    root = repo_root(cwd)
    primary_path = primary_tree(root)
    primary_settings = load_settings(primary_path)
    primary_layout = get_layout(primary_settings)

    claims = claim_branches(root)
    items = primary_layout.items()

    status_filter = args.status.strip() if getattr(args, "status", None) and args.status else None
    priority_filter = args.priority.strip().upper() if getattr(args, "priority", None) and args.priority else None

    matched_entries = select_list_items(
        items,
        claims,
        status_filter=status_filter,
        priority_filter=priority_filter,
        is_folders_layout=(primary_settings.layout == "folders"),
    )

    if not matched_entries:
        print("No items.")
        return 0

    for _, _, _, item, disp_status, created in matched_entries:
        print(f"{item.id}\t{item.priority or ''}\t{disp_status}\t{created}\t{item.title}")

    return 0


def cmd_next(args: argparse.Namespace) -> int:
    """Find and display the highest-priority ready backlog item (Decision 32)."""
    cwd = Path.cwd()
    root = repo_root(cwd)
    primary_path = primary_tree(root)
    primary_settings = load_settings(primary_path)
    primary_layout = get_layout(primary_settings)

    claims = claim_branches(root)
    items = primary_layout.items()

    best, blocked_count = select_next_item(
        items,
        claims,
        is_folders_layout=(primary_settings.layout == "folders"),
    )

    if not best:
        print(f"No ready item. {blocked_count} open item{'s' if blocked_count != 1 else ''} {'is' if blocked_count == 1 else 'are'} blocked.")
        return 0

    created = best.fields.get("created") or ""
    created_str = created if created else "unknown"
    prio_str = best.priority or "P2"
    print(f"[{best.id}] {best.title} ({prio_str}, created {created_str})")
    print(f"claim it with: python task.py claim '{best.id}'")
    return 0


