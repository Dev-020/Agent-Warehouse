"""Pytest fixtures and configuration for backlog-cli tests."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest

# Add tools/backlog-cli to sys.path so backlog_cli and task are importable
CLI_DIR = Path(__file__).resolve().parents[1]
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

import task
from backlog_cli.layouts import get_layout
from backlog_cli.settings import load_settings


@pytest.fixture(scope="session", autouse=True)
def hermetic_git_env(tmp_path_factory):
    """Isolate tests from user/system git config (Q2, [[testing]] §3)."""
    cfg_dir = tmp_path_factory.mktemp("git_isolation")
    empty_cfg = cfg_dir / "empty_gitconfig"
    empty_cfg.write_text("", encoding="utf-8")

    old_global = os.environ.get("GIT_CONFIG_GLOBAL")
    old_nosystem = os.environ.get("GIT_CONFIG_NOSYSTEM")

    os.environ["GIT_CONFIG_GLOBAL"] = str(empty_cfg)
    os.environ["GIT_CONFIG_NOSYSTEM"] = "1"
    try:
        yield
    finally:
        if old_global is None:
            os.environ.pop("GIT_CONFIG_GLOBAL", None)
        else:
            os.environ["GIT_CONFIG_GLOBAL"] = old_global
        if old_nosystem is None:
            os.environ.pop("GIT_CONFIG_NOSYSTEM", None)
        else:
            os.environ["GIT_CONFIG_NOSYSTEM"] = old_nosystem


def make_repo(path: Path) -> Path:
    """Create a temporary git repository with user config and an initial commit on main."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "core.autocrlf", "false"], cwd=str(path), check=True)
    (path / "README.md").write_text("# Test Repository\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(path), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial commit"], cwd=str(path), check=True)
    return path


_TEMPLATE_BASE: Path | None = None
_TEMPLATE_CACHE: dict[str, Path] = {}


@pytest.fixture(scope="session", autouse=True)
def _session_template_base(tmp_path_factory):
    global _TEMPLATE_BASE
    _TEMPLATE_BASE = tmp_path_factory.mktemp("layout_templates")


def _create_layout_template(layout: str, base_dir: Path) -> Path:
    repo = make_repo(base_dir / f"tpl_{layout}")
    if layout == "single":
        backlog_text = (
            "# Project Backlog\n\n"
            "> **How this backlog is run** (`convention/backlog`)\n"
            "> - **Layout:** single file\n"
            "> - **Entry style:** full\n\n"
            "## 📋 In Progress\n\n"
            "## 📌 Backlog (Open Tasks)\n\n"
            "## ✅ Completed\n\n"
            "## 🧊 Icebox (Not Doing / Rejected)\n"
        )
        (repo / "BACKLOG.md").write_text(backlog_text, encoding="utf-8")
        subprocess.run(["git", "add", "BACKLOG.md"], cwd=str(repo), check=True)
    elif layout == "split":
        (repo / ".warehouse.yml").write_text("settings:\n  backlog_layout: split\n", encoding="utf-8")
        bdir = repo / "BACKLOG"
        bdir.mkdir(parents=True)
        (bdir / "00_BACKLOG.md").write_text(
            "> **How this backlog is run** (`convention/backlog`)\n"
            "> - **Layout:** split files\n"
            "> - **Entry style:** full\n",
            encoding="utf-8",
        )
        (bdir / "Open.md").write_text(
            "## 📋 In Progress\n\n## 📌 Backlog (Open Tasks)\n", encoding="utf-8"
        )
        (bdir / "Closed.md").write_text(
            "## ✅ Completed\n\n## 🧊 Icebox (Not Doing / Rejected)\n", encoding="utf-8"
        )
        (repo / ".gitattributes").write_text("BACKLOG/Closed.md merge=union\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True)
    elif layout == "folders":
        (repo / ".warehouse.yml").write_text("settings:\n  backlog_layout: folders\n", encoding="utf-8")
        bdir = repo / "BACKLOG"
        bdir.mkdir(parents=True)
        (bdir / "00_BACKLOG.md").write_text(
            "> **How this backlog is run** (`convention/backlog`)\n"
            "> - **Layout:** item folders\n"
            "> - **Entry style:** full\n",
            encoding="utf-8",
        )
        (bdir / "open").mkdir(parents=True)
        (bdir / "closed").mkdir(parents=True)
        (bdir / "open" / ".gitkeep").write_text("", encoding="utf-8")
        (bdir / "closed" / ".gitkeep").write_text("", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "add backlog"], cwd=str(repo), check=True)
    return repo


def _init_repo_with_backlog(path: Path, layout: str = "single") -> Path:
    """Create a test repository seeded from a shared session template."""
    global _TEMPLATE_BASE
    if _TEMPLATE_BASE is None:
        _TEMPLATE_BASE = Path(tempfile.mkdtemp(prefix="tpl_fallback_"))
    if layout not in _TEMPLATE_CACHE:
        _TEMPLATE_CACHE[layout] = _create_layout_template(layout, _TEMPLATE_BASE)
    template = _TEMPLATE_CACHE[layout]
    shutil.copytree(str(template), str(path), dirs_exist_ok=True)
    return path


