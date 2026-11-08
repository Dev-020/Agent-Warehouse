"""Query command tests (list, next) across single, split, and folders layouts.

Decision 43:
- In-memory pure selection tests for list and next
- Git-backed integration tests with fixtures writing backlog directly and committing once
- Claim overlay tested via git branch claim/<ID>
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from backlog_cli import TaskError
from backlog_cli.commands import select_list_items, select_next_item
from backlog_cli.model import Item
from conftest import _init_repo_with_backlog, make_claim_branch, make_repo, seed_items


# ===========================================================================
# Pure in-memory unit tests (Decision 43)
# ===========================================================================


def test_pure_select_list_items():
    """In-memory testing of select_list_items filters and sorting."""
    items = [
        Item(id="TASK-1", title="Task 1", status="Open", priority="P1", fields={"created": "2026-10-01"}),
        Item(id="TASK-2", title="Task 2", status="Open", priority="P2", fields={"created": "2026-10-02"}),
        Item(id="TASK-3", title="Task 3", status="Open", priority="P1", fields={"created": "2026-10-03"}),
        Item(id="TASK-4", title="Task 4", status="Open", priority="P2", fields={"created": "2026-10-04"}),
        Item(id="TASK-5", title="Task 5", status="Rejected", priority="P3", fields={"created": "2026-10-05"}),
    ]
    claims = ["claim/TASK-3"]

    # 1. Default: Open and In Progress (TASK-3 has claim overlay)
    res_default = select_list_items(items, claims)
    ids_default = [entry[3].id for entry in res_default]
    assert ids_default == ["TASK-1", "TASK-3", "TASK-2", "TASK-4"]
    # Check claim overlay status
    assert res_default[1][4] == "In Progress (claim/TASK-3)"

    # 2. --status all
    res_all = select_list_items(items, claims, status_filter="all")
    ids_all = [entry[3].id for entry in res_all]
    assert "TASK-5" in ids_all

    # 3. --status Open: shows only unclaimed Open items
    res_open = select_list_items(items, claims, status_filter="Open")
    ids_open = [entry[3].id for entry in res_open]
    assert ids_open == ["TASK-1", "TASK-2", "TASK-4"]

    # 4. --status "In Progress": shows claimed item
    res_inp = select_list_items(items, claims, status_filter="In Progress")
    ids_inp = [entry[3].id for entry in res_inp]
    assert ids_inp == ["TASK-3"]

    # 5. --priority P1
    res_p1 = select_list_items(items, claims, priority_filter="P1")
    ids_p1 = [entry[3].id for entry in res_p1]
    assert ids_p1 == ["TASK-1", "TASK-3"]

    # 6. Combined --status Open --priority P1
    res_combo = select_list_items(items, claims, status_filter="Open", priority_filter="P1")
    ids_combo = [entry[3].id for entry in res_combo]
    assert ids_combo == ["TASK-1"]

    # 7. Invalid filters raise TaskError (Decision 42)
    with pytest.raises(TaskError, match="Invalid status"):
        select_list_items(items, claims, status_filter="InvalidStatus")
    with pytest.raises(TaskError, match="Invalid priority"):
        select_list_items(items, claims, priority_filter="P9")


def test_pure_select_next_item():
    """In-memory testing of select_next_item priority, ties, dependencies, and claimed items."""
    # 1. Priority P1 beats P2
    items1 = [
        Item(id="TASK-1", title="P2 task", status="Open", priority="P2", fields={"created": "2026-10-01"}),
        Item(id="TASK-2", title="P1 task", status="Open", priority="P1", fields={"created": "2026-10-02"}),
    ]
    best, blocked = select_next_item(items1, [])
    assert best and best.id == "TASK-2"
    assert blocked == 0

    # 2. Dependency: TASK-2 depends on TASK-1 (Open) -> TASK-2 blocked, TASK-1 chosen
    items2 = [
        Item(id="TASK-1", title="Blocker", status="Open", priority="P2", fields={"created": "2026-10-01"}),
        Item(id="TASK-2", title="Dependent", status="Open", priority="P1", fields={"created": "2026-10-02", "depends_on": ["TASK-1"]}),
    ]
    best, blocked = select_next_item(items2, [])
    assert best and best.id == "TASK-1"
    assert blocked == 1

    # 3. Dependency: TASK-1 is Closed -> TASK-2 unblocked and chosen
    items3 = [
        Item(id="TASK-1", title="Blocker", status="Closed", priority="P2", fields={"created": "2026-10-01"}),
        Item(id="TASK-2", title="Dependent", status="Open", priority="P1", fields={"created": "2026-10-02", "depends_on": ["TASK-1"]}),
    ]
    best, blocked = select_next_item(items3, [])
    assert best and best.id == "TASK-2"
    assert blocked == 0

    # 4. Dependency: TASK-1 is Rejected -> TASK-2 remains blocked, no ready items
    items4 = [
        Item(id="TASK-1", title="Blocker", status="Rejected", priority="P2", fields={"created": "2026-10-01"}),
        Item(id="TASK-2", title="Dependent", status="Open", priority="P1", fields={"created": "2026-10-02", "depends_on": ["TASK-1"]}),
    ]
    best, blocked = select_next_item(items4, [])
    assert best is None
    assert blocked == 1

    # 5. Claimed items excluded from blocked count (Decision 42 / N1)
    items5 = [
        Item(id="TASK-1", title="Claimed item", status="Open", priority="P1", fields={"created": "2026-10-01", "depends_on": ["TASK-2"]}),
        Item(id="TASK-2", title="Open item", status="Open", priority="P1", fields={"created": "2026-10-02", "depends_on": ["TASK-1"]}),
    ]
    # TASK-1 is claimed
    best, blocked = select_next_item(items5, ["claim/TASK-1"])
    assert best is None
    # Blocked count should be 1 (only TASK-2), not 2
    assert blocked == 1


# ===========================================================================
# Git-backed integration tests (Decision 43: fast direct writes, 1 per layout)
# ===========================================================================


@pytest.mark.medium
@pytest.mark.parametrize("layout", ["single", "split", "folders"])
def test_list_filters_and_default_statuses(tmp_path: Path, run_cli, layout: str):
    """Decision 31: list filters by status and priority, with default Open and In Progress."""
    repo = _init_repo_with_backlog(tmp_path / f"repo_filt_{layout}", layout=layout)

    open_items = """### [TASK-1] Task 1
