"""Tests for backlog layouts: parsing, surgical updates, priority placement, notes, LF/CRLF preservation, and ID allocation."""

from __future__ import annotations

from pathlib import Path

import pytest
from backlog_cli import TaskError
from backlog_cli.ids import allocate_id
from backlog_cli.layouts import ItemFoldersLayout, SingleFileLayout, SplitFilesLayout
from backlog_cli.model import Item


# ---------------------------------------------------------------------------
# Fixture Helpers
# ---------------------------------------------------------------------------


def make_single_fixture(tmp_path: Path, crlf: bool = False) -> SingleFileLayout:
    tmp_path.mkdir(parents=True, exist_ok=True)
    p = tmp_path / "BACKLOG.md"
    le = "\r\n" if crlf else "\n"
    content = le.join(
        [
            "# Project Backlog",
            "",
            "> **How this backlog is run** (`convention/backlog`)",
            "> - **Layout:** single file",
            "> - **Entry style:** full",
            "",
            "## 📋 In Progress",
            "",
            "### [#001] Existing in progress task",
            "- **Status**: `In Progress` | **Priority**: `P1`",
            "- **Created**: 2026-10-01",
            "",
            "#### Why",
            "Initial work.",
            "",
            "#### Wanted",
            "Working feature.",
            "",
            "#### Acceptance Criteria",
            "- [ ] #1 Tests pass.",
            "",
            "#### Outcome",
            "(Filled on completion.)",
            "",
            "## 📌 Backlog (Open Tasks)",
            "",
            "### [#010] P1 high priority task",
            "- **Status**: `Open` | **Priority**: `P1`",
            "- **Created**: 2026-10-02",
            "",
            "#### Why",
            "Important bug.",
            "",
            "#### Wanted",
            "Bug resolved.",
            "",
            "#### Acceptance Criteria",
            "- [ ] #1 Bug fixed.",
            "",
            "#### Outcome",
            "(Filled on completion.)",
            "",
            "### [#020] P3 low priority task",
            "- **Status**: `Open` | **Priority**: `P3`",
            "- **Created**: 2026-10-03",
            "",
            "#### Why",
            "Minor polish.",
            "",
            "#### Wanted",
            "Polished UI.",
            "",
            "#### Acceptance Criteria",
            "- [ ] #1 UI updated.",
            "",
            "#### Outcome",
            "(Filled on completion.)",
            "",
            "## ✅ Completed",
            "",
            "### [#000] Old done task",
            "- **Status**: `Closed` | **Priority**: `P2`",
            "- **Created**: 2026-09-01",
            "- **Resolved**: 2026-09-02",
            "",
            "#### Outcome",
            "Finished early.",
            "",
            "## 🧊 Icebox (Not Doing / Rejected)",
            "",
        ]
    ) + le
    p.write_bytes(content.encode("utf-8"))
    return SingleFileLayout(p)


def make_split_fixture(tmp_path: Path, crlf: bool = False) -> SplitFilesLayout:
    bdir = tmp_path / "BACKLOG"
    bdir.mkdir(parents=True, exist_ok=True)
    le = "\r\n" if crlf else "\n"

    hdr = le.join(
        [
            "> **How this backlog is run** (`convention/backlog`)",
            "> - **Layout:** split files",
            "> - **Entry style:** full",
            "",
        ]
    )
    (bdir / "00_BACKLOG.md").write_bytes(hdr.encode("utf-8"))

    open_content = le.join(
        [
            "## 📋 In Progress",
            "",
            "### [#001] Existing in progress task",
            "- **Status**: `In Progress` | **Priority**: `P1`",
            "- **Created**: 2026-10-01",
            "",
            "#### Why",
            "Initial work.",
            "",
            "#### Wanted",
            "Working feature.",
            "",
            "#### Acceptance Criteria",
            "- [ ] #1 Tests pass.",
            "",
            "#### Outcome",
            "(Filled on completion.)",
            "",
            "## 📌 Backlog (Open Tasks)",
            "",
            "### [#010] P1 high priority task",
            "- **Status**: `Open` | **Priority**: `P1`",
            "- **Created**: 2026-10-02",
            "",
            "#### Why",
            "Important bug.",
            "",
            "#### Wanted",
            "Bug resolved.",
            "",
            "#### Acceptance Criteria",
            "- [ ] #1 Bug fixed.",
            "",
            "#### Outcome",
            "(Filled on completion.)",
            "",
            "### [#020] P3 low priority task",
            "- **Status**: `Open` | **Priority**: `P3`",
            "- **Created**: 2026-10-03",
            "",
            "#### Why",
            "Minor polish.",
            "",
            "#### Wanted",
            "Polished UI.",
            "",
            "#### Acceptance Criteria",
            "- [ ] #1 UI updated.",
            "",
            "#### Outcome",
            "(Filled on completion.)",
            "",
        ]
    ) + le
    (bdir / "Open.md").write_bytes(open_content.encode("utf-8"))

    closed_content = le.join(
        [
            "## ✅ Completed",
            "",
            "### [#000] Old done task",
            "- **Status**: `Closed` | **Priority**: `P2`",
            "- **Created**: 2026-09-01",
            "- **Resolved**: 2026-09-02",
            "",
            "#### Outcome",
            "Finished early.",
            "",
            "## 🧊 Icebox (Not Doing / Rejected)",
            "",
        ]
    ) + le
    (bdir / "Closed.md").write_bytes(closed_content.encode("utf-8"))

    return SplitFilesLayout(bdir)


