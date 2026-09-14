"""Safety invariants I1-I10 across batch-1 commands (DESIGN §6; plan §8 No commits)."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from conftest import git, snapshot
from warehouse_core import fsops
from warehouse_core.errors import GuardError, UsageError
from warehouse_core.fsops import WriteGuard, atomic_write

DOC = "protocol/session-log"


def setup_world(wh):
    wh.publish(DOC, "1.0.0", body="Logs in {{folder}}.\n", settings={"folder": "F"})
    wh.publish("tool/t", "1.0.0", files={"tests/test_a.py": "def test_a(): pass\n"})
    wh.publish("skill/s", "1.0.0", requires=["tool/t@1"])
    wh.publish("protocol/extra", "1.0.0")
    p = wh.project("alpha", f"# comment\nitems:\n  - {DOC}@1\n  - skill/s@1\nsettings:\n  folder: AI\n")
    assert wh.run("sync")[0] == 0
    wh.publish(DOC, "1.1.0", body="Logs in {{folder}}. v2\n", settings={"folder": "F"})
    return p


COMMANDS = {
    "sync": (lambda wh, p: wh.run("sync"), False),
    "sync-explicit": (lambda wh, p: wh.run("sync", str(p)), False),
    "pull": (lambda wh, p: wh.run("pull", DOC, project=p), False),
    "pull-all": (lambda wh, p: wh.run("pull", "--all", project=p), False),
    "add": (lambda wh, p: wh.run("add", "protocol/extra", project=p), True),
    "remove": (lambda wh, p: wh.run("remove", "skill/s", "--prune", project=p), True),
    "status": (lambda wh, p: wh.run("status", project=p), False),
    "check": (lambda wh, p: wh.run("check"), False),
    "impact": (lambda wh, p: wh.run("impact", DOC), False),
}


@pytest.mark.parametrize("name", sorted(COMMANDS))
def test_writes_confined_to_target_lock(wh, name):
    p = setup_world(wh)
    outside = wh.project("bystander", "items: []\n")
    before, before_outside = snapshot(p), snapshot(outside)
    wh_before = snapshot(wh.root)
    func, manifest_allowed = COMMANDS[name]
    func(wh, p)
    after = snapshot(p)
    changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
    allowed = {k for k in changed if k.startswith("warehouse/") or k == ".warehouse.lock"}
    if manifest_allowed:
        allowed |= {".warehouse.yml"} & changed
    assert changed == allowed, changed - allowed
    assert snapshot(outside) == before_outside
    wh_after = snapshot(wh.root)
    wh_changed = {k for k in set(wh_before) | set(wh_after) if wh_before.get(k) != wh_after.get(k)}
    assert all(k.startswith("_tools/.state/") for k in wh_changed), wh_changed  # I9


@pytest.mark.parametrize("name", sorted(COMMANDS))
def test_no_git_in_projects(wh, git_spy, name):
    p = setup_world(wh)
    head, refs = git(p, "rev-parse", "HEAD"), git(p, "for-each-ref")
    index_bytes = (p / ".git" / "index").read_bytes()
    git_spy.clear()
    COMMANDS[name][0](wh, p)
    wh_real = os.path.normcase(os.path.realpath(wh.root))
    assert git_spy, "expected git calls against the warehouse"
    for call in git_spy:
        assert call[1] == "-C" and os.path.normcase(os.path.realpath(call[2])) == wh_real, call
    assert git(p, "rev-parse", "HEAD") == head and git(p, "for-each-ref") == refs
    assert (p / ".git" / "index").read_bytes() == index_bytes
    assert git(p, "log", "--oneline").count("\n") == 1


def test_write_guard_rejects_escape(tmp_path):
    proj = tmp_path / "proj"
    (proj / "warehouse").mkdir(parents=True)
    g = WriteGuard(proj, "warehouse")
    for bad in [proj / "warehouse" / ".." / "own.txt", proj / "own.txt", tmp_path / "elsewhere.txt",
                Path("C:/Windows/evil.txt"), proj / ".warehouse.yml"]:
        with pytest.raises(GuardError):
            atomic_write(g, bad, b"x")
    atomic_write(g, proj / "warehouse" / "ok.md", b"x")
    atomic_write(g, proj / ".warehouse.lock", b"{}")
    WriteGuard(proj, "warehouse", allow_manifest=True).check(proj / ".warehouse.yml")
    # target that is a junction / symlink
    real = tmp_path / "real-target"
    real.mkdir()
    link = proj / "linked"
    if os.name == "nt":
        cp = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(real)], capture_output=True)
        made = cp.returncode == 0
    else:
        link.symlink_to(real, target_is_directory=True)
        made = True
    if made:
        with pytest.raises(UsageError, match="symlink or junction"):
            WriteGuard(proj, "linked")
        os.rmdir(link) if os.name == "nt" else link.unlink()


def test_symlinked_target_reported_by_sync(wh):
    wh.publish(DOC, "1.0.0", body="x\n")
    real = wh.tmp / "outside-target"
    real.mkdir()
    p = wh.project("alpha", f"target: linked\nitems:\n  - {DOC}@1\n")
    if os.name == "nt":
        if subprocess.run(["cmd", "/c", "mklink", "/J", str(p / "linked"), str(real)], capture_output=True).returncode:
            pytest.skip("cannot create junction")
    else:
        (p / "linked").symlink_to(real, target_is_directory=True)
    code, out = wh.run("sync")
    assert code == 1 and "symlink or junction" in out
    assert list(real.iterdir()) == []


def test_interrupted_apply_recovers(wh, monkeypatch):
    wh.publish("skill/s", "1.0.0", files={"a.txt": "a1\n", "b.txt": "b1\n", "c.txt": "c1\n"})
    p = wh.project("alpha", "items:\n  - skill/s@1\n")
    wh.run("sync")
    wh.publish("skill/s", "1.1.0", files={"a.txt": "a2\n", "b.txt": "b2\n", "c.txt": "c2\n"})
    real_replace = os.replace
    count = {"n": 0}

    def flaky(src, dst):
        if str(dst).endswith("b.txt"):
            raise OSError("simulated crash")
        count["n"] += 1
        return real_replace(src, dst)

    monkeypatch.setattr(fsops.os, "replace", flaky)
    code, out = wh.run("sync")
    assert code == 1 and "error" in out
    lock = wh.lock(p)["items"]["skill/s"]
    assert lock["pending"] is not None and lock["version"] == "1.0.0"
    monkeypatch.setattr(fsops.os, "replace", real_replace)
    (p / "warehouse" / "skills" / "s" / "b.txt.warehouse-tmp-99999").write_text("junk")
    code, out = wh.run("sync")
    assert code == 0, out
    assert "drift" not in out
    lock = wh.lock(p)["items"]["skill/s"]
    assert lock["version"] == "1.1.0" and lock["pending"] is None
    base = p / "warehouse" / "skills" / "s"
    assert [base.joinpath(n).read_text() for n in ("a.txt", "b.txt", "c.txt")] == ["a2\n", "b2\n", "c2\n"]
    assert not [f for f in snapshot(p) if "warehouse-tmp" in f]


def test_git_env_vars_stripped(wh, monkeypatch):
    wh.publish(DOC, "1.0.0", body="x\n")
    p = wh.project("alpha", f"items:\n  - {DOC}@1\n")
    monkeypatch.setenv("GIT_DIR", str(p / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(p))
    code, out = wh.run("sync")
    assert code == 0 and (p / "warehouse" / "session-log.md").exists()


def test_partial_item_never_written_on_collision(wh):
    """I10: a collision on one file means no file of that item is written."""
    wh.publish("skill/s", "1.0.0", files={"a.txt": "a\n", "z.txt": "z\n"})
    p = wh.project("alpha", "items:\n  - skill/s@1\n")
    (p / "warehouse" / "skills" / "s").mkdir(parents=True)
    (p / "warehouse" / "skills" / "s" / "z.txt").write_text("mine\n")
    code, out = wh.run("sync")
    assert code == 1 and "collision" in out
    assert sorted(x.name for x in (p / "warehouse" / "skills" / "s").iterdir()) == ["z.txt"]
