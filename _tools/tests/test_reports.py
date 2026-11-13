"""check / impact / registry / cli (DESIGN §4.9-4.11, batch-2 stubs, real config file)."""
from __future__ import annotations

import json

import pytest

from conftest import TOOLS_DIR, git
from warehouse_core import config as config_mod

DOC = "protocol/session-log"
BREAK = "#### Changed\n- **BREAKING:** x.\n  **Migration:** y."


def test_check_reports_all_categories(wh):
    wh.publish(DOC, "1.0.0")
    wh.publish("protocol/dep", "1.0.0")
    wh.publish("protocol/set", "1.0.0", body="{{val}}\n", settings={"val": "A value"})
    wh.publish("tool/sw", "1.0.0", tool_fields={"requires-software": ["definitely-not-installed-xyz>=1.0", "python>=3.0"],
                                                "platforms": ["amigaos"]})
    wh.publish("tool/t", "1.0.0")
    wh.publish("skill/s", "1.0.0", requires=["tool/t@1"])
    wh.publish("protocol/gone", "1.0.0")
    p = wh.project("manual", "auto_sync: false\nitems:\n"
                   f"  - {DOC}@1\n  - protocol/dep@1\n  - protocol/set@1\n  - tool/sw@1\n  - skill/s@1\n"
                   "  - protocol/gone@1\nsettings:\n  val: V\n")
    assert wh.run("sync", str(p))[0] in (0, 1)
    wh.publish(DOC, "1.1.0")
    wh.publish(DOC, "2.0.0", notes=BREAK)
    wh.publish("protocol/dep", "1.1.0", status="deprecated")
    code, _ = wh.run("pull", "protocol/dep", project=p)
    (p / "warehouse" / "session-log.md").write_text("edited\n")
    (p / ".warehouse.yml").write_text((p / ".warehouse.yml").read_text().replace("  - skill/s@1\n", "")
                                      .replace("  val: V\n", ""))
    git(wh.root, "tag", "-d", "protocol/gone@1.0.0")
    (p / "warehouse" / "mine.txt").write_text("not ours\n")
    code, out = wh.run("check")
    assert code == 1
    for word in ["drift", "compatible", "major", "unfilled", "deprecated", "missing-software", "platform",
                 "orphan", "missing-tag", "untracked"]:
        assert f"  {word}" in out, word
    assert "definitely-not-installed-xyz not found" in out and "python" not in out.split("missing-software")[1].split("\n")[0]
    code, out = wh.run("--json", "check")
    data = json.loads(out)
    assert data["exit_code"] == 1 and data["summary"]["drift"] == 1


def test_check_clean_exit_0_and_info_only(wh):
    wh.publish(DOC, "1.0.0")
    p = wh.project("alpha", f"items:\n  - {DOC}@1\n")
    wh.run("sync")
    code, out = wh.run("check")
    assert code == 0, out
    (p / "warehouse" / "notes.md").write_text("mine\n")
    code, out = wh.run("check")
    assert code == 0 and "untracked" in out


def test_impact_lists_projects_and_dependents(wh):
    wh.publish("tool/t", "1.0.0")
    wh.publish("skill/s", "1.0.0", requires=["tool/t@1"])
    a = wh.project("a", "items:\n  - tool/t@1.0\n")
    b = wh.project("b", "auto_sync: false\nitems:\n  - skill/s@1\n")
    wh.project("c", "items: []\n")
    wh.run("sync", "--include-manual")
    code, out = wh.run("impact", "tool/t")
    assert code == 0
    assert f"| {a.as_posix()} | true | @1.0 | 1.0.0 | manifest | report only |" in out
    assert f"| {b.as_posix()} | false | @1 | 1.0.0 | required by skill/s | report only |" in out
    assert "/c |" not in out
    assert "skill/s 1.0.0 requires tool/t@1" in out
    assert wh.run("impact", "tool/unknown")[0] == 2


def test_registry_generated(wh):
    wh.publish(DOC, "1.0.0")
    a = wh.project("a", f"items:\n  - {DOC}@1\n")
    wh.project("bad", "nope: 1\n")
    wh.run("sync")
    (a / "warehouse" / "session-log.md").write_text("drifted\n")
    code, out = wh.run("registry")
    assert code == 0
    text = (wh.root / "_registry" / "projects.md").read_text()
    assert text.startswith("<!-- warehouse:generated")
    assert "Generated 2026-09-20 from 2 projects." in text
    assert f"| {a.as_posix()} | yes | warehouse/ | 1 | 1 drift |" in text
    assert "invalid manifest" in text
    assert f"| {DOC} | {a.as_posix()} | @1 | 1.0.0 | manifest |" in text
    assert git(wh.root, "status", "--porcelain", "-uall").strip() == "?? _registry/projects.md"


def test_real_config_file_is_valid():
    # The tracked config holds no machine paths; roots live in the gitignored local file.
    assert config_mod._read(TOOLS_DIR.parent / "warehouse.config.yml")["project_roots"] == []
    cfg = config_mod.load(TOOLS_DIR.parent)
    for d in (".git", "node_modules", ".claude", "worktrees", ".obsidian"):
        assert d in cfg.skip_dirs
    assert "warehouse.config.local.yml" in (TOOLS_DIR.parent / ".gitignore").read_text()


def test_config_validation(wh):
    wh.write_config(bogus=1)
    assert wh.run("sync")[0] == 2
    wh.write_config(max_depth=11)
    assert wh.run("sync")[0] == 2
    wh.write_config(project_roots=[(wh.tmp / "missing").as_posix()])
    code, out = wh.run("sync")
    assert code == 0 and "project root not found" in out
    (wh.root / "warehouse.config.local.yml").write_text("sync_exclude: []\n")
    assert wh.run("sync")[0] == 2
