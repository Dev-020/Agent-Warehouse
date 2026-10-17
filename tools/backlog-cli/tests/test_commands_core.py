"""Happy-path tests for core backlog-cli commands on a single-file backlog."""

from __future__ import annotations

import subprocess
from pathlib import Path

from conftest import make_repo


def _init_repo_with_backlog(path: Path) -> Path:
    repo = make_repo(path)
    backlog_text = (
        "# Project Backlog\n\n"
        "## 📋 In Progress\n\n"
        "## 📌 Backlog (Open Tasks)\n\n"
        "## ✅ Completed\n\n"
        "## 🧊 Icebox (Not Doing / Rejected)\n"
    )
    (repo / "BACKLOG.md").write_text(backlog_text, encoding="utf-8")
    subprocess.run(["git", "add", "BACKLOG.md"], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "add backlog"], cwd=str(repo), check=True)
    return repo


def test_cmd_open(tmp_path: Path, run_cli):
    repo = _init_repo_with_backlog(tmp_path / "repo")
    res = run_cli(repo, "open", "Build new feature", "--prefix", "TASK")
    assert res.exit_code == 0
    content = (repo / "BACKLOG.md").read_text(encoding="utf-8")
    assert "### [TASK-1] Build new feature" in content


def test_cmd_claim(tmp_path: Path, run_cli):
    repo = _init_repo_with_backlog(tmp_path / "repo")
    run_cli(repo, "open", "Task to claim", "--prefix", "TASK")
    res = run_cli(repo, "claim", "TASK-1")
    assert res.exit_code == 0

    # Branch claim/TASK-1 exists
    ref_check = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", "refs/heads/claim/TASK-1"],
        cwd=str(repo),
    )
    assert ref_check.returncode == 0

    # Worktree directory created
    wt_dir = (tmp_path / "worktrees" / "TASK-1").resolve()
    assert wt_dir.is_dir()

    # Inside worktree, status is In Progress
    wt_backlog = (wt_dir / "BACKLOG.md").read_text(encoding="utf-8")
    assert "In Progress" in wt_backlog


def test_cmd_adopt(tmp_path: Path, run_cli):
    repo = _init_repo_with_backlog(tmp_path / "repo")
    run_cli(repo, "open", "Task to adopt", "--prefix", "TASK")
    run_cli(repo, "claim", "TASK-1")

    res = run_cli(repo, "adopt", "TASK-1")
    assert res.exit_code == 0
    wt_dir = (tmp_path / "worktrees" / "TASK-1").resolve()
    assert str(wt_dir).replace("\\", "/") in res.output.replace("\\", "/")


def test_cmd_status(tmp_path: Path, run_cli):
    repo = _init_repo_with_backlog(tmp_path / "repo")
    run_cli(repo, "open", "Task to inspect", "--prefix", "TASK")
    run_cli(repo, "claim", "TASK-1")

    res = run_cli(repo, "status")
    assert res.exit_code == 0
    assert "TASK-1" in res.output
    assert "claim/TASK-1" in res.output


def test_cmd_close(tmp_path: Path, run_cli):
    repo = _init_repo_with_backlog(tmp_path / "repo")
    run_cli(repo, "open", "Task to complete", "--prefix", "TASK")
    run_cli(repo, "claim", "TASK-1")

    wt_dir = (tmp_path / "worktrees" / "TASK-1").resolve()
    # Add and commit a change in the worktree
    (wt_dir / "deliverable.txt").write_text("shipped\n", encoding="utf-8")
    subprocess.run(["git", "add", "deliverable.txt"], cwd=str(wt_dir), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "implement deliverable"], cwd=str(wt_dir), check=True)

    res = run_cli(repo, "close", "TASK-1", "--outcome", "Feature delivered successfully")
    assert res.exit_code == 0

    # Worktree removed
    assert not wt_dir.exists()

    # Branch deleted
    ref_check = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", "refs/heads/claim/TASK-1"],
        cwd=str(repo),
    )
    assert ref_check.returncode != 0

    # Merge landed on main
    assert (repo / "deliverable.txt").is_file()
    main_backlog = (repo / "BACKLOG.md").read_text(encoding="utf-8")
    assert "Closed" in main_backlog


def test_cmd_abandon(tmp_path: Path, run_cli):
    repo = _init_repo_with_backlog(tmp_path / "repo")
    run_cli(repo, "open", "Task to abandon", "--prefix", "TASK")
    run_cli(repo, "claim", "TASK-1")

    wt_dir = (tmp_path / "worktrees" / "TASK-1").resolve()
    assert wt_dir.is_dir()

    res = run_cli(repo, "abandon", "TASK-1")
    assert res.exit_code == 0

    # Worktree removed
    assert not wt_dir.exists()

    # Branch deleted
    ref_check = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", "refs/heads/claim/TASK-1"],
        cwd=str(repo),
    )
    assert ref_check.returncode != 0