- **Status**: `Open` | **Priority**: `P1`
- **Created**: 2026-10-01
### [TASK-2] Task 2
- **Status**: `Open` | **Priority**: `P2`
- **Created**: 2026-10-02
### [TASK-3] Task 3
- **Status**: `Open` | **Priority**: `P1`
- **Created**: 2026-10-03
### [TASK-4] Task 4
- **Status**: `Open` | **Priority**: `P2`
- **Created**: 2026-10-04
"""
    closed_items = """### [TASK-5] Task 5
- **Status**: `Rejected` | **Priority**: `P3`
- **Created**: 2026-10-05
- **Resolved**: 2026-10-06
"""
    f_open = {
        "TASK-1-task-1.md": '---\nid: "TASK-1"\ntitle: "Task 1"\nstatus: Open\npriority: P1\ncreated: 2026-10-01\n---\n# [TASK-1] Task 1\n',
        "TASK-2-task-2.md": '---\nid: "TASK-2"\ntitle: "Task 2"\nstatus: Open\npriority: P2\ncreated: 2026-10-02\n---\n# [TASK-2] Task 2\n',
        "TASK-3-task-3.md": '---\nid: "TASK-3"\ntitle: "Task 3"\nstatus: Open\npriority: P1\ncreated: 2026-10-03\n---\n# [TASK-3] Task 3\n',
        "TASK-4-task-4.md": '---\nid: "TASK-4"\ntitle: "Task 4"\nstatus: Open\npriority: P2\ncreated: 2026-10-04\n---\n# [TASK-4] Task 4\n',
    }
    f_closed = {
        "TASK-5-task-5.md": '---\nid: "TASK-5"\ntitle: "Task 5"\nstatus: Rejected\npriority: P3\ncreated: 2026-10-05\nresolved: 2026-10-06\n---\n# [TASK-5] Task 5\n',
    }
    seed_items(repo, layout, open_entries=open_items, closed_entries=closed_items, folders_open=f_open, folders_closed=f_closed)

    # Claim overlay via branch (Decision 43)
    make_claim_branch(repo, "TASK-3")

    # 1. Default: shows Open and In Progress (TASK-1, TASK-2, TASK-3, TASK-4)
    res_default = run_cli(repo, "list")
    assert res_default.exit_code == 0
    lines = [l for l in res_default.output.splitlines() if l.strip()]
    ids = [l.split("\t")[0] for l in lines]
    assert "TASK-1" in ids
    assert "TASK-2" in ids
    assert "TASK-3" in ids
    assert "TASK-4" in ids
    assert "TASK-5" not in ids

    # 2. --status all: shows all items including rejected
    res_all = run_cli(repo, "list", "--status", "all")
    assert res_all.exit_code == 0
    lines_all = [l for l in res_all.output.splitlines() if l.strip()]
    ids_all = [l.split("\t")[0] for l in lines_all]
    assert "TASK-5" in ids_all

    # 3. --status Open: shows only unclaimed Open items
    res_open = run_cli(repo, "list", "--status", "Open")
    assert res_open.exit_code == 0
    lines_open = [l for l in res_open.output.splitlines() if l.strip()]
    ids_open = [l.split("\t")[0] for l in lines_open]
    assert "TASK-1" in ids_open
    assert "TASK-2" in ids_open
    assert "TASK-4" in ids_open
    assert "TASK-3" not in ids_open

    # 4. --status "In Progress": shows claimed item
    res_inp = run_cli(repo, "list", "--status", "In Progress")
    assert res_inp.exit_code == 0
    lines_inp = [l for l in res_inp.output.splitlines() if l.strip()]
    ids_inp = [l.split("\t")[0] for l in lines_inp]
    assert ids_inp == ["TASK-3"]

    # 5. --priority P1: filters to P1 items (TASK-1 and TASK-3)
    res_p1 = run_cli(repo, "list", "--priority", "P1")
    assert res_p1.exit_code == 0
    lines_p1 = [l for l in res_p1.output.splitlines() if l.strip()]
    ids_p1 = [l.split("\t")[0] for l in lines_p1]
    assert set(ids_p1) == {"TASK-1", "TASK-3"}

    # 6. Combined --status Open --priority P1
    res_combo = run_cli(repo, "list", "--status", "Open", "--priority", "P1")
    assert res_combo.exit_code == 0
    lines_combo = [l for l in res_combo.output.splitlines() if l.strip()]
    ids_combo = [l.split("\t")[0] for l in lines_combo]
    assert ids_combo == ["TASK-1"]


@pytest.mark.medium
@pytest.mark.parametrize("layout", ["single", "split", "folders"])
def test_list_claim_overlay(tmp_path: Path, run_cli, layout: str):
    """Decision 31: item with claim/<ID> branch shows In Progress (claim/<ID>)."""
    repo = _init_repo_with_backlog(tmp_path / f"repo_over_{layout}", layout=layout)
    open_items = """### [TASK-1] Unclaimed task