def make_folders_fixture(tmp_path: Path) -> ItemFoldersLayout:
    bdir = tmp_path / "BACKLOG"
    (bdir / "open").mkdir(parents=True, exist_ok=True)
    (bdir / "closed").mkdir(parents=True, exist_ok=True)

    hdr = "> **How this backlog is run** (`convention/backlog`)\n> - **Layout:** item folders\n> - **Entry style:** full\n"
    (bdir / "00_BACKLOG.md").write_text(hdr, encoding="utf-8")

    item1 = (
        "---\n"
        'id: "#001"\n'
        "title: Existing in progress task\n"
        "status: In Progress\n"
        "priority: P1\n"
        "created: 2026-10-01\n"
        "---\n\n"
        "# [#001] Existing in progress task\n\n"
        "## Why\nInitial work.\n\n"
        "## Wanted\nWorking feature.\n\n"
        "## Acceptance Criteria\n- [ ] #1 Tests pass.\n\n"
        "## Outcome\n(Filled on completion.)\n"
    )
    (bdir / "open" / "001-existing-in-progress-task.md").write_text(item1, encoding="utf-8")

    item10 = (
        "---\n"
        'id: "#010"\n'
        "title: P1 high priority task\n"
        "status: Open\n"
        "priority: P1\n"
        "created: 2026-10-02\n"
        "---\n\n"
        "# [#010] P1 high priority task\n\n"
        "## Why\nImportant bug.\n\n"
        "## Wanted\nBug resolved.\n\n"
        "## Acceptance Criteria\n- [ ] #1 Bug fixed.\n\n"
        "## Outcome\n(Filled on completion.)\n"
    )
    (bdir / "open" / "010-p1-high-priority-task.md").write_text(item10, encoding="utf-8")

    item20 = (
        "---\n"
        'id: "#020"\n'
        "title: P3 low priority task\n"
        "status: Open\n"
        "priority: P3\n"
        "created: 2026-10-03\n"
        "---\n\n"
        "# [#020] P3 low priority task\n\n"
        "## Why\nMinor polish.\n\n"
        "## Wanted\nPolished UI.\n\n"
        "## Acceptance Criteria\n- [ ] #1 UI updated.\n\n"
        "## Outcome\n(Filled on completion.)\n"
    )
    (bdir / "open" / "020-p3-low-priority-task.md").write_text(item20, encoding="utf-8")

    item0 = (
        "---\n"
        'id: "#000"\n'
        "title: Old done task\n"
        "status: Closed\n"
        "priority: P2\n"
        "created: 2026-09-01\n"
        "resolved: 2026-09-02\n"
        "---\n\n"
        "# [#000] Old done task\n\n"
        "## Outcome\nFinished early.\n"
    )
    (bdir / "closed" / "000-old-done-task.md").write_text(item0, encoding="utf-8")

    return ItemFoldersLayout(bdir)


# ---------------------------------------------------------------------------
# Layout Tests (Single, Split, Folders)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("layout_type", ["single", "split", "folders"])
def test_layout_parse_and_find(tmp_path: Path, layout_type: str):
    sub = tmp_path / layout_type
    if layout_type == "single":
        layout = make_single_fixture(sub)
    elif layout_type == "split":
        layout = make_split_fixture(sub)
    else:
        layout = make_folders_fixture(sub)

    items = layout.items()
    ids = [it.id for it in items]
    assert "#001" in ids
    assert "#010" in ids
    assert "#020" in ids
    assert "#000" in ids

    # Find with leading # and without
    it1 = layout.find("#010")
    assert it1 is not None
    assert it1.title == "P1 high priority task"
    assert it1.priority == "P1"
    assert it1.status == "Open"

    it1_no_hash = layout.find("010")
    assert it1_no_hash is not None
    assert it1_no_hash.id == "#010"


