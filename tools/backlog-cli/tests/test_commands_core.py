"""Core command tests parameterized across single, split, and folders layouts."""

from __future__ import annotations

import stat
import subprocess
from pathlib import Path

import pytest
from conftest import make_repo


def _init_repo_with_backlog(path: Path, layout: str = "single") -> Path:
    repo = make_repo(path)
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


@pytest.mark.parametrize("layout", ["single", "split", "folders"])
def test_cmd_open(tmp_path: Path, run_cli, layout: str):
    repo = _init_repo_with_backlog(tmp_path / f"repo_{layout}", layout=layout)
    res = run_cli(repo, "open", "Build new feature", "--prefix", "TASK", "--new-prefix")
    assert res.exit_code == 0
    assert "Created backlog item [TASK-1]" in res.output

    if layout == "single":
        content = (repo / "BACKLOG.md").read_text(encoding="utf-8")
        assert "### [TASK-1] Build new feature" in content
    elif layout == "split":
        content = (repo / "BACKLOG" / "Open.md").read_text(encoding="utf-8")
        assert "### [TASK-1] Build new feature" in content
    else:
        item_file = repo / "BACKLOG" / "open" / "TASK-1-build-new-feature.md"
        assert item_file.is_file()
        content = item_file.read_text(encoding="utf-8")
        assert "title: Build new feature" in content


@pytest.mark.parametrize("layout", ["single", "split", "folders"])
def test_cmd_claim(tmp_path: Path, run_cli, layout: str):
    repo = _init_repo_with_backlog(tmp_path / f"repo_{layout}", layout=layout)
    run_cli(repo, "open", "Task to claim", "--prefix", "TASK", "--new-prefix")
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
    if layout == "single":
        wt_backlog = (wt_dir / "BACKLOG.md").read_text(encoding="utf-8")
        assert "In Progress" in wt_backlog
    elif layout == "split":
        wt_backlog = (wt_dir / "BACKLOG" / "Open.md").read_text(encoding="utf-8")
        assert "In Progress" in wt_backlog
    else:
        item_file = wt_dir / "BACKLOG" / "open" / "TASK-1-task-to-claim.md"
        assert "status: In Progress" in item_file.read_text(encoding="utf-8")


@pytest.mark.parametrize("layout", ["single", "split", "folders"])
def test_cmd_adopt(tmp_path: Path, run_cli, layout: str):
    repo = _init_repo_with_backlog(tmp_path / f"repo_{layout}", layout=layout)
    run_cli(repo, "open", "Task to adopt", "--prefix", "TASK", "--new-prefix")
    run_cli(repo, "claim", "TASK-1")

    res = run_cli(repo, "adopt", "TASK-1")
    assert res.exit_code == 0
    wt_dir = (tmp_path / "worktrees" / "TASK-1").resolve()
    assert str(wt_dir).replace("\\", "/") in res.output.replace("\\", "/")


@pytest.mark.parametrize("layout", ["single", "split", "folders"])
def test_cmd_status(tmp_path: Path, run_cli, layout: str):
    repo = _init_repo_with_backlog(tmp_path / f"repo_{layout}", layout=layout)
    run_cli(repo, "open", "Task to inspect", "--prefix", "TASK", "--new-prefix")
    run_cli(repo, "claim", "TASK-1")

    res = run_cli(repo, "status")
    assert res.exit_code == 0
    assert "TASK-1" in res.output
    assert "claim/TASK-1" in res.output


@pytest.mark.parametrize("layout", ["single", "split", "folders"])
def test_cmd_close(tmp_path: Path, run_cli, layout: str):
    repo = _init_repo_with_backlog(tmp_path / f"repo_{layout}", layout=layout)
    run_cli(repo, "open", "Task to complete", "--prefix", "TASK", "--new-prefix")
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
    if layout == "single":
        content = (repo / "BACKLOG.md").read_text(encoding="utf-8")
        assert "Closed" in content
        assert "Resolved" in content
    elif layout == "split":
        content = (repo / "BACKLOG" / "Closed.md").read_text(encoding="utf-8")
        assert "Closed" in content
        assert "Resolved" in content
    else:
        closed_file = repo / "BACKLOG" / "closed" / "TASK-1-task-to-complete.md"
        assert closed_file.is_file()
        content = closed_file.read_text(encoding="utf-8")
        assert "status: Closed" in content
        assert "resolved:" in content


