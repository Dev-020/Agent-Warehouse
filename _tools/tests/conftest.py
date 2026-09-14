"""Fixtures: a throwaway warehouse git repo and fake projects, all under pytest's tmp_path.

Tests never touch real projects or the real warehouse repo.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from warehouse_core import cli, gitrepo  # noqa: E402
from warehouse_core.items import DOCUMENT_KINDS, KINDS, kind_of, name_of  # noqa: E402

TODAY = "2026-09-20"
GIT_ENV_STRIP = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX")

INDEX_TEXT = """---
type: index
updated: 2026-09-14
---

# Warehouse Index

## How to read this

Hand-written intro that must survive.

## Catalog

<!-- warehouse:catalog:start -->
<!-- warehouse:catalog:end -->

## Recent releases

<!-- warehouse:releases:start -->
<!-- warehouse:releases:end -->

## Reference (not synced)

- [[warehouse-architecture]]
"""


def git(cwd, *args, env_extra=None, check=True) -> str:
    env = {k: v for k, v in os.environ.items() if k not in GIT_ENV_STRIP}
    if env_extra:
        env.update(env_extra)
    cp = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, env=env)
    if check and cp.returncode != 0:
        raise RuntimeError(f"git {args} failed: {cp.stderr.decode(errors='replace')}")
    return cp.stdout.decode("utf-8", "replace")


def git_init(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", "main")
    for k, v in [("user.name", "Test"), ("user.email", "test@example.invalid"), ("commit.gpgsign", "false"),
                 ("tag.gpgsign", "false"), ("core.autocrlf", "false"), ("core.safecrlf", "false"),
                 ("core.hooksPath", str(path / ".git" / "hooks"))]:
        git(path, "config", k, v)


def sha(b: bytes) -> str:
    return "sha256:" + hashlib.sha256(b).hexdigest()


def snapshot(root: Path) -> dict[str, str]:
    out = {}
    for dp, dirs, files in os.walk(root):
        if ".git" in dirs:
            dirs.remove(".git")
        for f in files:
            p = Path(dp) / f
            out[p.relative_to(root).as_posix()] = sha(p.read_bytes())
    return out


class Warehouse:
    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.root = tmp / "wh"
        self.projects_dir = tmp / "projects"
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.config = self.root / "warehouse.config.yml"
        self.today = TODAY
        self.history: dict[str, list[tuple[str, str]]] = {}
        git_init(self.root)
        for folder in KINDS.values():
            (self.root / folder).mkdir(parents=True, exist_ok=True)
        (self.root / "_registry").mkdir()
        (self.root / "_tools").mkdir()
        (self.root / "00_INDEX.md").write_bytes(INDEX_TEXT.encode())
        (self.root / ".gitignore").write_bytes(b"_tools/.state/\n__pycache__/\n")
        self.write_config()
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "init")

    def write_config(self, **overrides) -> None:
        data = {"config_version": 1, "project_roots": [self.projects_dir.as_posix()], "max_depth": 4,
                "skip_dirs": [".git", "node_modules", ".claude", ".venv", "venv", "__pycache__", ".pytest_cache",
                              ".obsidian", ".trash", "dist", "build", "worktrees"],
                "sync_exclude": ["tests/**", "**/desktop.ini", "**/.gitkeep", "**/__pycache__/**", "**/*.pyc"]}
        data.update(overrides)
        self.config.write_bytes(json.dumps(data, indent=2).encode())

    # ------------------------------------------------------------------ items
    def _frontmatter(self, item_id, version, status, settings, requires, replaces, tool_fields) -> str:
        if status is None:
            status = "draft" if version.startswith("0.") else "canonical"
        lines = ["---", f"id: {item_id}", f"version: {version}", f"status: {status}",
                 f"summary: Summary of {item_id}.", "applies-to: [vault, codebase]",
                 f"settings: {json.dumps(settings or {})}", f"requires: {json.dumps(requires or [])}",
                 f"replaces: {replaces if replaces else 'null'}"]
        if kind_of(item_id) == "tool":
            tf = {"entrypoint": "main.py", "requires-software": [], "platforms": []}
            tf.update(tool_fields or {})
            lines += [f"entrypoint: {tf['entrypoint']}", f"requires-software: {json.dumps(tf['requires-software'])}",
                      f"platforms: {json.dumps(tf['platforms'])}"]
        lines.append("---")
        return "\n".join(lines) + "\n"

    def _changelog(self, item_id, unreleased: str, document: bool) -> str:
        h2, h3, h4 = ("##", "###", "####") if document else ("#", "##", "###")
        out = [f"{h2} Changelog", "", f"{h3} [Unreleased]"]
        if unreleased:
            out += [f"{h4} Added", unreleased.rstrip("\n")]
        out.append("")
        for version, notes in reversed(self.history.get(item_id, [])):
            out += [f"{h3} [{version}] - 2026-09-14", *[l for l in notes.rstrip("\n").split("\n")], ""]
        return "\n".join(out)

    def write_item(self, item_id, version, body="Body text.\n", *, settings=None, requires=None, files=None,
                   status=None, replaces=None, tool_fields=None, unreleased="", record=None) -> Path:
        """Write the working-tree item. `record` (changelog notes) appends a released section for `version`."""
        if record is not None:
            self.history.setdefault(item_id, []).append((version, record))
        fm = self._frontmatter(item_id, version, status, settings, requires, replaces, tool_fields)
        document = kind_of(item_id) in DOCUMENT_KINDS
        title = f"# {name_of(item_id)}\n\n"
        if document:
            path = self.root / KINDS[kind_of(item_id)] / f"{name_of(item_id)}.md"
            path.write_bytes((fm + "\n" + title + body + "\n" + self._changelog(item_id, unreleased, True)).encode())
            return path
        folder = self.root / KINDS[kind_of(item_id)] / name_of(item_id)
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir(parents=True)
        main = "SKILL.md" if kind_of(item_id) == "skill" else "TOOL.md"
        (folder / main).write_bytes((fm + "\n" + title + body).encode())
        (folder / "CHANGELOG.md").write_bytes(self._changelog(item_id, unreleased, False).encode())
        files = dict(files or {})
        if kind_of(item_id) == "tool":
            files.setdefault("main.py", "print('tool')\n")
        for rel, content in files.items():
            p = folder / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(content.encode() if isinstance(content, str) else content)
        return folder

    def commit(self, msg="wip") -> None:
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "--allow-empty", "-m", msg, env_extra={"WAREHOUSE_RELEASING": "1"})

    def tag_raw(self, item_id, version) -> None:
        self.commit(f"release {item_id}@{version}")
        git(self.root, "tag", "-a", f"{item_id}@{version}", "-m", f"{item_id} {version}")

    def publish(self, item_id, version, body="Body text.\n", notes=None, **kw) -> None:
        """Write the item at `version` with a changelog section, commit and tag it (bypasses `release`)."""
        self.write_item(item_id, version, body, record=notes or "#### Added\n- Release " + version + ".", **kw)
        self.tag_raw(item_id, version)

    # ------------------------------------------------------------------ projects
    def project(self, name, manifest_text, *, git_repo=True, parent: Path | None = None) -> Path:
        root = (parent or self.projects_dir) / name
        root.mkdir(parents=True, exist_ok=True)
        (root / ".warehouse.yml").write_bytes(manifest_text.encode())
        if git_repo:
            git_init(root)
            (root / "own.txt").write_bytes(b"project file\n")
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", "project init")
        return root

    # ------------------------------------------------------------------ running
    def run(self, *argv, project: Path | None = None, today: str | None = None) -> tuple[int, str]:
        args = ["--warehouse", str(self.root), "--config", str(self.config), "--today", today or self.today]
        if project is not None:
            args += ["--project", str(project)]
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(args + list(argv))
        return code, out.getvalue() + err.getvalue()

    def lock(self, project: Path) -> dict:
        return json.loads((project / ".warehouse.lock").read_text(encoding="utf-8"))


@pytest.fixture
def wh(tmp_path, monkeypatch) -> Warehouse:
    for var in ("WAREHOUSE_CONFIG", "WAREHOUSE_TODAY", *GIT_ENV_STRIP):
        monkeypatch.delenv(var, raising=False)
    w = Warehouse(tmp_path)
    monkeypatch.setenv("WAREHOUSE_ROOT", str(w.root))
    assert Path(os.environ["WAREHOUSE_ROOT"]).resolve().is_relative_to(tmp_path.resolve())
    return w


@pytest.fixture
def git_spy(monkeypatch):
    calls: list[list[str]] = []
    real_run = subprocess.run

    def spy(cmd, *a, **kw):
        if isinstance(cmd, (list, tuple)) and cmd and os.path.basename(str(cmd[0])).lower() in ("git", "git.exe"):
            calls.append([str(c) for c in cmd] + [f"cwd={kw.get('cwd')}"])
        return real_run(cmd, *a, **kw)

    monkeypatch.setattr(gitrepo.subprocess, "run", spy)
    return calls


def copy_tool_into(wh: Warehouse) -> None:
    """Copy the tool (entry script, package, hooks) into the tmp warehouse, for real hook runs."""
    dest = wh.root / "_tools"
    shutil.copy2(TOOLS_DIR / "warehouse.py", dest / "warehouse.py")
    shutil.copytree(TOOLS_DIR / "warehouse_core", dest / "warehouse_core",
                    ignore=shutil.ignore_patterns("__pycache__", "desktop.ini"))
    shutil.copytree(TOOLS_DIR / "hooks", dest / "hooks", ignore=shutil.ignore_patterns("desktop.ini"))
