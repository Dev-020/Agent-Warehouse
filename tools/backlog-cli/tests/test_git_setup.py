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


def test_pointer_file_primary_tree_f16(tmp_path: Path, run_cli):
    """F16 / Decision 27: primary_tree behaviour in a .git pointer-file repository."""
    work_dir = tmp_path / "f16_work"
    git_dir = tmp_path / "f16_git"
    work_dir.mkdir(parents=True, exist_ok=True)

    subprocess.run(["git", "init", "-q", "-b", "main", f"--separate-git-dir={git_dir}", str(work_dir)], check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(work_dir), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(work_dir), check=True)
    subprocess.run(["git", "config", "core.autocrlf", "false"], cwd=str(work_dir), check=True)

    backlog_text = (
        "# Project Backlog\n\n"
        "> **How this backlog is run** (`convention/backlog`)\n"
        "> - **Layout:** single file\n"
        "> - **Entry style:** full\n\n"
        "## 📋 In Progress\n\n"
        "## 📌 Backlog (Open Tasks)\n\n"
        "### [#001] First task\n"
        "- **Status**: `Open` | **Priority**: `P2`\n"
        "- **Created**: 2026-10-01\n\n"
        "### [#002] Second task\n"
        "- **Status**: `Open` | **Priority**: `P2`\n"
        "- **Created**: 2026-10-01\n\n"
        "## ✅ Completed\n\n"
        "## 🧊 Icebox (Not Doing / Rejected)\n"
    )
    (work_dir / "BACKLOG.md").write_text(backlog_text, encoding="utf-8")
    subprocess.run(["git", "add", "BACKLOG.md"], cwd=str(work_dir), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init backlog"], cwd=str(work_dir), check=True)

    # doctor shows main tree line from main tree
    res_doc = run_cli(work_dir, "doctor")
    assert res_doc.exit_code == 0
    assert f"main tree: {work_dir.resolve()}" in res_doc.output

    # Create a non-claim linked worktree
    non_claim_wt = tmp_path / "f16_wt_non_claim"
    subprocess.run(["git", "worktree", "add", "-b", "feature", str(non_claim_wt), "main"], cwd=str(work_dir), check=True)

    # from non-claim linked worktree, doctor reports unknown main tree
    res_doc_wt = run_cli(non_claim_wt, "doctor")
    assert "main tree: unknown from here (run from the main tree)" in res_doc_wt.output

    # from a non-claim linked worktree, open refuses with decision 27's message
    expected_msg = (
        "This repository's git folder is outside the tree, and git doesn't record "
        "where the main tree is. Run this command from the main tree."
    )
    res_open_nc = run_cli(non_claim_wt, "open", "Task from non-claim")
    assert res_open_nc.exit_code != 0
    assert expected_msg in res_open_nc.output

    # claim #001 and #002 from main tree
    res_claim1 = run_cli(work_dir, "claim", "#001")
    assert res_claim1.exit_code == 0
    wt1 = (tmp_path / "worktrees" / "001").resolve()
    assert wt1.is_dir()

    res_claim2 = run_cli(work_dir, "claim", "#002")
    assert res_claim2.exit_code == 0
    wt2 = (tmp_path / "worktrees" / "002").resolve()
    assert wt2.is_dir()

    # Deliverable in wt1
    (wt1 / "file1.txt").write_text("done", encoding="utf-8")
    subprocess.run(["git", "add", "file1.txt"], cwd=str(wt1), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "work in wt1"], cwd=str(wt1), check=True)

    # from another claim's worktree (wt2), close refuses with decision 27's message
    res_close_other = run_cli(wt2, "close", "#001", "--outcome", "Done")
    assert res_close_other.exit_code != 0
    assert expected_msg in res_close_other.output

    # from the main tree, close works
    res_close_main = run_cli(work_dir, "close", "#001", "--outcome", "Done from main tree")
    assert res_close_main.exit_code == 0
    assert not wt1.exists()

    # from the main tree, open works
    res_open_main = run_cli(work_dir, "open", "Task in main tree")
    assert res_open_main.exit_code == 0
    assert "Created backlog item [#003]" in res_open_main.output

    # from inside a claim worktree (wt2), open writes there (S9)
    res_open_claim = run_cli(wt2, "open", "Child task in claim")
    assert res_open_claim.exit_code == 0
    assert "Created backlog item [#004]" in res_open_claim.output
    assert "[#004] Child task in claim" in (wt2 / "BACKLOG.md").read_text(encoding="utf-8")


def test_primary_tree_separate_git_dir_pointer(tmp_path: Path):
    """Decision 38 (S1): primary_tree returns main tree when .git is a pointer file resolving to common dir."""
    from backlog_cli.gitops import primary_tree

    work = tmp_path / "repo"
    store = tmp_path / "store"
    store.mkdir()
    subprocess.run(
        ["git", "init", "-q", "-b", "main", f"--separate-git-dir={(store / '.git').as_posix()}", str(work)],
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=str(work), check=True)
    subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=str(work), check=True)
    (work / "README.md").write_text("# Test\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(work), check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=str(work), check=True)

    pt = primary_tree(work)
    assert pt.resolve() == work.resolve()