@pytest.mark.parametrize("layout_type", ["single", "split", "folders"])
def test_layout_add_priority_placement(tmp_path: Path, layout_type: str):
    sub = tmp_path / layout_type
    if layout_type == "single":
        layout = make_single_fixture(sub)
    elif layout_type == "split":
        layout = make_split_fixture(sub)
    else:
        layout = make_folders_fixture(sub)

    # Insert a P2 item (should be placed after P1 #010 and before P3 #020 in single/split)
    new_item = Item(
        id="#015",
        title="Middle priority item",
        status="Open",
        priority="P2",
        fields={"why": "Needed feature", "wanted": "Deliverable", "criteria": ["Works"]},
    )
    layout.add(new_item, style="full")

    found = layout.find("#015")
    assert found is not None
    assert found.priority == "P2"

    if layout_type in ("single", "split"):
        target_file = sub / "BACKLOG.md" if layout_type == "single" else sub / "BACKLOG" / "Open.md"
        content = target_file.read_text(encoding="utf-8")
        # Ensure #015 appears between #010 and #020
        idx_p1 = content.index("[#010]")
        idx_p2 = content.index("[#015]")
        idx_p3 = content.index("[#020]")
        assert idx_p1 < idx_p2 < idx_p3


@pytest.mark.parametrize("layout_type", ["single", "split", "folders"])
def test_layout_claim_and_close_moves(tmp_path: Path, layout_type: str):
    sub = tmp_path / layout_type
    if layout_type == "single":
        layout = make_single_fixture(sub)
    elif layout_type == "split":
        layout = make_split_fixture(sub)
    else:
        layout = make_folders_fixture(sub)

    # 1. Claim #010
    layout.set_status("#010", "In Progress")
    it_claimed = layout.find("#010")
    assert it_claimed is not None
    assert it_claimed.status == "In Progress"

    # 2. Close #010
    layout.close("#010", "Closed", "Finished all criteria with evidence.")
    it_closed = layout.find("#010")
    assert it_closed is not None
    assert it_closed.status == "Closed"
    assert "resolved" in it_closed.fields or "- **Resolved**:" in it_closed.raw

    # Check bottom placement in Completed section
    if layout_type in ("single", "split"):
        target_file = sub / "BACKLOG.md" if layout_type == "single" else sub / "BACKLOG" / "Closed.md"
        content = target_file.read_text(encoding="utf-8")
        idx_old = content.index("[#000]")
        idx_new = content.index("[#010]")
        # #010 must be placed below the existing completed item #000
        assert idx_old < idx_new
        assert "Finished all criteria with evidence." in content
    else:
        # In folders, verify item moved to closed/
        assert not (sub / "BACKLOG" / "open" / "010-p1-high-priority-task.md").exists()
        closed_file = sub / "BACKLOG" / "closed" / "010-p1-high-priority-task.md"
        assert closed_file.is_file()
        content = closed_file.read_text(encoding="utf-8")
        assert "status: Closed" in content
        assert "Finished all criteria with evidence." in content


@pytest.mark.parametrize("layout_type", ["single", "split", "folders"])
def test_layout_append_note(tmp_path: Path, layout_type: str):
    sub = tmp_path / layout_type
    if layout_type == "single":
        layout = make_single_fixture(sub)
    elif layout_type == "split":
        layout = make_split_fixture(sub)
    else:
        layout = make_folders_fixture(sub)

    layout.append_note("#010", "Discovered new edge case during testing.")
    it = layout.find("#010")
    assert it is not None
    assert "Discovered new edge case during testing." in it.raw
    assert "Notes" in it.raw


# ---------------------------------------------------------------------------
# Byte-for-Byte Preservation (Decision 9)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("crlf", [False, True])
def test_single_byte_preservation(tmp_path: Path, crlf: bool):
    sub = tmp_path / f"single_{crlf}"
    layout = make_single_fixture(sub, crlf=crlf)
    initial_bytes = (sub / "BACKLOG.md").read_bytes()

    # Find the byte slice of untouched item #020
    it20 = layout.find("#020")
    assert it20 is not None

    # Perform a surgical edit on #010
    layout.append_note("#010", "Note on task 10.")
    updated_bytes = (sub / "BACKLOG.md").read_bytes()

    # The untouched item #020 raw slice must remain completely identical
    assert (b"\r\n" in updated_bytes) == crlf
    assert it20.raw.encode("utf-8") in updated_bytes