def _format_entry_md(it: dict[str, Any]) -> str:
    tid = it["id"]
    title = it.get("title", f"Task {tid}")
    status = it.get("status", "Open")
    priority = it.get("priority", "P2")
    created = it.get("created", "2026-10-01")
    lines = [f"### [{tid}] {title}"]
    lines.append(f"- **Status**: `{status}` | **Priority**: `{priority}`")
    lines.append(f"- **Created**: {created}")
    if "resolved" in it:
        lines.append(f"- **Resolved**: {it['resolved']}")
    if "depends_on" in it and it["depends_on"]:
        deps = ", ".join(f"[{d}]" for d in it["depends_on"])
        lines.append(f"- **Depends on**: {deps}")
    if "why" in it and it["why"]:
        lines.append(f"**Why:** {it['why']}")
    if "wanted" in it and it["wanted"]:
        lines.append(f"**Wanted:** {it['wanted']}")
    if "criteria" in it and it["criteria"]:
        if it.get("style") == "compact":
            lines.append(f"*Done when:* {it['criteria'][0]}")
        else:
            lines.append("#### Acceptance Criteria")
            for idx, c in enumerate(it["criteria"], 1):
                lines.append(f"- [ ] #{idx} {c}")
    if "notes" in it and it["notes"]:
        lines.append("#### Notes")
        for n in it["notes"]:
            lines.append(f"- {n}")
    if it.get("style") != "compact":
        lines.append("#### Outcome")
        if "outcome" in it and it["outcome"]:
            lines.append(it["outcome"])
    return "\n".join(lines) + "\n"


def _format_folder_item(it: dict[str, Any]) -> tuple[str, str]:
    tid = it["id"]
    title = it.get("title", f"Task {tid}")
    status = it.get("status", "Open")
    priority = it.get("priority", "P2")
    created = it.get("created", "2026-10-01")
    clean_id = tid.lstrip("#")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")
    filename = f"{clean_id}-{slug}.md" if slug else f"{clean_id}.md"

    fm = [
        "---",
        f'id: "{tid}"',
        f'title: "{title}"',
        f"status: {status}",
        f"priority: {priority}",
        f"created: {created}",
    ]
    if "resolved" in it:
        fm.append(f"resolved: {it['resolved']}")
    if "depends_on" in it and it["depends_on"]:
        fm.append(f"depends_on: {json.dumps(it['depends_on'])}")
    fm.append("---")
    body = [f"# [{tid}] {title}"]
    if "why" in it and it["why"]:
        body.append(f"**Why:** {it['why']}")
    if "wanted" in it and it["wanted"]:
        body.append(f"**Wanted:** {it['wanted']}")
    if "notes" in it and it["notes"]:
        body.append("## Notes")
        for n in it["notes"]:
            body.append(f"- {n}")
    content = "\n".join(fm) + "\n" + "\n".join(body) + "\n"
    return filename, content


