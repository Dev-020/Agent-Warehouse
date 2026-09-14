"""catalog + sync behaviour (DESIGN §4.2, §4.3, §7; plan §8 Propagation, MAJOR, Pins, History, Drift)."""
from __future__ import annotations

import json
import os
import time

import pytest

from conftest import git, sha, snapshot

DOC = "protocol/session-log"


def doc_manifest(pin="1", extra="", settings="  session_folder: AI/session\n", auto=True):
    return (f"auto_sync: {'true' if auto else 'false'}\nitems:\n  - {DOC}@{pin}\n{extra}"
            f"settings:\n{settings}")


def publish_doc(wh, version, text="Logs in {{session_folder}}.\n", **kw):
    wh.publish(DOC, version, body=text, settings={"session_folder": "Where logs live"}, **kw)


def read(p):
    return p.read_bytes().decode()


# ------------------------------------------------------------------ catalog

def test_catalog_reads_tag_not_working_tree(wh):
    publish_doc(wh, "1.0.0", "Released text.\n")
    wh.write_item(DOC, "1.0.0", "UNRELEASED WORKING TREE EDIT\n", settings={"session_folder": "x"})
    p = wh.project("alpha", doc_manifest())
    assert wh.run("sync")[0] == 0
    text = read(p / "warehouse" / "session-log.md")
    assert "Released text." in text and "UNRELEASED" not in text


def test_old_pinned_version_gets_exact_tag_content(wh):
    publish_doc(wh, "1.0.0", "Version one content.\n")
    publish_doc(wh, "1.1.0", "Version one-one content.\n")
    p = wh.project("alpha", doc_manifest(pin="1.0.0"))
    assert wh.run("sync")[0] == 0
    text = read(p / "warehouse" / "session-log.md")
    assert "Version one content." in text and "v1.0.0" in text
    lock = wh.lock(p)
    assert lock["items"][DOC]["version"] == "1.0.0"


def test_malformed_tag_ignored_and_checked(wh):
    publish_doc(wh, "1.0.0")
    git(wh.root, "tag", "-a", "protocol/session-log@1.0", "-m", "bad")
    git(wh.root, "tag", "protocol/session-log@1.5.0")  # lightweight
    git(wh.root, "tag", "-a", "protocol/session-log@1.9.0", "-m", "wrong content")  # content says 1.0.0
    p = wh.project("alpha", doc_manifest())
    code, out = wh.run("sync")
    assert code == 0 and wh.lock(p)["items"][DOC]["version"] == "1.0.0"
    code, out = wh.run("check")
    assert code == 1
    assert "malformed tag refs/tags/protocol/session-log@1.0" in out
    assert "lightweight" in out and "1.9.0 ignored" in out


# ------------------------------------------------------------------ sync

def test_sync_installs_with_header_and_lock(wh):
    publish_doc(wh, "2.1.0")
    p = wh.project("alpha", doc_manifest(pin="2"))
    code, out = wh.run("sync")
    assert code == 0, out
    data = (p / "warehouse" / "session-log.md").read_bytes()
    assert b"\r\n" not in data
    text = data.decode()
    fm_end = text.index("\n---\n", 4) + 5
    assert text[fm_end:].startswith(
        "\n> [!info] Warehouse item — protocol/session-log v2.1.0 (synced 2026-09-20)\n"
        "> Maintained in the AI warehouse. Edit it there, or run `warehouse promote protocol/session-log` "
        "to send a change upstream.\n\n# session-log\n")
    assert "Logs in AI/session." in text
    lock = wh.lock(p)
    item = lock["items"][DOC]
    assert item["files"] == {"session-log.md": sha(data)}
    assert item["pin"] == "2" and item["source"] == "manifest" and item["pending"] is None
    assert lock["readme"] == sha((p / "warehouse" / "README.md").read_bytes())
    assert "installed   protocol/session-log" in out


def test_sync_auto_updates_minor_patch_in_pin(wh):
    publish_doc(wh, "1.0.0")
    p = wh.project("alpha", doc_manifest())
    wh.run("sync")
    publish_doc(wh, "1.1.0", "New minor.\n")
    code, out = wh.run("sync", "--auto")
    assert code == 0 and "1.0.0 -> 1.1.0" in out
    publish_doc(wh, "1.1.1", "Patch.\n")
    wh.run("sync", "--auto")
    assert wh.lock(p)["items"][DOC]["version"] == "1.1.1"
    assert "Patch." in read(p / "warehouse" / "session-log.md")


