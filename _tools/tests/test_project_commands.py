"""status / pull / add / remove (DESIGN §4.4-4.7, §5)."""
from __future__ import annotations

from conftest import snapshot

DOC = "protocol/session-log"
BREAK = "#### Changed\n- **BREAKING:** logs now require `written_by`.\n  **Migration:** add `written_by:` to logs."


def test_status_shows_compatible_major_and_changelog(wh):
    wh.publish(DOC, "2.1.0")
    p = wh.project("alpha", f"auto_sync: false\nitems:\n  - {DOC}@2\n  - protocol/missing-one@1\n")
    wh.run("sync", str(p))
    wh.publish(DOC, "2.2.0", notes="#### Added\n- Optional open threads section.")
    wh.publish(DOC, "3.0.0", notes=BREAK)
    code, out = wh.run("status", project=p)
    assert code == 0
    assert "installed 2.1.0" in out and "pin @2" in out and "compatible 2.2.0" in out and "major 3.0.0" in out
    assert "2.2.0 — Added: Optional open threads section." in out
    assert "3.0.0 — BREAKING: logs now require `written_by`.  Migration: add `written_by:` to logs." in out
    assert "protocol/missing-one" in out and "not installable" in out


def test_status_no_manifest_exit_2(wh, tmp_path):
    (tmp_path / "empty").mkdir()
    code, out = wh.run("status", project=tmp_path / "empty")
    assert code == 2 and "no .warehouse.yml found" in out


def test_pull_manual_project_within_pin(wh):
    wh.publish(DOC, "1.0.0")
    wh.publish("protocol/b", "1.0.0")
    p = wh.project("alpha", f"auto_sync: false\nitems:\n  - {DOC}@1\n  - protocol/b@1\n")
    wh.run("sync", str(p))
    wh.publish(DOC, "1.1.0")
    wh.publish("protocol/b", "1.1.0")
    wh.publish(DOC, "2.0.0", notes=BREAK)
    code, out = wh.run("pull", DOC, project=p)
    assert code == 0
    lock = wh.lock(p)["items"]
    assert lock[DOC]["version"] == "1.1.0" and lock["protocol/b"]["version"] == "1.0.0"
    assert "major" in out
    assert wh.run("pull", "protocol/unknown", project=p)[0] == 2
    assert wh.run("pull", project=p)[0] == 2


def test_pull_all(wh):
    wh.publish(DOC, "1.0.0")
    wh.publish("protocol/b", "1.0.0")
    p = wh.project("alpha", f"auto_sync: false\nitems:\n  - {DOC}@1\n  - protocol/b@1\n")
    wh.run("sync", str(p))
    wh.publish(DOC, "1.0.1")
    wh.publish("protocol/b", "1.2.0")
    code, out = wh.run("pull", "--all", project=p)
    lock = wh.lock(p)["items"]
    assert code == 0 and lock[DOC]["version"] == "1.0.1" and lock["protocol/b"]["version"] == "1.2.0"


def test_pull_major_shows_breaking_moves_pin(wh):
    wh.publish(DOC, "2.1.0")
    p = wh.project("alpha", f"# top\nitems:\n  - {DOC}@2  # the log protocol\n")
    wh.run("sync")
    wh.publish(DOC, "3.0.0", notes=BREAK)
    code, out = wh.run("pull", DOC, project=p)
    assert wh.lock(p)["items"][DOC]["version"] == "2.1.0"
    code, out = wh.run("pull", DOC, "--major", project=p)
    assert code == 0, out
    assert "BREAKING" in out and "Migration" in out
    assert wh.lock(p)["items"][DOC]["version"] == "3.0.0" and wh.lock(p)["items"][DOC]["pin"] == "3"
    assert (p / ".warehouse.yml").read_text() == f"# top\nitems:\n  - {DOC}@3  # the log protocol\n"
    code, out = wh.run("pull", DOC, "--major", project=p)
    assert code == 0 and "unchanged" in out


