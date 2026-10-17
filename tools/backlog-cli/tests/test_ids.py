"""Tests for ID allocation across branches (Decision 23 / D1)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from conftest import make_repo
from test_commands_core import _init_repo_with_backlog


@pytest.mark.parametrize("layout", ["single", "split", "folders"])
def test_id_used_only_on_claim_branch_not_handed_out_again(tmp_path: Path, run_cli, layout: str):
    """An ID used only on a claim/* branch is not handed out again in primary tree."""
    repo = _init_repo_with_backlog(tmp_path / f"repo_{layout}", layout=layout)

    # 1. Open and claim initial task (#001)
    res1 = run_cli(repo, "open", "First task")
    assert res1.exit_code == 0
    assert "Created backlog item [#001]" in res1.output

    res_claim = run_cli(repo, "claim", "#001")
    assert res_claim.exit_code == 0
    wt_dir = (tmp_path / "worktrees" / "001").resolve()
    assert wt_dir.is_dir()

    # 2. Inside claim/001 worktree, open a second task (#002)
    res2 = run_cli(wt_dir, "open", "Second task in claim branch")
    assert res2.exit_code == 0
    assert "Created backlog item [#002]" in res2.output

    # 3. Back in primary tree, open a third task -> must allocate #003, not #002
    res3 = run_cli(repo, "open", "Third task in main")
    assert res3.exit_code == 0
    assert "Created backlog item [#003]" in res3.output


def test_open_primary_and_claim_worktree_different_ids(tmp_path: Path, run_cli):
    """open in primary tree and open inside a claim worktree get different IDs."""
    repo = _init_repo_with_backlog(tmp_path / "repo_diff_ids", layout="single")

    run_cli(repo, "open", "Task 1", "--prefix", "TASK", "--new-prefix")
    run_cli(repo, "claim", "TASK-1")
    wt_dir = (tmp_path / "worktrees" / "TASK-1").resolve()

    res_wt = run_cli(wt_dir, "open", "Task from WT", "--prefix", "TASK")
    assert res_wt.exit_code == 0
    assert "TASK-2" in res_wt.output

    res_main = run_cli(repo, "open", "Task from Main", "--prefix", "TASK")
    assert res_main.exit_code == 0
    assert "TASK-3" in res_main.output


def test_branch_without_backlog_file_skipped(tmp_path: Path, run_cli):
    """A claim/* branch without a backlog file is skipped during ID allocation."""
    repo = _init_repo_with_backlog(tmp_path / "repo_no_backlog", layout="single")

    # Create an unrelated claim branch without BACKLOG.md
    subprocess.run(["git", "checkout", "-b", "claim/unrelated"], cwd=str(repo), check=True)
    (repo / "BACKLOG.md").unlink()
    subprocess.run(["git", "add", "BACKLOG.md"], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "remove backlog on unrelated claim branch"], cwd=str(repo), check=True)
    subprocess.run(["git", "checkout", "main"], cwd=str(repo), check=True)

    # Opening in main succeeds and allocates ID properly
    res = run_cli(repo, "open", "Task when unrelated claim branch has no backlog")
    assert res.exit_code == 0
    assert "Created backlog item [#001]" in res.output