- **Status**: `Open` | **Priority**: `P2`
- **Created**: 2026-10-01
### [TASK-2] Claimed task
- **Status**: `Open` | **Priority**: `P2`
- **Created**: 2026-10-02
"""
    f_open = {
        "TASK-1-unclaimed.md": '---\nid: "TASK-1"\ntitle: "Unclaimed task"\nstatus: Open\npriority: P2\ncreated: 2026-10-01\n---\n# [TASK-1] Unclaimed task\n',
        "TASK-2-claimed.md": '---\nid: "TASK-2"\ntitle: "Claimed task"\nstatus: Open\npriority: P2\ncreated: 2026-10-02\n---\n# [TASK-2] Claimed task\n',
    }
    seed_items(repo, layout, open_entries=open_items, folders_open=f_open)

    # Claim overlay via branch (Decision 43)
    make_claim_branch(repo, "TASK-2")

    res = run_cli(repo, "list")
    assert res.exit_code == 0
    lines = [l for l in res.output.splitlines() if l.strip()]
    by_id = {l.split("\t")[0]: l.split("\t") for l in lines}

    assert by_id["TASK-1"][2] == "Open"
    assert by_id["TASK-2"][2] == "In Progress (claim/TASK-2)"


@pytest.mark.medium
@pytest.mark.parametrize("layout", ["single", "split", "folders"])
def test_list_sort_order(tmp_path: Path, run_cli, layout: str):
    """Decision 31: sort order is priority, then Created, then position/name."""
    repo = _init_repo_with_backlog(tmp_path / f"repo_sort_{layout}", layout=layout)

    open_items = """### [TASK-A] Task A
