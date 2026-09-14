"""Guarded, atomic filesystem writes (invariants I1, I6)."""
from __future__ import annotations

import os
import re
import time
from pathlib import Path

from .errors import GuardError, UsageError
from .manifest import LOCK_NAME, MANIFEST_NAME


def _norm(p) -> str:
    return os.path.normcase(os.path.realpath(p))


def _is_link(p: Path) -> bool:
    try:
        return p.is_symlink() or os.path.isjunction(p)
    except OSError:
        return False


def _inside(child: str, parent: str) -> bool:
    try:
        return os.path.commonpath([child, parent]) == parent
    except ValueError:
        return False


class WriteGuard:
    """Allows writes inside <root>/<target> (if target given), to <root>/.warehouse.lock (project guards),
    the manifest (allow_manifest) and explicit extra files."""

    def __init__(self, project_root, target: str | None, *, allow_manifest=False, extra_files=(),
                 allow_lock=True):
        self.root = Path(project_root)
        self.target = target
        self.target_dir = self.root / target if target else None
        root_real = _norm(self.root)
        self._target_real = None
        if self.target_dir is not None:
            cur = self.root
            for part in Path(target).parts:
                cur = cur / part
                if _is_link(cur):
                    raise UsageError(f"target {target} is a symlink or junction; refusing to write")
            self._target_real = _norm(self.target_dir)
            if not _inside(self._target_real, root_real) or self._target_real == root_real:
                raise UsageError(f"target {target} escapes the project root")
        self._files = set()
        if allow_lock:
            self._files.add(_norm(self.root / LOCK_NAME))
        if allow_manifest:
            self._files.add(_norm(self.root / MANIFEST_NAME))
        for f in extra_files:
            f = Path(f)
            self._files.add(_norm(f if f.is_absolute() else self.root / f))

    def check(self, path) -> Path:
        p = Path(path)
        real = _norm(p)
        if real in self._files or re.sub(r"\.warehouse-tmp-\d+$", "", real) in self._files:
            return p
        if self._target_real is not None and _inside(real, self._target_real) and real != self._target_real:
            return p
        raise GuardError(f"write outside allowed paths refused: {p}")

    def check_dir(self, path) -> Path:
        real = _norm(path)
        if self._target_real is not None and _inside(real, self._target_real):
            return Path(path)
        raise GuardError(f"directory outside target refused: {path}")


REPLACE_RETRIES = 3


def atomic_write(guard: WriteGuard, path, data: bytes) -> None:
    path = Path(path)
    guard.check(path)
    tmp_name = path.with_name(f"{path.name}.warehouse-tmp-{os.getpid()}")
    guard.check(tmp_name)
    if not path.parent.exists():
        if guard.target_dir is not None and _inside(_norm(path.parent), _norm(guard.target_dir)):
            guard.check_dir(path.parent)
        path.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp_name, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    try:
        for attempt in range(REPLACE_RETRIES + 1):
            try:
                os.replace(tmp_name, path)
                return
            except PermissionError:
                if attempt == REPLACE_RETRIES:
                    raise
                time.sleep(0.1)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def delete_file(guard: WriteGuard, path) -> None:
    path = Path(path)
    guard.check(path)
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def prune_empty_dirs(guard: WriteGuard, start_dir) -> None:
    if guard.target_dir is None:
        return
    top = _norm(guard.target_dir)
    d = Path(start_dir)
    while True:
        real = _norm(d)
        if real == top or not _inside(real, top):
            return
        try:
            d.rmdir()
        except OSError:
            return
        d = d.parent


TEMP_RE = re.compile(r"^.+\.warehouse-tmp-\d+$")


def is_temp_name(name: str) -> bool:
    """Exactly the names atomic_write creates: '<name>.warehouse-tmp-<pid>'."""
    return bool(TEMP_RE.match(name))


def cleanup_temp_files(guard: WriteGuard) -> None:
    for base in (LOCK_NAME, MANIFEST_NAME):
        for entry in guard.root.glob(f"{base}.warehouse-tmp-*"):
            if is_temp_name(entry.name) and entry.is_file():
                try:
                    entry.unlink()
                except OSError:
                    pass
    if guard.target_dir is None or not guard.target_dir.is_dir():
        return
    for dp, _, files in os.walk(guard.target_dir):
        for f in files:
            if is_temp_name(f):
                p = Path(dp) / f
                guard.check(p)
                try:
                    p.unlink()
                except OSError:
                    pass