@pytest.mark.parametrize("layout", ["single", "split", "folders"])
def test_cmd_abandon(tmp_path: Path, run_cli, layout: str):
    repo = _init_repo_with_backlog(tmp_path / f"repo_{layout}", layout=layout)
    run_cli(repo, "open", "Task to abandon", "--prefix", "TASK", "--new-prefix")
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


# ---------------------------------------------------------------------------
# Additional Step 1b Tests (S9, D3, Decision 18)
# ---------------------------------------------------------------------------


def test_open_inside_claim_worktree_writes_there(tmp_path: Path, run_cli):
    """Decision 16 / S9: open inside a claim worktree writes and commits there."""
    repo = _init_repo_with_backlog(tmp_path / "repo_s9")
    run_cli(repo, "open", "Parent task", "--prefix", "TASK", "--new-prefix")
    run_cli(repo, "claim", "TASK-1")

    wt_dir = (tmp_path / "worktrees" / "TASK-1").resolve()
    assert wt_dir.is_dir()

    # Run open from within the claim worktree
    res = run_cli(wt_dir, "open", "Child subtask", "--prefix", "TASK")
    assert res.exit_code == 0
    assert "Created backlog item [TASK-2]" in res.output

    # Child task was written to wt_dir's backlog
    wt_backlog = (wt_dir / "BACKLOG.md").read_text(encoding="utf-8")
    assert "[TASK-2] Child subtask" in wt_backlog

    # Primary repo's backlog does NOT have TASK-2 yet
    primary_backlog = (repo / "BACKLOG.md").read_text(encoding="utf-8")
    assert "[TASK-2]" not in primary_backlog


def test_failed_commit_leaves_tree_as_it_was(tmp_path: Path, run_cli):
    """Decision 17 / D3: a failed commit leaves the tree as it was."""
    repo = _init_repo_with_backlog(tmp_path / "repo_d3")
    content_before = (repo / "BACKLOG.md").read_bytes()

    # Install a failing pre-commit hook in repo
    hook_path = repo / ".git" / "hooks" / "pre-commit"
    hook_path.parent.mkdir(parents=True, exist_ok=True)
    hook_path.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    hook_path.chmod(hook_path.stat().st_mode | stat.S_IEXEC)

    res = run_cli(repo, "open", "Failing task", "--prefix", "FAIL", "--new-prefix")
    assert res.exit_code != 0

    # Content of BACKLOG.md was restored exactly
    assert (repo / "BACKLOG.md").read_bytes() == content_before

    # Git working tree is clean
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(repo),
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert status == ""


def test_claim_missing_or_closed_id_creates_no_branch(tmp_path: Path, run_cli):
    """Decision 18: claim of missing or closed ID refuses before creating branch."""
    repo = _init_repo_with_backlog(tmp_path / "repo_d18")

    # 1. Missing task ID
    res1 = run_cli(repo, "claim", "NONEXISTENT-999")
    assert res1.exit_code != 0
    assert "not found" in res1.output.lower()

    ref1 = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", "refs/heads/claim/NONEXISTENT-999"],
        cwd=str(repo),
    )
    assert ref1.returncode != 0
    assert not (tmp_path / "worktrees" / "NONEXISTENT-999").exists()

    # 2. Closed task ID
    run_cli(repo, "open", "Task to complete", "--prefix", "TASK", "--new-prefix")
    run_cli(repo, "claim", "TASK-1")
    run_cli(repo, "close", "TASK-1", "--outcome", "Done")

    res2 = run_cli(repo, "claim", "TASK-1")
    assert res2.exit_code != 0
    assert "Open" in res2.output or "status" in res2.output.lower()

    ref2 = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", "refs/heads/claim/TASK-1"],
        cwd=str(repo),
    )
    assert ref2.returncode != 0


# ---------------------------------------------------------------------------
# Step 1c Tests: Hooks, safety rollback, and abandon checks (Decisions 24, 25)
# ---------------------------------------------------------------------------


