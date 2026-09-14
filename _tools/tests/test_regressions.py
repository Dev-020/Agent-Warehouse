"""Regression tests for the batch-1 review defects (Reviewer repros A-H and items 1-14)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import git, snapshot
from warehouse_core import errors, fsops, gitrepo, items, software
from warehouse_core.fsops import WriteGuard, cleanup_temp_files
from warehouse_core.gitrepo import Git

DOC = "protocol/session-log"


def _replace_failing(monkeypatch, predicate):
    real = os.replace

    def fake(src, dst):
        if predicate(str(dst)):
            raise PermissionError("locked by another process")
        return real(src, dst)

    monkeypatch.setattr(fsops.os, "replace", fake)
    return real


# ------------------------------------------------------------------ 1 (repro A)

def test_double_interruption_no_false_drift(wh, monkeypatch):
    wh.publish("skill/s", "1.0.0", files={"a.txt": "a1\n", "b.txt": "b1\n"})
    p = wh.project("alpha", "items:\n  - skill/s@1\n")
    assert wh.run("sync")[0] == 0
    wh.publish("skill/s", "1.1.0", files={"a.txt": "a2\n", "b.txt": "b2\n"})
    real = _replace_failing(monkeypatch, lambda d: d.endswith("b.txt"))
    assert wh.run("sync")[0] == 1                       # a.txt -> a2, b.txt fails
    wh.publish("skill/s", "1.2.0", files={"a.txt": "a3\n", "b.txt": "b3\n"})
    _replace_failing(monkeypatch, lambda d: "skills" in d)
    assert wh.run("sync")[0] == 1                       # nothing written; pending moves to 1.2.0
    monkeypatch.setattr(fsops.os, "replace", real)
    code, out = wh.run("sync")
    assert code == 0, out
    assert "drift" not in out
    base = p / "warehouse" / "skills" / "s"
    assert (base / "a.txt").read_text() == "a3\n" and (base / "b.txt").read_text() == "b3\n"
    lock = wh.lock(p)["items"]["skill/s"]
    assert lock["version"] == "1.2.0" and lock["pending"] is None


# ------------------------------------------------------------------ 2 (repro B)

def test_guard_error_is_per_item_not_fatal(wh):
    assert not issubclass(errors.GuardError, AssertionError)
    wh.publish("tool/a", "1.0.0", files={"a.txt": "a1\n"})
    wh.publish("skill/s", "1.0.0")
    p = wh.project("alpha", "items:\n  - tool/a@1\n  - skill/s@1\n")
    q = wh.project("beta", "items:\n  - skill/s@1\n")
    outside = wh.tmp / "outside"
    outside.mkdir()
    (p / "warehouse" / "tools").mkdir(parents=True)
    link = p / "warehouse" / "tools" / "a"
    if os.name == "nt":
        if subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True).returncode:
            pytest.skip("cannot create junction")
    else:
        link.symlink_to(outside, target_is_directory=True)
    try:
        code, out = wh.run("sync")
    finally:
        os.rmdir(link) if os.name == "nt" else link.unlink()
    assert code == 1 and "error" in out and "GuardError" in out
    assert list(outside.iterdir()) == []
    assert (p / "warehouse" / "skills" / "s" / "SKILL.md").exists()          # other item in the same project
    assert (q / "warehouse" / "skills" / "s" / "SKILL.md").exists()          # other project


def test_unexpected_exception_in_one_project_does_not_stop_others(wh, monkeypatch):
    from warehouse_core.commands import sync as sync_cmd
    wh.publish(DOC, "1.0.0")
    a = wh.project("a", f"items:\n  - {DOC}@1\n")
    b = wh.project("b", f"items:\n  - {DOC}@1\n")
    real = sync_cmd.apply_actions

    def boom(ctx, proj, *args, **kw):
        if proj.root.name == "a":
            raise RuntimeError("unexpected")
        return real(ctx, proj, *args, **kw)

    monkeypatch.setattr(sync_cmd, "apply_actions", boom)
    code, out = wh.run("sync", "--auto")
    assert code == 1 and "RuntimeError: unexpected" in out
    assert (b / "warehouse" / "session-log.md").exists()
    state = json.loads((wh.root / "_tools" / ".state" / "auto-sync.json").read_text())
    assert state["needs_retry"] is True


# ------------------------------------------------------------------ 11 hook recovery

def test_if_new_tags_retries_after_error_or_pending(wh, monkeypatch):
    wh.publish("skill/s", "1.0.0", files={"a.txt": "a\n"})
    p = wh.project("alpha", "items:\n  - skill/s@1\n")
    real = _replace_failing(monkeypatch, lambda d: d.endswith("a.txt"))
    code, out = wh.run("sync", "--auto", "--if-new-tags")
    assert code == 1
    monkeypatch.setattr(fsops.os, "replace", real)
    code, out = wh.run("sync", "--auto", "--if-new-tags")   # tags unchanged, but last run needs retry
    assert code == 0 and "installed" in out
    assert wh.lock(p)["items"]["skill/s"]["pending"] is None
    assert wh.run("sync", "--auto", "--if-new-tags") == (0, "")


# ------------------------------------------------------------------ 3 (repro C)

def test_non_utf8_md_is_lint_error_and_not_fatal_in_sync(wh):
    wh.publish("skill/s", "1.0.0", files={"notes.md": b"caf\xe9\n"})
    wh.publish("protocol/z", "1.0.0")
    p = wh.project("alpha", "items:\n  - skill/s@1\n")
    q = wh.project("beta", "items:\n  - protocol/z@1\n")
    code, out = wh.run("sync")
    assert code == 1 and "not valid UTF-8" in out
    assert not (p / "warehouse" / "skills").exists()
    assert (q / "warehouse" / "z.md").exists()
    assert "encoding" in {pr.code for pr in items.lint_item(wh.root, "skill/s")}
    wh.write_item("skill/s", "1.0.0", files={"notes.md": b"caf\xe9\n"}, unreleased="- x.")
    code, out = wh.run("release", "skill/s", "patch", "--no-sync")
    assert code == 5 and "encoding" in out


# ------------------------------------------------------------------ 4 (repro D)

def test_pull_major_skill_brings_tool_major(wh):
    wh.publish("tool/t", "1.0.0")
    wh.publish("skill/s", "1.0.0", requires=["tool/t@1"])
    p = wh.project("alpha", "items:\n  - skill/s@1\n")
    code, out = wh.run("sync")
    assert code == 0, out
    wh.publish("tool/t", "2.0.0")
    wh.publish("skill/s", "2.0.0", requires=["tool/t@2"])
    code, out = wh.run("pull", "skill/s", "--major", project=p)
    assert code == 0, out
    lock = wh.lock(p)["items"]
    assert lock["skill/s"]["version"] == "2.0.0" and lock["tool/t"]["version"] == "2.0.0"
    assert "  - skill/s@2\n" in (p / ".warehouse.yml").read_text()


def test_minor_skill_needing_tool_major_has_a_way_out(wh):
    wh.publish("tool/t", "1.0.0")
    wh.publish("skill/s", "1.0.0", requires=["tool/t@1"])
    p = wh.project("alpha", "items:\n  - skill/s@1\n")
    q = wh.project("beta", "items:\n  - skill/s@1\n")
    assert wh.run("sync")[0] == 0
    wh.publish("tool/t", "2.0.0")
    wh.publish("skill/s", "1.1.0", requires=["tool/t@2"])
    code, out = wh.run("sync")
    assert "warehouse pull skill/s --major" in out and "pull tool/t --major" not in out
    code, out = wh.run("pull", "tool/t", "--major", project=p)
    assert code == 1 and "pull the requiring item with --major" in out
    code, out = wh.run("pull", "skill/s", "--major", project=p)
    assert code == 0, out
    lock = wh.lock(p)["items"]
    assert lock["skill/s"]["version"] == "1.1.0" and lock["tool/t"]["version"] == "2.0.0"
    code, out = wh.run("pull", "--all", "--major", project=q)
    assert code == 0, out
    lock = wh.lock(q)["items"]
    assert lock["skill/s"]["version"] == "1.1.0" and lock["tool/t"]["version"] == "2.0.0"
    body = [l for l in out.splitlines() if l.startswith("  ")]
    assert len(body) == len(set(body)), out


# ------------------------------------------------------------------ 5 (repro E)

def test_failed_release_commit_leaves_index_clean(wh):
    wh.write_item(DOC, "1.0.0", record="#### Added\n- First.")
    wh.commit("init item")
    assert wh.run("release", DOC, "initial", "--no-sync")[0] == 0
    wh.write_item(DOC, "1.0.0", unreleased="- Change.")
    (wh.root / "other.txt").write_text("user staged\n")
    git(wh.root, "add", "other.txt")
    (wh.root / ".git" / "hooks" / "pre-commit").write_text("#!/bin/sh\nexit 1\n")
    code, out = wh.run("release", DOC, "minor", "--no-sync")
    assert code == 3 and "index restored" in out
    assert git(wh.root, "diff", "--cached", "--name-only").split() == ["other.txt"]


# ------------------------------------------------------------------ 6 (repro F)

def test_same_line_pin_narrowing_is_outside_pin_not_major(wh):
    wh.publish("tool/t", "1.0.0")
    wh.publish("skill/s", "2.3.0", requires=["tool/t@1"])
    wh.publish("skill/s", "2.4.0", requires=["tool/t@1"])
    p = wh.project("alpha", "items:\n  - skill/s@2\n")
    assert wh.run("sync")[0] == 0
    (p / ".warehouse.yml").write_text("items:\n  - skill/s@2.3\n")
    before = snapshot(p)
    code, out = wh.run("sync")
    assert code == 0, out
    assert "outside-pin" in out and "run warehouse pull skill/s" in out
    assert "orphan" not in out and "--major" not in out and "  major" not in out
    after = snapshot(p)
    changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
    assert changed <= {".warehouse.lock", "warehouse/README.md"}   # pin metadata only; no item file written
    code, out = wh.run("pull", "skill/s", project=p)
    assert code == 0 and wh.lock(p)["items"]["skill/s"]["version"] == "2.3.0"
    assert wh.lock(p)["items"]["tool/t"]["required_by"] == ["skill/s"]


# ------------------------------------------------------------------ 7 (repro G)

def test_case_only_rename_between_versions(wh):
    wh.publish("skill/s", "1.0.0", files={"Notes.txt": "n1\n"})
    p = wh.project("alpha", "items:\n  - skill/s@1\n")
    assert wh.run("sync")[0] == 0
    git(wh.root, "rm", "-q", "--cached", "skills/s/Notes.txt")
    (wh.root / "skills" / "s" / "Notes.txt").unlink()
    wh.publish("skill/s", "1.1.0", files={"notes.txt": "n2\n"})
    code, out = wh.run("sync")
    assert code == 0, out
    base = p / "warehouse" / "skills" / "s"
    assert "notes.txt" in os.listdir(base) and "Notes.txt" not in os.listdir(base)
    assert (base / "notes.txt").read_text() == "n2\n"
    code, out = wh.run("sync")
    assert code == 0 and "collision" not in out
    assert list(wh.lock(p)["items"]["skill/s"]["files"]) == ["skills/s/CHANGELOG.md", "skills/s/SKILL.md",
                                                               "skills/s/notes.txt"]


# ------------------------------------------------------------------ 8 (repro H)

def test_hand_removed_entry_during_pending_update_cleans_up(wh, monkeypatch):
    wh.publish("skill/s", "1.0.0", files={"a.txt": "a1\n"})
    p = wh.project("alpha", "items:\n  - skill/s@1\n")
    assert wh.run("sync")[0] == 0
    wh.publish("skill/s", "1.1.0", files={"a.txt": "a1\n", "new.txt": "n\n", "z.txt": "z\n"})
    real = _replace_failing(monkeypatch, lambda d: d.endswith("z.txt"))
    wh.run("sync")
    monkeypatch.setattr(fsops.os, "replace", real)
    assert (p / "warehouse" / "skills" / "s" / "new.txt").exists()
    (p / ".warehouse.yml").write_text("items: []\n")
    code, out = wh.run("sync")
    assert code == 0 and "removed" in out, out
    assert not (p / "warehouse" / "skills").exists()
    assert wh.lock(p)["items"] == {}


# ------------------------------------------------------------------ 9

def test_replaces_archived_matches_exact_id(wh):
    arch = wh.root / "_archive"
    arch.mkdir()
    (arch / "session-log-old.md").write_text("---\nid: protocol/session-log-old\n---\n")
    (arch / "backlog.md").write_text("---\nid: convention/backlog\n---\n")
    assert items.archived_ids(wh.root) == {"protocol/session-log-old", "convention/backlog"}
    wh.write_item("protocol/new1", "1.0.0", replaces="protocol/session-log", record="- x.")   # prefix only
    wh.write_item("protocol/new2", "1.0.0", replaces="protocol/backlog", record="- x.")       # wrong kind
    wh.write_item("protocol/new3", "1.0.0", replaces="convention/backlog", record="- x.")    # exact
    codes = lambda i: {pr.code for pr in items.lint_item(wh.root, i) if pr.level == "error"}
    assert "replaces" in codes("protocol/new1") and "replaces" in codes("protocol/new2")
    assert "replaces" not in codes("protocol/new3")


# ------------------------------------------------------------------ 10

def test_i2_violation_raises_even_with_optimizations(wh, tmp_path):
    gitrepo.register_warehouse_root(wh.root)
    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(errors.GitError, match="only run in the warehouse"):
        Git(other).run("status")
    code = ("import sys; sys.path.insert(0, sys.argv[1]); from warehouse_core import gitrepo, errors\n"
            "gitrepo.register_warehouse_root(sys.argv[2])\n"
            "try:\n    gitrepo.Git(sys.argv[3]).run('status')\nexcept errors.GitError:\n    sys.exit(7)\n")
    tools = str(Path(__file__).resolve().parents[1])
    r = subprocess.run([sys.executable, "-O", "-c", code, tools, str(wh.root), str(other)])
    assert r.returncode == 7


# ------------------------------------------------------------------ 12

def test_software_lookup_ignores_current_directory(tmp_path, monkeypatch):
    name = "wh-fake-tool-xyz"
    (tmp_path / f"{name}.exe").write_bytes(b"MZ")
    (tmp_path / name).write_bytes(b"#!/bin/sh\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", "")
    assert software.which_on_path(name) is None
    assert software.check(name)[0] == "missing"
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / f"{name}.exe").write_bytes(b"MZ")
    target = bindir / name
    target.write_bytes(b"#!/bin/sh\n")
    target.chmod(0o755)
    monkeypatch.setenv("PATH", os.pathsep.join([".", "relative", str(bindir)]))
    assert software.which_on_path(name) is not None
    assert Path(software.which_on_path(name)).parent == bindir


# ------------------------------------------------------------------ 13

def test_temp_cleanup_exact_pattern_incl_manifest(tmp_path):
    proj = tmp_path / "proj"
    (proj / "warehouse" / "sub").mkdir(parents=True)
    junk = [proj / ".warehouse.yml.warehouse-tmp-123", proj / ".warehouse.lock.warehouse-tmp-9",
            proj / "warehouse" / "sub" / "a.md.warehouse-tmp-4567"]
    keep = [proj / "warehouse" / "my.warehouse-tmp-notes.md", proj / "warehouse" / "x.warehouse-tmp-12a",
            proj / ".warehouse.yml.warehouse-tmp-backup", proj / "warehouse" / ".warehouse-tmp-1"]
    for f in junk + keep:
        f.write_text("x")
    cleanup_temp_files(WriteGuard(proj, "warehouse"))
    assert not any(f.exists() for f in junk)
    assert all(f.exists() for f in keep)


# ------------------------------------------------------------------ 14

def test_skill_blocked_when_required_tool_not_synced(wh):
    wh.publish("tool/t", "1.0.0", body="Needs {{tool_home}}.\n", settings={"tool_home": "Where"})
    wh.publish("skill/s", "1.0.0", requires=["tool/t@1"])
    p = wh.project("alpha", "items:\n  - skill/s@1\n")
    code, out = wh.run("sync")
    assert code == 1
    assert "unfilled" in out and "blocked" in out and "needs tool/t, which was not synced (unfilled)" in out
    assert "installed   skill/s" not in out
    assert wh.lock(p)["items"] == {} if (p / ".warehouse.lock").exists() else True
    assert not (p / "warehouse" / "skills").exists()


# ------------------------------------------------------------------ ALSO

def test_add_major_does_not_move_pin_when_blocked(wh):
    wh.publish("tool/t", "1.0.0")
    wh.publish("tool/t", "2.0.0")
    wh.publish("skill/s", "1.0.0", requires=["tool/t@1"])
    p = wh.project("alpha", "items:\n  - skill/s@1\n  - tool/t@1\n")
    assert wh.run("sync")[0] == 0
    before = (p / ".warehouse.yml").read_text()
    code, out = wh.run("add", "tool/t@2", "--major", project=p)
    assert code == 1 and "manifest unchanged" in out
    assert (p / ".warehouse.yml").read_text() == before
    assert wh.lock(p)["items"]["tool/t"]["version"] == "1.0.0"


def test_keep_shortcut_does_not_claim_restore_it_cannot_do(wh):
    wh.publish("skill/s", "1.0.0", files={"a.txt": "a\n", "desk.bin": "b\n"})
    p = wh.project("alpha", "items:\n  - skill/s@1\n")
    assert wh.run("sync")[0] == 0
    (p / "warehouse" / "skills" / "s" / "desk.bin").unlink()
    wh.write_config(sync_exclude=["tests/**", "**/*.bin"])   # the release no longer renders desk.bin
    code, out = wh.run("sync")
    assert code == 1 and "restored" not in out and "cannot restore skills/s/desk.bin" in out


def test_remove_cleans_stale_required_by_on_orphans(wh):
    wh.publish("tool/t", "1.0.0")
    wh.publish("skill/s", "1.0.0", requires=["tool/t@1"])
    p = wh.project("alpha", "items:\n  - skill/s@1\n")
    wh.run("sync")
    code, out = wh.run("remove", "skill/s", project=p)
    assert code == 0 and "orphan" in out
    assert wh.lock(p)["items"]["tool/t"]["required_by"] == []


def test_discovery_skips_linked_git_worktrees(wh):
    wh.publish(DOC, "1.0.0")
    main = wh.project("main", f"items:\n  - {DOC}@1\n")
    wt = wh.projects_dir / "main-feature"          # name does not say "worktrees"
    git(main, "worktree", "add", "-q", str(wt))
    (wt / ".warehouse.yml").write_text(f"items:\n  - {DOC}@1\n")
    assert (wt / ".git").is_file()
    code, out = wh.run("sync")
    assert (main / "warehouse" / "session-log.md").exists()
    assert not (wt / "warehouse").exists() and "main-feature" not in out


def test_desktop_ini_refs_ignored(wh):
    wh.publish(DOC, "1.0.0")
    ini = b"[.ShellClassInfo]\r\nIconResource=C:\\x.exe,27\r\n"
    for d in (wh.root / ".git" / "refs" / "tags", wh.root / ".git" / "refs" / "tags" / "protocol",
              wh.root / ".git" / "refs" / "heads"):
        d.mkdir(parents=True, exist_ok=True)
        (d / "desktop.ini").write_bytes(ini)
    gitrepo.register_warehouse_root(wh.root)
    names = [t.refname for t in Git(wh.root).tags()]
    assert names == ["refs/tags/protocol/session-log@1.0.0"]
    p = wh.project("alpha", f"items:\n  - {DOC}@1\n")
    assert wh.run("sync")[0] == 0 and (p / "warehouse" / "session-log.md").exists()
    code, out = wh.run("check")
    assert "desktop.ini" not in out and "malformed" not in out




def test_dependency_ordering_failure(wh):
    wh.publish('skill/z', '1.0.0', body='Needs {{x}}.\n', settings={'x': 'val'})
    wh.publish('skill/a', '1.0.0', requires=['skill/z@1'])
    p = wh.project('alpha', 'items:\n  - skill/a@1\n')
    code, out = wh.run('sync')
    assert code == 1
    assert 'blocked' in out and 'skill/a' in out and 'skill/z' in out
    assert 'installed   skill/a' not in out
    assert not (p / 'warehouse' / 'skills' / 'z').exists()
    assert not (p / 'warehouse' / 'skills' / 'a').exists()

def test_drifted_dependency_blocks_requirer(wh):
    wh.publish('tool/t', '1.0.0', files={'a.txt': 'a1\n'})
    wh.publish('skill/s', '1.0.0', requires=['tool/t@1.1'])
    p = wh.project('alpha', 'items:\n  - tool/t@1\n')
    wh.run('sync')
    (p / 'warehouse' / 'tools' / 't' / 'a.txt').write_text('drift\n')
    wh.publish('tool/t', '1.1.0', files={'a.txt': 'a2\n'})
    (p / '.warehouse.yml').write_text('items:\n  - skill/s@1\n  - tool/t@1\n')
    code, out = wh.run('sync')
    assert code == 1
    assert 'drift' in out
    assert 'blocked' in out and 'skill/s' in out

def test_keep_shortcut_hash_mismatch(wh):
    wh.publish('skill/s', '1.0.0', files={'a.txt': 'a1\n'})
    p = wh.project('alpha', 'items:\n  - skill/s@1\n')
    assert wh.run('sync')[0] == 0
    (p / 'warehouse' / 'skills' / 's' / 'a.txt').unlink()
    import subprocess
    subprocess.run(["git", "-C", str(wh.root), "tag", "-d", "skill/s@1.0.0"], check=True, capture_output=True)
    wh.publish('skill/s', '1.0.0', files={'a.txt': 'a2\n'})
    code, out = wh.run('sync')
    assert code == 1 and 'restored' not in out and 'cannot restore skills/s/a.txt' in out
