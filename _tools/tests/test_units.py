"""semver / pins, file formats, changelog, lint, index."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import TOOLS_DIR, git
from warehouse_core import changelog, frontmatter, items, lockfile, manifest, render
from warehouse_core.catalog import Catalog
from warehouse_core.errors import UsageError
from warehouse_core.fsops import WriteGuard
from warehouse_core.gitrepo import Git
from warehouse_core.semver import Pin, Version

REAL_WAREHOUSE = TOOLS_DIR.parent


# ------------------------------------------------------------------ semver / pins

def test_version_parse_strict():
    assert Version.parse("1.2.3") == Version(1, 2, 3)
    for bad in ["1.0", "01.2.3", "1.2.3-rc1", "1.2.3+b", "v1.2.3", 1.0]:
        with pytest.raises(UsageError):
            Version.parse(bad)


def test_pin_matching_levels():
    assert Pin.parse("2").matches(Version(2, 9, 0)) and not Pin.parse("2").matches(Version(3, 0, 0))
    assert Pin.parse("2.3").matches(Version(2, 3, 1)) and not Pin.parse("2.3").matches(Version(2, 4, 0))
    exact = Pin.parse("1.4.2")
    assert exact.matches(Version(1, 4, 2))
    assert not exact.matches(Version(1, 4, 3)) and not exact.matches(Version(1, 5, 0))


def test_draft_line_and_default_pin():
    assert Version(0, 3, 2).line == (0, 3)
    assert Version(2, 3, 2).line == (2,)
    assert Pin.default_for(Version(0, 3, 2)).text == "0.3"
    assert Pin.default_for(Version(2, 3, 2)).text == "2"
    with pytest.raises(UsageError):
        Pin.parse("0")
    assert not Pin.parse("1").matches(Version(0, 9, 0))


def test_bump_table():
    v = Version(2, 4, 1)
    assert (str(v.bump("major")), str(v.bump("minor")), str(v.bump("patch"))) == ("3.0.0", "2.5.0", "2.4.2")
    d = Version(0, 3, 2)
    assert (str(d.bump("major")), str(d.bump("minor")), str(d.bump("patch"))) == ("1.0.0", "0.4.0", "0.3.3")


def test_pin_moved_to():
    assert Pin.parse("2").moved_to(Version(3, 1, 0)).text == "3"
    assert Pin.parse("2.3").moved_to(Version(3, 1, 0)).text == "3.1"
    assert Pin.parse("2.3.1").moved_to(Version(3, 1, 4)).text == "3.1.4"
    assert Pin.parse("0.3").moved_to(Version(1, 0, 0)).text == "1"
    assert Pin.parse("0.3").moved_to(Version(0, 4, 0)).text == "0.4"


def test_tag_name_is_valid_ref():
    import subprocess
    assert subprocess.run(["git", "check-ref-format", "refs/tags/protocol/session-log@2.1.0"]).returncode == 0
    assert subprocess.run(["git", "check-ref-format", "refs/tags/tool/tex-compile@0.10.3"]).returncode == 0


# ------------------------------------------------------------------ formats

def _m(text, tmp_path):
    return manifest.load_text(text, tmp_path / ".warehouse.yml")


def test_manifest_defaults_and_validation(tmp_path):
    m = _m("", tmp_path)
    assert m.auto_sync is True and m.target == "warehouse" and m.entries == [] and m.settings == {}
    m = _m("target: 'ai\\\\copies/'\nitems:\n  - protocol/a@2\n  - convention/b\nsettings:\n  n: 3\n", tmp_path)
    assert m.target == "ai/copies" and m.entries[0].pin.text == "2" and m.entries[1].pin is None
    assert m.settings == {"n": "3"}
    bad = ["itmes: []\n", "items:\n  - protocol/a@0\n", "items:\n  - protocol/a\n  - protocol/a@1\n",
           "items:\n  - template/plan\n", "settings:\n  x: true\n", "target: ../out\n", "target: C:/abs\n",
           "target: .\n", "target: .git/x\n", "auto_sync: maybe\n", "settings:\n  x: [1]\n"]
    for text in bad:
        with pytest.raises(UsageError):
            _m(text, tmp_path)
    with pytest.raises(UsageError, match="unknown key 'itmes'"):
        _m("itmes: []\n", tmp_path)
    with pytest.raises(UsageError, match="warehouse template"):
        _m("items:\n  - template/plan\n", tmp_path)


def test_manifest_text_edit_preserves_comments(tmp_path):
    text = ("# my manifest\nauto_sync: false  # manual\nitems:\n  - protocol/a@1  # keep me\n"
            "  # a comment line\n  - convention/b@2.3\nsettings:\n  x: y  # setting comment\n")
    m = _m(text, tmp_path)
    t2 = manifest.add_or_replace_entry(m, "protocol/a", Pin.parse("2"))
    assert "  - protocol/a@2  # keep me\n" in t2 and "# my manifest" in t2 and "# a comment line" in t2
    m2 = _m(t2, tmp_path)
    t3 = manifest.add_or_replace_entry(m2, "skill/c", Pin.parse("1"))
    lines = t3.split("\n")
    assert lines.index("  - skill/c@1") == lines.index("  - convention/b@2.3") + 1
    t4 = manifest.remove_entry(_m(t3, tmp_path), "convention/b")
    assert "convention/b" not in t4 and "# a comment line" in t4 and "  x: y  # setting comment" in t4
    t5 = manifest.ensure_settings_keys(_m(t4, tmp_path), {"folder": "Where logs go"})
    assert '  folder: ""  # Where logs go' in t5 and "  x: y  # setting comment" in t5
    t6 = manifest.add_or_replace_entry(_m("auto_sync: true\n", tmp_path), "protocol/a", None)
    assert t6.endswith("items:\n  - protocol/a\n")
    with pytest.raises(UsageError, match="by hand"):
        manifest.add_or_replace_entry(_m("items: [protocol/a]\n", tmp_path), "protocol/b", None)


def test_lock_roundtrip_deterministic(tmp_path):
    lock = lockfile.Lock()
    lock.items["tool/b"] = lockfile.LockItem(version="1.0.0", pin="1", files={"tools/b/TOOL.md": "sha256:1"})
    lock.items["protocol/a"] = lockfile.LockItem(version="2.1.0", pin="2", files={"a.md": "sha256:2"})
    guard = WriteGuard(tmp_path, "warehouse")
    lockfile.save(tmp_path, lock, guard)
    first = (tmp_path / ".warehouse.lock").read_bytes()
    assert first.endswith(b"}\n") and b"\r\n" not in first
    lockfile.save(tmp_path, lockfile.load(tmp_path), guard)
    assert (tmp_path / ".warehouse.lock").read_bytes() == first
    assert list(json.loads(first)["items"]) == ["protocol/a", "tool/b"]
    (tmp_path / ".warehouse.lock").write_text('{"lock_version": 2, "items": {}}')
    with pytest.raises(UsageError, match="lock_version"):
        lockfile.load(tmp_path)


def test_frontmatter_set_scalar_only_in_frontmatter():
    text = "---\nid: protocol/a\nversion: 1.0.0\n---\n\nversion: 9.9.9 in body\n"
    out = frontmatter.set_scalar(text, "version", "1.1.0")
    assert "version: 1.1.0\n---" in out and "version: 9.9.9 in body" in out


def test_changelog_ignores_fenced_examples():
    text = (REAL_WAREHOUSE / "conventions" / "warehouse-item.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    secs = changelog.parse(text, is_document=True)
    names = [s.name for s in secs]
    assert names[0] == "Unreleased" and "0.1.0" in names
    assert changelog.validate(secs) == []
    # the fenced example's own "## Changelog" is not the one parsed
    assert all("session log protocol" not in "\n".join(s.body) for s in secs)
    text2 = (REAL_WAREHOUSE / "conventions" / "changelog.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert [s.name for s in changelog.parse(text2, is_document=True)][-1] == "0.1.0"


def test_changelog_entries_between_and_breaking():
    text = """# Changelog