def _install_failing_hook(repo: Path) -> Path:
    hooks_dir = repo / ".git_hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook = hooks_dir / "pre-commit"
    hook.write_text("#!/bin/sh\necho 'hook rejection'\nexit 1\n", encoding="utf-8")
    hook.chmod(hook.stat().st_mode | stat.S_IEXEC)
    subprocess.run(["git", "config", "core.hooksPath", str(hooks_dir).replace("\\", "/")], cwd=str(repo), check=True)
    return hooks_dir


def _setup_unrelated_files(repo: Path):
    mod_file = repo / "unrelated_modified.txt"
    staged_file = repo / "unrelated_staged.txt"
    mod_file.write_text("initial mod\n", encoding="utf-8")
    staged_file.write_text("initial staged\n", encoding="utf-8")
    subprocess.run(["git", "add", "unrelated_modified.txt", "unrelated_staged.txt"], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "add unrelated files"], cwd=str(repo), check=True)

    # Modify one, stage the other
    mod_file.write_text("modified content\n", encoding="utf-8")
    staged_file.write_text("staged content\n", encoding="utf-8")
    subprocess.run(["git", "add", "unrelated_staged.txt"], cwd=str(repo), check=True)

    return mod_file, staged_file


def _assert_unrelated_files_unchanged(repo: Path, mod_file: Path, staged_file: Path):
    assert mod_file.read_text(encoding="utf-8") == "modified content\n"
    assert staged_file.read_text(encoding="utf-8") == "staged content\n"
    diff_cached = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=str(repo), capture_output=True, text=True).stdout
    diff_worktree = subprocess.run(["git", "diff", "--name-only"], cwd=str(repo), capture_output=True, text=True).stdout
    assert "unrelated_staged.txt" in diff_cached
    assert "unrelated_modified.txt" in diff_worktree
    assert "unrelated_modified.txt" not in diff_cached


def test_hook_failure_open_leaves_backlog_and_unrelated_untouched(tmp_path: Path, run_cli):
    """Hooks (Decision 25): open failure restores backlog; unrelated modified/staged files unchanged."""
    repo = _init_repo_with_backlog(tmp_path / "repo_hook_open")
    mod_file, staged_file = _setup_unrelated_files(repo)
    backlog_before = (repo / "BACKLOG.md").read_bytes()

    _install_failing_hook(repo)

    res = run_cli(repo, "open", "Failing task", "--prefix", "FAIL", "--new-prefix")
    assert res.exit_code != 0
    assert "hook rejection" in res.output or "failed" in res.output

    # Backlog restored
    assert (repo / "BACKLOG.md").read_bytes() == backlog_before
    # Unrelated files unchanged
    _assert_unrelated_files_unchanged(repo, mod_file, staged_file)


def test_hook_failure_claim_leaves_no_branch_or_worktree_and_unrelated_untouched(tmp_path: Path, run_cli):
    """Hooks (Decision 25): claim commit failure removes worktree, deletes branch, leaves unrelated files."""
    repo = _init_repo_with_backlog(tmp_path / "repo_hook_claim")
    run_cli(repo, "open", "Task to claim", "--prefix", "TASK", "--new-prefix")
    mod_file, staged_file = _setup_unrelated_files(repo)

    _install_failing_hook(repo)

    res = run_cli(repo, "claim", "TASK-1")
    assert res.exit_code != 0

    # No branch and no worktree left
    ref_check = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", "refs/heads/claim/TASK-1"],
        cwd=str(repo),
    )
    assert ref_check.returncode != 0
    assert not (tmp_path / "worktrees" / "TASK-1").exists()

    # Unrelated files unchanged
    _assert_unrelated_files_unchanged(repo, mod_file, staged_file)


