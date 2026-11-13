"""release (DESIGN §4.8) and hooks (§4.13, §4.14, §4.14b, User decision 5)."""
from __future__ import annotations

import re

import json
import os
import subprocess
import shutil
import time

import pytest

from conftest import TOOLS_DIR, copy_tool_into, git, snapshot

DOC = "protocol/session-log"


def tags(wh):
    return git(wh.root, "tag", "--list").split()


def initial(wh, item_id=DOC, version="1.0.0", **kw):
    wh.write_item(item_id, version, record=kw.pop("record", "#### Added\n- First release."), **kw)
    wh.commit("add item")
    code, out = wh.run("release", item_id, "initial", "--no-sync")
    assert code == 0, out


def test_release_minor_moves_unreleased_bumps_commits_tags(wh):
    initial(wh)
    wh.write_item(DOC, "1.0.0", "Changed body.\n", unreleased="- New optional section.")
    (wh.root / "other.txt").write_text("staged but unrelated\n")
    git(wh.root, "add", "other.txt")
    code, out = wh.run("release", DOC, "minor", "--no-sync")
    assert code == 0, out
    text = (wh.root / "protocols" / "session-log.md").read_text()
    assert "version: 1.1.0" in text
    assert "### [Unreleased]\n\n### [1.1.0] - 2026-09-20\n#### Added\n- New optional section.\n\n### [1.0.0]" in text
    names = git(wh.root, "show", "--name-only", "--format=%s", "HEAD").split()
    assert names[0] == "release:" and set(names[2:]) == {"00_INDEX.md", "protocols/session-log.md"}
    assert git(wh.root, "diff", "--cached", "--name-only").split() == ["other.txt"]
    assert "protocol/session-log@1.1.0" in tags(wh)
    assert git(wh.root, "cat-file", "-t", "refs/tags/protocol/session-log@1.1.0").strip() == "tag"
    index = (wh.root / "00_INDEX.md").read_text()
    assert "| protocol | 1.1.0 | 1.1.0 | canonical |" in index and "— protocol/session-log 1.1.0" in index
    assert "Hand-written intro that must survive." in index


def test_release_requires_nonempty_unreleased(wh):
    initial(wh)
    code, out = wh.run("release", DOC, "patch", "--no-sync")
    assert code == 5 and "no entries" in out
    code, out = wh.run("release", "protocol/nope", "patch")
    assert code == 5


def test_release_frontmatter_must_match_latest_tag(wh):
    initial(wh)
    wh.write_item(DOC, "1.0.0", unreleased="- x.")
    p = wh.root / "protocols" / "session-log.md"
    p.write_text(p.read_text().replace("version: 1.0.0", "version: 1.0.5").replace("[1.0.0]", "[1.0.5]"))
    code, out = wh.run("release", DOC, "patch", "--no-sync")
    assert code == 5 and "not the latest tag" in out


def test_release_major_requires_breaking_and_migration(wh):
    initial(wh)
    wh.write_item(DOC, "1.0.0", unreleased="- Just a change.")
    code, out = wh.run("release", DOC, "major", "--no-sync")
    assert code == 5 and "BREAKING" in out
    wh.write_item(DOC, "1.0.0", unreleased="- **BREAKING:** renamed field.")
    code, out = wh.run("release", DOC, "major", "--no-sync")
    assert code == 5 and "Migration" in out
    wh.write_item(DOC, "1.0.0", unreleased="- **BREAKING:** renamed field.\n  **Migration:** rename it.")
    code, out = wh.run("release", DOC, "major", "--no-sync")
    assert code == 0, out
    assert "protocol/session-log@2.0.0" in tags(wh)


def test_release_runs_tool_tests_and_aborts_on_failure(wh):
    initial(wh, "tool/t", files={"tests/test_ok.py": "def test_ok():\n    assert True\n"})
    wh.write_item("tool/t", "1.0.0", unreleased="- Fix.", files={"tests/test_bad.py": "def test_bad():\n    assert False\n"})
    wh.commit("wip")
    head = git(wh.root, "rev-parse", "HEAD")
    before = snapshot(wh.root)
    code, out = wh.run("release", "tool/t", "patch", "--no-sync")
    assert code == 5 and "tool tests failed" in out
    assert git(wh.root, "rev-parse", "HEAD") == head
    after = snapshot(wh.root)
    assert {k: v for k, v in after.items() if not k.startswith("_tools/.state")} == \
           {k: v for k, v in before.items() if not k.startswith("_tools/.state")}
    assert not any(k for k in after if "__pycache__" in k or ".pytest_cache" in k)
    (wh.root / "tools" / "t" / "tests" / "test_bad.py").write_text("def test_bad():\n    assert True\n")
    code, out = wh.run("release", "tool/t", "patch", "--no-sync")
    assert code == 0, out