# ---------------------------------------------------------------------------
# ID Allocation & Refusal Tests (Decision 13)
# ---------------------------------------------------------------------------


def test_id_allocation():
    # 1. No IDs yet -> #001
    assert allocate_id([]) == "#001"

    # 2. Sequential in use
    assert allocate_id(["#001", "#042"]) == "#043"
    assert allocate_id(["#1000"]) == "#1001"
    # Zero-padded to at least 3
    assert allocate_id(["#01"]) == "#002"

    # 3. Exactly one prefix in use
    assert allocate_id(["WH-1", "WH-5"]) == "WH-6"

    # 4. Multiple schemes in use without --prefix -> refuses
    with pytest.raises(TaskError) as exc_info:
        allocate_id(["#001", "WH-1"])
    err = str(exc_info.value)
    assert "#" in err and "WH" in err

    # 5. With --prefix matching existing
    assert allocate_id(["#001", "WH-1"], prefix="WH") == "WH-2"
    assert allocate_id(["#001", "WH-1"], prefix="#") == "#002"

    # 6. With --prefix not in use without --new-prefix -> refuses
    with pytest.raises(TaskError) as exc_info:
        allocate_id(["WH-1"], prefix="INF")
    assert "WH" in str(exc_info.value)

    # 7. With --prefix not in use WITH --new-prefix -> allowed
    assert allocate_id(["WH-1"], prefix="INF", new_prefix=True) == "INF-1"
    assert allocate_id(["WH-1"], prefix="#", new_prefix=True) == "#001"


# ---------------------------------------------------------------------------
# Full vs Compact Entries (Decision 14)
# ---------------------------------------------------------------------------


def test_compact_entry_style(tmp_path: Path):
    layout = make_single_fixture(tmp_path / "compact")
    item = Item(
        id="#099",
        title="Compact item",
        status="Open",
        priority="P2",
        fields={
            "why": "Brief explanation.",
            "wanted": "Quick fix.",
            "criteria": ["One criterion verified."],
        },
    )
    layout.add(item, style="compact")

    found = layout.find("#099")
    assert found is not None
    assert "*Wanted:* Quick fix." in found.raw
    assert "*Done when:* One criterion verified." in found.raw
    assert "#### Acceptance Criteria" not in found.raw


# ---------------------------------------------------------------------------
# Defect Tests B1, B2, B3 (Decision 22)
# ---------------------------------------------------------------------------

PROBE_ENTRY_SINGLE = """# Project Backlog

> **How this backlog is run** (`convention/backlog`)
> - **Layout:** single file

## 📋 In Progress

### [#001] Probe test task
- **Status**: `In Progress` | **Priority**: `P1`
- **Created**: 2026-10-01

#### Why
- **Note** prose.

#### Wanted
Something.

#### Acceptance Criteria
- [ ] #1 Tests pass.

#### Notes
- 2026-10-01: first

#### Outcome
(Filled on completion.)

## 📌 Backlog (Open Tasks)

## ✅ Completed

## 🧊 Icebox (Not Doing / Rejected)
"""

PROBE_ENTRY_SPLIT_OPEN = """# Open Tasks

> **How this backlog is run** (`convention/backlog`)
> - **Layout:** split files

## 📋 In Progress

### [#001] Probe test task
- **Status**: `In Progress` | **Priority**: `P1`
- **Created**: 2026-10-01

#### Why
- **Note** prose.

#### Wanted
Something.

#### Acceptance Criteria
- [ ] #1 Tests pass.

#### Notes
- 2026-10-01: first

#### Outcome
(Filled on completion.)

## 📌 Backlog (Open Tasks)
"""

PROBE_ENTRY_SPLIT_CLOSED = """# Closed Tasks

## ✅ Completed

## 🧊 Icebox (Not Doing / Rejected)
"""

PROBE_ENTRY_FOLDERS_ITEM = """---
id: "#001"
title: Probe test task
status: In Progress
priority: P1
created: 2026-10-01
---

# [#001] Probe test task

## Why
- **Note** prose.

## Wanted
Something.

## Acceptance Criteria
- [ ] #1 Tests pass.

## Notes
- 2026-10-01: first

## Outcome
(Filled on completion.)
"""


