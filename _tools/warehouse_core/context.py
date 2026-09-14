"""Context: warehouse root, config, git, catalog, today, run lock (D9)."""
from __future__ import annotations

import contextlib
import datetime as dt
import json
import os
import re
import time
from pathlib import Path

from . import config as config_mod
from . import manifest as manifest_mod
from .catalog import Catalog
from .errors import GitError, UsageError
from .gitrepo import Git, register_warehouse_root

STALE_SECONDS = 30 * 60


class Context:
    def __init__(self, *, warehouse: str | None = None, config: str | None = None, project: str | None = None,
                 today: str | None = None, json_out: bool = False, verbose: bool = False):
        root = warehouse or os.environ.get("WAREHOUSE_ROOT")
        self.warehouse_root = Path(root).resolve() if root else Path(__file__).resolve().parents[2]
        register_warehouse_root(self.warehouse_root)
        self.config_path = config or os.environ.get("WAREHOUSE_CONFIG")
        self.project_arg = project
        today = today or os.environ.get("WAREHOUSE_TODAY")
        if today:
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", today):
                raise UsageError("--today must be YYYY-MM-DD")
            self.today = today
        else:
            self.today = dt.date.today().isoformat()
        self.json = json_out
        self.verbose = verbose
        self.git = Git(self.warehouse_root)
        self._config = None
        self._catalog = None

    @property
    def config(self) -> config_mod.Config:
        if self._config is None:
            self._config = config_mod.load(self.warehouse_root, Path(self.config_path) if self.config_path else None)
        return self._config

    @property
    def catalog(self) -> Catalog:
        if self._catalog is None:
            self._catalog = Catalog(self.git)
        return self._catalog

    def invalidate_catalog(self) -> None:
        self._catalog = None

    @property
    def state_dir(self) -> Path:
        return self.warehouse_root / "_tools" / ".state"

    def project_root(self) -> Path:
        start = Path(self.project_arg) if self.project_arg else Path.cwd()
        return manifest_mod.find_project_root(start)

    # ------------------------------------------------------------------ run lock
    @contextlib.contextmanager
    def run_lock(self):
        """Yields True if acquired, False if busy."""
        self.state_dir.mkdir(parents=True, exist_ok=True)
        path = self.state_dir / "run.lock"
        acquired = False
        for _ in range(2):
            try:
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, "w") as fh:
                    fh.write(json.dumps({"pid": os.getpid(), "time": time.time()}))
                acquired = True
                break
            except FileExistsError:
                try:
                    started = json.loads(path.read_text()).get("time", 0)
                except (OSError, ValueError):
                    started = path.stat().st_mtime if path.exists() else 0
                if time.time() - started > STALE_SECONDS:
                    with contextlib.suppress(OSError):
                        path.unlink()
                    continue
                break
        try:
            yield acquired
        finally:
            if acquired:
                with contextlib.suppress(OSError):
                    path.unlink()

    def busy_error(self) -> GitError:
        return GitError("another warehouse run is active (_tools/.state/run.lock)")

    # ------------------------------------------------------------------ auto-sync state
    def read_auto_state(self) -> dict:
        p = self.state_dir / "auto-sync.json"
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def write_auto_state(self, digest: str, needs_retry: bool = False) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        p = self.state_dir / "auto-sync.json"
        p.write_text(json.dumps({"tags_digest": digest, "needs_retry": bool(needs_retry),
                                 "at": dt.datetime.now().isoformat(timespec="seconds")},
                                sort_keys=True) + "\n", encoding="utf-8")