def test_release_initial_for_phase1_items(wh):
    import re
    # the real Phase-1 convention items must be releasable as `initial` once [Unreleased] is empty
    names = ("warehouse-item", "versioning", "changelog")
    for name in names:
        shutil.copy(TOOLS_DIR.parent / "conventions" / f"{name}.md", wh.root / "conventions" / f"{name}.md")
    wh.commit("phase 1 conventions")
    for name in names:
        path = wh.root / "conventions" / f"{name}.md"
        text = path.read_text(encoding="utf-8")
        if re.search(r"### \[Unreleased\]\n#", text):
            code, out = wh.run("release", f"convention/{name}", "initial", "--no-sync")
            assert code == 5 and "[Unreleased] has entries" in out
            path.write_text(re.sub(r"(### \[Unreleased\]\n)(?:#.*\n|- .*\n)+", r"\1", text), encoding="utf-8")
        code, out = wh.run("release", f"convention/{name}", "initial", "--no-sync")
        assert code == 0, out
    versions = {n: re.search(r"^version: (\S+)$", (wh.root / "conventions" / f"{n}.md").read_text(encoding="utf-8"), re.M).group(1)
                for n in names}
    assert {f"convention/{n}@{v}" for n, v in versions.items()} <= set(tags(wh))
    code, out = wh.run("release", "convention/versioning", "initial", "--no-sync")
    assert code == 5 and "already has releases" in out


def test_release_draft_major_sets_canonical(wh):
    initial(wh, "protocol/d", "0.2.0")
    wh.write_item("protocol/d", "0.2.0", unreleased="- Ready.")
    code, out = wh.run("release", "protocol/d", "major", "--no-sync")
    assert code == 0, out
    text = (wh.root / "protocols" / "d.md").read_text()
    assert "version: 1.0.0" in text and "status: canonical" in text


def test_release_triggers_sync_and_hook_noops(wh):
    copy_tool_into(wh)
    wh.commit("tool")
    assert wh.run("install-hook")[0] == 0
    initial(wh)
    p = wh.project("alpha", f"items:\n  - {DOC}@1\n")
    manual = wh.project("manual", f"auto_sync: false\nitems:\n  - {DOC}@1\n")
    wh.write_item(DOC, "1.0.0", "Now better.\n", unreleased="- Better.")
    code, out = wh.run("release", DOC, "minor")
    assert code == 0, out
    assert "released protocol/session-log@1.1.0" in out and "installed" in out
    assert wh.lock(p)["items"][DOC]["version"] == "1.1.0"
    assert not (manual / ".warehouse.lock").exists()
    state = wh.root / "_tools" / ".state"
    log = (state / "hook.log").read_text() if (state / "hook.log").exists() else ""
    assert "sync --auto" not in log  # the hook skipped; release ran its own sync
    assert all("skipped (release in progress" in line for line in log.splitlines()), log
    digest = json.loads((state / "auto-sync.json").read_text())["tags_digest"]
    from warehouse_core.catalog import Catalog
    from warehouse_core.gitrepo import Git
    assert digest == Catalog(Git(wh.root)).tags_digest()


def test_release_restores_files_on_commit_failure(wh):
    initial(wh)
    wh.write_item(DOC, "1.0.0", unreleased="- Change.")
    hook = wh.root / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n")
    before = snapshot(wh.root)
    code, out = wh.run("release", DOC, "minor", "--no-sync")
    assert code == 3 and "files and index restored" in out
    assert git(wh.root, "diff", "--cached", "--name-only").strip() == ""
    after = snapshot(wh.root)
    assert {k: v for k, v in after.items() if not k.startswith("_tools/.state")} == \
           {k: v for k, v in before.items() if not k.startswith("_tools/.state")}
    assert "protocol/session-log@1.1.0" not in tags(wh)


def test_release_refuses_mid_merge(wh):
    initial(wh)
    (wh.root / ".git" / "MERGE_HEAD").write_text(git(wh.root, "rev-parse", "HEAD"))
    code, out = wh.run("release", DOC, "patch")
    assert code == 3


# ------------------------------------------------------------------ hooks

def test_install_hook_idempotent_and_force_backup(wh):
    copy_tool_into(wh)
    hooks = wh.root / ".git" / "hooks"
    code, out = wh.run("install-hook")
    assert code == 0 and "post-commit: installed" in out and "post-merge: installed" in out
    shipped_commit = (TOOLS_DIR / "hooks" / "post-commit").read_bytes().replace(b"\r\n", b"\n")
    assert (hooks / "post-commit").read_bytes() == shipped_commit
    assert b"sync --auto --if-new-tags" in (hooks / "post-merge").read_bytes()
    code, out = wh.run("install-hook")
    assert code == 0 and out.count("already installed") == 4
    (hooks / "post-merge").write_text("#!/bin/sh\necho mine\n")
    code, out = wh.run("install-hook")
    assert code == 2 and "--force" in out
    code, out = wh.run("install-hook", "--force")
    assert code == 0 and (hooks / "post-merge.bak").read_text() == "#!/bin/sh\necho mine\n"
    assert (wh.root / "_tools" / ".state").is_dir()


