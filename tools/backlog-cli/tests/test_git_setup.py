"""Tests for git repository setups and environment handling (Decision 26 / Plan §4.4)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from backlog_cli.gitops import GIT_DIR_MSG, NO_GIT_MSG
from test_commands_core import _init_repo_with_backlog


def test_separate_git_dir_pointer_file_cycle(tmp_path: Path, run_cli):
    """In a repository made with git init --separate-git-dir, open/claim/close then open/claim/abandon works."""
    work_dir = tmp_path / "work"
    git_dir = tmp_path / "gitdir"
    work_dir.mkdir(parents=True, exist_ok=True)

    subprocess.run(["git", "init", "-q", "-b", "main", f"--separate-git-dir={git_dir}", str(work_dir)], check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(work_dir), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(work_dir), check=True)
    subprocess.run(["git", "config", "core.autocrlf", "false"], cwd=str(work_dir), check=True)

    # Initialize backlog
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
    (work_dir / "BACKLOG.md").write_text(backlog_text, encoding="utf-8")
    subprocess.run(["git", "add", "BACKLOG.md"], cwd=str(work_dir), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init backlog"], cwd=str(work_dir), check=True)

    # Verify .git is a pointer file
    assert (work_dir / ".git").is_file()

    # Cycle 1: open, claim, close
    res_open1 = run_cli(work_dir, "open", "Task One", "--prefix", "TASK", "--new-prefix")
    assert res_open1.exit_code == 0
    assert "Created backlog item [TASK-1]" in res_open1.output

    res_claim1 = run_cli(work_dir, "claim", "TASK-1")
    assert res_claim1.exit_code == 0
    wt_dir1 = (tmp_path / "worktrees" / "TASK-1").resolve()
    assert wt_dir1.is_dir()

    # Deliverable in worktree
    (wt_dir1 / "file1.txt").write_text("done", encoding="utf-8")
    subprocess.run(["git", "add", "file1.txt"], cwd=str(wt_dir1), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "ship file1"], cwd=str(wt_dir1), check=True)

    res_close1 = run_cli(work_dir, "close", "TASK-1", "--outcome", "Completed task 1")
    assert res_close1.exit_code == 0
    assert not wt_dir1.exists()

    # Cycle 2: open, claim, abandon
    res_open2 = run_cli(work_dir, "open", "Task Two", "--prefix", "TASK")
    assert res_open2.exit_code == 0
    assert "Created backlog item [TASK-2]" in res_open2.output

    res_claim2 = run_cli(work_dir, "claim", "TASK-2")
    assert res_claim2.exit_code == 0
    wt_dir2 = (tmp_path / "worktrees" / "TASK-2").resolve()
    assert wt_dir2.is_dir()

    res_abandon2 = run_cli(work_dir, "abandon", "TASK-2")
    assert res_abandon2.exit_code == 0
    assert not wt_dir2.exists()


def test_git_dir_env_refusals_and_open(tmp_path: Path, monkeypatch, run_cli):
    """With GIT_DIR set, claim, close and abandon refuse and open works."""
    repo = _init_repo_with_backlog(tmp_path / "repo_gitdir")
    dot_git = (repo / ".git").resolve()

    # Open initial task without GIT_DIR
    run_cli(repo, "open", "Task to test", "--prefix", "TASK", "--new-prefix")

    # Set GIT_DIR
    monkeypatch.setenv("GIT_DIR", str(dot_git))

    # claim refuses
    res_claim = run_cli(repo, "claim", "TASK-1")
    assert res_claim.exit_code != 0
    assert GIT_DIR_MSG in res_claim.output

    # close refuses
    res_close = run_cli(repo, "close", "TASK-1", "--outcome", "Done")
    assert res_close.exit_code != 0
    assert GIT_DIR_MSG in res_close.output

    # abandon refuses
    res_abandon = run_cli(repo, "abandon", "TASK-1")
    assert res_abandon.exit_code != 0
    assert GIT_DIR_MSG in res_abandon.output

    # open works
    res_open = run_cli(repo, "open", "Task created under GIT_DIR", "--prefix", "TASK")
    assert res_open.exit_code == 0
    assert "Created backlog item [TASK-2]" in res_open.output


def test_outside_repo_and_missing_git_message(tmp_path: Path, monkeypatch, run_cli):
    """Outside any repository, and with git missing from PATH, the exact message appears."""
    empty_dir = tmp_path / "not_a_repo"
    empty_dir.mkdir()

    # 1. Outside repository
    res_open = run_cli(empty_dir, "open", "Cannot open")
    assert res_open.exit_code != 0
    assert NO_GIT_MSG in res_open.output

    res_doctor = run_cli(empty_dir, "doctor")
    assert res_doctor.exit_code == 1
    assert NO_GIT_MSG in res_doctor.output

    # 2. Git missing from PATH
    repo = _init_repo_with_backlog(tmp_path / "repo_no_git")
    monkeypatch.setattr(shutil, "which", lambda cmd: None if cmd == "git" else shutil.which(cmd))

    res_open_nogit = run_cli(repo, "open", "Cannot open without git")
    assert res_open_nogit.exit_code != 0
    assert NO_GIT_MSG in res_open_nogit.output

    res_doc_nogit = run_cli(repo, "doctor")
    assert res_doc_nogit.exit_code == 1
    assert NO_GIT_MSG in res_doc_nogit.output


def test_doctor_reports_three_git_discovery_sources(tmp_path: Path, monkeypatch, run_cli):
    """doctor reports how git was found across the three mechanisms."""
    # 1. .git folder
    repo_std = _init_repo_with_backlog(tmp_path / "repo_std")
    res1 = run_cli(repo_std, "doctor")
    assert ".git folder" in res1.output

    # 2. .git pointer file
    work_dir = tmp_path / "ptr_work"
    git_dir = tmp_path / "ptr_git"
    work_dir.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", f"--separate-git-dir={git_dir}", str(work_dir)], check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(work_dir), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(work_dir), check=True)
    (work_dir / "BACKLOG.md").write_text("# Backlog\n## 📌 Backlog (Open Tasks)\n", encoding="utf-8")
    subprocess.run(["git", "add", "BACKLOG.md"], cwd=str(work_dir), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=str(work_dir), check=True)

    res2 = run_cli(work_dir, "doctor")
    assert ".git pointer file ->" in res2.output

    # 3. GIT_DIR/GIT_WORK_TREE environment
    monkeypatch.setenv("GIT_DIR", str(repo_std / ".git"))
    res3 = run_cli(repo_std, "doctor")
    assert "GIT_DIR/GIT_WORK_TREE environment" in res3.output
