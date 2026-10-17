"""Tests for manifest parsing, settings resolution, precedence, and doctor output."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from backlog_cli import TaskError
from backlog_cli.settings import load_settings, read_manifest_settings


# ---------------------------------------------------------------------------
# Manifest Parser
# ---------------------------------------------------------------------------


def test_manifest_no_file(tmp_path: Path):
    assert read_manifest_settings(tmp_path) == {}


def test_manifest_quoted_and_unquoted(tmp_path: Path):
    manifest = tmp_path / ".warehouse.yml"
    manifest.write_text(
        'settings:\n  backlog_layout: "split"\n  backlog_file: \'CUSTOM.md\'\n  backlog_dir: TASKS\n',
        encoding="utf-8",
    )
    res = read_manifest_settings(tmp_path)
    assert res == {
        "backlog_layout": "split",
        "backlog_file": "CUSTOM.md",
        "backlog_dir": "TASKS",
    }


def test_manifest_comments(tmp_path: Path):
    manifest = tmp_path / ".warehouse.yml"
    manifest.write_text(
        "settings: # top-level settings\n"
        "  # a full line comment\n"
        "  backlog_layout: split # layout comment\n"
        "  backlog_file: \"BACKLOG.md\" # file comment\n",
        encoding="utf-8",
    )
    res = read_manifest_settings(tmp_path)
    assert res["backlog_layout"] == "split"
    assert res["backlog_file"] == "BACKLOG.md"


def test_manifest_empty_block(tmp_path: Path):
    manifest = tmp_path / ".warehouse.yml"
    manifest.write_text("settings: {}\n", encoding="utf-8")
    assert read_manifest_settings(tmp_path) == {}


def test_manifest_nested_blocks_skipped(tmp_path: Path):
    manifest = tmp_path / ".warehouse.yml"
    manifest.write_text(
        "settings:\n"
        "  other_plugin:\n"
        "    nested_key: value\n"
        "    list_key:\n"
        "      - item1\n"
        "      - item2\n"
        "  backlog_layout: folders\n",
        encoding="utf-8",
    )
    res = read_manifest_settings(tmp_path)
    assert res == {"backlog_layout": "folders"}


def test_manifest_bom_and_crlf(tmp_path: Path):
    manifest = tmp_path / ".warehouse.yml"
    content = "\ufeffsettings:\r\n  backlog_layout: split\r\n  backlog_file: SPLIT.md\r\n"
    manifest.write_bytes(content.encode("utf-8"))
    res = read_manifest_settings(tmp_path)
    assert res == {"backlog_layout": "split", "backlog_file": "SPLIT.md"}


def test_manifest_non_scalar_backlog_key_fails(tmp_path: Path):
    manifest = tmp_path / ".warehouse.yml"
    # Nested mapping for backlog key
    manifest.write_text(
        "settings:\n"
        "  some_other: val\n"
        "  backlog_layout:\n"
        "    nested: fail\n",
        encoding="utf-8",
    )
    with pytest.raises(TaskError) as exc_info:
        read_manifest_settings(tmp_path)
    err = str(exc_info.value)
    assert "backlog_layout" in err
    assert "Line 3:" in err  # line number 3

    # Inline list for backlog key
    manifest.write_text(
        "settings:\n"
        "  backlog_file: [a, b]\n",
        encoding="utf-8",
    )
    with pytest.raises(TaskError) as exc_info:
        read_manifest_settings(tmp_path)
    err = str(exc_info.value)
    assert "backlog_file" in err
    assert "Line 2:" in err  # line number 2


# ---------------------------------------------------------------------------
# Precedence Rules (Decision 2)
# ---------------------------------------------------------------------------


def test_precedence_layout(tmp_path: Path):
    # 1. Default
    s = load_settings(tmp_path, git_config=lambda _: None, environ={})
    assert s.layout == "single"
    assert s.sources["layout"] == "default"

    # 2. Manifest
    (tmp_path / ".warehouse.yml").write_text("settings:\n  backlog_layout: split\n", encoding="utf-8")
    s = load_settings(tmp_path, git_config=lambda _: None, environ={})
    assert s.layout == "split"
    assert s.sources["layout"] == ".warehouse.yml"

    # 3. Git config overrides manifest
    s = load_settings(
        tmp_path,
        git_config=lambda k: "folders" if k == "backlog.layout" else None,
        environ={},
    )
    assert s.layout == "folders"
    assert s.sources["layout"] == "git config backlog.layout"

    # 4. Env var overrides git config
    s = load_settings(
        tmp_path,
        git_config=lambda k: "folders" if k == "backlog.layout" else None,
        environ={"BACKLOG_LAYOUT": "single"},
    )
    assert s.layout == "single"
    assert s.sources["layout"] == "env BACKLOG_LAYOUT"


def test_precedence_backlog_file(tmp_path: Path):
    # 1. Default
    s = load_settings(tmp_path, git_config=lambda _: None, environ={})
    assert s.backlog_file == tmp_path / "BACKLOG.md"
    assert s.sources["backlog_file"] == "default"

    # 2. Manifest
    (tmp_path / ".warehouse.yml").write_text("settings:\n  backlog_file: MANIFEST.md\n", encoding="utf-8")
    s = load_settings(tmp_path, git_config=lambda _: None, environ={})
    assert s.backlog_file == tmp_path / "MANIFEST.md"
    assert s.sources["backlog_file"] == ".warehouse.yml"

    # 3. Git config overrides manifest
    s = load_settings(
        tmp_path,
        git_config=lambda k: "GIT.md" if k == "backlog.file" else None,
        environ={},
    )
    assert s.backlog_file == tmp_path / "GIT.md"
    assert s.sources["backlog_file"] == "git config backlog.file"

    # 4. BACKLOG_PATH env var overrides git config
    s = load_settings(
        tmp_path,
        git_config=lambda k: "GIT.md" if k == "backlog.file" else None,
        environ={"BACKLOG_PATH": "ENV_PATH.md"},
    )
    assert s.backlog_file == tmp_path / "ENV_PATH.md"
    assert s.sources["backlog_file"] == "env BACKLOG_PATH"

    # 5. BACKLOG_FILE env var overrides BACKLOG_PATH
    s = load_settings(
        tmp_path,
        git_config=lambda k: "GIT.md" if k == "backlog.file" else None,
        environ={"BACKLOG_FILE": "ENV_FILE.md", "BACKLOG_PATH": "ENV_PATH.md"},
    )
    assert s.backlog_file == tmp_path / "ENV_FILE.md"
    assert s.sources["backlog_file"] == "env BACKLOG_FILE"

    # 6. Flag --backlog-path overrides all
    s = load_settings(
        tmp_path,
        backlog_path="FLAG.md",
        git_config=lambda k: "GIT.md" if k == "backlog.file" else None,
        environ={"BACKLOG_FILE": "ENV_FILE.md"},
    )
    assert s.backlog_file == tmp_path / "FLAG.md"
    assert s.sources["backlog_file"] == "--backlog-path"


def test_precedence_backlog_dir(tmp_path: Path):
    # 1. Default
    s = load_settings(tmp_path, git_config=lambda _: None, environ={})
    assert s.backlog_dir == tmp_path / "BACKLOG"
    assert s.sources["backlog_dir"] == "default"

    # 2. Manifest
    (tmp_path / ".warehouse.yml").write_text("settings:\n  backlog_dir: MDIR\n", encoding="utf-8")
    s = load_settings(tmp_path, git_config=lambda _: None, environ={})
    assert s.backlog_dir == tmp_path / "MDIR"
    assert s.sources["backlog_dir"] == ".warehouse.yml"

    # 3. Git config
    s = load_settings(
        tmp_path,
        git_config=lambda k: "GDIR" if k == "backlog.dir" else None,
        environ={},
    )
    assert s.backlog_dir == tmp_path / "GDIR"
    assert s.sources["backlog_dir"] == "git config backlog.dir"

    # 4. Env var
    s = load_settings(
        tmp_path,
        git_config=lambda k: "GDIR" if k == "backlog.dir" else None,
        environ={"BACKLOG_DIR": "EDIR"},
    )
    assert s.backlog_dir == tmp_path / "EDIR"
    assert s.sources["backlog_dir"] == "env BACKLOG_DIR"


def test_precedence_worktree_root(tmp_path: Path):
    # 1. Default
    s = load_settings(tmp_path, git_config=lambda _: None, environ={})
    assert s.worktree_root == (tmp_path.parent / "worktrees").resolve()
    assert s.sources["worktree_root"] == "default"

    # 2. Git config
    s = load_settings(
        tmp_path,
        git_config=lambda k: "custom_wt" if k == "vault.worktreeRoot" else None,
        environ={},
    )
    assert s.worktree_root == (tmp_path / "custom_wt").resolve()
    assert s.sources["worktree_root"] == "git config vault.worktreeRoot"

    # 3. Env var
    s = load_settings(
        tmp_path,
        git_config=lambda k: "custom_wt" if k == "vault.worktreeRoot" else None,
        environ={"WORKTREE_DIR": "env_wt"},
    )
    assert s.worktree_root == (tmp_path / "env_wt").resolve()
    assert s.sources["worktree_root"] == "env WORKTREE_DIR"


def test_precedence_base_branch(tmp_path: Path):
    # 1. Default (when no git ref or config)
    s = load_settings(tmp_path, git_config=lambda _: None, environ={})
    assert s.base_branch == "main"
    assert s.sources["base_branch"] == "default"

    # 2. Git config
    s = load_settings(
        tmp_path,
        git_config=lambda k: "develop" if k == "backlog.baseBranch" else None,
        environ={},
    )
    assert s.base_branch == "develop"
    assert s.sources["base_branch"] == "git config backlog.baseBranch"


# ---------------------------------------------------------------------------
# Layout Validation (Decision 4)
# ---------------------------------------------------------------------------


def test_layout_tracker_refused(tmp_path: Path):
    with pytest.raises(TaskError) as exc_info:
        load_settings(tmp_path, environ={"BACKLOG_LAYOUT": "tracker"}, git_config=lambda _: None)
    assert "backlog_layout is 'tracker': this tool works only on file-based backlogs; use the tracker's own CLI." in str(
        exc_info.value
    )


def test_layout_unknown_refused(tmp_path: Path):
    with pytest.raises(TaskError) as exc_info:
        load_settings(tmp_path, environ={"BACKLOG_LAYOUT": "foo"}, git_config=lambda _: None)
    err = str(exc_info.value)
    assert "single, split, folders" in err


# ---------------------------------------------------------------------------
# Doctor Command Output & Init (Decisions 6 & 7)
# ---------------------------------------------------------------------------


def test_doctor_prints_settings_with_sources(tmp_path: Path, run_cli):
    from conftest import make_repo

    repo = make_repo(tmp_path / "repo")
    (repo / ".warehouse.yml").write_text("settings:\n  backlog_layout: single\n", encoding="utf-8")
    (repo / "BACKLOG.md").write_text("# Backlog\n", encoding="utf-8")

    res = run_cli(repo, "doctor")
    assert res.exit_code == 0
    # Layout with source
    assert "layout: single (.warehouse.yml)" in res.output
    # Backlog file with source
    assert "backlog file:" in res.output and "(default)" in res.output
    # Worktree root with source
    assert "worktree root:" in res.output and "(default)" in res.output
    # Base branch with source
    assert "base branch: main (default)" in res.output


def test_doctor_init_does_not_write_backlog_file(tmp_path: Path, run_cli):
    from conftest import make_repo

    repo = make_repo(tmp_path / "repo")
    (repo / "BACKLOG.md").write_text("# Backlog\n", encoding="utf-8")

    res = run_cli(repo, "doctor", "--init")
    assert res.exit_code == 0

    # Decision 6: doctor --init no longer writes backlog.file
    out = subprocess.run(
        ["git", "config", "--get", "backlog.file"],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    assert out.returncode != 0
    assert out.stdout.strip() == ""

    # vault.worktreeRoot is configured
    wt_cfg = subprocess.run(
        ["git", "config", "--get", "vault.worktreeRoot"],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    assert wt_cfg.returncode == 0
    assert wt_cfg.stdout.strip() != ""