def test_pull_downgrades_to_narrowed_pin(wh):
    wh.publish(DOC, "1.3.0")
    wh.publish(DOC, "1.4.0")
    p = wh.project("alpha", f"items:\n  - {DOC}@1\n")
    wh.run("sync")
    (p / ".warehouse.yml").write_text(f"items:\n  - {DOC}@1.3\n")
    code, out = wh.run("sync")
    assert wh.lock(p)["items"][DOC]["version"] == "1.4.0"  # sync never downgrades
    code, out = wh.run("pull", DOC, project=p)
    assert code == 0 and "downgraded" in out and wh.lock(p)["items"][DOC]["version"] == "1.3.0"


def test_sync_pin_moved_to_other_line_by_hand(wh):
    wh.publish(DOC, "1.0.0")
    wh.publish(DOC, "2.0.0", notes=BREAK)
    p = wh.project("alpha", f"items:\n  - {DOC}@1\n")
    wh.run("sync")
    (p / ".warehouse.yml").write_text(f"items:\n  - {DOC}@2\n")
    before = snapshot(p)
    code, out = wh.run("sync")
    assert "pin changed" in out and f"pull {DOC} --major" in out
    assert snapshot(p) == before


def test_add_unpinned_records_current_major(wh):
    wh.publish(DOC, "2.3.1")
    p = wh.project("alpha", "auto_sync: true\n")
    code, out = wh.run("add", DOC, project=p)
    assert code == 0, out
    assert (p / ".warehouse.yml").read_text() == f"auto_sync: true\nitems:\n  - {DOC}@2\n"
    assert wh.lock(p)["items"][DOC]["version"] == "2.3.1"
    assert wh.run("add", "template/plan", project=p)[0] == 2
    assert wh.run("add", "protocol/nope", project=p)[0] == 2
    assert wh.run("add", f"{DOC}@5", project=p)[0] == 2


def test_add_draft_records_zero_minor(wh):
    wh.publish("protocol/d", "0.3.2")
    p = wh.project("alpha", "items:\n")
    code, out = wh.run("add", "protocol/d", project=p)
    assert code == 0, out
    assert "  - protocol/d@0.3\n" in (p / ".warehouse.yml").read_text()


def test_add_writes_missing_settings_keys(wh):
    wh.publish(DOC, "1.0.0", body="{{folder}} {{opt}}\n",
               settings={"folder": "Where logs live", "opt": {"description": "Optional", "default": "x"}})
    p = wh.project("alpha", "items: []\n".replace("items: []\n", "auto_sync: true\n"))
    code, out = wh.run("add", DOC, project=p)
    assert code == 1 and "needs settings: folder" in out
    text = (p / ".warehouse.yml").read_text()
    assert 'settings:\n  folder: ""  # Where logs live\n' in text and "opt" not in text
    assert not (p / "warehouse" / "session-log.md").exists()


def test_add_skill_pulls_required_tool(wh):
    wh.publish("tool/t", "1.2.0")
    wh.publish("skill/s", "1.0.0", requires=["tool/t@1"])
    p = wh.project("alpha", "auto_sync: false\n")
    code, out = wh.run("add", "skill/s", project=p)
    assert code == 0, out
    lock = wh.lock(p)["items"]
    assert lock["tool/t"]["source"] == "dependency" and lock["tool/t"]["required_by"] == ["skill/s"]
    assert lock["tool/t"]["pin"] == "1" and (p / "warehouse" / "tools" / "t" / "main.py").exists()
    assert "required by skill/s" in (p / "warehouse" / "README.md").read_text()
    assert "tool/t" not in (p / ".warehouse.yml").read_text()
    # adding a dependency-only item makes it manifest-sourced
    code, out = wh.run("add", "tool/t", project=p)
    assert wh.lock(p)["items"]["tool/t"]["source"] == "manifest"