def test_hook_failure_close_restores_worktree_and_leaves_main_unmerged(tmp_path: Path, run_cli):
    """Hooks (Decision 25): close commit failure restores worktree backlog, leaves main unmerged."""
    repo = _init_repo_with_backlog(tmp_path / "repo_hook_close")
    run_cli(repo, "open", "Task to close", "--prefix", "TASK", "--new-prefix")
    run_cli(repo, "claim", "TASK-1")

    wt_dir = (tmp_path / "worktrees" / "TASK-1").resolve()
    (wt_dir / "deliverable.txt").write_text("feature work\n", encoding="utf-8")
    subprocess.run(["git", "add", "deliverable.txt"], cwd=str(wt_dir), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "work in progress"], cwd=str(wt_dir), check=True)

    wt_backlog_before = (wt_dir / "BACKLOG.md").read_bytes()
    mod_file, staged_file = _setup_unrelated_files(repo)
    main_head_before = subprocess.run(["git", "rev-parse", "main"], cwd=str(repo), capture_output=True, text=True).stdout.strip()

    _install_failing_hook(repo)

    res = run_cli(repo, "close", "TASK-1", "--outcome", "All done")
    assert res.exit_code != 0

    # Worktree backlog restored
    assert (wt_dir / "BACKLOG.md").read_bytes() == wt_backlog_before

    # main unmerged
    main_head_after = subprocess.run(["git", "rev-parse", "main"], cwd=str(repo), capture_output=True, text=True).stdout.strip()
    assert main_head_after == main_head_before
    assert not (repo / "deliverable.txt").exists()

    # Worktree and branch still exist
    assert wt_dir.is_dir()
    ref_check = subprocess.run(["git", "show-ref", "--verify", "--quiet", "refs/heads/claim/TASK-1"], cwd=str(repo))
    assert ref_check.returncode == 0

    # Unrelated files unchanged
    _assert_unrelated_files_unchanged(repo, mod_file, staged_file)


def test_abandon_refuses_own_commits_and_force_restores(tmp_path: Path, run_cli):
    """Decision 24 (D2, S10): abandon refuses branch with own commits; --force prints restore command and deletes."""
    repo = _init_repo_with_backlog(tmp_path / "repo_abandon_check")
    run_cli(repo, "open", "Task to abandon", "--prefix", "TASK", "--new-prefix")
    run_cli(repo, "claim", "TASK-1")

    wt_dir = (tmp_path / "worktrees" / "TASK-1").resolve()
    # Add a commit of its own on the claim branch
    (wt_dir / "work.txt").write_text("my progress\n", encoding="utf-8")
    subprocess.run(["git", "add", "work.txt"], cwd=str(wt_dir), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "feat: my progress"], cwd=str(wt_dir), check=True)

    tip_hash = subprocess.run(["git", "rev-parse", "--short", "claim/TASK-1"], cwd=str(repo), capture_output=True, text=True).stdout.strip()

    # 1. Refuse without --force
    res_refuse = run_cli(repo, "abandon", "TASK-1")
    assert res_refuse.exit_code != 0
    assert "has commits not on main" in res_refuse.output
    assert "feat: my progress" in res_refuse.output

    # Branch and worktree still exist
    assert wt_dir.is_dir()
    ref_check = subprocess.run(["git", "show-ref", "--verify", "--quiet", "refs/heads/claim/TASK-1"], cwd=str(repo))
    assert ref_check.returncode == 0

    # 2. Delete with --force
    res_force = run_cli(repo, "abandon", "TASK-1", "--force")
    assert res_force.exit_code == 0
    assert f"Branch claim/TASK-1 tip was {tip_hash}" in res_force.output
    assert f"git branch claim/TASK-1 {tip_hash}" in res_force.output
    assert not wt_dir.exists()

    ref_check_after = subprocess.run(["git", "show-ref", "--verify", "--quiet", "refs/heads/claim/TASK-1"], cwd=str(repo))
    assert ref_check_after.returncode != 0


def test_close_from_inside_claim_worktree_refuses(tmp_path: Path, run_cli):
    """F1: close run from inside the claim worktree refuses cleanly naming primary tree."""
    repo = _init_repo_with_backlog(tmp_path / "repo_f1")
    run_cli(repo, "open", "Task F1")
    run_cli(repo, "claim", "#001")
    wt_dir = (tmp_path / "worktrees" / "001").resolve()
    res = run_cli(wt_dir, "close", "#001", "--outcome", "Done")
    assert res.exit_code != 0
    assert "Cannot close from inside the claim worktree" in res.output
    assert str(repo.resolve()) in res.output


