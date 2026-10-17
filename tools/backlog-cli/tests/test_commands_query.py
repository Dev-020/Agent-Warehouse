"""Query command tests (list, next) across single, split, and folders layouts."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from conftest import make_repo
from test_commands_core import _init_repo_with_backlog


@pytest.mark.parametrize("layout", ["single", "split", "folders"])
def test_list_filters_and_default_statuses(tmp_path: Path, run_cli, layout: str):
    """Decision 31: list filters by status and priority, with default Open and In Progress."""
    repo = _init_repo_with_backlog(tmp_path / f"repo_filt_{layout}", layout=layout)
    run_cli(repo, "open", "Task 1", "--prefix", "TASK", "--new-prefix", "--priority", "P1")
    run_cli(repo, "open", "Task 2", "--prefix", "TASK", "--priority", "P2")
    run_cli(repo, "open", "Task 3", "--prefix", "TASK", "--priority", "P1")
    run_cli(repo, "open", "Task 4", "--prefix", "TASK", "--priority", "P2")
    run_cli(repo, "open", "Task 5", "--prefix", "TASK", "--priority", "P3")

    # Claim Task 3 (In Progress)
    run_cli(repo, "claim", "TASK-3")

    # Reject Task 5
    run_cli(repo, "reject", "TASK-5", "--reason", "Not doing")

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


@pytest.mark.parametrize("layout", ["single", "split", "folders"])
def test_list_claim_overlay(tmp_path: Path, run_cli, layout: str):
    """Decision 31: item with claim/<ID> branch shows In Progress (claim/<ID>)."""
    repo = _init_repo_with_backlog(tmp_path / f"repo_over_{layout}", layout=layout)
    run_cli(repo, "open", "Unclaimed task", "--prefix", "TASK", "--new-prefix")
    run_cli(repo, "open", "Claimed task", "--prefix", "TASK")

    # Claim TASK-2
    run_cli(repo, "claim", "TASK-2")

    res = run_cli(repo, "list")
    assert res.exit_code == 0
    lines = [l for l in res.output.splitlines() if l.strip()]
    by_id = {l.split("\t")[0]: l.split("\t") for l in lines}

    assert by_id["TASK-1"][2] == "Open"
    assert by_id["TASK-2"][2] == "In Progress (claim/TASK-2)"


@pytest.mark.parametrize("layout", ["single", "split", "folders"])
def test_list_sort_order(tmp_path: Path, run_cli, layout: str):
    """Decision 31: sort order is priority, then Created, then position/name."""
    repo = _init_repo_with_backlog(tmp_path / f"repo_sort_{layout}", layout=layout)

    # We manually prepare tasks with specific priority, created date, and order
    if layout == "single":
        backlog_text = (
            "# Project Backlog\n\n"
            "> **How this backlog is run** (`convention/backlog`)\n"
            "> - **Layout:** single file\n"
            "> - **Entry style:** compact\n\n"
            "## 📋 In Progress\n\n"
            "## 📌 Backlog (Open Tasks)\n\n"
            "### [TASK-A] Task A\n"
            "- **Status**: `Open` | **Priority**: `P2`\n"
            "- **Created**: 2026-10-01\n"
            "*Wanted:* A\n\n"
            "### [TASK-B] Task B\n"
            "- **Status**: `Open` | **Priority**: `P1`\n"
            "- **Created**: 2026-10-10\n"
            "*Wanted:* B\n\n"
            "### [TASK-C] Task C\n"
            "- **Status**: `Open` | **Priority**: `P1`\n"
            "- **Created**: 2026-10-05\n"
            "*Wanted:* C\n\n"
            "### [TASK-D] Task D\n"
            "- **Status**: `Open` | **Priority**: `P1`\n"
            "- **Created**: 2026-10-05\n"
            "*Wanted:* D\n\n"
            "## ✅ Completed\n\n"
            "## 🧊 Icebox (Not Doing / Rejected)\n"
        )
        (repo / "BACKLOG.md").write_text(backlog_text, encoding="utf-8")
        subprocess.run(["git", "add", "BACKLOG.md"], cwd=str(repo), check=True)
        subprocess.run(["git", "commit", "-q", "-m", "add test items"], cwd=str(repo), check=True)
    elif layout == "split":
        open_text = (
            "## 📋 In Progress\n\n"
            "## 📌 Backlog (Open Tasks)\n\n"
            "### [TASK-A] Task A\n"
            "- **Status**: `Open` | **Priority**: `P2`\n"
            "- **Created**: 2026-10-01\n"
            "*Wanted:* A\n\n"
            "### [TASK-B] Task B\n"
            "- **Status**: `Open` | **Priority**: `P1`\n"
            "- **Created**: 2026-10-10\n"
            "*Wanted:* B\n\n"
            "### [TASK-C] Task C\n"
            "- **Status**: `Open` | **Priority**: `P1`\n"
            "- **Created**: 2026-10-05\n"
            "*Wanted:* C\n\n"
            "### [TASK-D] Task D\n"
            "- **Status**: `Open` | **Priority**: `P1`\n"
            "- **Created**: 2026-10-05\n"
            "*Wanted:* D\n"
        )
        (repo / "BACKLOG" / "Open.md").write_text(open_text, encoding="utf-8")
        subprocess.run(["git", "add", "BACKLOG/Open.md"], cwd=str(repo), check=True)
        subprocess.run(["git", "commit", "-q", "-m", "add test items"], cwd=str(repo), check=True)
    else:
        # For folders, position is filename order
        bdir = repo / "BACKLOG" / "open"
        (bdir / "TASK-A-a.md").write_text(
            '---\nid: "TASK-A"\ntitle: "Task A"\nstatus: Open\npriority: P2\ncreated: 2026-10-01\n---\n# [TASK-A] Task A\n',
            encoding="utf-8",
        )
        (bdir / "TASK-B-b.md").write_text(
            '---\nid: "TASK-B"\ntitle: "Task B"\nstatus: Open\npriority: P1\ncreated: 2026-10-10\n---\n# [TASK-B] Task B\n',
            encoding="utf-8",
        )
        (bdir / "TASK-C-c.md").write_text(
            '---\nid: "TASK-C"\ntitle: "Task C"\nstatus: Open\npriority: P1\ncreated: 2026-10-05\n---\n# [TASK-C] Task C\n',
            encoding="utf-8",
        )
        (bdir / "TASK-D-d.md").write_text(
            '---\nid: "TASK-D"\ntitle: "Task D"\nstatus: Open\npriority: P1\ncreated: 2026-10-05\n---\n# [TASK-D] Task D\n',
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True)
        subprocess.run(["git", "commit", "-q", "-m", "add test items"], cwd=str(repo), check=True)

    res = run_cli(repo, "list")
    assert res.exit_code == 0
    lines = [l for l in res.output.splitlines() if l.strip()]
    ids = [l.split("\t")[0] for l in lines]

    # Priority P1 comes before P2 (TASK-A is last)
    # Among P1: 2026-10-05 comes before 2026-10-10 (C and D before B)
    # Between C and D: position / filename order (C before D)
    assert ids == ["TASK-C", "TASK-D", "TASK-B", "TASK-A"]


@pytest.mark.parametrize("layout", ["single", "split", "folders"])
def test_list_no_items(tmp_path: Path, run_cli, layout: str):
    """Decision 31: empty list prints No items. and exits 0."""
    repo = _init_repo_with_backlog(tmp_path / f"repo_empty_{layout}", layout=layout)
    res = run_cli(repo, "list")
    assert res.exit_code == 0
    assert res.output.strip() == "No items."

    # When items exist but filter doesn't match
    run_cli(repo, "open", "Only task", "--prefix", "TASK", "--new-prefix", "--priority", "P2")
    res_none = run_cli(repo, "list", "--priority", "P1")
    assert res_none.exit_code == 0
    assert res_none.output.strip() == "No items."


@pytest.mark.parametrize("layout", ["single", "split", "folders"])
def test_next_with_priorities_ties_dependencies(tmp_path: Path, run_cli, layout: str):
    """Decision 32: next selects highest priority ready item, ties on Created, checks dependencies."""
    repo = _init_repo_with_backlog(tmp_path / f"repo_nxt_{layout}", layout=layout)

    # 1. P2 vs P1: next picks P1
    run_cli(repo, "open", "P2 task", "--prefix", "TASK", "--new-prefix", "--priority", "P2")
    run_cli(repo, "open", "P1 task", "--prefix", "TASK", "--priority", "P1")

    res_p1 = run_cli(repo, "next")
    assert res_p1.exit_code == 0
    assert "[TASK-2] P1 task (P1, created " in res_p1.output
    assert "claim it with: python task.py claim 'TASK-2'" in res_p1.output

    # 2. Dependency: TASK-3 depends on TASK-1 (which is Open) -> TASK-3 is not ready
    if layout == "single":
        fpath = repo / "BACKLOG.md"
        content = fpath.read_text(encoding="utf-8")
        # Change TASK-2 to depend on TASK-1
        content = content.replace("### [TASK-2] P1 task\n", "### [TASK-2] P1 task\n- **Depends on**: [TASK-1]\n")
        fpath.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", "BACKLOG.md"], cwd=str(repo), check=True)
    elif layout == "split":
        fpath = repo / "BACKLOG" / "Open.md"
        content = fpath.read_text(encoding="utf-8")
        content = content.replace("### [TASK-2] P1 task\n", "### [TASK-2] P1 task\n- **Depends on**: [TASK-1]\n")
        fpath.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", "BACKLOG/Open.md"], cwd=str(repo), check=True)
    else:
        fpath = next((repo / "BACKLOG" / "open").glob("TASK-2-*.md"))
        content = fpath.read_text(encoding="utf-8")
        content = content.replace("status: Open\n", 'status: Open\ndepends_on: ["TASK-1"]\n')
        fpath.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", str(fpath)], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "add dep"], cwd=str(repo), check=True)

    # Now TASK-2 (P1) is blocked because TASK-1 is Open. Next should pick TASK-1 (P2)!
    res_dep_open = run_cli(repo, "next")
    assert res_dep_open.exit_code == 0
    assert "[TASK-1] P2 task (P2, created " in res_dep_open.output

    # 3. Reject TASK-1: TASK-2's dependency is now Rejected -> TASK-2 is still not ready!
    run_cli(repo, "reject", "TASK-1", "--reason", "Won't do")
    res_dep_rej = run_cli(repo, "next")
    assert res_dep_rej.exit_code == 0
    assert "No ready item." in res_dep_rej.output
    assert "1 open item is blocked." in res_dep_rej.output


@pytest.mark.parametrize("layout", ["single", "split", "folders"])
def test_next_no_ready_item_blocked_count(tmp_path: Path, run_cli, layout: str):
    """Decision 32: when nothing is ready, print No ready item. and count of blocked open items."""
    repo = _init_repo_with_backlog(tmp_path / f"repo_blk_{layout}", layout=layout)

    # When backlog has no open items at all
    res_empty = run_cli(repo, "next")
    assert res_empty.exit_code == 0
    assert "No ready item." in res_empty.output
    assert "0 open items are blocked." in res_empty.output

    # Open two items, both depending on a missing item
    run_cli(repo, "open", "Blocked one", "--prefix", "TASK", "--new-prefix")
    run_cli(repo, "open", "Blocked two", "--prefix", "TASK")

    if layout == "single":
        fpath = repo / "BACKLOG.md"
        content = fpath.read_text(encoding="utf-8")
        content = content.replace("### [TASK-1] Blocked one\n", "### [TASK-1] Blocked one\n- **Depends on**: [MISSING-1]\n")
        content = content.replace("### [TASK-2] Blocked two\n", "### [TASK-2] Blocked two\n- **Depends on**: [MISSING-2]\n")
        fpath.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", "BACKLOG.md"], cwd=str(repo), check=True)
    elif layout == "split":
        fpath = repo / "BACKLOG" / "Open.md"
        content = fpath.read_text(encoding="utf-8")
        content = content.replace("### [TASK-1] Blocked one\n", "### [TASK-1] Blocked one\n- **Depends on**: [MISSING-1]\n")
        content = content.replace("### [TASK-2] Blocked two\n", "### [TASK-2] Blocked two\n- **Depends on**: [MISSING-2]\n")
        fpath.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", "BACKLOG/Open.md"], cwd=str(repo), check=True)
    else:
        f1 = next((repo / "BACKLOG" / "open").glob("TASK-1-*.md"))
        f2 = next((repo / "BACKLOG" / "open").glob("TASK-2-*.md"))
        c1 = f1.read_text(encoding="utf-8").replace("status: Open\n", 'status: Open\ndepends_on: ["MISSING-1"]\n')
        c2 = f2.read_text(encoding="utf-8").replace("status: Open\n", 'status: Open\ndepends_on: ["MISSING-2"]\n')
        f1.write_text(c1, encoding="utf-8")
        f2.write_text(c2, encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "add missing deps"], cwd=str(repo), check=True)

    res_blk = run_cli(repo, "next")
    assert res_blk.exit_code == 0
    assert "No ready item." in res_blk.output
    assert "2 open items are blocked." in res_blk.output
