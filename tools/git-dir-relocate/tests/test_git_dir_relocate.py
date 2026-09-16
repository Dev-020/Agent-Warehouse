"""Tests for git_dir_relocate. Every repository is created under pytest's tmp_path."""
from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("gdr", Path(__file__).resolve().parents[1] / "git_dir_relocate.py")
gdr = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gdr)


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                          text=True, env=gdr._env()).stdout.strip()


def make_repo(path: Path, commits: int = 2) -> Path:
    path.mkdir(parents=True)
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.name", "t")
    git(path, "config", "user.email", "t@t")
    git(path, "config", "core.autocrlf", "false")
    for i in range(commits):
        (path / f"f{i}.md").write_text(f"note {i}\n", encoding="utf-8")
        git(path, "add", "-A")
        git(path, "commit", "-q", "-m", f"c{i}")
    git(path, "remote", "add", "origin", "https://example.invalid/repo.git")
    return path


def litter(git_dir: Path) -> int:
    n = 0
    for d in [git_dir, git_dir / "refs", git_dir / "refs" / "heads", git_dir / "refs" / "tags", git_dir / "objects"]:
        d.mkdir(parents=True, exist_ok=True)
        (d / "desktop.ini").write_text("[.ShellClassInfo]\n", encoding="utf-8")
        n += 1
    return n


def run(*argv: str) -> int:
    return gdr.main(list(argv))


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / "git-dirs"


def test_relocate_moves_database_and_preserves_repo(tmp_path, root, capsys):
    repo = make_repo(tmp_path / "Vault")
    (repo / "wip.md").write_text("uncommitted\n", encoding="utf-8")
    head = git(repo, "rev-parse", "HEAD")
    status = git(repo, "status", "--porcelain")

    assert run("relocate", str(repo), "--git-dirs", str(root)) == 0

    target = root / "Vault.git"
    assert target.is_dir() and (target / "HEAD").is_file()
    assert (repo / ".git").is_file()
    assert (repo / ".git").read_text(encoding="utf-8").strip().lower() == f"gitdir: {target.as_posix()}".lower()
    assert git(repo, "rev-parse", "HEAD") == head
    assert git(repo, "status", "--porcelain") == status
    assert "example.invalid" in git(repo, "remote", "-v")
    assert "verified" in capsys.readouterr().out


def test_relocate_removes_syncer_litter_so_refs_work(tmp_path, root):
    repo = make_repo(tmp_path / "Vault")
    litter(repo / ".git")
    assert run("relocate", str(repo), "--git-dirs", str(root)) == 0
    assert not list((root / "Vault.git").rglob("desktop.ini"))
    assert gdr.fsck_problems(repo) == []


def test_relocate_is_idempotent(tmp_path, root, capsys):
    repo = make_repo(tmp_path / "Vault")
    assert run("relocate", str(repo), "--git-dirs", str(root)) == 0
    assert run("relocate", str(repo), "--git-dirs", str(root)) == 0
    assert "already relocated" in capsys.readouterr().out


def test_dry_run_changes_nothing(tmp_path, root):
    repo = make_repo(tmp_path / "Vault")
    n = litter(repo / ".git")
    assert run("relocate", str(repo), "--git-dirs", str(root), "--dry-run") == 0
    assert (repo / ".git").is_dir()
    assert not root.exists()
    assert len(list((repo / ".git").rglob("desktop.ini"))) == n


def test_refuses_existing_target(tmp_path, root):
    repo = make_repo(tmp_path / "Vault")
    (root / "Vault.git").mkdir(parents=True)
    assert run("relocate", str(repo), "--git-dirs", str(root)) == gdr.EXIT_REFUSED
    assert (repo / ".git").is_dir()


def test_custom_name(tmp_path, root):
    repo = make_repo(tmp_path / "AI")
    assert run("relocate", str(repo), "--git-dirs", str(root), "--name", "AI-Agent-Warehouse") == 0
    assert (root / "AI-Agent-Warehouse.git").is_dir()


@pytest.mark.parametrize("bad", ["../escape", "..", "a b"])
def test_invalid_name_is_usage_error(tmp_path, root, bad):
    repo = make_repo(tmp_path / "Vault")
    assert run("relocate", str(repo), "--git-dirs", str(root), "--name", bad) == gdr.EXIT_USAGE
    assert (repo / ".git").is_dir()


def test_refuses_operation_in_progress(tmp_path, root):
    repo = make_repo(tmp_path / "Vault")
    (repo / ".git" / "MERGE_HEAD").write_text(git(repo, "rev-parse", "HEAD") + "\n", encoding="utf-8")
    assert run("relocate", str(repo), "--git-dirs", str(root)) == gdr.EXIT_REFUSED
    assert (repo / ".git").is_dir()