def test_close_rerun_after_sync_conflict_skips_item_update(tmp_path: Path, run_cli):
    """F2: close rerun after resolving sync conflict succeeds and doesn't duplicate outcome."""
    repo = _init_repo_with_backlog(tmp_path / "repo_f2")
    run_cli(repo, "open", "Task F2")
    run_cli(repo, "claim", "#001")
    wt_dir = (tmp_path / "worktrees" / "001").resolve()

    # Create conflict on README.md
    (wt_dir / "README.md").write_text("branch edit\n", encoding="utf-8")
    subprocess.run(["git", "commit", "-qam", "branch edit"], cwd=str(wt_dir), check=True)
    (repo / "README.md").write_text("main edit\n", encoding="utf-8")
    subprocess.run(["git", "commit", "-qam", "main edit"], cwd=str(repo), check=True)

    # First close attempt fails on sync merge
    p1 = run_cli(repo, "close", "#001", "--outcome", "OUTCOME-ONCE")
    assert p1.exit_code != 0

    # Resolve conflict in worktree
    subprocess.run(["git", "checkout", "--ours", "README.md"], cwd=str(wt_dir), check=True)
    subprocess.run(["git", "add", "README.md"], cwd=str(wt_dir), check=True)
    subprocess.run(["git", "commit", "-qm", "resolve"], cwd=str(wt_dir), check=True)

    # Re-run close succeeds
    p2 = run_cli(repo, "close", "#001", "--outcome", "OUTCOME-ONCE")
    assert p2.exit_code == 0
    content = (repo / "BACKLOG.md").read_text(encoding="utf-8")
    assert content.count("OUTCOME-ONCE") == 1


def test_claim_branches_from_base_branch(tmp_path: Path, run_cli):
    """F4: claim branches from base branch, not from current tree HEAD."""
    repo = _init_repo_with_backlog(tmp_path / "repo_f4")
    run_cli(repo, "open", "Task 1")
    run_cli(repo, "open", "Task 2")
    run_cli(repo, "claim", "#001")
    wt1 = (tmp_path / "worktrees" / "001").resolve()
    (wt1 / "work.txt").write_text("wt1 work\n", encoding="utf-8")
    subprocess.run(["git", "add", "work.txt"], cwd=str(wt1), check=True)
    subprocess.run(["git", "commit", "-qm", "wt1 work"], cwd=str(wt1), check=True)

    # Run claim for #002 from inside wt1
    p = run_cli(wt1, "claim", "#002")
    assert p.exit_code == 0
    # claim/002 should not contain wt1's unmerged work commit
    a_work = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(wt1), capture_output=True, text=True).stdout.strip()
    leaked = subprocess.run(["git", "merge-base", "--is-ancestor", a_work, "claim/002"], cwd=str(repo)).returncode == 0
    assert not leaked