def test_sync_auto_skips_manual_projects(wh):
    publish_doc(wh, "1.0.0")
    auto = wh.project("auto", doc_manifest())
    manual = wh.project("manual", doc_manifest(auto=False))
    wh.run("sync", "--include-manual")
    before = snapshot(manual)
    publish_doc(wh, "1.1.0")
    code, out = wh.run("sync", "--auto")
    assert "skipped: auto_sync is false" in out
    assert snapshot(manual) == before
    assert wh.lock(auto)["items"][DOC]["version"] == "1.1.0"
    code, out = wh.run("status", project=manual)
    assert "compatible 1.1.0" in out


def test_sync_explicit_project_ignores_auto_sync_false(wh):
    publish_doc(wh, "1.0.0")
    manual = wh.project("manual", doc_manifest(auto=False))
    code, out = wh.run("sync", str(manual))
    assert code == 0 and wh.lock(manual)["items"][DOC]["version"] == "1.0.0"
    code, out = wh.run("sync", str(wh.tmp / "nowhere"))
    assert code == 2


def test_major_never_auto_applied(wh):
    publish_doc(wh, "2.1.0")
    p = wh.project("alpha", doc_manifest(pin="2"))
    wh.run("sync")
    before = snapshot(p)
    publish_doc(wh, "3.0.0", "Breaking.\n",
                notes="#### Changed\n- **BREAKING:** logs need `written_by`.\n  **Migration:** add `written_by:`.")
    code, out = wh.run("sync", "--auto")
    assert code == 0
    assert snapshot(p) == before
    assert "major" in out and "3.0.0 available: warehouse pull protocol/session-log --major" in out


def test_draft_minor_never_auto_applied(wh):
    wh.publish("protocol/draft", "0.2.0")
    p = wh.project("alpha", "items:\n  - protocol/draft@0.2\n")
    wh.run("sync")
    wh.publish("protocol/draft", "0.2.1")
    wh.publish("protocol/draft", "0.3.0")
    code, out = wh.run("sync", "--auto")
    assert wh.lock(p)["items"]["protocol/draft"]["version"] == "0.2.1"
    assert "0.3.0 available" in out


def test_canonical_pin_never_selects_draft(wh):
    wh.publish("protocol/x", "0.9.0")
    p = wh.project("alpha", "items:\n  - protocol/x\n")
    code, out = wh.run("sync")
    assert code == 1 and "not-installable" in out and "@0.MINOR" in out
    assert not (p / "warehouse" / "x.md").exists()
    wh.publish("protocol/x", "1.0.0")
    wh.publish("protocol/y", "1.0.0")
    p2 = wh.project("beta", "items:\n  - protocol/y@1\n")
    wh.run("sync")
    assert wh.lock(p)["items"]["protocol/x"]["version"] == "1.0.0"
    assert wh.lock(p)["items"]["protocol/x"]["pin"] == "1"


def test_pin_levels_minor_and_exact(wh):
    publish_doc(wh, "2.3.0")
    minor = wh.project("minor", doc_manifest(pin="2.3"))
    exact = wh.project("exact", doc_manifest(pin="2.3.0"))
    wh.run("sync")
    publish_doc(wh, "2.3.1")
    publish_doc(wh, "2.4.0")
    code, out = wh.run("sync", "--auto")
    assert wh.lock(minor)["items"][DOC]["version"] == "2.3.1"
    assert wh.lock(exact)["items"][DOC]["version"] == "2.3.0"
    assert "outside-pin" in out


def test_unfilled_placeholder_blocks_item(wh):
    publish_doc(wh, "1.0.0")
    wh.publish("protocol/other", "1.0.0")
    p = wh.project("alpha", f"items:\n  - {DOC}@1\n  - protocol/other@1\n")
    code, out = wh.run("sync")
    assert code == 1
    assert "unfilled" in out and "needs settings: session_folder" in out
    assert not (p / "warehouse" / "session-log.md").exists()
    assert (p / "warehouse" / "other.md").exists()
    assert DOC not in wh.lock(p)["items"]