def test_skill_blocked_when_tool_major_needed(wh):
    wh.publish("tool/t", "1.0.0")
    wh.publish("skill/s", "1.0.0", requires=["tool/t@1"])
    p = wh.project("alpha", "items:\n  - skill/s@1\n")
    wh.run("sync")
    wh.publish("tool/t", "2.0.0", notes=BREAK)
    wh.publish("skill/s", "1.1.0", requires=["tool/t@2"])
    code, out = wh.run("sync")
    assert code == 1
    assert wh.lock(p)["items"]["skill/s"]["version"] == "1.0.0"
    assert "blocked" in out and "skill/s 1.1.0 needs tool/t@2 (project has 1.0.0): warehouse pull skill/s --major" in out
    # a project without the skill cannot install the incompatible pair
    wh.publish("skill/other", "1.0.0", requires=["tool/t@1"])
    q = wh.project("beta", "items:\n  - skill/other@1\n  - tool/t@2\n")
    code, out = wh.run("sync", str(q))
    assert "not-installable" in out and "skill/other" not in wh.lock(q)["items"]
    # pull --major on a dependency-only tool while the skill needs @1 -> blocked
    code, out = wh.run("pull", "tool/t", "--major", project=p)
    assert code == 1 and "required by skill/s@1" in out


def test_remove_orphans_tool_and_prune(wh):
    wh.publish("tool/t", "1.0.0")
    wh.publish("skill/s", "1.0.0", requires=["tool/t@1"])
    wh.publish("skill/s2", "1.0.0", requires=["tool/t@1"])
    p = wh.project("alpha", "items:\n  - skill/s@1\n")
    q = wh.project("beta", "items:\n  - skill/s@1\n")
    wh.run("sync")
    code, out = wh.run("remove", "skill/s", project=p)
    assert code == 0 and "orphan" in out
    assert (p / "warehouse" / "tools" / "t" / "TOOL.md").exists() and not (p / "warehouse" / "skills").exists()
    assert "skill/s" not in (p / ".warehouse.yml").read_text()
    code, out = wh.run("sync", str(p))
    assert "orphan" in out
    code, out = wh.run("remove", "skill/s", "--prune", project=q)
    assert code == 0 and "pruned" in out
    assert not (q / "warehouse" / "tools").exists() and wh.lock(q)["items"] == {}
    assert not (q / "warehouse" / "README.md").exists()


def test_remove_refuses_drift_and_required(wh):
    wh.publish("tool/t", "1.0.0")
    wh.publish("skill/s", "1.0.0", requires=["tool/t@1"])
    p = wh.project("alpha", "items:\n  - skill/s@1\n  - tool/t@1\n")
    wh.run("sync")
    code, out = wh.run("remove", "tool/t", project=p)
    assert code == 1 and "blocked" in out and "required by skill/s" in out
    f = p / "warehouse" / "skills" / "s" / "SKILL.md"
    f.write_text(f.read_text() + "edit\n")
    code, out = wh.run("remove", "skill/s", project=p)
    assert code == 1 and "drift" in out and "detach" in out and f.exists()
    code, out = wh.run("remove", "skill/s", "--force", project=p)
    assert code == 0 and not f.exists()
    q = wh.project("beta", "items:\n  - skill/s@1\n")
    wh.run("sync", str(q))
    code, out = wh.run("remove", "tool/t", project=q)
    assert code == 2 and "required by skill/s" in out


def test_add_other_line_requires_major(wh):
    wh.publish(DOC, "1.0.0")
    wh.publish(DOC, "2.0.0", notes=BREAK)
    p = wh.project("alpha", f"items:\n  - {DOC}@1\n")
    wh.run("sync")
    code, out = wh.run("add", f"{DOC}@2", project=p)
    assert code == 2 and "--major" in out
    assert wh.lock(p)["items"][DOC]["version"] == "1.0.0"
    code, out = wh.run("add", f"{DOC}@2", "--major", project=p)
    assert code == 0, out
    assert wh.lock(p)["items"][DOC]["version"] == "2.0.0"
    assert f"  - {DOC}@2\n" in (p / ".warehouse.yml").read_text()


def test_sync_json_output(wh):
    wh.publish(DOC, "1.0.0")
    wh.project("alpha", f"items:\n  - {DOC}@1\n")
    code, out = wh.run("--json", "sync")
    import json
    data = json.loads(out)
    assert data["command"] == "sync" and data["exit_code"] == 0 and data["summary"] == {"installed": 1}
    assert data["lines"][0]["status"] == "installed" and data["lines"][0]["id"] == DOC
