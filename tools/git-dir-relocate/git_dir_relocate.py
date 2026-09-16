#!/usr/bin/env python3
"""git-dir-relocate: keep a git repository's database outside a cloud-synced folder.

File syncers such as Google Drive for Desktop write marker files (desktop.ini) into every
directory they sync, including .git/. Git reads the ones under refs/ as broken refs and the ones
under objects/ as corrupt objects. The fix is to move the database elsewhere and leave a one-line
`.git` pointer file in the working tree:

    .git  ->  gitdir: <git-dirs root>/<name>.git

Commands
    status   <repo>...                       report layout and syncer litter (read-only)
    relocate <repo> [--name N] [--dry-run]   move an existing in-tree .git out
    init     <path> [--name N]               create a new repo with the database outside
    clean    <repo>                          delete syncer marker files inside the git dir

The git-dirs root comes from --git-dirs, else the GIT_DIRS_ROOT environment variable.

Exit codes: 0 ok · 1 finished with warnings · 2 usage error · 3 refused (nothing changed)
            4 failed after changes began (read the notes printed) · 5 unexpected crash
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
import traceback
from pathlib import Path

LITTER_NAMES = {"desktop.ini", "thumbs.db", ".ds_store"}
IN_PROGRESS = ["MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_LOG", "rebase-merge", "rebase-apply"]
FSCK_PROBLEM = re.compile(r"^(error|fatal|bad|broken|missing|corrupt)", re.I)
REF_CONTENT = re.compile(r"^([0-9a-f]{40}([0-9a-f]{24})?|ref: )")

EXIT_OK, EXIT_WARN, EXIT_USAGE, EXIT_REFUSED, EXIT_FAILED, EXIT_CRASH = 0, 1, 2, 3, 4, 5


class Refused(Exception):
    pass


class Usage(Exception):
    pass


class Failed(Exception):
    """Something went wrong after the repository started changing."""


def _env() -> dict:
    env = dict(os.environ)
    for k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY"):
        env.pop(k, None)
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    cp = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                        encoding="utf-8", errors="replace", env=_env())
    if check and cp.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed ({cp.returncode}): {cp.stderr.strip()}")
    return cp


def to_path(raw: str) -> Path:
    """Accept Git Bash style /c/... paths on Windows."""
    m = re.match(r"^/([a-zA-Z])(/.*)?$", raw)
    if os.name == "nt" and m:
        raw = f"{m.group(1).upper()}:{m.group(2) or '/'}"
    return Path(raw).expanduser()


def norm(p: Path | str) -> str:
    return str(Path(p).resolve()).replace("\\", "/").rstrip("/").lower()


def is_link(p: Path) -> bool:
    return p.is_symlink() or (hasattr(os.path, "isjunction") and os.path.isjunction(p))


def read_gitfile(repo: Path) -> Path | None:
    """Target of a `.git` pointer file, or None if `.git` is not a pointer file."""
    g = repo / ".git"
    if not g.is_file() or is_link(g):
        return None
    first = g.read_text(encoding="utf-8", errors="replace").splitlines()[:1]
    if not first or not first[0].lower().startswith("gitdir:"):
        return None
    target = Path(first[0][len("gitdir:"):].strip())
    return target if target.is_absolute() else (repo / target).resolve()


def git_dirs_root(arg: str | None) -> Path:
    raw = arg or os.environ.get("GIT_DIRS_ROOT")
    if not raw:
        raise Usage("no git-dirs root: pass --git-dirs <dir> or set GIT_DIRS_ROOT")
    root = to_path(raw)
    if not root.is_absolute():
        raise Usage(f"git-dirs root must be an absolute path: {raw}")
    if root.exists() and not root.is_dir():
        raise Usage(f"git-dirs root exists and is not a directory: {root}")
    return root


def find_litter(git_dir: Path) -> list[Path]:
    """Syncer marker files inside a git dir. Never follows links; never touches a real ref file."""
    found = []
    for dirpath, dirnames, filenames in os.walk(git_dir, followlinks=False):
        dirnames[:] = [d for d in dirnames if not is_link(Path(dirpath) / d)]
        for f in filenames:
            if f.lower() not in LITTER_NAMES:
                continue
            p = Path(dirpath) / f
            try:
                head = p.read_bytes()[:64].decode("utf-8", errors="replace")
            except OSError:
                continue
            if REF_CONTENT.match(head):  # a real ref that happens to have this name
                continue
            found.append(p)
    return found


def remove_litter(paths: list[Path]) -> list[str]:
    failures = []
    for p in paths:
        try:
            os.chmod(p, 0o666)
            p.unlink()
        except OSError as e:
            failures.append(f"could not delete {p}: {e}")
    return failures


def linked_worktrees(repo: Path) -> list[str]:
    out = git(repo, "worktree", "list", "--porcelain").stdout
    paths = [line[len("worktree "):] for line in out.splitlines() if line.startswith("worktree ")]
    return [p for p in paths if norm(p) != norm(repo)]


def fsck_problems(repo: Path) -> list[str]:
    """fsck problems, ignoring the ones caused by syncer marker files."""
    cp = git(repo, "fsck", "--no-progress", "--no-dangling", check=False)
    lines = (cp.stdout + "\n" + cp.stderr).splitlines()
    problems = [l for l in lines
                if FSCK_PROBLEM.match(l.strip()) and not any(n in l.lower() for n in LITTER_NAMES)]
    if cp.returncode != 0 and not problems and not any(any(n in l.lower() for n in LITTER_NAMES) for l in lines):
        problems = [f"git fsck exited {cp.returncode}"]
    return problems


def local_config(repo: Path) -> list[str]:
    return git(repo, "config", "--local", "--list").stdout.splitlines()


def snapshot(repo: Path) -> dict:
    refs = git(repo, "for-each-ref", "--format=%(refname) %(objectname)").stdout
    head = git(repo, "rev-parse", "--verify", "-q", "HEAD", check=False).stdout.strip() or None
    return {
        "head": head,
        "branch": git(repo, "symbolic-ref", "-q", "--short", "HEAD", check=False).stdout.strip(),
        "refs": hashlib.sha256(refs.encode()).hexdigest(),
        "remotes": git(repo, "remote", "-v").stdout.strip(),
        "config": local_config(repo),
        "status": git(repo, "status", "--porcelain=v1", "--untracked-files=all").stdout,
    }


def sync_exclude_warnings(repo: Path) -> list[str]:
    """Syncing workflows that exclude `.git/**` do not match a `.git` *file*."""
    warnings = []
    wf_dir = repo / ".github" / "workflows"
    for f in sorted(wf_dir.glob("*.y*ml")) if wf_dir.is_dir() else []:
        code = "\n".join(l for l in f.read_text(encoding="utf-8", errors="replace").splitlines()
                         if not l.lstrip().startswith("#"))
        rel = f.relative_to(repo).as_posix()
        if ".git/**" in code and not re.search(r"""(^|["'\s=])\.git(["'\s,\]]|$)""", code, re.M):
            warnings.append(f"{rel} excludes '.git/**' but not a bare '.git' file; "
                            "add an exclude for '.git' so the pointer file is not synced")
        if re.search(r"--(exclude|filter)-from", code):
            warnings.append(f"{rel} reads exclude/filter files; check they exclude a bare '.git' file too")
    return warnings


def check_name(name: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", name) or name in (".", ".."):
        raise Usage(f"invalid repository name for the git-dirs root: {name!r}")


# ---------------------------------------------------------------- commands

def cmd_status(args) -> int:
    worst = EXIT_OK
    for raw in args.repos:
        repo = to_path(raw).resolve()
        g = repo / ".git"
        if is_link(g):
            print(f"{repo}: .git is a symlink/junction (not supported; fix by hand)")
            worst = max(worst, EXIT_WARN)
        elif g.is_dir():
            litter = find_litter(g)
            note = f", {len(litter)} syncer marker file(s) inside" if litter else ""
            print(f"{repo}: IN-TREE .git directory{note}")
            if litter:
                worst = max(worst, EXIT_WARN)
        elif g.is_file():
            target = read_gitfile(repo)
            if target is None or not target.is_dir():
                print(f"{repo}: BROKEN .git pointer ({target})")
                worst = max(worst, EXIT_WARN)
                continue
            litter = find_litter(target)
            note = f", {len(litter)} syncer marker file(s) inside" if litter else ""
            print(f"{repo}: relocated -> {target.as_posix()}{note}")
        else:
            print(f"{repo}: not a git repository root")
            worst = max(worst, EXIT_WARN)
    return worst


def cmd_relocate(args) -> int:
    repo = to_path(args.repo).resolve()
    root = git_dirs_root(args.git_dirs)
    g = repo / ".git"

    # ---------------- preflight: read-only; any problem refuses with nothing changed
    if is_link(g):
        raise Refused(f"{g} is a symlink or junction; resolve it by hand first")
    if g.is_file():
        target = read_gitfile(repo)
        if target is not None and norm(target.parent) == norm(root):
            print(f"already relocated: {repo} -> {target.as_posix()}")
            return EXIT_OK
        raise Refused(f"{g} is already a pointer file to {target}; not under {root.as_posix()}")
    if not g.is_dir():
        raise Refused(f"{repo} has no .git directory (is it the repository root?)")
    if git(repo, "rev-parse", "--is-bare-repository").stdout.strip() == "true":
        raise Refused("bare repositories are not supported")
    top = git(repo, "rev-parse", "--show-toplevel").stdout.strip()
    if norm(top) != norm(repo):
        raise Refused(f"{repo} is not the top of its repository (top is {top})")
    name = args.name or repo.name
    check_name(name)
    target = root / f"{name}.git"
    if target.exists():
        raise Refused(f"target already exists: {target.as_posix()} (choose another --name)")
    if norm(root) == norm(repo) or norm(root).startswith(norm(repo) + "/"):
        raise Refused("the git-dirs root must be outside the repository")
    if git(repo, "config", "--local", "--get", "core.worktree", check=False).stdout.strip():
        raise Refused("core.worktree is set; relocating would point git at the wrong working tree")
    includes = git(repo, "config", "--local", "--get-regexp", r"^include(if\..*)?\.path$", check=False).stdout
    relative = [l for l in includes.splitlines() if l.split(" ", 1)[-1] and not Path(l.split(" ", 1)[-1]).is_absolute()]
    if relative:
        raise Refused(f"relative include paths in config would break after the move: {relative[0]}")
    busy = [p for p in IN_PROGRESS if (g / p).exists()]
    busy += [p.relative_to(g).as_posix() for p in g.rglob("*.lock") if p.is_file()]
    if busy:
        raise Refused(f"an operation is in progress or a lock is held: {', '.join(busy[:5])} "
                      "(close Obsidian/git tools; delete stale locks only if nothing is running)")
    if (g / "modules").is_dir():
        raise Refused("repository has submodules under .git/modules; relocate by hand (their gitfiles use relative paths)")
    worktrees = linked_worktrees(repo)
    if worktrees and not args.repair_worktrees:
        raise Refused(f"{len(worktrees)} linked worktree(s) exist; rerun with --repair-worktrees")
    problems = fsck_problems(repo)
    if problems:
        raise Refused(f"git fsck reports {len(problems)} problem(s) unrelated to marker files; "
                      f"fix them first. First: {problems[0]}")
    before = snapshot(repo)
    config_bytes = (g / "config").read_bytes()
    litter = find_litter(g)

    print(f"repository : {repo}")
    print(f"move .git  : -> {target.as_posix()}")
    print(f"marker files inside .git to delete: {len(litter)}")
    if worktrees:
        print(f"linked worktrees to repair: {len(worktrees)}")
    if args.dry_run:
        print("dry run: nothing changed")
        return EXIT_OK

    # ---------------- change
    failures = remove_litter(litter)
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise Failed(f"could not create the git-dirs root {root}: {e}. Only marker files were deleted; "
                     "the repository is otherwise unchanged.")
    cp = git(repo, "init", "--quiet", f"--separate-git-dir={target.as_posix()}", check=False)
    pointer = read_gitfile(repo)
    moved = target.is_dir() and pointer is not None and norm(pointer) == norm(target)
    if not moved:
        if g.is_dir() and not target.exists():
            raise Failed(f"git init --separate-git-dir exited {cp.returncode}: {cp.stderr.strip()}\n"
                         "nothing moved; the in-tree .git directory is intact.")
        raise Failed(f"git init --separate-git-dir exited {cp.returncode}: {cp.stderr.strip()}\n"
                     f"state is unclear: .git directory present={g.is_dir()}, pointer file present={g.is_file()}, "
                     f"{target.as_posix()} present={target.exists()}. Do not run git; inspect by hand.")
    if cp.returncode != 0:
        raise Failed(f"the database moved to {target.as_posix()} and .git points to it, but git then failed "
                     f"({cp.returncode}): {cp.stderr.strip()}. Fix that error (e.g. a stale lock file inside the "
                     "moved database) and rerun `status`.")

    warnings: list[str] = list(failures)
    try:  # reinit rewrites some core.* values; restore the original bytes atomically
        tmp = target / "config.relocate-tmp"
        tmp.write_bytes(config_bytes)
        os.replace(tmp, target / "config")
    except OSError as e:
        raise Failed(f"the database moved to {target.as_posix()} and .git points to it, but restoring the "
                     f"original config failed: {e}. The original bytes were:\n{config_bytes.decode('utf-8', 'replace')}")
    try:
        if worktrees:
            git(repo, "worktree", "repair")
        remove_litter(find_litter(target))
        if args.gc:
            git(repo, "gc", "--quiet")
        after = snapshot(repo)
    except RuntimeError as e:
        raise Failed(f"the database moved to {target.as_posix()} and .git points to it, but a follow-up step "
                     f"failed: {e}")
    changed = [k for k in before if before[k] != after[k]]
    if changed:
        raise Failed(f"relocated to {target.as_posix()}, but {', '.join(changed)} changed. Do not commit; "
                     "inspect `git status` and `git config --local --list` against the values before.")
    new_problems = fsck_problems(repo)
    if new_problems:
        raise Failed(f"relocated to {target.as_posix()}, but git fsck now reports: {new_problems[0]}")

    warnings += sync_exclude_warnings(repo)
    print(f"relocated  : .git -> gitdir: {target.as_posix()}")
    print(f"verified   : HEAD {before['head'] or '(no commits)'}; refs, branch, remotes, config and working tree "
          "unchanged; git fsck clean")
    print("note       : hooks now live in the relocated git dir and are per-machine; a clone does not carry them")
    for w in warnings:
        print(f"  warn  {w}")
    return EXIT_WARN if warnings else EXIT_OK


def cmd_init(args) -> int:
    path = to_path(args.path).resolve()
    root = git_dirs_root(args.git_dirs)
    if (path / ".git").exists() or is_link(path / ".git"):
        raise Refused(f"{path} already has a .git; use `relocate` for an existing repository")
    name = args.name or path.name
    check_name(name)
    target = root / f"{name}.git"
    if target.exists():
        raise Refused(f"target already exists: {target.as_posix()} (choose another --name)")
    if norm(root) == norm(path) or norm(root).startswith(norm(path) + "/"):
        raise Refused("the git-dirs root must be outside the repository")
    path.mkdir(parents=True, exist_ok=True)
    root.mkdir(parents=True, exist_ok=True)
    extra = [f"--initial-branch={args.initial_branch}"] if args.initial_branch else []
    git(path, "init", "--quiet", *extra, f"--separate-git-dir={target.as_posix()}")
    print(f"initialized: {path} with gitdir {target.as_posix()}")
    return EXIT_OK


def cmd_clean(args) -> int:
    repo = to_path(args.repo).resolve()
    g = repo / ".git"
    git_dir = g if (g.is_dir() and not is_link(g)) else read_gitfile(repo)
    if git_dir is None or not git_dir.is_dir():
        raise Usage(f"{repo} is not a git repository root")
    litter = find_litter(git_dir)
    if args.dry_run:
        print(f"would delete {len(litter)} marker file(s) inside {git_dir.as_posix()}")
        return EXIT_OK
    failures = remove_litter(litter)
    print(f"deleted {len(litter) - len(failures)} marker file(s) inside {git_dir.as_posix()}")
    for f in failures:
        print(f"  warn  {f}")
    return EXIT_WARN if failures else EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="git-dir-relocate", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("status", help="report where each repository's database lives (read-only)")
    p.add_argument("repos", nargs="+")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("relocate", help="move an in-tree .git directory to the git-dirs root")
    p.add_argument("repo")
    p.add_argument("--git-dirs", help="git-dirs root (default: $GIT_DIRS_ROOT)")
    p.add_argument("--name", help="database name, <name>.git (default: the repository folder name)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--repair-worktrees", action="store_true", help="allow linked worktrees and repair their pointers")
    p.add_argument("--gc", action="store_true", help="run `git gc` (without --prune=now) after moving")
    p.set_defaults(func=cmd_relocate)

    p = sub.add_parser("init", help="create a new repository with its database in the git-dirs root")
    p.add_argument("path")
    p.add_argument("--git-dirs", help="git-dirs root (default: $GIT_DIRS_ROOT)")
    p.add_argument("--name", help="database name, <name>.git (default: the folder name)")
    p.add_argument("--initial-branch", help="e.g. main")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("clean", help="delete syncer marker files (desktop.ini, Thumbs.db, .DS_Store) inside the git dir")
    p.add_argument("repo")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_clean)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except Usage as e:
        print(f"usage error: {e}", file=sys.stderr)
        return EXIT_USAGE
    except Refused as e:
        print(f"refused (nothing changed): {e}", file=sys.stderr)
        return EXIT_REFUSED
    except Failed as e:
        print(f"FAILED: {e}", file=sys.stderr)
        return EXIT_FAILED
    except RuntimeError as e:  # git errors before any change
        print(f"refused (nothing changed): {e}", file=sys.stderr)
        return EXIT_REFUSED
    except Exception:  # noqa: BLE001 - never report a crash as success or warning
        traceback.print_exc()
        return EXIT_CRASH


if __name__ == "__main__":
    sys.exit(main())
