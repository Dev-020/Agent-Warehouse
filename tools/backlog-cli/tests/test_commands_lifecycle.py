"""Lifecycle command tests (reject, cancel, amend) across single, split, and folders layouts."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from conftest import make_repo
from test_commands_core import _assert_unrelated_files_unchanged, _init_repo_with_backlog, _install_failing_hook, _setup_unrelated_files


@pytest.mark.parametrize("layout", ["single", "split", "folders"])
def test_reject_and_cancel_move_to_icebox(tmp_path: Path, run_cli, layout: str):
    """Decision 29: reject and cancel move entries to Icebox/closed with Resolved and reason."""
    repo = _init_repo_with_backlog(tmp_path / f"repo_rc_{layout}", layout=layout)
    run_cli(repo, "open", "First task", "--prefix", "TASK", "--new-prefix")
    run_cli(repo, "open", "Second task", "--prefix", "TASK")

    # 1. Reject TASK-1
    res_reject = run_cli(repo, "reject", "TASK-1", "--reason", "Not needed anymore")
    assert res_reject.exit_code == 0
    assert "Rejected [TASK-1]" in res_reject.output

    # Check commit
    log_reject = subprocess.run(
        ["git", "log", "-1", "--format=%s"], cwd=str(repo), capture_output=True, text=True, check=True
    ).stdout.strip()
    assert log_reject == "chore(backlog): reject [TASK-1]"

    # 2. Cancel TASK-2
    res_cancel = run_cli(repo, "cancel", "TASK-2", "--reason", "Superseded by other work")
    assert res_cancel.exit_code == 0
    assert "Cancelled [TASK-2]" in res_cancel.output

    # Check commit
    log_cancel = subprocess.run(
        ["git", "log", "-1", "--format=%s"], cwd=str(repo), capture_output=True, text=True, check=True
    ).stdout.strip()
    assert log_cancel == "chore(backlog): cancel [TASK-2]"

    if layout == "single":
        content = (repo / "BACKLOG.md").read_text(encoding="utf-8")
        assert "## 🧊 Icebox (Not Doing / Rejected)" in content
        icebox_part = content.split("## 🧊 Icebox (Not Doing / Rejected)")[1]
        assert "[TASK-1]" in icebox_part
        assert "- **Status**: `Rejected`" in icebox_part
        assert "Not needed anymore" in icebox_part
        assert "[TASK-2]" in icebox_part
        assert "- **Status**: `Cancelled`" in icebox_part
        assert "Superseded by other work" in icebox_part
        # TASK-2 should be after TASK-1 at the bottom of Icebox
        pos1 = icebox_part.find("[TASK-1]")
        pos2 = icebox_part.find("[TASK-2]")
        assert pos1 < pos2
    elif layout == "split":
        content_open = (repo / "BACKLOG" / "Open.md").read_text(encoding="utf-8")
        assert "[TASK-1]" not in content_open
        assert "[TASK-2]" not in content_open
        content_closed = (repo / "BACKLOG" / "Closed.md").read_text(encoding="utf-8")
        assert "## 🧊 Icebox (Not Doing / Rejected)" in content_closed
        icebox_part = content_closed.split("## 🧊 Icebox (Not Doing / Rejected)")[1]
        assert "[TASK-1]" in icebox_part
        assert "- **Status**: `Rejected`" in icebox_part
        assert "Not needed anymore" in icebox_part
        assert "[TASK-2]" in icebox_part
        assert "- **Status**: `Cancelled`" in icebox_part
        assert "Superseded by other work" in icebox_part
        pos1 = icebox_part.find("[TASK-1]")
        pos2 = icebox_part.find("[TASK-2]")
        assert pos1 < pos2
    else:
        open_files = list((repo / "BACKLOG" / "open").glob("TASK-*.md"))
        assert len(open_files) == 0
        closed_files = list((repo / "BACKLOG" / "closed").glob("TASK-*.md"))
        assert len(closed_files) == 2
        f1 = next((repo / "BACKLOG" / "closed").glob("TASK-1-*.md"))
        f2 = next((repo / "BACKLOG" / "closed").glob("TASK-2-*.md"))
        c1 = f1.read_text(encoding="utf-8")
        c2 = f2.read_text(encoding="utf-8")
        assert "status: Rejected" in c1
        assert "resolved: " in c1
        assert "Not needed anymore" in c1
        assert "status: Cancelled" in c2
        assert "resolved: " in c2
        assert "Superseded by other work" in c2


@pytest.mark.parametrize("layout", ["single", "split", "folders"])
def test_reject_and_cancel_refuse_claimed_and_non_open(tmp_path: Path, run_cli, layout: str):
    """Decision 29: refuse claimed items and items that are not Open."""
    repo = _init_repo_with_backlog(tmp_path / f"repo_refuse_{layout}", layout=layout)
    run_cli(repo, "open", "Task to claim", "--prefix", "TASK", "--new-prefix")
    run_cli(repo, "open", "Task to close", "--prefix", "TASK")

    # Claim TASK-1
    res_claim = run_cli(repo, "claim", "TASK-1")
    assert res_claim.exit_code == 0

    # Claimed item refused
    res_rej_claimed = run_cli(repo, "reject", "TASK-1", "--reason", "Cannot do this")
    assert res_rej_claimed.exit_code != 0
    assert "[TASK-1] is claimed; abandon or close the claim first" in res_rej_claimed.output

    res_canc_claimed = run_cli(repo, "cancel", "TASK-1", "--reason", "Cannot do this")
    assert res_canc_claimed.exit_code != 0
    assert "[TASK-1] is claimed; abandon or close the claim first" in res_canc_claimed.output

    # Reject TASK-2
    res_rej2 = run_cli(repo, "reject", "TASK-2", "--reason", "Closing")
    assert res_rej2.exit_code == 0

    # Non-open item refused
    res_rej_again = run_cli(repo, "reject", "TASK-2", "--reason", "Again")
    assert res_rej_again.exit_code != 0
    assert "[TASK-2] is Rejected; only Open items can be rejected or cancelled" in res_rej_again.output

    res_canc_again = run_cli(repo, "cancel", "TASK-2", "--reason", "Again")
    assert res_canc_again.exit_code != 0
    assert "[TASK-2] is Rejected; only Open items can be rejected or cancelled" in res_canc_again.output


@pytest.mark.parametrize("layout", ["single", "split", "folders"])
def test_dependents_updated_in_same_commit(tmp_path: Path, run_cli, layout: str):
    """Decision 29: dependents get note in same commit, warnings for claim-branch-only items."""
    repo = _init_repo_with_backlog(tmp_path / f"repo_dep_{layout}", layout=layout)
    run_cli(repo, "open", "Blocker task", "--prefix", "TASK", "--new-prefix")
    run_cli(repo, "open", "Dependent task", "--prefix", "TASK")

    # Set dependency on TASK-1 in TASK-2
    if layout == "single":
        fpath = repo / "BACKLOG.md"
        content = fpath.read_text(encoding="utf-8")
        content = content.replace("### [TASK-2] Dependent task\n", "### [TASK-2] Dependent task\n- **Depends on**: [TASK-1]\n")
        fpath.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", "BACKLOG.md"], cwd=str(repo), check=True)
    elif layout == "split":
        fpath = repo / "BACKLOG" / "Open.md"
        content = fpath.read_text(encoding="utf-8")
        content = content.replace("### [TASK-2] Dependent task\n", "### [TASK-2] Dependent task\n- **Depends on**: [TASK-1]\n")
        fpath.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", "BACKLOG/Open.md"], cwd=str(repo), check=True)
    else:
        fpath = next((repo / "BACKLOG" / "open").glob("TASK-2-*.md"))
        content = fpath.read_text(encoding="utf-8")
        content = content.replace("status: Open\n", 'status: Open\ndepends_on: ["TASK-1"]\n')
        fpath.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", str(fpath)], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "add dependency"], cwd=str(repo), check=True)

    head_before = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True).stdout.strip()

    # Reject TASK-1
    res = run_cli(repo, "reject", "TASK-1", "--reason", "Invalid approach")
    assert res.exit_code == 0

    # Exactly one commit created
    log_count = subprocess.run(
        ["git", "rev-list", f"{head_before}..HEAD", "--count"], cwd=str(repo), capture_output=True, text=True, check=True
    ).stdout.strip()
    assert log_count == "1"

    # Verify dependent note in TASK-2
    expected_note = (
        "Depends on [TASK-1], which was rejected: Invalid approach. "
        "Check whether this item is still blocked or needs rethinking."
    )
    if layout == "single":
        content = (repo / "BACKLOG.md").read_text(encoding="utf-8")
        assert expected_note in content
    elif layout == "split":
        content = (repo / "BACKLOG" / "Open.md").read_text(encoding="utf-8")
        assert expected_note in content
    else:
        content = fpath.read_text(encoding="utf-8")
        assert expected_note in content


@pytest.mark.parametrize("layout", ["single", "split", "folders"])
def test_reject_leaves_files_untouched_on_hook_failure(tmp_path: Path, run_cli, layout: str):
    """Decision 29 / Invariant: pre-commit hook failure restores files cleanly."""
    repo = _init_repo_with_backlog(tmp_path / f"repo_hook_{layout}", layout=layout)
    run_cli(repo, "open", "Task to reject", "--prefix", "TASK", "--new-prefix")

    mod_file, staged_file = _setup_unrelated_files(repo)

    if layout == "single":
        before_bytes = (repo / "BACKLOG.md").read_bytes()
    elif layout == "split":
        before_bytes = (repo / "BACKLOG" / "Open.md").read_bytes()
    else:
        f = next((repo / "BACKLOG" / "open").glob("TASK-1-*.md"))
        before_bytes = f.read_bytes()

    _install_failing_hook(repo)

    res = run_cli(repo, "reject", "TASK-1", "--reason", "Hook should abort")
    assert res.exit_code != 0

    if layout == "single":
        assert (repo / "BACKLOG.md").read_bytes() == before_bytes
    elif layout == "split":
        assert (repo / "BACKLOG" / "Open.md").read_bytes() == before_bytes
    else:
        assert f.exists()
        assert f.read_bytes() == before_bytes
        assert not list((repo / "BACKLOG" / "closed").glob("TASK-1-*.md"))

    _assert_unrelated_files_unchanged(repo, mod_file, staged_file)


@pytest.mark.parametrize("layout", ["single", "split", "folders"])
def test_amend_note_unclaimed_and_claimed(tmp_path: Path, run_cli, layout: str):
    """Decision 30: amend --note writes to primary tree when unclaimed, worktree when claimed."""
    repo = _init_repo_with_backlog(tmp_path / f"repo_amend_{layout}", layout=layout)
    run_cli(repo, "open", "Unclaimed task", "--prefix", "TASK", "--new-prefix")
    run_cli(repo, "open", "Claimed task", "--prefix", "TASK")

    # 1. Amend unclaimed task -> writes in primary tree
    res_amend1 = run_cli(repo, "amend", "TASK-1", "--note", "Note on unclaimed")
    assert res_amend1.exit_code == 0
    log_amend1 = subprocess.run(
        ["git", "log", "-1", "--format=%s"], cwd=str(repo), capture_output=True, text=True, check=True
    ).stdout.strip()
    assert log_amend1 == "chore(backlog): amend [TASK-1]"

    # 2. Claim TASK-2
    res_claim = run_cli(repo, "claim", "TASK-2")
    assert res_claim.exit_code == 0
    wt_dir = (tmp_path / "worktrees" / "TASK-2").resolve()

    primary_head_before = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True).stdout.strip()

    # 3. Amend claimed task from primary tree -> writes in claim worktree
    res_amend2 = run_cli(repo, "amend", "TASK-2", "--note", "Note on claimed")
    assert res_amend2.exit_code == 0

    # Primary tree HEAD did not change
    primary_head_after = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True).stdout.strip()
    assert primary_head_after == primary_head_before

    # Worktree has the commit
    wt_log = subprocess.run(
        ["git", "log", "-1", "--format=%s"], cwd=str(wt_dir), capture_output=True, text=True, check=True
    ).stdout.strip()
    assert wt_log == "chore(backlog): amend [TASK-2]"


@pytest.mark.parametrize("layout", ["single", "split", "folders"])
def test_amend_priority_validation(tmp_path: Path, run_cli, layout: str):
    """Decision 30: --priority requires --note, refuses same priority, refuses closed."""
    repo = _init_repo_with_backlog(tmp_path / f"repo_pval_{layout}", layout=layout)
    run_cli(repo, "open", "Task validation", "--prefix", "TASK", "--new-prefix")

    # 1. --priority without --note refused
    res_no_note = run_cli(repo, "amend", "TASK-1", "--priority", "P1")
    assert res_no_note.exit_code != 0
    assert "--priority requires --note" in res_no_note.output

    # 2. Same priority refused
    res_same = run_cli(repo, "amend", "TASK-1", "--priority", "P2", "--note", "Same priority")
    assert res_same.exit_code != 0
    assert "[TASK-1] is already P2" in res_same.output

    # 3. Closed item refused
    run_cli(repo, "reject", "TASK-1", "--reason", "Drop it")
    res_closed = run_cli(repo, "amend", "TASK-1", "--note", "Try amend closed")
    assert res_closed.exit_code != 0
    assert "[TASK-1] is Rejected; only open or in-progress items can be amended" in res_closed.output


@pytest.mark.parametrize("layout", ["single", "split", "folders"])
def test_amend_priority_moves_open_leaves_in_progress(tmp_path: Path, run_cli, layout: str):
    """Decision 30: Open item priority change re-orders in Open tasks; In Progress item stays in place."""
    repo = _init_repo_with_backlog(tmp_path / f"repo_pmove_{layout}", layout=layout)
    run_cli(repo, "open", "Alpha task", "--prefix", "TASK", "--new-prefix", "--priority", "P1")
    run_cli(repo, "open", "Beta task", "--prefix", "TASK", "--priority", "P2")
    run_cli(repo, "open", "Gamma task", "--prefix", "TASK", "--priority", "P3")

    # Change Gamma (P3) to P1 -> moves into P1 group
    res_p1 = run_cli(repo, "amend", "TASK-3", "--priority", "P1", "--note", "Escalated")
    assert res_p1.exit_code == 0

    if layout == "single":
        content = (repo / "BACKLOG.md").read_text(encoding="utf-8")
        open_part = content.split("## 📌 Backlog (Open Tasks)")[1].split("## ✅ Completed")[0]
        pos_alpha = open_part.find("[TASK-1]")
        pos_beta = open_part.find("[TASK-2]")
        pos_gamma = open_part.find("[TASK-3]")
        assert pos_alpha < pos_gamma < pos_beta
        assert "priority P3 → P1: Escalated" in open_part
    elif layout == "split":
        open_part = (repo / "BACKLOG" / "Open.md").read_text(encoding="utf-8")
        pos_alpha = open_part.find("[TASK-1]")
        pos_beta = open_part.find("[TASK-2]")
        pos_gamma = open_part.find("[TASK-3]")
        assert pos_alpha < pos_gamma < pos_beta
        assert "priority P3 → P1: Escalated" in open_part
    else:
        f = next((repo / "BACKLOG" / "open").glob("TASK-3-*.md"))
        c = f.read_text(encoding="utf-8")
        assert "priority: P1" in c
        assert "priority P3 → P1: Escalated" in c

    # Claim Beta (TASK-2)
    run_cli(repo, "claim", "TASK-2")
    wt_dir = (tmp_path / "worktrees" / "TASK-2").resolve()

    # Amend Beta while In Progress
    res_inp = run_cli(repo, "amend", "TASK-2", "--priority", "P1", "--note", "Urgent in flight")
    assert res_inp.exit_code == 0

    if layout == "single":
        content = (wt_dir / "BACKLOG.md").read_text(encoding="utf-8")
        inp_part = content.split("## 📋 In Progress")[1].split("## 📌 Backlog (Open Tasks)")[0]
        assert "[TASK-2]" in inp_part
        assert "**Priority**: `P1`" in inp_part
        assert "priority P2 → P1: Urgent in flight" in inp_part
    elif layout == "split":
        content = (wt_dir / "BACKLOG" / "Open.md").read_text(encoding="utf-8")
        inp_part = content.split("## 📋 In Progress")[1].split("## 📌 Backlog (Open Tasks)")[0]
        assert "[TASK-2]" in inp_part
        assert "**Priority**: `P1`" in inp_part
        assert "priority P2 → P1: Urgent in flight" in inp_part
    else:
        f = next((wt_dir / "BACKLOG" / "open").glob("TASK-2-*.md"))
        c = f.read_text(encoding="utf-8")
        assert "priority: P1" in c
        assert "priority P2 → P1: Urgent in flight" in c
