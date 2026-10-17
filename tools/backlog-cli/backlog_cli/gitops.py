"""Git plumbing, worktrees, claims, and file safety operations."""

from __future__ import annotations

import datetime
import os
import shutil
import stat
import subprocess
from pathlib import Path

from backlog_cli import TaskError

BRANCH_PREFIX = "claim/"
CHORE_PREFIX = "chore/"
WORKTREE_PREFIXES = (BRANCH_PREFIX, CHORE_PREFIX)

CFG_ROOT = "vault.worktreeRoot"
CFG_BACKLOG = "backlog.file"
CFG_BASE_BRANCH = "backlog.baseBranch"

STALE_DAYS = 2.0


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
        parts = [p.strip() for p in (proc.stdout, proc.stderr) if p and p.strip()]
        err = "\n".join(parts) if parts else f"git {' '.join(args)} exited with code {proc.returncode}"
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


NO_GIT_MSG = "tool-only writing needs git; without it, use one named writer (skill/backlog-governance §4)"
GIT_DIR_MSG = (
    "claim, close and abandon can't run while GIT_DIR or GIT_WORK_TREE is set: "
    "their worktree commands would act on the main tree. Unset them, or keep "
    "the repository outside the folder with a .git pointer file (tool/git-dir-relocate)."
)


def check_no_git_dir_env() -> None:
    """Refuse commands that manipulate worktrees while GIT_DIR or GIT_WORK_TREE is set."""
    if "GIT_DIR" in os.environ or "GIT_WORK_TREE" in os.environ:
        raise TaskError(GIT_DIR_MSG)


def find_repo_root(cwd: str | Path | None = None) -> Path:
    """Find git and repo root, raising exact TaskError if git is missing or folder is not in a repository."""
    if shutil.which("git") is None:
        raise TaskError(NO_GIT_MSG)
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        out = proc.stdout.strip()
        if proc.returncode == 0 and out:
            return Path(out).resolve()
        if ("GIT_DIR" in os.environ or "GIT_WORK_TREE" in os.environ) and git_ok("rev-parse", "--git-dir", cwd=cwd):
            return Path(cwd or Path.cwd()).resolve()
        raise TaskError(NO_GIT_MSG)
    except OSError:
        raise TaskError(NO_GIT_MSG)


def repo_root(cwd: str | Path | None = None) -> Path:
    """Return top-level directory of current git working tree."""
    return find_repo_root(cwd)


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


def content_dirt(
    cwd: str | Path,
    *pathspec: str,
    untracked: bool = True,
    worktree_root: Path | None = None,
) -> str:
    """Return porcelain-style diff lines comparing content, avoiding CRLF false positives."""
    sep = ["--", *pathspec] if pathspec else []
    changed = git("diff", "--name-only", "HEAD", *sep, cwd=cwd, check=False).splitlines()
    others = []
    if untracked:
        out = git("ls-files", "--others", "--exclude-standard", *sep, cwd=cwd, check=False)
        others = out.splitlines()
        wroot = worktree_root
        if wroot is None:
            try:
                wroot = (repo_root(cwd).parent / "worktrees").resolve()
            except Exception:
                pass
        if wroot is not None:
            try:
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
