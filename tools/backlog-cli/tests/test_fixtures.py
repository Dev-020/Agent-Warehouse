"""Contract tests for test fixtures and doubles (WH-6, [[testing]] §6)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from conftest import _init_repo_with_backlog, make_claim
from backlog_cli.settings import load_settings


@pytest.mark.parametrize("layout", ["single", "split", "folders"])
def test_make_claim_contract_with_real_claim(tmp_path: Path, run_cli, layout: str):
    """Contract test: make_claim produces the exact branch, tree SHA, and files as real claim."""
    repo_real = _init_repo_with_backlog(tmp_path / "box_real" / f"repo_{layout}", layout=layout)
    repo_fake = _init_repo_with_backlog(tmp_path / "box_fake" / f"repo_{layout}", layout=layout)

    # 1. Open identical TASK-1 in both
    res_real = run_cli(repo_real, "open", "Task to claim", "--prefix", "TASK", "--new-prefix")
    assert res_real.exit_code == 0
    res_fake = run_cli(repo_fake, "open", "Task to claim", "--prefix", "TASK", "--new-prefix")
    assert res_fake.exit_code == 0

    # 2. Run real claim in repo_real
    res_claim = run_cli(repo_real, "claim", "TASK-1")
    assert res_claim.exit_code == 0

    # 3. Run fake make_claim in repo_fake
    wt_fake = make_claim(repo_fake, "TASK-1", layout=layout)
    assert wt_fake.is_dir()

    # 4. Compare branch existence
    branch = "claim/TASK-1"
    assert subprocess.run(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=str(repo_real)).returncode == 0
    assert subprocess.run(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=str(repo_fake)).returncode == 0

    # 5. Compare commit tree SHA
    tree_real = subprocess.run(["git", "rev-parse", f"{branch}^{{tree}}"], cwd=str(repo_real), capture_output=True, text=True, check=True).stdout.strip()
    tree_fake = subprocess.run(["git", "rev-parse", f"{branch}^{{tree}}"], cwd=str(repo_fake), capture_output=True, text=True, check=True).stdout.strip()
    assert tree_real == tree_fake, f"Tree mismatch for {layout}: {tree_real} != {tree_fake}"

    # 6. Compare worktree backlog files
    wt_real = load_settings(repo_real).worktree_root / "TASK-1"
    if layout == "single":
        f_real = (wt_real / "BACKLOG.md").read_text(encoding="utf-8")
        f_fake = (wt_fake / "BACKLOG.md").read_text(encoding="utf-8")
        assert f_real == f_fake
    elif layout == "split":
        f_real = (wt_real / "BACKLOG" / "Open.md").read_text(encoding="utf-8")
        f_fake = (wt_fake / "BACKLOG" / "Open.md").read_text(encoding="utf-8")
        assert f_real == f_fake
    elif layout == "folders":
        files_real = sorted(p.name for p in (wt_real / "BACKLOG" / "open").glob("*.md"))
        files_fake = sorted(p.name for p in (wt_fake / "BACKLOG" / "open").glob("*.md"))
        assert files_real == files_fake
        for name in files_real:
            f_real = (wt_real / "BACKLOG" / "open" / name).read_text(encoding="utf-8")
            f_fake = (wt_fake / "BACKLOG" / "open" / name).read_text(encoding="utf-8")
            assert f_real == f_fake