def test_setting_default_used_when_project_omits_it(wh):
    """User decision 1: settings may have defaults."""
    wh.publish("protocol/dflt", "1.0.0", body="Req {{req}}; opt {{opt}}.\n",
               settings={"req": "Required", "opt": {"description": "Optional", "default": "DEFAULT"}})
    p = wh.project("alpha", "items:\n  - protocol/dflt@1\nsettings:\n  req: R\n")
    q = wh.project("beta", "items:\n  - protocol/dflt@1\nsettings:\n  req: R\n  opt: MINE\n")
    r = wh.project("gamma", "items:\n  - protocol/dflt@1\nsettings:\n  opt: MINE\n")
    code, out = wh.run("sync")
    assert "Req R; opt DEFAULT." in read(p / "warehouse" / "dflt.md")
    assert "Req R; opt MINE." in read(q / "warehouse" / "dflt.md")
    assert not (r / "warehouse" / "dflt.md").exists()
    assert "needs settings: req" in out and "opt" not in out.split("needs settings: req")[1].split("\n")[0]


def test_undeclared_placeholder_left_literal(wh):
    publish_doc(wh, "1.0.0", "Logs in {{session_folder}}; example `{{other}}` and {{nope}}.\n")
    p = wh.project("alpha", doc_manifest())
    wh.run("sync")
    assert "Logs in AI/session; example `{{other}}` and {{nope}}." in read(p / "warehouse" / "session-log.md")


def test_placeholders_only_in_md(wh):
    wh.publish("tool/t", "1.0.0", body="Use {{folder}}.\n", settings={"folder": "F"},
               files={"main.py": "PATH = '{{folder}}'\n"})
    p = wh.project("alpha", "items:\n  - tool/t@1\nsettings:\n  folder: X\n")
    wh.run("sync")
    assert read(p / "warehouse" / "tools" / "t" / "main.py") == "PATH = '{{folder}}'\n"
    assert "Use X." in read(p / "warehouse" / "tools" / "t" / "TOOL.md")


def test_settings_change_rerenders(wh):
    publish_doc(wh, "1.0.0")
    p = wh.project("alpha", doc_manifest())
    wh.run("sync")
    (p / ".warehouse.yml").write_text(doc_manifest(settings="  session_folder: Logs/New\n"))
    code, out = wh.run("sync")
    assert code == 0 and "settings changed" in out
    assert "Logs in Logs/New." in read(p / "warehouse" / "session-log.md")
    code, out = wh.run("sync")
    assert "settings changed" not in out


def test_drift_skipped_and_reported(wh):
    publish_doc(wh, "1.0.0")
    p = wh.project("alpha", doc_manifest())
    wh.run("sync")
    f = p / "warehouse" / "session-log.md"
    f.write_bytes(f.read_bytes() + b"\nMy local edit.\n")
    edited = f.read_bytes()
    publish_doc(wh, "1.1.0")
    code, out = wh.run("sync", "--auto")
    assert code == 1 and "drift" in out and "session-log.md edited locally" in out
    assert f.read_bytes() == edited
    assert wh.lock(p)["items"][DOC]["version"] == "1.0.0"


def test_crlf_only_change_is_not_drift(wh):
    publish_doc(wh, "1.0.0")
    p = wh.project("alpha", doc_manifest())
    wh.run("sync")
    f = p / "warehouse" / "session-log.md"
    f.write_bytes(f.read_bytes().replace(b"\n", b"\r\n"))
    crlf = f.read_bytes()
    code, out = wh.run("sync")
    assert code == 0 and "drift" not in out
    assert f.read_bytes() == crlf  # never rewritten just for EOL
    publish_doc(wh, "1.1.0")
    code, out = wh.run("sync")
    assert code == 0 and "1.0.0 -> 1.1.0" in out
    assert b"\r\n" not in f.read_bytes()


def test_deleted_file_restored(wh):
    """User decision 2: a deleted synced file is restored."""
    wh.publish("skill/s", "1.0.0", files={"helper.txt": "help\n"})
    p = wh.project("alpha", "items:\n  - skill/s@1\n")
    wh.run("sync")
    lock_before = wh.lock(p)
    helper = p / "warehouse" / "skills" / "s" / "helper.txt"
    main = p / "warehouse" / "skills" / "s" / "SKILL.md"
    main_bytes = main.read_bytes()
    helper.unlink()
    main.unlink()
    code, out = wh.run("sync", today="2026-10-01")
    assert code == 0 and "restored" in out
    assert helper.read_text() == "help\n"
    assert main.read_bytes() == main_bytes  # restored with the original synced date
    assert wh.lock(p) == lock_before