def test_b1_resolved_metadata_block_single(tmp_path: Path):
    """B1: close puts Resolved in metadata block under heading, not inside Why."""
    p = tmp_path / "BACKLOG.md"
    p.write_text(PROBE_ENTRY_SINGLE, encoding="utf-8")
    layout = SingleFileLayout(p)

    layout.close("#001", "Closed", "Done.")
    text = p.read_text(encoding="utf-8")

    # Resolved must be under Created, before Why
    assert "- **Created**: 2026-10-01\n- **Resolved**:" in text
    # Why must keep its bullet without Resolved inside it
    assert "#### Why\n- **Note** prose.\n\n#### Wanted" in text


def test_b1_resolved_metadata_block_split(tmp_path: Path):
    """B1 (split): close puts Resolved in metadata block under heading in Closed.md."""
    bdir = tmp_path / "BACKLOG"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "00_BACKLOG.md").write_text("# Backlog Header\n", encoding="utf-8")
    (bdir / "Open.md").write_text(PROBE_ENTRY_SPLIT_OPEN, encoding="utf-8")
    (bdir / "Closed.md").write_text(PROBE_ENTRY_SPLIT_CLOSED, encoding="utf-8")
    layout = SplitFilesLayout(bdir)

    layout.close("#001", "Closed", "Done.")
    closed_text = (bdir / "Closed.md").read_text(encoding="utf-8")

    assert "- **Created**: 2026-10-01\n- **Resolved**:" in closed_text
    assert "#### Why\n- **Note** prose.\n\n#### Wanted" in closed_text


def test_b2_append_note_spacing_single(tmp_path: Path):
    """B2 (single): append_note puts new note right after last note with single blank line before heading."""
    p = tmp_path / "BACKLOG.md"
    p.write_text(PROBE_ENTRY_SINGLE, encoding="utf-8")
    layout = SingleFileLayout(p)

    layout.append_note("#001", "second")
    text = p.read_text(encoding="utf-8")

    # Notes section must have consecutive note bullets, then one blank line, then Outcome
    assert "#### Notes\n- 2026-10-01: first\n- " in text
    assert ": second\n\n#### Outcome" in text


def test_b2_append_note_spacing_split(tmp_path: Path):
    """B2 (split): append_note puts new note right after last note with single blank line before heading."""
    bdir = tmp_path / "BACKLOG"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "00_BACKLOG.md").write_text("# Backlog Header\n", encoding="utf-8")
    (bdir / "Open.md").write_text(PROBE_ENTRY_SPLIT_OPEN, encoding="utf-8")
    (bdir / "Closed.md").write_text(PROBE_ENTRY_SPLIT_CLOSED, encoding="utf-8")
    layout = SplitFilesLayout(bdir)

    layout.append_note("#001", "second")
    open_text = (bdir / "Open.md").read_text(encoding="utf-8")

    assert "#### Notes\n- 2026-10-01: first\n- " in open_text
    assert ": second\n\n#### Outcome" in open_text


def test_b2_append_note_spacing_folders(tmp_path: Path):
    """B2 (folders): append_note puts new note right after last note with single blank line before heading."""
    bdir = tmp_path / "BACKLOG"
    open_dir = bdir / "open"
    open_dir.mkdir(parents=True, exist_ok=True)
    (bdir / "closed").mkdir(parents=True, exist_ok=True)
    (bdir / "00_BACKLOG.md").write_text("# Backlog Header\n", encoding="utf-8")
    item_file = open_dir / "001-probe-test-task.md"
    item_file.write_text(PROBE_ENTRY_FOLDERS_ITEM, encoding="utf-8")
    layout = ItemFoldersLayout(bdir)

    layout.append_note("#001", "second")
    item_text = item_file.read_text(encoding="utf-8")

    assert "## Notes\n- 2026-10-01: first\n- " in item_text
    assert ": second\n\n## Outcome" in item_text


def test_b3_close_single_blank_line_spacing(tmp_path: Path):
    """B3 (single): closing a full entry leaves exactly one blank line after Outcome, not two."""
    p = tmp_path / "BACKLOG.md"
    p.write_text(PROBE_ENTRY_SINGLE, encoding="utf-8")
    layout = SingleFileLayout(p)

    layout.close("#001", "Closed", "Done.")
    text = p.read_text(encoding="utf-8")

    # In Completed section, after Outcome\nDone. there must be exactly one blank line before ## 🧊 Icebox
    assert "#### Outcome\nDone.\n\n## 🧊 Icebox" in text
    assert "#### Outcome\nDone.\n\n\n## 🧊 Icebox" not in text