def seed_items(
    repo: Path,
    layout: str,
    items: list[dict[str, Any]] | None = None,
    *,
    open_entries: str = "",
    closed_entries: str = "",
    folders_open: dict[str, str] | None = None,
    folders_closed: dict[str, str] | None = None,
) -> None:
    """Seed items directly into repo backlog files for any layout, then make one commit."""
    settings = load_settings(repo)
    if items is not None:
        open_parts = []
        in_prog_parts = []
        comp_parts = []
        ice_parts = []
        f_open = {}
        f_closed = {}

        for it in items:
            st = it.get("status", "Open")
            md = _format_entry_md(it)
            fname, fcontent = _format_folder_item(it)

            if st == "Open":
                open_parts.append(md)
                f_open[fname] = fcontent
            elif st == "In Progress":
                in_prog_parts.append(md)
                f_open[fname] = fcontent
            elif st == "Completed":
                comp_parts.append(md)
                f_closed[fname] = fcontent
            else:  # Rejected / Cancelled / Icebox
                ice_parts.append(md)
                f_closed[fname] = fcontent

        if layout == "single":
            single_text = (
                "# Project Backlog\n\n"
                "> **How this backlog is run** (`convention/backlog`)\n"
                "> - **Layout:** single file\n"
                "> - **Entry style:** full\n\n"
                "## 📋 In Progress\n"
                + ("\n" + "".join(in_prog_parts) if in_prog_parts else "\n")
                + "## 📌 Backlog (Open Tasks)\n"
                + ("\n" + "".join(open_parts) if open_parts else "\n")
                + "## ✅ Completed\n"
                + ("\n" + "".join(comp_parts) if comp_parts else "\n")
                + "## 🧊 Icebox (Not Doing / Rejected)\n"
                + ("\n" + "".join(ice_parts) if ice_parts else "")
            )
            settings.backlog_file.write_text(single_text, encoding="utf-8")
        elif layout == "split":
            open_text = (
                "## 📋 In Progress\n"
                + ("\n" + "".join(in_prog_parts) if in_prog_parts else "\n")
                + "## 📌 Backlog (Open Tasks)\n"
                + ("\n" + "".join(open_parts) if open_parts else "")
            )
            closed_text = (
                "## ✅ Completed\n"
                + ("\n" + "".join(comp_parts) if comp_parts else "\n")
                + "## 🧊 Icebox (Not Doing / Rejected)\n"
                + ("\n" + "".join(ice_parts) if ice_parts else "")
            )
            (settings.backlog_dir / "Open.md").write_text(open_text, encoding="utf-8")
            (settings.backlog_dir / "Closed.md").write_text(closed_text, encoding="utf-8")
        else:  # folders
            for fn, cnt in f_open.items():
                (settings.backlog_dir / "open" / fn).write_text(cnt, encoding="utf-8")
            for fn, cnt in f_closed.items():
                (settings.backlog_dir / "closed" / fn).write_text(cnt, encoding="utf-8")
    else:
        # Caller provided pre-formatted strings/dicts
        if layout == "single":
            single_text = (
                "# Project Backlog\n\n"
                "## 📋 In Progress\n\n"
                "## 📌 Backlog (Open Tasks)\n"
                f"{open_entries}\n"
                "## ✅ Completed\n"
                f"{closed_entries}\n"
                "## 🧊 Icebox (Not Doing / Rejected)\n"
            )
            settings.backlog_file.write_text(single_text, encoding="utf-8")
        elif layout == "split":
            open_text = f"## 📋 In Progress\n\n## 📌 Backlog (Open Tasks)\n{open_entries}\n"
            closed_text = f"## ✅ Completed\n{closed_entries}\n## 🧊 Icebox (Not Doing / Rejected)\n"
            (settings.backlog_dir / "Open.md").write_text(open_text, encoding="utf-8")
            (settings.backlog_dir / "Closed.md").write_text(closed_text, encoding="utf-8")
        else:
            if folders_open:
                for fname, content in folders_open.items():
                    (settings.backlog_dir / "open" / fname).write_text(content, encoding="utf-8")
            if folders_closed:
                for fname, content in folders_closed.items():
                    (settings.backlog_dir / "closed" / fname).write_text(content, encoding="utf-8")

    subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed test items"], cwd=str(repo), check=True)


def make_claim_branch(repo: Path, task_id: str) -> None:
    """Create claim/<ID> branch overlay without a worktree."""
    clean_id = task_id.strip().strip("'\"").strip("[]").lstrip("#")
    subprocess.run(["git", "branch", f"claim/{clean_id}"], cwd=str(repo), check=True)


def make_claim(repo: Path, task_id: str, layout: str = "single", base_branch: str = "main") -> Path:
    """Build exactly the state claim leaves (branch, worktree, status In Progress, commit)."""
    clean_id = task_id.strip().strip("'\"").strip("[]").lstrip("#")
    branch = f"claim/{clean_id}"
    settings = load_settings(repo)
    target_dir = (settings.worktree_root / clean_id).resolve()
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "worktree", "add", "-b", branch, str(target_dir), base_branch], cwd=str(repo), check=True)

    wt_settings = load_settings(target_dir)
    wt_layout = get_layout(wt_settings)
    wt_layout.set_status(task_id, "In Progress")

    paths = [str(p) for p in wt_layout.paths_for(task_id)]
    subprocess.run(["git", "add"] + paths, cwd=str(target_dir), check=True)
    summary = f"chore(backlog): claim [{task_id}]"[:72]
    subprocess.run(["git", "commit", "-q", "-m", summary], cwd=str(target_dir), check=True)
    return target_dir


class RunResult:
    """Result of running task.main CLI helper."""

    def __init__(self, exit_code: int, output: str, stdout: str = "", stderr: str = ""):
        self.exit_code = exit_code
        self.output = output
        self.stdout = stdout
        self.stderr = stderr

    def __iter__(self):
        return iter((self.exit_code, self.output))

    def __getitem__(self, item):
        return (self.exit_code, self.output)[item]

    def __eq__(self, other):
        if isinstance(other, tuple) and len(other) == 2:
            return (self.exit_code, self.output) == other
        return super().__eq__(other)

    def __repr__(self):
        return f"RunResult(exit_code={self.exit_code}, output={self.output!r})"


@pytest.fixture
def run_cli(monkeypatch, capsys):
    """Run task.main in the specified directory, returning (exit_code, output)."""

    def _run(cwd: Path, *args: str) -> RunResult:
        monkeypatch.chdir(cwd)
        try:
            exit_code = task.main(list(args))
        except SystemExit as exc:
            exit_code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        return RunResult(exit_code, combined, captured.out, captured.err)

    return _run