- **Status**: `Open` | **Priority**: `P2`
- **Created**: 2026-10-01
### [TASK-B] Task B
- **Status**: `Open` | **Priority**: `P1`
- **Created**: 2026-10-10
### [TASK-C] Task C
- **Status**: `Open` | **Priority**: `P1`
- **Created**: 2026-10-05
### [TASK-D] Task D
- **Status**: `Open` | **Priority**: `P1`
- **Created**: 2026-10-05
"""
    f_open = {
        "TASK-A-a.md": '---\nid: "TASK-A"\ntitle: "Task A"\nstatus: Open\npriority: P2\ncreated: 2026-10-01\n---\n# [TASK-A] Task A\n',
        "TASK-B-b.md": '---\nid: "TASK-B"\ntitle: "Task B"\nstatus: Open\npriority: P1\ncreated: 2026-10-10\n---\n# [TASK-B] Task B\n',
        "TASK-C-c.md": '---\nid: "TASK-C"\ntitle: "Task C"\nstatus: Open\npriority: P1\ncreated: 2026-10-05\n---\n# [TASK-C] Task C\n',
        "TASK-D-d.md": '---\nid: "TASK-D"\ntitle: "Task D"\nstatus: Open\npriority: P1\ncreated: 2026-10-05\n---\n# [TASK-D] Task D\n',
    }
    seed_items(repo, layout, open_entries=open_items, folders_open=f_open)

    res = run_cli(repo, "list")
    assert res.exit_code == 0
    lines = [l for l in res.output.splitlines() if l.strip()]
    ids = [l.split("\t")[0] for l in lines]
    assert ids == ["TASK-C", "TASK-D", "TASK-B", "TASK-A"]


@pytest.mark.medium
@pytest.mark.parametrize("layout", ["single", "split", "folders"])
def test_list_no_items(tmp_path: Path, run_cli, layout: str):
    """Decision 31: empty list prints No items. and exits 0."""
    repo = _init_repo_with_backlog(tmp_path / f"repo_empty_{layout}", layout=layout)
    res = run_cli(repo, "list")
    assert res.exit_code == 0
    assert res.output.strip() == "No items."

    open_items = """### [TASK-1] Only task
- **Status**: `Open` | **Priority**: `P2`
- **Created**: 2026-10-01
"""
    f_open = {"TASK-1-only.md": '---\nid: "TASK-1"\ntitle: "Only task"\nstatus: Open\npriority: P2\ncreated: 2026-10-01\n---\n# [TASK-1] Only task\n'}
    seed_items(repo, layout, open_entries=open_items, folders_open=f_open)

    res_none = run_cli(repo, "list", "--priority", "P1")
    assert res_none.exit_code == 0
    assert res_none.output.strip() == "No items."


@pytest.mark.medium
@pytest.mark.parametrize("layout", ["single", "split", "folders"])
def test_next_with_priorities_ties_dependencies(tmp_path: Path, run_cli, layout: str):
    """Decision 32: next selects highest priority ready item, ties on Created, checks dependencies."""
    repo = _init_repo_with_backlog(tmp_path / f"repo_nxt_{layout}", layout=layout)

    # 1. P2 vs P1: next picks P1
    open_items1 = """### [TASK-1] P2 task