## [Unreleased]

## [3.0.0] - 2026-09-30
### Changed
- **BREAKING:** logs need `written_by`.
  **Migration:** add `written_by:`.
- Other change.

## [2.2.0] - 2026-09-25
### Added
- Open threads.

## [2.1.0] - 2026-09-20
### Added
- Old.
"""
    secs = changelog.parse(text, is_document=False)
    between = changelog.entries_between(secs, Version(2, 1, 0), Version(3, 0, 0))
    assert [s.name for s in between] == ["3.0.0", "2.2.0"]
    br = changelog.breaking(between[0])
    assert len(br) == 1 and "**Migration:** add `written_by:`." in br[0]
    assert changelog.categorized_bullets(between[1]) == [("Added", "- Open threads.")]


def test_changelog_release_edit():
    text = "# T\n\n## Changelog\n\n### [Unreleased]\n#### Added\n- New thing.\n\n### [1.0.0] - 2026-09-14\n- Old.\n"
    out = changelog.release_edit(text, Version(1, 1, 0), "2026-09-20", is_document=True)
    assert "### [Unreleased]\n\n### [1.1.0] - 2026-09-20\n#### Added\n- New thing.\n\n### [1.0.0]" in out


def _lint_codes(root, iid, catalog=None):
    return {p.code for p in items.lint_item(root, iid, catalog=catalog) if p.level == "error"}


def test_lint_rules(wh):
    root = wh.root
    wh.write_item("protocol/good", "1.0.0", "Uses {{folder}} and `{{literal}}`.\n", settings={"folder": "F"},
                  record="- First.")
    assert _lint_codes(root, "protocol/good") == set()
    # fm-missing
    (root / "protocols" / "nofm.md").write_text("# no frontmatter\n")
    assert "fm-missing" in _lint_codes(root, "protocol/nofm")
    # fm-field / version / status
    p = wh.write_item("protocol/bad", "1.0.0", record="- x.")
    t = p.read_text().replace("summary: Summary of protocol/bad.\n", "").replace("version: 1.0.0", "version: 1.0")
    p.write_text(t)
    codes = _lint_codes(root, "protocol/bad")
    assert {"fm-field", "version"} <= codes
    wh.write_item("protocol/st", "0.2.0", status="canonical", unreleased="- x.")
    assert "status" in _lint_codes(root, "protocol/st")
    # id-path
    p = wh.write_item("protocol/moved", "1.0.0", record="- x.")
    p.write_text(p.read_text().replace("id: protocol/moved", "id: protocol/other"))
    assert "id-path" in _lint_codes(root, "protocol/moved")
    # settings
    wh.write_item("protocol/sett", "1.0.0", settings={"Bad-Name": "x"}, record="- x.")
    assert "settings" in _lint_codes(root, "protocol/sett")
    # placeholder-undeclared (outside code only)
    wh.write_item("protocol/ph", "1.0.0", "Use {{undeclared}}.\n\n```\n{{ok_in_code}}\n```\n", record="- x.")
    probs = [p for p in items.lint_item(root, "protocol/ph") if p.code == "placeholder-undeclared"]
    assert len(probs) == 1 and "undeclared" in probs[0].msg
    # requires: missing id, self, cycle
    wh.write_item("skill/a", "1.0.0", requires=["tool/missing@1"], record="- x.")
    assert "requires" in _lint_codes(root, "skill/a")
    wh.write_item("skill/c1", "1.0.0", requires=["skill/c2@1"], record="- x.")
    wh.write_item("skill/c2", "1.0.0", requires=["skill/c1@1"], record="- x.")
    assert any("cycle" in p.msg for p in items.lint_item(root, "skill/c1"))
    # replaces
    wh.write_item("protocol/rep", "1.0.0", replaces="protocol/nothing", record="- x.")
    assert "replaces" in _lint_codes(root, "protocol/rep")
    # deprecated-replacement (warning)
    wh.write_item("protocol/old", "1.0.0", status="deprecated", record="- x.")
    assert any(p.code == "deprecated-replacement" and p.level == "warning" for p in items.lint_item(root, "protocol/old"))
    # name-collision
    wh.write_item("convention/good", "1.0.0", record="- x.")
    assert "name-collision" in _lint_codes(root, "convention/good")
    # case-collision
    wh.write_item("skill/case", "1.0.0", files={"Helper.txt": "a"}, record="- x.")
    (root / "skills" / "case" / "sub").mkdir()
    (root / "skills" / "case" / "sub" / "a.txt").write_text("a")
    (root / "skills" / "case" / "sub" / "A2.txt").write_text("a")
    probs_case = items.lint_item(root, "skill/case")
    assert "case-collision" not in {p.code for p in probs_case}
    fake_files = [root / "skills" / "case" / "x.txt", root / "skills" / "case" / "X.txt"]
    orig = items._item_files
    items._item_files = lambda r, i: fake_files + orig(r, i)
    try:
        assert "case-collision" in _lint_codes(root, "skill/case")
    finally:
        items._item_files = orig
    # entrypoint
    wh.write_item("tool/ep", "1.0.0", tool_fields={"entrypoint": "nope.py"}, record="- x.")
    assert "entrypoint" in _lint_codes(root, "tool/ep")
    # changelog
    p = wh.write_item("protocol/cl", "1.0.0", record="- x.")
    p.write_text(p.read_text().replace("### [Unreleased]\n", ""))
    assert "changelog" in _lint_codes(root, "protocol/cl")
    p = wh.write_item("protocol/cl2", "1.1.0", record=None, unreleased="")
    wh.history["protocol/cl2"] = [("1.0.0", "- x.")]
    wh.write_item("protocol/cl2", "1.1.0")
    assert "changelog" in _lint_codes(root, "protocol/cl2")


def test_settings_default_form_parsed_and_linted(wh):
    s = items.parse_settings({"a": "Required", "b": {"description": "Optional", "default": "AI/session"}})
    assert not s["a"].has_default and s["b"].default == "AI/session"
    for bad in [{"c": {"default": "x"}}, {"c": {"description": "d", "default": True}},
                {"c": {"description": "d", "extra": 1}}, {"c": 5}]:
        with pytest.raises(UsageError):
            items.parse_settings(bad)
    wh.write_item("protocol/dflt", "1.0.0", "In {{b}}.\n", settings={"b": {"description": "d", "default": "x"}},
                  record="- x.")
    assert _lint_codes(wh.root, "protocol/dflt") == set()


def test_index_regenerates_only_marked_regions(wh):
    wh.publish("protocol/a", "1.0.0")
    wh.write_item("protocol/a", "1.1.0", record="- more.")
    before = (wh.root / "00_INDEX.md").read_text()
    code, out = wh.run("index")
    assert code == 0
    after = (wh.root / "00_INDEX.md").read_text()
    assert "| [[protocols/a\\|protocol/a]] | protocol | 1.1.0 | 1.0.0 | canonical |" in after
    assert "— protocol/a 1.0.0" in after
    assert "updated: 2026-09-20" in after
    strip = lambda t: t.split("<!-- warehouse:catalog:start -->")[0].replace("updated: 2026-09-20", "updated: 2026-09-14")
    assert strip(after) == strip(before)
    assert after.split("<!-- warehouse:releases:end -->")[1] == before.split("<!-- warehouse:releases:end -->")[1]
    (wh.root / "00_INDEX.md").write_text("# no markers\n")
    code, out = wh.run("index")
    assert code == 2 and "markers" in out


def test_render_placeholders_header_roundtrip():
    meta = items.parse_meta("---\nid: protocol/a\nversion: 1.0.0\nstatus: canonical\nsummary: s\napplies-to: []\n"
                            "settings: {x: d, y: {description: e, default: dy}}\nrequires: []\nreplaces: null\n---\n")
    files = {"a.md": b"---\nid: protocol/a\n---\n\n# A\n{{x}} {{y}} {{z}}\n"}
    res = render.render_release(meta, files, {"x": "X"}, "2026-09-20", exclude=[])
    text = res.files["a.md"].decode()
    assert "X dy {{z}}" in text
    assert render.strip_header(text) == "---\nid: protocol/a\n---\n\n# A\nX dy {{z}}\n"
    assert res.unfilled == []
    assert render.effective_settings(meta, {"x": ""})[1] == ["x"]