def test_refuses_subdirectory_of_repo(tmp_path, root):
    repo = make_repo(tmp_path / "Vault")
    (repo / "sub").mkdir()
    assert run("relocate", str(repo / "sub"), "--git-dirs", str(root)) == gdr.EXIT_REFUSED


def test_refuses_git_dirs_root_inside_repo(tmp_path):
    repo = make_repo(tmp_path / "Vault")
    assert run("relocate", str(repo), "--git-dirs", str(repo / "dbs")) == gdr.EXIT_REFUSED
    assert (repo / ".git").is_dir()


def test_worktrees_require_flag_and_are_repaired(tmp_path, root):
    repo = make_repo(tmp_path / "Vault")
    wt = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", "-b", "claim/x", str(wt))
    assert run("relocate", str(repo), "--git-dirs", str(root)) == gdr.EXIT_REFUSED
    assert run("relocate", str(repo), "--git-dirs", str(root), "--repair-worktrees") in (0, 1)
    assert "Vault.git/worktrees" in (wt / ".git").read_text(encoding="utf-8").replace("\\", "/")
    assert git(wt, "rev-parse", "--abbrev-ref", "HEAD") == "claim/x"


def test_pointer_elsewhere_is_refused(tmp_path, root):
    repo = make_repo(tmp_path / "Vault")
    assert run("relocate", str(repo), "--git-dirs", str(tmp_path / "other")) == 0
    assert run("relocate", str(repo), "--git-dirs", str(root)) == gdr.EXIT_REFUSED


def test_missing_root_is_usage_error(tmp_path, monkeypatch):
    monkeypatch.delenv("GIT_DIRS_ROOT", raising=False)
    repo = make_repo(tmp_path / "Vault")
    assert run("relocate", str(repo)) == gdr.EXIT_USAGE


def test_root_from_environment(tmp_path, root, monkeypatch):
    monkeypatch.setenv("GIT_DIRS_ROOT", str(root))
    repo = make_repo(tmp_path / "Vault")
    assert run("relocate", str(repo)) == 0
    assert (root / "Vault.git").is_dir()


def test_init_creates_external_database(tmp_path, root):
    path = tmp_path / "NewVault"
    assert run("init", str(path), "--git-dirs", str(root), "--initial-branch", "main") == 0
    assert (path / ".git").is_file() and (root / "NewVault.git" / "HEAD").is_file()
    assert git(path, "symbolic-ref", "--short", "HEAD") == "main"


def test_init_refuses_existing_repo(tmp_path, root):
    repo = make_repo(tmp_path / "Vault")
    assert run("init", str(repo), "--git-dirs", str(root)) == gdr.EXIT_REFUSED


def test_clean_and_status(tmp_path, root, capsys):
    repo = make_repo(tmp_path / "Vault")
    assert run("relocate", str(repo), "--git-dirs", str(root)) == 0
    litter(root / "Vault.git")
    assert run("status", str(repo)) == 0          # relocated: litter is reported, not a warning state
    assert "marker file" in capsys.readouterr().out
    assert run("clean", str(repo)) == 0
    assert not list((root / "Vault.git").rglob("desktop.ini"))


def test_status_flags_in_tree_litter(tmp_path):
    repo = make_repo(tmp_path / "Vault")
    litter(repo / ".git")
    assert run("status", str(repo)) == gdr.EXIT_WARN


