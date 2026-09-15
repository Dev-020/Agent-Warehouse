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
import datetime
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

BRANCH_PREFIX = "claim/"
CHORE_PREFIX = "chore/"
WORKTREE_PREFIXES = (BRANCH_PREFIX, CHORE_PREFIX)

CFG_ROOT = "vault.worktreeRoot"
CFG_BACKLOG = "backlog.file"
CFG_BASE_BRANCH = "backlog.baseBranch"

PRIORITY_LEVELS = ("P1", "P2", "P3")
STALE_DAYS = 2.0


class TaskError(Exception):
    """User-facing task error without stack trace."""


# ---------------------------------------------------------------------------
# Git Plumbing
# ---------------------------------------------------------------------------


def git(*args: str, cwd: str | Path | None = None, check: bool = True) -> str:
    """Execute git command and return stripped stdout."""
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and proc.returncode != 0:
        err = (proc.stderr or proc.stdout).strip()
        raise TaskError(f"git {' '.join(args)} failed:\n{err}")
    return proc.stdout.strip()


def git_ok(*args: str, cwd: str | Path | None = None) -> bool:
    """Check if git command succeeds (exit code 0)."""
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def repo_root(cwd: str | Path | None = None) -> Path:
    """Return top-level directory of current git working tree."""
    out = git("rev-parse", "--show-toplevel", cwd=cwd, check=True)
    return Path(out).resolve()


def git_dir(cwd: str | Path | None = None) -> Path:
    """Return git directory path (common dir for worktrees)."""
    out = git("rev-parse", "--git-common-dir", cwd=cwd, check=True)
    p = Path(out)
    if not p.is_absolute():
        p = (repo_root(cwd) / p).resolve()
    return p


def base_branch(cwd: str | Path | None = None) -> str:
    """Detect main or master branch name."""
    configured = git("config", "--get", CFG_BASE_BRANCH, cwd=cwd, check=False)
    if configured:
        return configured.strip()
    if git_ok("show-ref", "--verify", "--quiet", "refs/heads/main", cwd=cwd):
        return "main"
    if git_ok("show-ref", "--verify", "--quiet", "refs/heads/master", cwd=cwd):
        return "master"
    return "main"


def content_dirt(cwd: str | Path, *pathspec: str, untracked: bool = True) -> str:
    """Return porcelain-style diff lines comparing content, avoiding CRLF false positives."""
    sep = ["--", *pathspec] if pathspec else []
    changed = git("diff", "--name-only", "HEAD", *sep, cwd=cwd, check=False).splitlines()
    others = []
    if untracked:
        out = git("ls-files", "--others", "--exclude-standard", *sep, cwd=cwd, check=False)
        others = out.splitlines()
        try:
            wroot = resolve_worktree_root(Path(cwd))
            rel = wroot.relative_to(Path(cwd)).as_posix()
            others = [p for p in others if not p.replace("\\", "/").startswith(rel)]
        except Exception:
            pass
    lines = [f" M {p}" for p in changed if p.strip()] + [f"?? {p}" for p in others if p.strip()]
    return "\n".join(lines)


def staged_differs(cwd: str | Path, *paths: str) -> bool:
    """Check if index differs from HEAD for specific paths."""
    sep = ["--", *paths] if paths else []
    return not git_ok("diff", "--cached", "--quiet", *sep, cwd=cwd)


def branch_exists(branch: str, cwd: str | Path | None = None) -> bool:
    return git_ok("show-ref", "--verify", "--quiet", f"refs/heads/{branch}", cwd=cwd)


def branches_with_prefix(prefix: str, cwd: str | Path | None = None) -> list[str]:
    out = git("for-each-ref", "--format=%(refname:short)", f"refs/heads/{prefix}", cwd=cwd, check=False)
    return [b.strip() for b in out.splitlines() if b.strip()]


def claim_branches(cwd: str | Path | None = None) -> list[str]:
    return branches_with_prefix(BRANCH_PREFIX, cwd=cwd)


def worktree_list(cwd: str | Path | None = None) -> list[dict[str, str]]:
    """Parse git worktree list --porcelain."""
    out = git("worktree", "list", "--porcelain", cwd=cwd, check=False)
    found, current = [], {}
    for line in out.splitlines():
        if not line.strip():
            if current:
                found.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    if current:
        found.append(current)

    result = []
    for entry in found:
        branch = entry.get("branch", "")
        if branch.startswith("refs/heads/"):
            branch_short = branch[len("refs/heads/") :]
        else:
            branch_short = branch
        result.append(
            {
                "path": entry.get("worktree", "").replace("\\", "/"),
                "branch": branch_short,
                "head": entry.get("HEAD", ""),
            }
        )
    return result


def branch_created_at(branch: str, cwd: str | Path | None = None) -> str | None:
    """Extract branch creation timestamp from reflog."""
    out = git("reflog", "show", "--date=iso", branch, cwd=cwd, check=False)
    lines = [l for l in out.splitlines() if l.strip()]
    if not lines:
        return None
    stamp = lines[-1]
    start, end = stamp.find("@{"), stamp.find("}")
    if start == -1 or end == -1:
        return None
    return stamp[start + 2 : end].strip()