def test_shipped_hooks_present_and_safe():
    for name in ("post-commit", "post-merge"):
        text = (TOOLS_DIR / "hooks" / name).read_text()
        assert text.startswith("#!/bin/sh\n")
        assert 'if [ -n "$WAREHOUSE_RELEASING" ]; then' in text
        assert 'done (exit $?)' in text
        assert "unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_PREFIX" in text
        assert "sync --auto --if-new-tags" in text and text.rstrip().endswith("exit 0")


def _hook_log(wh):
    p = wh.root / "_tools" / ".state" / "hook.log"
    return p.read_text() if p.exists() else ""


def test_hook_script_manual_tag_then_commit_syncs(wh):
    if shutil.which("python") is None:
        pytest.skip("python not on PATH for the hook shell")
    copy_tool_into(wh)
    wh.commit("tool")
    assert wh.run("install-hook")[0] == 0
    wh.publish(DOC, "1.0.0")
    p = wh.project("alpha", f"items:\n  - {DOC}@1\n")
    # manual tag (commit done with WAREHOUSE_RELEASING so that commit's hook no-ops)
    wh.publish(DOC, "1.1.0", body="Tagged by hand.\n")
    assert not (p / ".warehouse.lock").exists()
    (wh.root / "notes.txt").write_text("unrelated\n")
    git(wh.root, "add", "notes.txt")
    git(wh.root, "commit", "-q", "-m", "chore: ordinary commit")  # real post-commit hook runs
    lock = wh.lock(p)
    assert lock["items"][DOC]["version"] == "1.1.0", _hook_log(wh)
    assert "Tagged by hand." in (p / "warehouse" / "session-log.md").read_text()
    log = _hook_log(wh)
    assert re.search(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d post-commit: sync --auto --if-new-tags$", log, re.M), log
    assert re.search(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d post-commit: done \(exit 0\)$", log, re.M), log
    assert "post-commit: skipped (release in progress" in log  # publish() commits with WAREHOUSE_RELEASING


def test_post_merge_hook_syncs_new_tags(wh):
    """User decision 5: a pull/merge bringing new tags triggers sync."""
    if shutil.which("python") is None:
        pytest.skip("python not on PATH for the hook shell")
    copy_tool_into(wh)
    wh.commit("tool")
    wh.publish(DOC, "1.0.0")
    p = wh.project("alpha", f"items:\n  - {DOC}@1\n")
    assert wh.run("sync", "--auto")[0] == 0
    assert wh.run("install-hook")[0] == 0
    git(wh.root, "checkout", "-q", "-b", "feature")
    wh.publish(DOC, "1.2.0", body="From the other branch.\n")
    git(wh.root, "checkout", "-q", "main")
    git(wh.root, "merge", "-q", "--no-edit", "feature")  # post-merge hook runs
    assert wh.lock(p)["items"][DOC]["version"] == "1.2.0", _hook_log(wh)


def _run_hook(wh, name, *args, stdin="", env_extra=None):
    env = {k: v for k, v in os.environ.items() if k != "WAREHOUSE_RELEASING"}
    env.update(env_extra or {})
    # bytes, not text: on Windows, text mode turns the LF line endings git sends into CRLF
    cp = subprocess.run([shutil.which("sh"), str(wh.root / ".git" / "hooks" / name), *args], cwd=wh.root,
                        input=stdin.encode(), capture_output=True, env=env)
    return cp.returncode, (cp.stdout + cp.stderr).decode("utf-8", "replace")


def _install_hooks(wh):
    if shutil.which("python") is None or shutil.which("sh") is None:
        pytest.skip("python or sh not on PATH for the hook shell")
    copy_tool_into(wh)
    wh.commit("tool")
    assert wh.run("install-hook")[0] == 0


def _push(wh, remote_sha, ref="refs/heads/main"):
    head = git(wh.root, "rev-parse", "HEAD").strip()
    return _run_hook(wh, "pre-push", "origin", "url", stdin=f"{ref} {head} {ref} {remote_sha}\n")


def test_pre_push_checks_the_tip_not_each_commit(wh):
    _install_hooks(wh)
    base = git(wh.root, "rev-parse", "HEAD").strip()
    wh.write_item(DOC, "1.0.0", record="#### Added\n- First release.")
    wh.commit("feat: draft the session log")  # item work committed before its release
    assert wh.run("release", DOC, "initial", "--no-sync")[0] == 0

    code, out = _push(wh, base)
    assert code == 0 and "validation passed" in out, out
    code, out = _push(wh, "0" * 40)  # empty remote (a recreated repo): the whole history is pushed
    assert code == 0 and "validation passed" in out, out

    wh.write_item("protocol/new-draft", "0.1.0", unreleased="- First draft.")
    wh.commit("chore: add a draft protocol")
    code, out = _push(wh, base)
    assert code == 1 and "protocol/new-draft" in out and "never released" in out, out
    assert DOC not in out

    deletion = f"(delete) {'0' * 40} refs/heads/old {base}\n"
    assert _run_hook(wh, "pre-push", "origin", "url", stdin=deletion)[0] == 0
    code, out = _push(wh, base, ref="refs/tags/protocol/new-draft@0.1.0")  # a tag push is not checked
    assert code == 0, out


def test_pre_push_blocks_a_released_item_changed_since_its_release(wh):
    _install_hooks(wh)
    base = git(wh.root, "rev-parse", "HEAD").strip()
    wh.write_item(DOC, "1.0.0", record="#### Added\n- First release.")
    wh.commit("feat: add the session log")
    assert wh.run("release", DOC, "initial", "--no-sync")[0] == 0
    wh.write_item(DOC, "1.0.0", body="Changed body.\n", unreleased="- Changed the body.")
    wh.commit("feat: change the session log")
    code, out = _push(wh, base)
    assert code == 1 and DOC in out and "differs from 1.0.0" in out and "[Unreleased]" in out, out


def test_pre_push_allows_unsynced_tool_test_changes(wh):
    _install_hooks(wh)
    base = git(wh.root, "rev-parse", "HEAD").strip()
    tool = "tool/demo"
    wh.write_item(tool, "0.1.0", record="### Added\n- First release.", files={"tests/test_demo.py": "def test_ok():\n    assert True\n"})
    wh.commit("feat: add the demo tool")
    assert wh.run("release", tool, "initial", "--no-sync")[0] == 0

    wh.write_item(tool, "0.1.0", files={"tests/test_demo.py": "def test_ok():\n    assert 1 == 1\n"})
    wh.commit("test: reword the demo test")
    code, out = _push(wh, base)
    assert code == 0 and "validation passed" in out, out  # tests/ never syncs, so no release is needed

    wh.write_item(tool, "0.1.0", files={"main.py": "print('changed')\n", "tests/test_demo.py": "def test_ok():\n    assert 1 == 1\n"})
    wh.commit("fix: change the demo tool")
    code, out = _push(wh, base)
    assert code == 1 and tool in out and "main.py" in out, out


def test_unreleased_accepts_an_older_release_at_an_older_commit(wh):
    wh.write_item(DOC, "1.0.0", record="#### Added\n- First release.")
    wh.commit("feat: add the session log")
    assert wh.run("release", DOC, "initial", "--no-sync")[0] == 0
    first = git(wh.root, "rev-parse", "HEAD").strip()
    wh.write_item(DOC, "1.0.0", body="Changed body.\n", unreleased="- Changed the body.")
    wh.commit("feat: change the session log")
    middle = git(wh.root, "rev-parse", "HEAD").strip()
    assert wh.run("release", DOC, "patch", "--no-sync")[0] == 0

    assert wh.run("unreleased")[0] == 0
    code, out = wh.run("unreleased", first)  # holds 1.0.0, older than the newest release
    assert code == 0, out
    code, out = wh.run("unreleased", middle)
    assert code == 1 and "differs from 1.0.0" in out, out
    assert wh.run("unreleased", "no-such-rev")[0] == 2


def test_commit_msg_hook_enforces_conventional_commits(wh):
    if shutil.which("sh") is None:
        pytest.skip("sh not on PATH for the hook shell")
    copy_tool_into(wh)
    assert wh.run("install-hook")[0] == 0
    msg = wh.root / "MSG"
    for text, expected in [("fix(hooks): read pushed refs from stdin\n", 0), ("chore: tidy up\n", 0),
                           ("ordinary commit\n", 1), ("Fix: capitalised summary\n", 1),
                           ("Merge branch 'feature'\n", 0)]:
        msg.write_text(text)
        assert _run_hook(wh, "commit-msg", str(msg))[0] == expected, text
    msg.write_text("release protocol/x@1.0.0\n")
    assert _run_hook(wh, "commit-msg", str(msg))[0] == 1
    assert _run_hook(wh, "commit-msg", str(msg), env_extra={"WAREHOUSE_RELEASING": "1"})[0] == 0