- **Status**: `Open` | **Priority**: `P2`
- **Created**: 2026-10-01
### [TASK-2] P1 task
- **Status**: `Open` | **Priority**: `P1`
- **Created**: 2026-10-02
"""
    f_open1 = {
        "TASK-1-p2.md": '---\nid: "TASK-1"\ntitle: "P2 task"\nstatus: Open\npriority: P2\ncreated: 2026-10-01\n---\n# [TASK-1] P2 task\n',
        "TASK-2-p1.md": '---\nid: "TASK-2"\ntitle: "P1 task"\nstatus: Open\npriority: P1\ncreated: 2026-10-02\n---\n# [TASK-2] P1 task\n',
    }
    seed_items(repo, layout, open_entries=open_items1, folders_open=f_open1)

    res_p1 = run_cli(repo, "next")
    assert res_p1.exit_code == 0
    assert "[TASK-2] P1 task (P1, created " in res_p1.output

    # 2. Dependency: TASK-2 depends on TASK-1 (which is Open) -> TASK-2 is blocked
    open_items2 = """### [TASK-1] P2 task
- **Status**: `Open` | **Priority**: `P2`
- **Created**: 2026-10-01
### [TASK-2] P1 task
- **Status**: `Open` | **Priority**: `P1`
- **Created**: 2026-10-02
- **Depends on**: [TASK-1]
"""
    f_open2 = {
        "TASK-1-p2.md": '---\nid: "TASK-1"\ntitle: "P2 task"\nstatus: Open\npriority: P2\ncreated: 2026-10-01\n---\n# [TASK-1] P2 task\n',
        "TASK-2-p1.md": '---\nid: "TASK-2"\ntitle: "P1 task"\nstatus: Open\npriority: P1\ncreated: 2026-10-02\ndepends_on: ["TASK-1"]\n---\n# [TASK-2] P1 task\n',
    }
    seed_items(repo, layout, open_entries=open_items2, folders_open=f_open2)

    res_dep_open = run_cli(repo, "next")
    assert res_dep_open.exit_code == 0
    assert "[TASK-1] P2 task (P2, created " in res_dep_open.output

    # 3. TASK-1 is Rejected -> TASK-2's dependency is Rejected -> TASK-2 is still not ready!
    open_items3 = """### [TASK-2] P1 task
- **Status**: `Open` | **Priority**: `P1`
- **Created**: 2026-10-02
- **Depends on**: [TASK-1]
"""
    closed_items3 = """### [TASK-1] P2 task
- **Status**: `Rejected` | **Priority**: `P2`
- **Created**: 2026-10-01
- **Resolved**: 2026-10-03
"""
    f_open3 = {
        "TASK-2-p1.md": '---\nid: "TASK-2"\ntitle: "P1 task"\nstatus: Open\npriority: P1\ncreated: 2026-10-02\ndepends_on: ["TASK-1"]\n---\n# [TASK-2] P1 task\n',
    }
    f_closed3 = {
        "TASK-1-p2.md": '---\nid: "TASK-1"\ntitle: "P2 task"\nstatus: Rejected\npriority: P2\ncreated: 2026-10-01\nresolved: 2026-10-03\n---\n# [TASK-1] P2 task\n',
    }
    if layout == "folders":
        old = repo / "BACKLOG" / "open" / "TASK-1-p2.md"
        if old.exists():
            old.unlink()
    seed_items(repo, layout, open_entries=open_items3, closed_entries=closed_items3, folders_open=f_open3, folders_closed=f_closed3)

    res_dep_rej = run_cli(repo, "next")
    assert res_dep_rej.exit_code == 0
    assert "No ready item." in res_dep_rej.output
    assert "1 open item is blocked." in res_dep_rej.output


@pytest.mark.medium
@pytest.mark.parametrize("layout", ["single", "split", "folders"])
def test_next_no_ready_item_blocked_count(tmp_path: Path, run_cli, layout: str):
    """Decision 32: when nothing is ready, print No ready item. and count of blocked open items."""
    repo = _init_repo_with_backlog(tmp_path / f"repo_blk_{layout}", layout=layout)

    # Empty backlog
    res_empty = run_cli(repo, "next")
    assert res_empty.exit_code == 0
    assert "No ready item." in res_empty.output
    assert "0 open items are blocked." in res_empty.output

    # Two items, both depending on a missing/unresolved item
    open_items = """### [TASK-1] Blocked one
