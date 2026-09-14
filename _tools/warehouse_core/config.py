"""warehouse.config.yml (+ warehouse.config.local.yml) (DESIGN §2.1)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .errors import UsageError

DEFAULT_SKIP = [".git", "node_modules", ".claude", ".venv", "venv", "__pycache__", ".pytest_cache",
                ".obsidian", ".trash", "dist", "build", "worktrees"]
DEFAULT_EXCLUDE = ["tests/**", "**/desktop.ini", "**/.gitkeep", "**/__pycache__/**", "**/*.pyc"]
KEYS = {"config_version", "project_roots", "max_depth", "skip_dirs", "sync_exclude"}
LOCAL_KEYS = {"project_roots", "max_depth"}


@dataclass
class Config:
    project_roots: list[Path] = field(default_factory=list)
    max_depth: int = 4
    skip_dirs: list[str] = field(default_factory=lambda: list(DEFAULT_SKIP))
    sync_exclude: list[str] = field(default_factory=lambda: list(DEFAULT_EXCLUDE))
    warnings: list[str] = field(default_factory=list)


def _read(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise UsageError(f"{path.name} is not valid YAML: {e}") from None
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise UsageError(f"{path.name} must be a mapping")
    return data


def _apply(cfg: Config, data: dict, base: Path, allowed: set, name: str) -> None:
    unknown = set(data) - allowed
    if unknown:
        raise UsageError(f"{name}: unknown key(s) {sorted(unknown)}")
    if "project_roots" in data:
        roots = data["project_roots"] or []
        if not isinstance(roots, list) or not all(isinstance(r, str) for r in roots):
            raise UsageError(f"{name}: project_roots must be a list of strings")
        cfg.project_roots = []
        for r in roots:
            p = Path(r)
            if not p.is_absolute():
                p = base / p
            cfg.project_roots.append(p)
    if "max_depth" in data:
        d = data["max_depth"]
        if isinstance(d, bool) or not isinstance(d, int) or not 1 <= d <= 10:
            raise UsageError(f"{name}: max_depth must be an integer 1-10")
        cfg.max_depth = d
    for key in ("skip_dirs", "sync_exclude"):
        if key in data:
            v = data[key] or []
            if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
                raise UsageError(f"{name}: {key} must be a list of strings")
            setattr(cfg, key, list(v))


def load(warehouse_root: Path, config_path: Path | None = None) -> Config:
    warehouse_root = Path(warehouse_root)
    path = Path(config_path) if config_path else warehouse_root / "warehouse.config.yml"
    if not path.is_file():
        raise UsageError(f"config file not found: {path}")
    data = _read(path)
    if data.get("config_version") != 1:
        raise UsageError(f"{path.name}: config_version must be 1")
    cfg = Config()
    _apply(cfg, data, warehouse_root, KEYS, path.name)
    local = warehouse_root / "warehouse.config.local.yml"
    if local.is_file():
        _apply(cfg, _read(local), warehouse_root, LOCAL_KEYS, local.name)
    for r in cfg.project_roots:
        if not r.is_dir():
            cfg.warnings.append(f"project root not found: {r.as_posix()}")
    return cfg