def test_claim_close_abandon_missing_base_refuses(tmp_path: Path, run_cli):
    """F5: claim, close, and abandon refuse if base branch ref does not exist."""
    repo = tmp_path / "repo_f5"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "trunk"], cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(repo), check=True)
    (repo / "BACKLOG.md").write_text("# Project Backlog\n\n- **Entry style:** full\n\n## 📋 In Progress\n\n## 📌 Backlog (Open Tasks)\n\n## ✅ Completed\n\n## 🧊 Icebox (Not Doing / Rejected)\n", encoding="utf-8")
    (repo / "README.md").write_text("readme\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=str(repo), check=True)

    run_cli(repo, "open", "Task on trunk")

    # 1. claim refuses when base branch ('main') not found
    res_claim = run_cli(repo, "claim", "#001")
    assert res_claim.exit_code != 0
    assert "base branch 'main' not found; set backlog.baseBranch" in res_claim.output

    # Configure baseBranch and claim
    subprocess.run(["git", "config", "backlog.baseBranch", "trunk"], cwd=str(repo), check=True)
    res_claim_ok = run_cli(repo, "claim", "#001")
    assert res_claim_ok.exit_code == 0

    # Unset baseBranch again
    subprocess.run(["git", "config", "--unset", "backlog.baseBranch"], cwd=str(repo), check=True)

    # 2. close refuses when base branch not found
    res_close = run_cli(repo, "close", "#001", "--outcome", "Done")
    assert res_close.exit_code != 0
    assert "base branch 'main' not found; set backlog.baseBranch" in res_close.output

    # 3. abandon refuses when base branch not found
    res_abandon = run_cli(repo, "abandon", "#001")
    assert res_abandon.exit_code != 0
    assert "base branch 'main' not found; set backlog.baseBranch" in res_abandon.output


def test_close_refuses_when_primary_not_on_base(tmp_path: Path, run_cli):
    """F9: close refuses before any write unless the primary tree is on the base branch."""
    repo = _init_repo_with_backlog(tmp_path / "repo_f9")
    run_cli(repo, "open", "Task F9")
    run_cli(repo, "claim", "#001")
    subprocess.run(["git", "checkout", "-q", "-b", "side"], cwd=str(repo), check=True)
    res = run_cli(repo, "close", "#001", "--outcome", "Done")
    assert res.exit_code != 0
    assert "expected base branch 'main'" in res.output


def test_claim_hint_quotes_task_id(tmp_path: Path, run_cli):
    """F15: claim hint quotes the task ID so shell '#' does not start a comment."""
    repo = _init_repo_with_backlog(tmp_path / "repo_f15")
    run_cli(repo, "open", "Task F15")
    res = run_cli(repo, "claim", "#001")
    assert res.exit_code == 0
    assert "python task.py close '#001' --outcome 'Summary'" in res.output


def test_tool_commits_do_not_have_co_authored_trailer(tmp_path: Path, run_cli):
    """F14: tool commits must not include a hardcoded Co-Authored-By trailer."""
    repo = _init_repo_with_backlog(tmp_path / "repo_f14")
    run_cli(repo, "open", "Task F14")
    msg = subprocess.run(
        ["git", "log", "-1", "--format=%B"], cwd=str(repo), capture_output=True, text=True, check=True
    ).stdout
    assert "Gemini" not in msg
    assert "Antigravity" not in msg


def test_folder_item_restore_on_hook_failure(tmp_path: Path, run_cli):
    """F3: rollback folder move and restore files intact when close commit fails due to hook."""
    repo = tmp_path / "repo_f3"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(repo), check=True)
    (repo / ".warehouse.yml").write_text("settings:\n  backlog_layout: folders\n", encoding="utf-8")
    b = repo / "BACKLOG"
    (b / "open").mkdir(parents=True)
    (b / "closed").mkdir(parents=True)
    (b / "00_BACKLOG.md").write_text("# Backlog\n\n- **Entry style:** full\n", encoding="utf-8")
    (b / "open" / ".gitkeep").write_text("", encoding="utf-8")
    (b / "closed" / ".gitkeep").write_text("", encoding="utf-8")
    (repo / "README.md").write_text("readme\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=str(repo), check=True)

    run_cli(repo, "open", "Alpha task")
    o = repo / "BACKLOG" / "open"
    f = next(o.glob("001-*.md"))
    folder = o / f.stem
    folder.mkdir()
    f.rename(folder / f.name)
    (folder / "evidence.txt").write_text("precious evidence\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-qm", "item becomes a folder"], cwd=str(repo), check=True)

    run_cli(repo, "claim", "#001")
    wt_dir = (tmp_path / "worktrees" / "001").resolve()
    wfolder = wt_dir / "BACKLOG" / "open" / folder.name
    before_bytes = (wfolder / f.name).read_bytes()

    _install_failing_hook(repo)
    res = run_cli(repo, "close", "#001", "--outcome", "Done")
    assert res.exit_code != 0

    assert (wfolder / "evidence.txt").is_file()
    assert (wfolder / "evidence.txt").read_text(encoding="utf-8") == "precious evidence\n"
    assert (wfolder / f.name).is_file()
    assert (wfolder / f.name).read_bytes() == before_bytes
    assert not (wt_dir / "BACKLOG" / "closed" / folder.name).exists()
    st = subprocess.run(["git", "status", "--porcelain"], cwd=str(wt_dir), capture_output=True, text=True).stdout
    assert st.strip() == ""