def test_removed_file_between_versions_deleted_if_clean(wh):
    wh.publish("skill/s", "1.0.0", files={"deep/nested/old.txt": "old\n", "keep.txt": "k\n"})
    p = wh.project("alpha", "items:\n  - skill/s@1\n")
    wh.run("sync")
    assert (p / "warehouse" / "skills" / "s" / "deep" / "nested" / "old.txt").exists()
    wh.publish("skill/s", "1.1.0", files={"keep.txt": "k\n"})
    code, out = wh.run("sync")
    assert code == 0
    assert not (p / "warehouse" / "skills" / "s" / "deep").exists()
    assert (p / "warehouse" / "skills" / "s" / "keep.txt").exists()
    assert (p / "warehouse").is_dir()
    assert "skills/s/deep/nested/old.txt" not in wh.lock(p)["items"]["skill/s"]["files"]


def test_collision_with_untracked_file(wh):
    publish_doc(wh, "1.0.0")
    p = wh.project("alpha", doc_manifest())
    (p / "warehouse").mkdir()
    (p / "warehouse" / "session-log.md").write_text("my own notes\n")
    code, out = wh.run("sync")
    assert code == 1 and "collision" in out and "is not a warehouse copy" in out
    assert (p / "warehouse" / "session-log.md").read_text() == "my own notes\n"


def test_adopt_matching_untracked_file(wh):
    publish_doc(wh, "1.0.0")
    p = wh.project("alpha", doc_manifest())
    wh.run("sync", today="2026-09-01")
    (p / ".warehouse.lock").unlink()
    f = p / "warehouse" / "session-log.md"
    f.write_bytes(f.read_bytes().replace(b"\n", b"\r\n"))
    before = f.read_bytes()
    code, out = wh.run("sync")
    assert code == 0 and "adopted" in out
    assert f.read_bytes() == before
    assert wh.lock(p)["items"][DOC]["files"]["session-log.md"] == sha(before)


def test_readme_generated_and_foreign_readme_collision(wh):
    publish_doc(wh, "1.0.0")
    wh.publish("skill/s", "1.0.0", requires=[], files={})
    p = wh.project("alpha", doc_manifest(extra="  - skill/s@1\n"))
    wh.run("sync")
    readme = read(p / "warehouse" / "README.md")
    assert readme.startswith("<!-- warehouse:generated")
    assert "| protocol/session-log | 1.0.0 | @1 | [session-log.md](session-log.md) |  |" in readme
    assert "| skill/s | 1.0.0 | @1 | [skills/s/](skills/s/SKILL.md) |  |" in readme
    q = wh.project("beta", doc_manifest())
    (q / "warehouse").mkdir()
    (q / "warehouse" / "README.md").write_text("Our own readme\n")
    code, out = wh.run("sync")
    assert code == 1 and "README.md exists and is not generated" in out
    assert (q / "warehouse" / "README.md").read_text() == "Our own readme\n"
    assert (q / "warehouse" / "session-log.md").exists()


def test_tool_tests_dir_never_copied(wh):
    wh.publish("tool/t", "1.0.0", files={"tests/test_x.py": "def test(): pass\n", "lib/util.py": "x = 1\n",
                                         "desktop.ini": "[x]\n"})
    p = wh.project("alpha", "items:\n  - tool/t@1\n")
    wh.run("sync")
    base = p / "warehouse" / "tools" / "t"
    assert (base / "lib" / "util.py").exists() and (base / "TOOL.md").exists()
    assert not (base / "tests").exists() and not (base / "desktop.ini").exists()


