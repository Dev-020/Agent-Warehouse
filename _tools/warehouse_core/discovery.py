"""Find projects (.warehouse.yml) under the configured roots (DESIGN §2.1, §7 nested projects)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from . import manifest as manifest_mod
from .config import Config
from .errors import UsageError

VAULT_MARKERS = (".obsidian",)

CODEBASE_MARKERS = (
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "setup.py",
    "go.mod",
    "Cargo.toml",
    "pom.xml",
    "tsconfig.json",
    "deno.json",
    "index.html",
    "composer.json",
    "Gemfile",
    "build.gradle",
)

CODEBASE_GLOBS = (
    "*.csproj",
    "*.sln",
)


def detect_project_types(root: Path) -> set[str]:
    root = Path(root)
    types: set[str] = set()
    for vm in VAULT_MARKERS:
        if (root / vm).is_dir():
            types.add("vault")
            break
    for marker in CODEBASE_MARKERS:
        if (root / marker).is_file():
            types.add("codebase")
            break
    if "codebase" not in types:
        for glob_pat in CODEBASE_GLOBS:
            if any(root.glob(glob_pat)):
                types.add("codebase")
                break
    return types


@dataclass
class Project:
    root: Path
    manifest: manifest_mod.Manifest | None
    error: str | None = None

    @property
    def name(self) -> str:
        return self.root.as_posix()


def _key(p) -> str:
    return os.path.normcase(os.path.realpath(p))


def load_project(root: Path) -> Project:
    try:
        return Project(Path(root), manifest_mod.load(root))
    except UsageError as e:
        return Project(Path(root), None, str(e))


def _is_link(entry: os.DirEntry) -> bool:
    try:
        return entry.is_symlink() or os.path.isjunction(entry.path)
    except OSError:
        return True


def is_linked_worktree(d: Path) -> bool:
    """A linked git worktree has a `.git` FILE whose `gitdir:` points into `<repo>/.git/worktrees/<name>`.
    Its `.warehouse.yml` is a checkout of the main project's, so it is never a separate project."""
    g = d / ".git"
    try:
        if not g.is_file():
            return False
        first = g.read_text(encoding="utf-8", errors="replace").splitlines()[0].strip()
    except (OSError, IndexError):
        return False
    if not first.lower().startswith("gitdir:"):
        return False
    pointer = first[len("gitdir:"):].strip().replace("\\", "/")
    return "/worktrees/" in pointer


def find_projects(config: Config, warehouse_root: Path) -> list[Project]:
    wh_key = _key(warehouse_root)
    skip = {s.lower() for s in config.skip_dirs}
    found: dict[str, Project] = {}

    def walk(d: Path, depth: int):
        if _key(d) == wh_key or is_linked_worktree(d):
            return
        target_key = None
        if (d / manifest_mod.MANIFEST_NAME).is_file():
            k = _key(d)
            if k not in found:
                proj = load_project(d)
                found[k] = proj
            proj = found[k]
            target = proj.manifest.target if proj.manifest else "warehouse"
            target_key = _key(d / target)
        if depth >= config.max_depth:
            return
        try:
            entries = sorted(os.scandir(d), key=lambda e: e.name)
        except OSError:
            return
        for e in entries:
            if not e.is_dir(follow_symlinks=False) or _is_link(e):
                continue
            if e.name.lower() in skip:
                continue
            if target_key is not None and _key(e.path) == target_key:
                continue
            walk(Path(e.path), depth + 1)

    for r in config.project_roots:
        if Path(r).is_dir():
            walk(Path(r), 0)
    return sorted(found.values(), key=lambda p: p.root.as_posix().lower())


def target_contains_project(project: Project) -> bool:
    if project.manifest is None:
        return False
    t = project.root / project.manifest.target
    if not t.is_dir():
        return False
    for dp, dirs, files in os.walk(t):
        if manifest_mod.MANIFEST_NAME in files:
            return True
    return False