- **Status**: `Open` | **Priority**: `P2`
- **Depends on**: [MISSING-1]
### [TASK-2] Blocked two
- **Status**: `Open` | **Priority**: `P2`
- **Depends on**: [MISSING-2]
"""
    f_open = {
        "TASK-1-one.md": '---\nid: "TASK-1"\ntitle: "Blocked one"\nstatus: Open\npriority: P2\ndepends_on: ["MISSING-1"]\n---\n# [TASK-1] Blocked one\n',
        "TASK-2-two.md": '---\nid: "TASK-2"\ntitle: "Blocked two"\nstatus: Open\npriority: P2\ndepends_on: ["MISSING-2"]\n---\n# [TASK-2] Blocked two\n',
    }
    seed_items(repo, layout, open_entries=open_items, folders_open=f_open)

    res_blk = run_cli(repo, "next")
    assert res_blk.exit_code == 0
    assert "No ready item." in res_blk.output
    assert "2 open items are blocked." in res_blk.output


@pytest.mark.medium
@pytest.mark.parametrize("layout", ["single", "split", "folders"])
def test_next_blocked_count_excludes_claimed(tmp_path: Path, run_cli, layout: str):
    """Decision 42 (N1): next blocked count excludes claimed items."""
    repo = _init_repo_with_backlog(tmp_path / f"repo_ex_{layout}", layout=layout)

    open_items = """### [TASK-1] Alpha
- **Status**: `Open` | **Priority**: `P1`
- **Depends on**: [TASK-2]
### [TASK-2] Beta
- **Status**: `Open` | **Priority**: `P1`
- **Depends on**: [TASK-1]
"""
    f_open = {
        "TASK-1-alpha.md": '---\nid: "TASK-1"\ntitle: "Alpha"\nstatus: Open\npriority: P1\ndepends_on: ["TASK-2"]\n---\n# [TASK-1] Alpha\n',
        "TASK-2-beta.md": '---\nid: "TASK-2"\ntitle: "Beta"\nstatus: Open\npriority: P1\ndepends_on: ["TASK-1"]\n---\n# [TASK-2] Beta\n',
    }
    seed_items(repo, layout, open_entries=open_items, folders_open=f_open)

    # Claim TASK-1 via branch (Decision 43)
    make_claim_branch(repo, "TASK-1")

    res = run_cli(repo, "next")
    assert res.exit_code == 0
    assert "1 open item is blocked." in res.output


@pytest.mark.medium
def test_list_rejects_unknown_status_and_priority(tmp_path: Path, run_cli):
    """Decision 42 (N4): list rejects unknown status and priority values."""
    repo = _init_repo_with_backlog(tmp_path / "repo_rej_args", layout="single")

    res_st = run_cli(repo, "list", "--status", "Opne")
    assert res_st.exit_code != 0
    assert "Invalid status 'Opne'" in res_st.output

    res_pr = run_cli(repo, "list", "--priority", "P9")
    assert res_pr.exit_code != 0
    assert "Invalid priority 'P9'" in res_pr.output