def test_hand_removed_manifest_entry_removes_clean_copy(wh):
    """User decision 3: entry removed by hand -> clean copies deleted, edited copies kept + reported."""
    wh.publish("skill/s", "1.0.0", files={"a.txt": "a\n", "b.txt": "b\n"})
    publish_doc(wh, "1.0.0")
    p = wh.project("alpha", doc_manifest(extra="  - skill/s@1\n"))
    wh.run("sync")
    (p / "warehouse" / "skills" / "s" / "b.txt").write_text("edited\n")
    (p / ".warehouse.yml").write_text(doc_manifest())
    code, out = wh.run("sync")
    assert code == 1 and "drift" in out and "kept edited file(s): skills/s/b.txt" in out
    assert not (p / "warehouse" / "skills" / "s" / "a.txt").exists()
    assert not (p / "warehouse" / "skills" / "s" / "SKILL.md").exists()
    assert (p / "warehouse" / "skills" / "s" / "b.txt").read_text() == "edited\n"
    # fully clean removal
    (p / ".warehouse.yml").write_text("items: []\n")
    code, out = wh.run("sync")
    assert "removed" in out and not (p / "warehouse" / "session-log.md").exists()
    assert DOC not in wh.lock(p)["items"]


def test_deprecated_item_warned(wh):
    publish_doc(wh, "1.0.0")
    p = wh.project("alpha", doc_manifest())
    wh.run("sync")
    publish_doc(wh, "1.1.0", status="deprecated")
    wh.publish("protocol/session-log-v2", "1.0.0", replaces=DOC)
    code, out = wh.run("sync")
    assert "deprecated" in out and "use protocol/session-log-v2" in out
    assert "deprecated: use protocol/session-log-v2" in read(p / "warehouse" / "README.md")


def test_invalid_manifest_does_not_stop_other_projects(wh):
    publish_doc(wh, "1.0.0")
    bad = wh.project("aaa-bad", "itmes:\n  - x\n")
    good = wh.project("zzz-good", doc_manifest())
    code, out = wh.run("sync")
    assert code == 1 and "invalid-manifest" in out
    assert wh.lock(good)["items"][DOC]["version"] == "1.0.0"
    assert not (bad / ".warehouse.lock").exists()


def test_nested_projects_and_skip_dirs_and_depth(wh):
    publish_doc(wh, "1.0.0")
    outer = wh.project("outer", doc_manifest())
    inner = wh.project("inner", doc_manifest(), parent=outer / "sub")
    skipped = [wh.project("p", doc_manifest(), parent=wh.projects_dir / "x" / d, git_repo=False)
               for d in ("node_modules", ".claude/worktrees", "worktrees")]
    too_deep = wh.project("deep", doc_manifest(), parent=wh.projects_dir / "a" / "b" / "c" / "d", git_repo=False)
    # a copy of the warehouse under a project root is never scanned
    wh.write_config(project_roots=[wh.projects_dir.as_posix(), wh.tmp.as_posix()], max_depth=4)
    code, out = wh.run("sync")
    assert (outer / "warehouse" / "session-log.md").exists()
    assert (inner / "warehouse" / "session-log.md").exists()
    for s in skipped:
        assert not (s / ".warehouse.lock").exists()
    assert not (too_deep / ".warehouse.lock").exists()
    assert not (wh.root / "warehouse").exists()
    # outer target containing another project -> error for outer
    trap = wh.project("trap", doc_manifest())
    (trap / "warehouse" / "nested").mkdir(parents=True)
    (trap / "warehouse" / "nested" / ".warehouse.yml").write_text("items: []\n")
    code, out = wh.run("sync")
    assert "target contains another project" in out and not (trap / ".warehouse.lock").exists()


def test_if_new_tags_noop_when_unchanged(wh):
    publish_doc(wh, "1.0.0")
    p = wh.project("alpha", doc_manifest())
    code, out = wh.run("sync", "--auto", "--if-new-tags")
    assert code == 0 and "installed" in out
    before = snapshot(p)
    code, out = wh.run("sync", "--auto", "--if-new-tags")
    assert code == 0 and out == ""
    assert snapshot(p) == before
    publish_doc(wh, "1.1.0")
    code, out = wh.run("sync", "--auto", "--if-new-tags")
    assert "1.0.0 -> 1.1.0" in out


def test_run_lock_busy(wh):
    publish_doc(wh, "1.0.0")
    wh.project("alpha", doc_manifest())
    state = wh.root / "_tools" / ".state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "run.lock").write_text(json.dumps({"pid": 1, "time": time.time()}))
    assert wh.run("sync", "--auto") == (0, "")
    code, out = wh.run("sync")
    assert code == 3 and "another warehouse run is active" in out
    (state / "run.lock").write_text(json.dumps({"pid": 1, "time": time.time() - 3600}))
    assert wh.run("sync")[0] == 0
    assert not (state / "run.lock").exists()