def branch_last_activity(branch: str, base: str, cwd: str | Path | None = None) -> tuple[str | None, int]:
    """Return (iso_timestamp, commits_ahead)."""
    ahead_str = git("rev-list", "--count", f"{base}..{branch}", cwd=cwd, check=False)
    try:
        ahead = int(ahead_str or "0")
    except ValueError:
        ahead = 0
    if ahead == 0:
        return None, 0
    stamp = git("log", "-1", "--format=%cI", branch, cwd=cwd, check=False)
    return stamp, ahead


def days_since(iso_str: str | None) -> float | None:
    if not iso_str:
        return None
    text = iso_str.strip().replace(" ", "T", 1)
    for cut in ("+", "-"):
        idx = text.find(cut, 11)
        if idx != -1:
            text = text[:idx]
            break
    try:
        when = datetime.datetime.fromisoformat(text)
    except ValueError:
        return None
    return (datetime.datetime.now() - when).total_seconds() / 86400.0


# ---------------------------------------------------------------------------
# File Operations & Safety
# ---------------------------------------------------------------------------


def clear_readonly(root: str | Path) -> None:
    """Clear Windows ReadOnly attributes recursively."""
    for dirpath, dirnames, filenames in os.walk(str(root)):
        for name in dirnames + filenames:
            path = os.path.join(dirpath, name)
            try:
                os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
            except OSError:
                pass
    try:
        os.chmod(str(root), stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass


def force_rmtree(path: str | Path) -> None:
    """shutil.rmtree with ReadOnly permission cleanup."""
    def on_error(func, target, _exc):
        try:
            os.chmod(target, stat.S_IWRITE | stat.S_IREAD)
            func(target)
        except OSError:
            pass

    clear_readonly(path)
    shutil.rmtree(str(path), onerror=on_error)


def write_atomic(path: Path, content: str) -> None:
    """Atomic file write via temporary file."""
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    os.replace(tmp, path)


class MergeLock:
    """Process-exclusive lockfile in git directory."""

    def __init__(self, lock_path: Path):
        self.path = Path(lock_path)
        self.fd: int | None = None

    def __enter__(self):
        try:
            self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise TaskError(
                f"Another merge or operation is in progress (lock exists at {self.path}).\n"
                "Wait and retry. If no task is running, remove that file."
            )
        os.write(self.fd, str(os.getpid()).encode("utf-8"))
        return self

    def __exit__(self, *exc):
        if self.fd is not None:
            os.close(self.fd)
        try:
            os.remove(str(self.path))
        except OSError:
            pass


class Restorable:
    """Snapshot files in memory and restore if an exception occurs."""

    def __init__(self, paths: list[Path]):
        self.paths = [Path(p) for p in paths]
        self.saved: dict[Path, bytes] = {}

    def __enter__(self):
        for p in self.paths:
            if p.is_file():
                self.saved[p] = p.read_bytes()
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            for p, data in self.saved.items():
                p.write_bytes(data)
        return False


# ---------------------------------------------------------------------------
# Backlog Parsing (convention/backlog)
# ---------------------------------------------------------------------------


def resolve_backlog_path(root: Path, custom_path: str | None = None) -> Path:
    """Locate backlog file path."""
    if custom_path:
        p = Path(custom_path)
        return p if p.is_absolute() else (root / p).resolve()
    env = os.environ.get("BACKLOG_FILE") or os.environ.get("BACKLOG_PATH")
    if env:
        p = Path(env)
        return p if p.is_absolute() else (root / p).resolve()
    cfg = git("config", "--get", CFG_BACKLOG, cwd=root, check=False)
    if cfg:
        p = Path(cfg)
        return p if p.is_absolute() else (root / p).resolve()
    # Default: BACKLOG.md
    std = root / "BACKLOG.md"
    if std.is_file():
        return std
    # Legacy fallback: BACKLOG/Open.md
    legacy = root / "BACKLOG" / "Open.md"
    if legacy.is_file():
        return legacy
    return std


def resolve_worktree_root(root: Path, custom_root: str | None = None) -> Path:
    """Locate directory where worktrees are created."""
    if custom_root:
        p = Path(custom_root)
        return p if p.is_absolute() else (root / p).resolve()
    env = os.environ.get("WORKTREE_DIR")
    if env:
        p = Path(env)
        return p if p.is_absolute() else (root / p).resolve()
    cfg = git("config", "--get", CFG_ROOT, cwd=root, check=False)
    if cfg:
        p = Path(cfg)
        return p if p.is_absolute() else (root / p).resolve()
    # Default to parallel worktrees folder outside repo root
    return (root.parent / "worktrees").resolve()


def parse_task_id(header_line: str) -> str | None:
    """Extract ID from ### [ID] or - [ ] **ID**."""
    line = header_line.strip()
    # Format: ### [ID] or ### [#ID]
    m = re.match(r"^###\s+\[#?([^\]]+)\]", line)
    if m:
        return m.group(1).strip()
    # Format: - [ ] **ID** or - [/] **ID**
    m2 = re.search(r"[-*]\s*\[[ x/\-]\]\s*\*\*([^*]+)\*\*", line)
    if m2:
        return m2.group(1).strip()
    return None


def extract_all_ids(text: str) -> list[str]:
    ids = []
    for line in text.splitlines():
        tid = parse_task_id(line)
        if tid:
            ids.append(tid)
    return ids


def find_next_id(prefix: str, text: str) -> str:
    """Allocate next ID matching prefix."""
    used = []
    for tid in extract_all_ids(text):
        if prefix.lower() == "num" or prefix == "#":
            clean = tid.lstrip("#")
            if clean.isdigit():
                used.append(int(clean))
        elif tid.startswith(prefix + "-"):
            tail = tid[len(prefix) + 1 :]
            if tail.isdigit():
                used.append(int(tail))
        elif tid.startswith(prefix):
            tail = tid[len(prefix) :].lstrip("-#")
            if tail.isdigit():
                used.append(int(tail))

    nxt = (max(used) + 1) if used else 1
    if prefix.lower() in ("num", "#"):
        return f"#{nxt:03d}"
    return f"{prefix}-{nxt}"


def locate_section(lines: list[str], heading_pattern: str) -> int | None:
    """Find line index of section heading matching pattern."""
    regex = re.compile(heading_pattern, re.IGNORECASE)
    for i, line in enumerate(lines):
        if line.startswith("## ") and regex.search(line):
            return i
    return None


def find_task_span(lines: list[str], task_id: str) -> tuple[int, int] | None:
    """Find [start, end) line range for task entry."""
    start = None
    for i, line in enumerate(lines):
        tid = parse_task_id(line)
        if tid == task_id or tid == f"#{task_id}" or (task_id.startswith("#") and tid == task_id[1:]):
            start = i
            break
    if start is None:
        return None

    end = len(lines)
    for j in range(start + 1, len(lines)):
        line = lines[j]
        if line.startswith("## ") or line.startswith("### ") or (line.startswith("- [") and "**" in line):
            end = j
            break
    return start, end


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_doctor(args: argparse.Namespace) -> int:
    """Check or initialize repository configuration and hooks."""
    cwd = Path.cwd()
    root = repo_root(cwd)
    problems: list[str] = []
    notes: list[str] = []

    if args.init:
        git("config", CFG_BACKLOG, "BACKLOG.md", cwd=root)
        wroot = (root.parent / "worktrees").resolve()
        git("config", CFG_ROOT, str(wroot).replace("\\", "/"), cwd=root)
        wroot.mkdir(parents=True, exist_ok=True)
        notes.append(f"Configured {CFG_BACKLOG} = BACKLOG.md")
        notes.append(f"Configured {CFG_ROOT} = {wroot}")

    bpath = resolve_backlog_path(root)
    if bpath.is_file():
        notes.append(f"Backlog found: {bpath}")
    else:
        problems.append(f"Backlog file not found at {bpath}. Create one or run doctor --init.")

    wroot = resolve_worktree_root(root)
    if wroot.is_dir():
        notes.append(f"Worktree root directory: {wroot}")
    else:
        notes.append(f"Worktree root does not exist yet (will create on first claim): {wroot}")

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
    base = base_branch(root)
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
    bpath = resolve_backlog_path(root)
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
    bpath = resolve_backlog_path(root, getattr(args, "backlog_path", None))
    task_id = args.id.lstrip("#")
    branch = f"{BRANCH_PREFIX}{task_id}"

    if branch_exists(branch, cwd=root):
        raise TaskError(f"Task [{task_id}] is already claimed: branch {branch} exists.")

    wroot = resolve_worktree_root(root)
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
    task_id = args.id.lstrip("#")
    branch = f"{BRANCH_PREFIX}{task_id}"

    if not branch_exists(branch, cwd=root):
        raise TaskError(f"Task [{task_id}] is not claimed (branch {branch} does not exist).")

    for t in worktree_list(root):
        if t["branch"] == branch:
            print(f"Existing worktree for [{task_id}]:\n{t['path']}")
            return 0

    wroot = resolve_worktree_root(root)
    recreated = (wroot / task_id).resolve()
    raise TaskError(
        f"Branch {branch} exists but has no active worktree.\n"
        f"Recreate it with: git worktree add {recreated} {branch}"
    )


def cmd_close(args: argparse.Namespace) -> int:
    """Record completion, gate, merge to base branch, and tear down worktree."""
    cwd = Path.cwd()
    root = repo_root(cwd)
    base = base_branch(root)
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
    dirt = content_dirt(wt_path)
    if dirt:
        raise TaskError(
            f"Worktree {wt_path} contains uncommitted work:\n{dirt}\n"
            "Commit all changes inside the worktree before running close."
        )

    bpath_rel = resolve_backlog_path(root).relative_to(root)
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
    main_dirt = content_dirt(root)
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
            dirt = content_dirt(wt_path)
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


# ---------------------------------------------------------------------------
# CLI Entrypoint
# ---------------------------------------------------------------------------


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