def test_sync_workflow_warning(tmp_path, root, capsys):
    repo = make_repo(tmp_path / "Vault")
    wf = repo / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "sync.yml").write_text("run: rclone sync . remote: --exclude '.git/**'\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "wf")
    assert run("relocate", str(repo), "--git-dirs", str(root)) == gdr.EXIT_WARN
    assert "bare '.git' file" in capsys.readouterr().out


# ---------------------------------------------------------------- review fixes (2026-09-16)

def test_refuses_git_junction_or_symlink(tmp_path, root):
    repo = make_repo(tmp_path / "Vault")
    real = tmp_path / "realdb"
    (repo / ".git").rename(real)
    if os.name == "nt":
        r = subprocess.run(["cmd", "/c", "mklink", "/J", str(repo / ".git"), str(real)], capture_output=True)
        if r.returncode != 0:
            pytest.skip("cannot create junction")
    else:
        os.symlink(real, repo / ".git")
    assert run("relocate", str(repo), "--git-dirs", str(root), "--repair-worktrees") == gdr.EXIT_REFUSED
    assert real.is_dir() and not root.exists()


def test_refuses_core_worktree(tmp_path, root):
    repo = make_repo(tmp_path / "Vault")
    git(repo, "config", "core.worktree", "..")
    assert run("relocate", str(repo), "--git-dirs", str(root)) == gdr.EXIT_REFUSED
    assert (repo / ".git").is_dir()


def test_refuses_relative_include_path(tmp_path, root):
    repo = make_repo(tmp_path / "Vault")
    git(repo, "config", "include.path", "../shared.gitconfig")
    assert run("relocate", str(repo), "--git-dirs", str(root)) == gdr.EXIT_REFUSED


def test_refuses_root_equal_to_repo(tmp_path):
    repo = make_repo(tmp_path / "Vault")
    assert run("relocate", str(repo), "--git-dirs", str(repo)) == gdr.EXIT_REFUSED
    assert (repo / ".git").is_dir()


@pytest.mark.parametrize("lock", ["index.lock", "config.lock", "refs/heads/main.lock"])
def test_refuses_lock_files(tmp_path, root, lock):
    repo = make_repo(tmp_path / "Vault")
    (repo / ".git" / lock).write_text("", encoding="utf-8")
    assert run("relocate", str(repo), "--git-dirs", str(root)) == gdr.EXIT_REFUSED
    assert (repo / ".git").is_dir() and not root.exists()


def test_refuses_existing_fsck_problems(tmp_path, root):
    repo = make_repo(tmp_path / "Vault")
    (repo / ".git" / "refs" / "heads" / "broken").write_text("0" * 40 + "\n", encoding="utf-8")
    assert run("relocate", str(repo), "--git-dirs", str(root)) == gdr.EXIT_REFUSED
    assert (repo / ".git").is_dir()


def test_unreachable_objects_are_not_pruned(tmp_path, root):
    repo = make_repo(tmp_path / "Vault")
    blob = subprocess.run(["git", "-C", str(repo), "hash-object", "-w", "--stdin"], input="dropped work\n",
                          capture_output=True, text=True, check=True, env=gdr._env()).stdout.strip()
    assert run("relocate", str(repo), "--git-dirs", str(root), "--gc") == 0
    assert git(repo, "cat-file", "-t", blob) == "blob"


def test_config_preserved_exactly(tmp_path, root):
    repo = make_repo(tmp_path / "Vault")
    git(repo, "config", "core.repositoryformatversion", "1")
    git(repo, "config", "extensions.worktreeConfig", "true")
    git(repo, "config", "core.filemode", "true")
    before = (repo / ".git" / "config").read_bytes()
    assert run("relocate", str(repo), "--git-dirs", str(root)) == 0
    assert (root / "Vault.git" / "config").read_bytes() == before


def test_real_ref_named_like_litter_is_kept(tmp_path, root):
    repo = make_repo(tmp_path / "Vault")
    git(repo, "branch", "desktop.ini")
    assert run("relocate", str(repo), "--git-dirs", str(root)) == 0
    assert git(repo, "rev-parse", "--verify", "refs/heads/desktop.ini") == git(repo, "rev-parse", "HEAD")


def test_crash_has_its_own_exit_code(tmp_path, root, monkeypatch):
    repo = make_repo(tmp_path / "Vault")
    monkeypatch.setattr(gdr, "linked_worktrees", lambda r: (_ for _ in ()).throw(ValueError("boom")))
    assert run("relocate", str(repo), "--git-dirs", str(root)) == gdr.EXIT_CRASH


def test_root_that_is_a_file_is_usage_error(tmp_path):
    repo = make_repo(tmp_path / "Vault")
    f = tmp_path / "notadir"
    f.write_text("x", encoding="utf-8")
    assert run("relocate", str(repo), "--git-dirs", str(f)) == gdr.EXIT_USAGE


def test_commented_git_exclude_does_not_hide_warning(tmp_path, root, capsys):
    repo = make_repo(tmp_path / "Vault")
    wf = repo / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "sync.yml").write_text("# excludes .git too\nrun: rclone sync . r: --exclude '.git/**'\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "wf")
    assert run("relocate", str(repo), "--git-dirs", str(root)) == gdr.EXIT_WARN


def test_workflow_excluding_both_has_no_warning(tmp_path, root):
    repo = make_repo(tmp_path / "Vault")
    wf = repo / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "sync.yml").write_text("run: rclone sync . r: --exclude '.git/**' --exclude '.git'\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "wf")
    assert run("relocate", str(repo), "--git-dirs", str(root)) == 0


@pytest.mark.skipif(os.name != "nt", reason="Git Bash paths are a Windows concern")
def test_git_bash_style_root_path(tmp_path):
    repo = make_repo(tmp_path / "Vault")
    root = tmp_path / "gd"
    bash = "/" + root.drive[0].lower() + root.as_posix()[2:]
    assert run("relocate", str(repo), "--git-dirs", bash) == 0
    assert (root / "Vault.git").is_dir()
