"""Tests for pre-merge check module (backlog_cli/check.py) and close pre-merge gate.

Adheres to Decision 44:
- in-memory testing of duplicate checking logic and unticked criteria warning
- a new duplicate blocks close (single, split, folders), naming every copy
- an old duplicate on the base branch doesn't block
- after fixing the duplicate in the worktree and committing, re-running close merges
- unticked criteria warn and don't block
- compact entries get no warning
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from backlog_cli.check import (
    check_duplicates,
    check_unticked_criteria,
    format_duplicate_error,
)
from test_commands_core import _init_repo_with_backlog


# ===========================================================================
# Pure in-memory unit tests
# ===========================================================================


def test_in_memory_duplicate_detection_no_duplicates():
    base = [("TASK-1", "BACKLOG.md:10"), ("TASK-2", "BACKLOG.md:20")]
    claim = [
        ("TASK-1", "BACKLOG.md:10"),
        ("TASK-2", "BACKLOG.md:20"),
        ("TASK-3", "BACKLOG.md:30"),
    ]
    dups = check_duplicates(base, claim)
    assert dups == {}


def test_in_memory_duplicate_detection_new_duplicate():
    base = [("TASK-1", "BACKLOG.md:10")]
    claim = [("TASK-1", "BACKLOG.md:10"), ("TASK-1", "BACKLOG.md:25")]
    dups = check_duplicates(base, claim)
    assert "TASK-1" in dups
    assert dups["TASK-1"] == ["BACKLOG.md:10", "BACKLOG.md:25"]


def test_in_memory_duplicate_detection_old_duplicate_ignored():
    """Duplicates that already exist on the base branch are ignored."""
    base = [("OLD-1", "BACKLOG.md:5"), ("OLD-1", "BACKLOG.md:15")]
    claim = [("OLD-1", "BACKLOG.md:5"), ("OLD-1", "BACKLOG.md:15")]
    dups = check_duplicates(base, claim)
    assert dups == {}


def test_in_memory_duplicate_detection_old_duplicate_increased():
    """An ID appearing more often at claim tip than base tip is a new duplicate."""
    base = [("OLD-1", "BACKLOG.md:5"), ("OLD-1", "BACKLOG.md:15")]
    claim = [
        ("OLD-1", "BACKLOG.md:5"),
        ("OLD-1", "BACKLOG.md:15"),
        ("OLD-1", "BACKLOG.md:30"),
    ]
    dups = check_duplicates(base, claim)
    assert "OLD-1" in dups
    assert dups["OLD-1"] == ["BACKLOG.md:5", "BACKLOG.md:15", "BACKLOG.md:30"]


def test_in_memory_duplicate_normalized_ids():
    """Different representations (#001, 001) are normalized and detected as duplicates."""
    base = []
    claim = [("#001", "BACKLOG.md:10"), ("001", "BACKLOG.md:30")]
    dups = check_duplicates(base, claim)
    assert len(dups) == 1
    key = list(dups.keys())[0]
    assert key in ("#001", "001")
    assert dups[key] == ["BACKLOG.md:10", "BACKLOG.md:30"]


def test_in_memory_format_duplicate_error():
    duplicates = {"TASK-1": ["BACKLOG.md:10", "BACKLOG.md:25"]}
    msg = format_duplicate_error(duplicates)
    assert "Duplicate ID [TASK-1]:" in msg
    assert "  BACKLOG.md:10" in msg
    assert "  BACKLOG.md:25" in msg
    assert "Fix the duplicate in the claim worktree, commit, and re-run close." in msg


def test_in_memory_unticked_criteria_warning():
    raw_entry = """### [TASK-1] Example Task
- **Status**: `Closed` | **Priority**: `P2`
- **Created**: 2026-10-19
- **Resolved**: 2026-10-19

#### Why
Motivation

#### Wanted
Feature

#### Acceptance Criteria
- [x] #1 First done
- [ ] #2 Second pending
- [ ] #3 Third pending

#### Outcome
Implemented
"""
    warn = check_unticked_criteria(raw_entry, "TASK-1")
    assert warn == "Warning: [TASK-1] closed with 2 unticked criteria: #2, #3"


def test_in_memory_unticked_criteria_all_ticked():
    raw_entry = """### [TASK-1] Example Task
- **Status**: `Closed` | **Priority**: `P2`

#### Acceptance Criteria
- [x] #1 First done
- [x] #2 Second done

#### Outcome
Done
"""
    warn = check_unticked_criteria(raw_entry, "TASK-1")
    assert warn is None


def test_in_memory_unticked_criteria_no_numbers():
    raw_entry = """### [TASK-1] Example Task
- **Status**: `Closed` | **Priority**: `P2`

#### Acceptance Criteria
- [ ] First pending
- [ ] Second pending

#### Outcome
Done
"""
    warn = check_unticked_criteria(raw_entry, "TASK-1")
    assert warn == "Warning: [TASK-1] closed with 2 unticked criteria"


def test_in_memory_unticked_criteria_compact_style():
    raw_entry = """### [TASK-1] Compact Task
- **Status**: `Closed` | **Priority**: `P2`

Prose description here.

*Wanted:* something
*Done when:* feature works
*Outcome (2026-10-19):* Done
"""
    warn = check_unticked_criteria(raw_entry, "TASK-1")
    assert warn is None


def test_in_memory_unticked_criteria_code_block_ignored():
    raw_entry = """### [TASK-1] Code Block Task
- **Status**: `Closed` | **Priority**: `P2`

#### Why
Check this code block:
```markdown
- [ ] #1 Not a real criterion
```

#### Acceptance Criteria
- [x] #1 Real criterion ticked

#### Outcome
Done
"""
    warn = check_unticked_criteria(raw_entry, "TASK-1")
    assert warn is None


# ===========================================================================
# Git-backed integration tests through close
# ===========================================================================


def test_close_blocked_by_new_duplicate_single(tmp_path: Path, run_cli):
    """A new duplicate blocks close on single-file layout, naming every copy."""
    repo = _init_repo_with_backlog(tmp_path / "repo_single", layout="single")
    run_cli(repo, "open", "Task to claim", "--prefix", "TASK", "--new-prefix")
    run_cli(repo, "claim", "TASK-1")

    wt_dir = (tmp_path / "worktrees" / "TASK-1").resolve()
    # Introduce duplicate TASK-1 entry in worktree's BACKLOG.md
    bfile = wt_dir / "BACKLOG.md"
    content = bfile.read_text(encoding="utf-8")
    duplicate_entry = (
        "\n### [TASK-1] Duplicate copy\n"
        "- **Status**: `Open` | **Priority**: `P2`\n"
        "- **Created**: 2026-10-19\n\n"
        "Duplicate description.\n"
    )
    bfile.write_text(content + duplicate_entry, encoding="utf-8")
    subprocess.run(["git", "commit", "-am", "add duplicate TASK-1"], cwd=str(wt_dir), check=True)

    res = run_cli(repo, "close", "TASK-1", "--outcome", "Feature finished")
    assert res.exit_code != 0
    assert "Duplicate ID [TASK-1]:" in res.output
    assert "BACKLOG.md:" in res.output
    # Check that both copies are named (there are at least 2 BACKLOG.md lines in output)
    lines_with_loc = [l for l in res.output.splitlines() if "BACKLOG.md:" in l]
    assert len(lines_with_loc) >= 2
    assert "Fix the duplicate in the claim worktree, commit, and re-run close." in res.output
    # Worktree must still exist because close stopped before merging
    assert wt_dir.is_dir()


def test_close_blocked_by_new_duplicate_split(tmp_path: Path, run_cli):
    """A new duplicate blocks close on split layout, naming every copy."""
    repo = _init_repo_with_backlog(tmp_path / "repo_split", layout="split")
    run_cli(repo, "open", "Task to claim", "--prefix", "TASK", "--new-prefix")
    run_cli(repo, "claim", "TASK-1")

    wt_dir = (tmp_path / "worktrees" / "TASK-1").resolve()
    # Introduce duplicate entry in worktree's BACKLOG/Open.md
    open_file = wt_dir / "BACKLOG" / "Open.md"
    content = open_file.read_text(encoding="utf-8")
    duplicate_entry = (
        "\n### [TASK-1] Duplicate copy\n"
        "- **Status**: `Open` | **Priority**: `P2`\n"
        "- **Created**: 2026-10-19\n\n"
        "Duplicate description.\n"
    )
    open_file.write_text(content + duplicate_entry, encoding="utf-8")
    subprocess.run(["git", "commit", "-am", "add duplicate TASK-1"], cwd=str(wt_dir), check=True)

    res = run_cli(repo, "close", "TASK-1", "--outcome", "Feature finished")
    assert res.exit_code != 0
    assert "Duplicate ID [TASK-1]:" in res.output
    assert "BACKLOG/Open.md:" in res.output or "BACKLOG/Closed.md:" in res.output
    assert "Fix the duplicate in the claim worktree, commit, and re-run close." in res.output
    assert wt_dir.is_dir()


def test_close_blocked_by_new_duplicate_folders(tmp_path: Path, run_cli):
    """A new duplicate blocks close on folders layout, naming every copy."""
    repo = _init_repo_with_backlog(tmp_path / "repo_folders", layout="folders")
    run_cli(repo, "open", "Task to claim", "--prefix", "TASK", "--new-prefix")
    run_cli(repo, "claim", "TASK-1")

    wt_dir = (tmp_path / "worktrees" / "TASK-1").resolve()
    # Create duplicate item file with id: "TASK-1"
    dup_file = wt_dir / "BACKLOG" / "open" / "TASK-1-duplicate.md"
    dup_file.write_text(
        '---\nid: "TASK-1"\ntitle: Duplicate Item\nstatus: Open\npriority: P2\ncreated: 2026-10-19\n---\n\n'
        "# [TASK-1] Duplicate Item\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=str(wt_dir), check=True)
    subprocess.run(["git", "commit", "-m", "add duplicate item"], cwd=str(wt_dir), check=True)

    res = run_cli(repo, "close", "TASK-1", "--outcome", "Feature finished")
    assert res.exit_code != 0
    assert "Duplicate ID [TASK-1]:" in res.output
    assert "TASK-1-duplicate.md" in res.output
    assert "TASK-1-task-to-claim.md" in res.output
    assert "Fix the duplicate in the claim worktree, commit, and re-run close." in res.output
    assert wt_dir.is_dir()


def test_close_allows_old_duplicate_on_base(tmp_path: Path, run_cli):
    """An old duplicate on the base branch doesn't block close."""
    repo = _init_repo_with_backlog(tmp_path / "repo_old_dup", layout="single")
    # Add an old duplicate on main before claiming
    bfile = repo / "BACKLOG.md"
    content = bfile.read_text(encoding="utf-8")
    old_dup = (
        "\n### [OLD-1] First copy on base\n"
        "- **Status**: `Open` | **Priority**: `P2`\n"
        "- **Created**: 2026-10-01\n\n"
        "### [OLD-1] Second copy on base\n"
        "- **Status**: `Open` | **Priority**: `P2`\n"
        "- **Created**: 2026-10-02\n"
    )
    bfile.write_text(content + old_dup, encoding="utf-8")
    subprocess.run(["git", "commit", "-am", "pre-existing duplicate on base"], cwd=str(repo), check=True)

    # Open and claim a new task
    run_cli(repo, "open", "New task", "--prefix", "TASK", "--new-prefix")
    run_cli(repo, "claim", "TASK-1")

    wt_dir = (tmp_path / "worktrees" / "TASK-1").resolve()
    (wt_dir / "work.txt").write_text("done\n", encoding="utf-8")
    subprocess.run(["git", "add", "work.txt"], cwd=str(wt_dir), check=True)
    subprocess.run(["git", "commit", "-m", "complete work"], cwd=str(wt_dir), check=True)

    res = run_cli(repo, "close", "TASK-1", "--outcome", "Completed despite old dup")
    assert res.exit_code == 0
    assert "Successfully closed and merged [TASK-1]" in res.output
    assert not wt_dir.exists()


def test_close_merges_after_fixing_duplicate_in_worktree(tmp_path: Path, run_cli):
    """After fixing the duplicate in the worktree and committing, re-running close merges."""
    repo = _init_repo_with_backlog(tmp_path / "repo_fix_dup", layout="single")
    run_cli(repo, "open", "Task to claim", "--prefix", "TASK", "--new-prefix")
    run_cli(repo, "claim", "TASK-1")

    wt_dir = (tmp_path / "worktrees" / "TASK-1").resolve()
    bfile = wt_dir / "BACKLOG.md"
    original_content = bfile.read_text(encoding="utf-8")

    # Introduce duplicate DUP-1 twice
    dup_entries = (
        "\n### [DUP-1] First copy\n"
        "- **Status**: `Open` | **Priority**: `P2`\n"
        "- **Created**: 2026-10-19\n\n"
        "### [DUP-1] Second copy\n"
        "- **Status**: `Open` | **Priority**: `P2`\n"
        "- **Created**: 2026-10-19\n"
    )
    bfile.write_text(original_content + dup_entries, encoding="utf-8")
    subprocess.run(["git", "commit", "-am", "introduce duplicate DUP-1"], cwd=str(wt_dir), check=True)

    # First close run should fail
    res1 = run_cli(repo, "close", "TASK-1", "--outcome", "First attempt")
    assert res1.exit_code != 0
    assert "Duplicate ID [DUP-1]:" in res1.output
    assert wt_dir.is_dir()

    # Fix the duplicate in worktree: change second copy to DUP-2
    fixed_content = (original_content + dup_entries).replace(
        "### [DUP-1] Second copy", "### [DUP-2] Second copy"
    )
    bfile.write_text(fixed_content, encoding="utf-8")
    subprocess.run(["git", "commit", "-am", "fix duplicate DUP-1 -> DUP-2"], cwd=str(wt_dir), check=True)

    # Re-running close should succeed (Decision 44, F2)
    res2 = run_cli(repo, "close", "TASK-1", "--outcome", "Second attempt")
    assert res2.exit_code == 0
    assert "Successfully closed and merged [TASK-1]" in res2.output
    assert not wt_dir.exists()


def test_close_warns_on_unticked_criteria_and_merges(tmp_path: Path, run_cli):
    """Unticked criteria warn and don't block close."""
    repo = _init_repo_with_backlog(tmp_path / "repo_unticked", layout="single")
    run_cli(
        repo,
        "open",
        "Task with criteria",
        "--prefix",
        "TASK",
        "--new-prefix",
        "--criterion",
        "Criterion one",
        "--criterion",
        "Criterion two",
        "--criterion",
        "Criterion three",
    )
    run_cli(repo, "claim", "TASK-1")

    wt_dir = (tmp_path / "worktrees" / "TASK-1").resolve()
    # In worktree, tick #1 only; leave #2 and #3 unticked
    bfile = wt_dir / "BACKLOG.md"
    content = bfile.read_text(encoding="utf-8")
    content = content.replace("- [ ] #1 Criterion one", "- [x] #1 Criterion one")
    bfile.write_text(content, encoding="utf-8")
    subprocess.run(["git", "commit", "-am", "tick criterion #1"], cwd=str(wt_dir), check=True)

    res = run_cli(repo, "close", "TASK-1", "--outcome", "Closed partially")
    assert res.exit_code == 0
    assert "Warning: [TASK-1] closed with 2 unticked criteria: #2, #3" in res.output
    assert "Successfully closed and merged [TASK-1]" in res.output
    assert not wt_dir.exists()


def test_close_compact_entry_no_warning(tmp_path: Path, run_cli):
    """Compact entries get no warning when closed."""
    repo = _init_repo_with_backlog(tmp_path / "repo_compact", layout="single")
    run_cli(
        repo,
        "open",
        "Compact task",
        "--prefix",
        "TASK",
        "--new-prefix",
        "--style",
        "compact",
        "--criterion",
        "Done when tests pass",
    )
    run_cli(repo, "claim", "TASK-1")

    wt_dir = (tmp_path / "worktrees" / "TASK-1").resolve()
    (wt_dir / "file.txt").write_text("ok\n", encoding="utf-8")
    subprocess.run(["git", "add", "file.txt"], cwd=str(wt_dir), check=True)
    subprocess.run(["git", "commit", "-m", "work"], cwd=str(wt_dir), check=True)

    res = run_cli(repo, "close", "TASK-1", "--outcome", "Compact task completed")
    assert res.exit_code == 0
    assert "Warning:" not in res.output
    assert "Successfully closed and merged [TASK-1]" in res.output
    assert not wt_dir.exists()


def test_close_duplicate_check_subfolder_single(tmp_path: Path, run_cli):
    """B1 regression: check detects duplicate when backlog is in a subfolder (single layout)."""
    repo = _init_repo_with_backlog(tmp_path / "repo_sub_single", layout="single")
    (repo / "docs").mkdir()
    subprocess.run(["git", "mv", "BACKLOG.md", "docs/BACKLOG.md"], cwd=str(repo), check=True)
    (repo / ".warehouse.yml").write_text(
        "settings:\n  backlog_layout: single\n  backlog_file: docs/BACKLOG.md\n", encoding="utf-8"
    )
    subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-m", "move backlog to docs/"], cwd=str(repo), check=True)

    run_cli(repo, "open", "First task", "--prefix", "TASK", "--new-prefix")
    run_cli(repo, "open", "Second task", "--prefix", "TASK")
    run_cli(repo, "claim", "TASK-2")

    wt_dir = (tmp_path / "worktrees" / "TASK-2").resolve()
    bfile = wt_dir / "docs" / "BACKLOG.md"
    content = bfile.read_text(encoding="utf-8")
    content = content.replace(
        "## 📌 Backlog (Open Tasks)\n",
        "## 📌 Backlog (Open Tasks)\n\n### [TASK-1] Duplicate copy\n- **Status**: `Open` | **Priority**: `P2`\n",
        1,
    )
    bfile.write_text(content, encoding="utf-8")
    subprocess.run(["git", "commit", "-am", "add dup TASK-1"], cwd=str(wt_dir), check=True)

    res = run_cli(repo, "close", "TASK-2", "--outcome", "done")
    assert res.exit_code != 0
    assert "Duplicate ID [TASK-1]:" in res.output
    assert "docs/BACKLOG.md:" in res.output
    assert wt_dir.is_dir()


def test_close_duplicate_check_subfolder_split(tmp_path: Path, run_cli):
    """B1 regression: check detects duplicate when backlog is in a subfolder (split layout)."""
    repo = _init_repo_with_backlog(tmp_path / "repo_sub_split", layout="split")
    (repo / "docs").mkdir()
    subprocess.run(["git", "mv", "BACKLOG", "docs/BACKLOG"], cwd=str(repo), check=True)
    (repo / ".warehouse.yml").write_text(
        "settings:\n  backlog_layout: split\n  backlog_dir: docs/BACKLOG\n", encoding="utf-8"
    )
    subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-m", "move split backlog to docs/"], cwd=str(repo), check=True)

    run_cli(repo, "open", "First task", "--prefix", "TASK", "--new-prefix")
    run_cli(repo, "open", "Second task", "--prefix", "TASK")
    run_cli(repo, "claim", "TASK-2")

    wt_dir = (tmp_path / "worktrees" / "TASK-2").resolve()
    open_file = wt_dir / "docs" / "BACKLOG" / "Open.md"
    content = open_file.read_text(encoding="utf-8")
    open_file.write_text(
        content + "\n### [TASK-1] Dup copy\n- **Status**: `Open` | **Priority**: `P2`\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "commit", "-am", "add dup TASK-1"], cwd=str(wt_dir), check=True)

    res = run_cli(repo, "close", "TASK-2", "--outcome", "done")
    assert res.exit_code != 0
    assert "Duplicate ID [TASK-1]:" in res.output
    assert "docs/BACKLOG/Open.md:" in res.output
    assert wt_dir.is_dir()


def test_close_duplicate_check_subfolder_folders(tmp_path: Path, run_cli):
    """B1 regression: check detects duplicate when backlog is in a subfolder (folders layout)."""
    repo = _init_repo_with_backlog(tmp_path / "repo_sub_folders", layout="folders")
    (repo / "docs").mkdir()
    subprocess.run(["git", "mv", "BACKLOG", "docs/BACKLOG"], cwd=str(repo), check=True)
    (repo / ".warehouse.yml").write_text(
        "settings:\n  backlog_layout: folders\n  backlog_dir: docs/BACKLOG\n", encoding="utf-8"
    )
    subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-m", "move folders backlog to docs/"], cwd=str(repo), check=True)

    run_cli(repo, "open", "First task", "--prefix", "TASK", "--new-prefix")
    run_cli(repo, "open", "Second task", "--prefix", "TASK")
    run_cli(repo, "claim", "TASK-2")

    wt_dir = (tmp_path / "worktrees" / "TASK-2").resolve()
    dup_file = wt_dir / "docs" / "BACKLOG" / "open" / "TASK-1-dup.md"
    dup_file.write_text(
        '---\nid: "TASK-1"\ntitle: Dup\nstatus: Open\npriority: P2\ncreated: 2026-10-20\n---\n\n# [TASK-1] Dup\n',
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=str(wt_dir), check=True)
    subprocess.run(["git", "commit", "-m", "add dup item"], cwd=str(wt_dir), check=True)

    res = run_cli(repo, "close", "TASK-2", "--outcome", "done")
    assert res.exit_code != 0
    assert "Duplicate ID [TASK-1]:" in res.output
    assert "docs/BACKLOG/open/" in res.output
    assert wt_dir.is_dir()


def test_close_rerun_syncs_moved_base(tmp_path: Path, run_cli):
    """B2 regression: re-run of close syncs moved base and detects duplicate."""
    repo = _init_repo_with_backlog(tmp_path / "repo_rerun_sync", layout="folders")
    run_cli(repo, "open", "Alpha", "--prefix", "TASK", "--new-prefix")
    run_cli(repo, "open", "Beta", "--prefix", "TASK")
    run_cli(repo, "claim", "TASK-2")

    wt_dir = (tmp_path / "worktrees" / "TASK-2").resolve()
    dup_file = wt_dir / "BACKLOG" / "open" / "TASK-1-dup.md"
    dup_file.write_text(
        '---\nid: "TASK-1"\ntitle: Dup\nstatus: Open\npriority: P2\ncreated: 2026-10-20\n---\n\n# [TASK-1] Dup\n',
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=str(wt_dir), check=True)
    subprocess.run(["git", "commit", "-m", "dup TASK-1"], cwd=str(wt_dir), check=True)

    # First close attempt blocked by TASK-1 duplicate
    res1 = run_cli(repo, "close", "TASK-2", "--outcome", "done")
    assert res1.exit_code != 0
    assert "Duplicate ID [TASK-1]" in res1.output

    # Meanwhile base gains TASK-7
    base_file = repo / "BACKLOG" / "open" / "TASK-7-on-main.md"
    base_file.write_text(
        '---\nid: "TASK-7"\ntitle: On main\nstatus: Open\npriority: P2\ncreated: 2026-10-20\n---\n\n# [TASK-7] Main\n',
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-m", "base adds TASK-7"], cwd=str(repo), check=True)

    # Worktree fixes TASK-1 dup, but adds its own TASK-7
    dup_file.unlink()
    branch_file = wt_dir / "BACKLOG" / "open" / "TASK-7-on-branch.md"
    branch_file.write_text(
        '---\nid: "TASK-7"\ntitle: On branch\nstatus: Open\npriority: P2\ncreated: 2026-10-20\n---\n\n# [TASK-7] Branch\n',
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=str(wt_dir), check=True)
    subprocess.run(["git", "commit", "-m", "fix dup 1, add 7"], cwd=str(wt_dir), check=True)

    # Re-running close should sync base and catch duplicate TASK-7
    res2 = run_cli(repo, "close", "TASK-2", "--outcome", "done")
    assert res2.exit_code != 0
    assert "Duplicate ID [TASK-7]" in res2.output
    assert wt_dir.is_dir()


def test_close_indented_heading_in_note_not_false_positive(tmp_path: Path, run_cli):
    """S1 regression: indented heading in note or code block does not trigger false positive."""
    repo = _init_repo_with_backlog(tmp_path / "repo_indented_note", layout="single")
    run_cli(repo, "open", "Alpha", "--prefix", "TASK", "--new-prefix")
    run_cli(repo, "open", "Beta", "--prefix", "TASK")
    run_cli(repo, "claim", "TASK-2")

    wt_dir = (tmp_path / "worktrees" / "TASK-2").resolve()
    bfile = wt_dir / "BACKLOG.md"
    t = bfile.read_text(encoding="utf-8")
    anchor = "### [TASK-2] Beta\n"
    i = t.index(anchor)
    j = t.index("#### Outcome", i)
    t = (
        t[:j]
        + "#### Notes\n- 2026-10-20: code block quoting TASK-1:\n\n"
        + "      ### [TASK-1] Alpha\n\n"
        + t[j:]
    )
    bfile.write_text(t, encoding="utf-8")
    subprocess.run(["git", "commit", "-am", "note quoting TASK-1"], cwd=str(wt_dir), check=True)

    res = run_cli(repo, "close", "TASK-2", "--outcome", "done")
    assert res.exit_code == 0
    assert "Duplicate ID" not in res.output
    assert not wt_dir.exists()
