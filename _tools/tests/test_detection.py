"""Tests for shared project-type detection and profile applies-to warnings (WH-9)."""
from pathlib import Path
import pytest

from warehouse_core.discovery import (
    CODEBASE_MARKERS,
    CODEBASE_GLOBS,
    VAULT_MARKERS,
    detect_project_types,
)
from warehouse_core.profiles import Profile, save_profile


@pytest.mark.parametrize("marker", [
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "setup.py",
    "go.mod",
    "Cargo.toml",
    "pom.xml",
    "tsconfig.json",
    "deno.json",
    "index.html",
    "composer.json",
    "Gemfile",
    "build.gradle",
    "app.csproj",
    "app.sln",
])
def test_detect_project_types_codebase_markers(tmp_path, marker):
    (tmp_path / marker).touch()
    assert detect_project_types(tmp_path) == {"codebase"}


def test_detect_project_types_vault_marker(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    assert detect_project_types(tmp_path) == {"vault"}


def test_detect_project_types_empty(tmp_path):
    assert detect_project_types(tmp_path) == set()


def test_detect_project_types_both(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "package.json").touch()
    assert detect_project_types(tmp_path) == {"vault", "codebase"}


def _make_starter_profile(wh):
    save_profile(wh.root, Profile(
        name="starter",
        description="Starter profile",
        tier=0,
        applies_to=["vault", "codebase"],
        items=[],
    ))


def test_bootstrap_tsconfig_and_index_html_no_marker_warning(wh):
    _make_starter_profile(wh)
    p = wh.projects_dir / "ts_html_proj"
    p.mkdir()
    (p / "tsconfig.json").touch()
    (p / "index.html").touch()
    code, out = wh.run("bootstrap", project=p)
    assert code == 0
    assert "no vault or codebase markers found" not in out
    assert "auto_sync: true" in out


def test_bootstrap_empty_folder_d4_fallback(wh):
    _make_starter_profile(wh)
    p = wh.projects_dir / "empty_proj"
    p.mkdir()
    code, out = wh.run("bootstrap", project=p)
    assert code == 0
    assert "warehouse bootstrap: no vault or codebase markers found; assuming codebase" in out
    assert "auto_sync: true" in out


def test_bootstrap_vault_profile_in_codebase_warns(wh):
    save_profile(wh.root, Profile(
        name="academic",
        description="Academic notes",
        tier=1,
        applies_to=["vault"],
        items=[],
    ))
    p = wh.projects_dir / "codebase_proj"
    p.mkdir()
    (p / "package.json").touch()
    code, out = wh.run("bootstrap", "--profile", "academic", project=p)
    assert code == 0
    assert "warehouse bootstrap: profile 'academic' applies to [vault]; this project looks like [codebase]" in out
    assert "auto_sync: true" in out


def test_bootstrap_empty_folder_vault_profile_no_mismatch_warning(wh):
    save_profile(wh.root, Profile(
        name="academic",
        description="Academic notes",
        tier=1,
        applies_to=["vault"],
        items=[],
    ))
    p = wh.projects_dir / "empty_vault_proj"
    p.mkdir()
    code, out = wh.run("bootstrap", "--profile", "academic", project=p)
    assert code == 0
    assert "warehouse bootstrap: no vault or codebase markers found; assuming codebase" in out
    assert "applies to" not in out
    assert "auto_sync: true" in out


def test_profile_apply_mismatch_warns(wh):
    save_profile(wh.root, Profile(
        name="academic",
        description="Academic notes",
        tier=1,
        applies_to=["vault"],
        items=[],
    ))
    p = wh.project("codebase_apply", "auto_sync: true\ntarget: warehouse/\nitems: []\n")
    (p / "package.json").touch()
    code, out = wh.run("profile", "apply", "academic", project=p)
    assert code == 0
    assert "warehouse profile apply: profile 'academic' applies to [vault]; this project looks like [codebase]" in out
