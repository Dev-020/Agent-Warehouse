"""Git access for the warehouse repo ONLY (invariant I2)."""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .errors import GitError

_STRIP_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX", "GIT_OBJECT_DIRECTORY",
              "GIT_COMMON_DIR", "GIT_NAMESPACE", "GIT_CEILING_DIRECTORIES")

_WAREHOUSE_ROOT: str | None = None


def register_warehouse_root(root: Path) -> None:
    global _WAREHOUSE_ROOT
    _WAREHOUSE_ROOT = os.path.normcase(os.path.realpath(root))


@dataclass
class TagInfo:
    refname: str
    objectname: str
    objecttype: str
    date: str


def git_env(extra: dict | None = None) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in _STRIP_ENV}
    if extra:
        env.update(extra)
    return env


class Git:
    def __init__(self, root: Path):
        self.root = Path(root)
        self._real = os.path.normcase(os.path.realpath(self.root))

    def run(self, *args, check=True, env_extra=None, input=None) -> subprocess.CompletedProcess:
        if _WAREHOUSE_ROOT is not None and self._real != _WAREHOUSE_ROOT:  # invariant I2; not an assert (-O safe)
            raise GitError(f"git may only run in the warehouse ({_WAREHOUSE_ROOT}), not {self._real}")
        cmd = ["git", "-C", str(self.root), *args]
        try:
            cp = subprocess.run(cmd, capture_output=True, env=git_env(env_extra), input=input)
        except FileNotFoundError:
            raise GitError("git executable not found") from None
        if check and cp.returncode != 0:
            msg = cp.stderr.decode("utf-8", "replace").strip() or cp.stdout.decode("utf-8", "replace").strip()
            raise GitError(f"git {' '.join(args[:3])} failed: {msg}")
        return cp

    def out(self, *args, **kw) -> str:
        return self.run(*args, **kw).stdout.decode("utf-8", "replace")

    def is_repo(self) -> bool:
        cp = self.run("rev-parse", "--show-toplevel", check=False)
        return cp.returncode == 0

    def tags(self) -> list[TagInfo]:
        cp = self.run("for-each-ref", "refs/tags",
                      "--format=%(refname)%00%(objectname)%00%(objecttype)%00%(creatordate:short)", check=False)
        if cp.returncode != 0:
            raise GitError("not a git repository: " + str(self.root))
        out = []
        for line in cp.stdout.decode("utf-8", "replace").splitlines():
            parts = line.split("\x00")
            if parts[0].rsplit("/", 1)[-1].lower() == "desktop.ini":  # Google Drive litter inside .git
                continue
            if len(parts) == 4:
                out.append(TagInfo(*parts))
        return out

    def tree_files(self, tag_ref: str, path: str) -> list[tuple[str, str]]:
        cp = self.run("ls-tree", "-r", "-z", "--full-tree", f"{tag_ref}^{{tree}}", "--", path)
        res = []
        for rec in cp.stdout.decode("utf-8").split("\x00"):
            if not rec:
                continue
            meta, fname = rec.split("\t", 1)
            mode, typ, oid = meta.split(" ")
            if typ == "blob" and mode != "120000":
                res.append((fname, oid))
        return res

    def blob(self, oid: str) -> bytes:
        return self.run("cat-file", "blob", oid).stdout

    def git_dir(self) -> Path:
        p = Path(self.out("rev-parse", "--git-dir").strip())
        return p if p.is_absolute() else self.root / p

    def git_path(self, name: str) -> Path:
        p = Path(self.out("rev-parse", "--git-path", name).strip())
        return p if p.is_absolute() else self.root / p

    def is_clean_state(self) -> bool:
        gd = self.git_dir()
        for marker in ("MERGE_HEAD", "rebase-merge", "rebase-apply", "CHERRY_PICK_HEAD", "REVERT_HEAD"):
            if (gd / marker).exists():
                return False
        return self.run("symbolic-ref", "-q", "HEAD", check=False).returncode == 0

    def index_snapshot(self, paths: list[str]) -> str:
        """Index entries (ls-files -s) for paths, to restore after a failed commit."""
        return self.out("ls-files", "-s", "--", *paths)

    def restore_index(self, paths: list[str], snapshot: str) -> None:
        self.run("rm", "-r", "-q", "-f", "--cached", "--ignore-unmatch", "--", *paths)
        if snapshot.strip():
            self.run("update-index", "--index-info", input=snapshot.encode("utf-8"))

    def commit_only(self, paths: list[str], message: str) -> str:
        self.run("add", "-A", "--", *paths)
        self.run("commit", "--only", "-m", message, "--", *paths, env_extra={"WAREHOUSE_RELEASING": "1"})
        return self.out("rev-parse", "HEAD").strip()

    def tag(self, name: str, message: str) -> None:
        self.run("tag", "-a", name, "-m", message)

    def merge_file(self, ours: bytes, base: bytes, theirs: bytes) -> tuple[bytes, int]:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            p_ours = Path(td) / "ours"
            p_base = Path(td) / "base"
            p_theirs = Path(td) / "theirs"
            p_ours.write_bytes(ours)
            p_base.write_bytes(base)
            p_theirs.write_bytes(theirs)
            cp = self.run("merge-file", "-p", "--diff3", str(p_ours), str(p_base), str(p_theirs), check=False)
            return cp.stdout, cp.returncode
