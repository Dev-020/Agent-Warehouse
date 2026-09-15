"""Tests for warehouse profiles (loadouts) management and CLI commands."""
import json
from pathlib import Path
import pytest

from warehouse_core import profiles
from warehouse_core.profiles import Profile


def test_list_profiles_empty_and_with_files(tmp_path):
    # Empty warehouse root
    assert profiles.list_profiles(tmp_path) == []

    # Save profiles with different tiers and names
    p1 = Profile(
        name="standard",
        description="Standard operational workflow (Tier 1)",
        tier=1,
        applies_to=["vault", "codebase"],
        items=["protocol/agent-protocol@0.1", "convention/commits@0.1"],
        settings={},
    )
    p2 = Profile(
        name="starter",
        description="Minimal viable operating posture (Tier 0)",
        tier=0,
        applies_to=["vault", "codebase"],
        items=["protocol/agent-protocol@0.1"],
        settings={"key": "val"},
    )
    p3 = Profile(
        name="academic",
        description="Academic notes (Tier 3)",
        tier=3,
        applies_to=["vault"],
        items=["tool/tex-compile@0.1"],
        settings={},
    )
    profiles.save_profile(tmp_path, p1)
    profiles.save_profile(tmp_path, p2)
    profiles.save_profile(tmp_path, p3)

    listed = profiles.list_profiles(tmp_path)
    assert len(listed) == 3
    # Verify sorting by tier, then name: starter (0) -> standard (1) -> academic (3)
    assert [p.name for p in listed] == ["starter", "standard", "academic"]
    assert listed[0].tier == 0
    assert listed[0].settings == {"key": "val"}
    assert listed[1].tier == 1
    assert listed[2].tier == 3


def test_save_and_get_roundtrip(tmp_path):
    p = Profile(
        name="custom",
        description="Custom profile for testing",
        tier=2,
        applies_to=["codebase"],
        items=["tool/backlog-cli@0.1", "skill/backlog-governance@0.1"],
        settings={"backlog_file": "TODO.md"},
    )
    path = profiles.save_profile(tmp_path, p)
    assert path.is_file()
    assert path.name == "custom.yml"

    loaded = profiles.get_profile(tmp_path, "custom")
    assert loaded is not None
    assert loaded.name == "custom"
    assert loaded.description == "Custom profile for testing"
    assert loaded.tier == 2
    assert loaded.applies_to == ["codebase"]
    assert loaded.items == ["tool/backlog-cli@0.1", "skill/backlog-governance@0.1"]
    assert loaded.settings == {"backlog_file": "TODO.md"}

    # Also test get with .yml extension
    loaded_ext = profiles.get_profile(tmp_path, "custom.yml")
    assert loaded_ext is not None
    assert loaded_ext.name == "custom"

    # Non-existent profile
    assert profiles.get_profile(tmp_path, "nonexistent") is None


def test_delete_profile(tmp_path):
    p = Profile(name="temporary", description="Temporary", tier=0, applies_to=[], items=[])
    profiles.save_profile(tmp_path, p)
    assert (tmp_path / "profiles" / "temporary.yml").is_file()

    # Delete existing
    deleted = profiles.delete_profile(tmp_path, "temporary")
    assert deleted is True
    assert not (tmp_path / "profiles" / "temporary.yml").exists()

    # Delete again (not found)
    deleted_again = profiles.delete_profile(tmp_path, "temporary")
    assert deleted_again is False


def test_cli_profile_list(wh):
    # Empty
    code, out = wh.run("profile", "list")
    assert code == 0
    assert "No profiles found" in out

    # Add profiles
    profiles.save_profile(wh.root, Profile(
        name="starter",
        description="Minimal posture",
        tier=0,
        applies_to=["vault", "codebase"],
        items=["protocol/agent-protocol@0.1"],
    ))
    profiles.save_profile(wh.root, Profile(
        name="standard",
        description="Standard posture",
        tier=1,
        applies_to=["codebase"],
        items=["protocol/agent-protocol@0.1", "protocol/safe-write@0.1"],
    ))

    code, out = wh.run("profile", "list")
    assert code == 0
    assert "starter" in out
    assert "standard" in out
    assert "Minimal posture" in out
    assert "Name" in out
    assert "Tier" in out

    # --json output
    code, out = wh.run("profile", "list", "--json")
    assert code == 0
    data = json.loads(out)
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["name"] == "starter"
    assert data[0]["tier"] == 0
    assert data[1]["name"] == "standard"
    assert data[1]["tier"] == 1


def test_cli_profile_show(wh):
    profiles.save_profile(wh.root, Profile(
        name="starter",
        description="Minimal viable posture",
        tier=0,
        applies_to=["vault", "codebase"],
        items=["protocol/agent-protocol@0.1", "protocol/working-memory@0.1"],
        settings={"opt": "val"},
    ))

    # Text output
    code, out = wh.run("profile", "show", "starter")
    assert code == 0
    assert "Name: starter" in out
    assert "Tier: 0" in out
    assert "Applies-to: vault, codebase" in out
    assert "Description: Minimal viable posture" in out
    assert "protocol/agent-protocol@0.1" in out
    assert "protocol/working-memory@0.1" in out
    assert "opt: val" in out

    # --json output
    code, out = wh.run("profile", "show", "starter", "--json")
    assert code == 0
    data = json.loads(out)
    assert data["name"] == "starter"
    assert data["tier"] == 0
    assert data["settings"] == {"opt": "val"}
    assert len(data["items"]) == 2

    # Unknown profile errors cleanly
    code, out = wh.run("profile", "show", "unknown")
    assert code == 2
    assert "profile 'unknown' not found" in out


def test_cli_profile_save_and_delete(wh):
    # Save with explicit CLI flags
    code, out = wh.run(
        "profile", "save", "data-science",
        "--description", "Data science profile",
        "--tier", "1",
        "--items", "protocol/agent-protocol@0.1,protocol/safe-write@0.1",
        "--applies-to", "codebase",
    )
    assert code == 0
    assert "Saved profile data-science" in out

    prof = profiles.get_profile(wh.root, "data-science")
    assert prof is not None
    assert prof.description == "Data science profile"
    assert prof.tier == 1
    assert prof.applies_to == ["codebase"]
    assert prof.items == ["protocol/agent-protocol@0.1", "protocol/safe-write@0.1"]

    # Save from manifest
    p = wh.project("sample", "items:\n  - convention/commits@0.1\n  - convention/backlog@0.1\nsettings:\n  backlog_file: \"TODO.md\"\n")
    code, out = wh.run("profile", "save", "from-proj", "--from-manifest", "--tier", "2", project=p)
    assert code == 0
    assert "Saved profile from-proj" in out

    prof_from_m = profiles.get_profile(wh.root, "from-proj")
    assert prof_from_m is not None
    assert prof_from_m.tier == 2
    assert prof_from_m.items == ["convention/commits@0.1", "convention/backlog@0.1"]
    assert prof_from_m.settings == {"backlog_file": "TODO.md"}

    # Delete without --yes in non-interactive environment fails
    code, out = wh.run("profile", "delete", "data-science")
    assert code == 2
    assert "use --yes" in out
    assert (wh.root / "profiles" / "data-science.yml").exists()

    # Delete with --yes succeeds
    code, out = wh.run("profile", "delete", "data-science", "--yes")
    assert code == 0
    assert "Deleted profile data-science" in out
    assert not (wh.root / "profiles" / "data-science.yml").exists()

    # Delete nonexistent profile
    code, out = wh.run("profile", "delete", "data-science", "--yes")
    assert code == 2
    assert "profile 'data-science' not found" in out


def test_cli_profile_apply(wh):
    profiles.save_profile(wh.root, Profile(
        name="standard",
        description="Standard operational workflow",
        tier=1,
        applies_to=["vault", "codebase"],
        items=["protocol/agent-protocol@0.1", "convention/commits@0.1", "convention/backlog@0.1"],
        settings={"backlog_file": "BACKLOG.md"},
    ))

    # Existing project with only 1 item
    p = wh.project("myproj", "auto_sync: true\ntarget: warehouse/\nitems:\n  - protocol/agent-protocol@0.1\n")
    code, out = wh.run("profile", "apply", "standard", project=p)
    assert code == 0
    assert "Applied profile 'standard'" in out
    assert "convention/commits@0.1" in out
    assert "convention/backlog@0.1" in out

    m_text = (p / ".warehouse.yml").read_text(encoding="utf-8")
    assert "convention/commits@0.1" in m_text
    assert "convention/backlog@0.1" in m_text
    assert "backlog_file: \"BACKLOG.md\"" in m_text

    # Apply again -> nothing added
    code, out = wh.run("profile", "apply", "standard", project=p)
    assert code == 0
    assert "already present" in out

    # Apply to project without .warehouse.yml fails
    empty_proj = wh.projects_dir / "empty"
    empty_proj.mkdir()
    code, out = wh.run("profile", "apply", "standard", project=empty_proj)
    assert code == 2

    # Apply nonexistent profile fails
    code, out = wh.run("profile", "apply", "unknown", project=p)
    assert code == 2
    assert "profile 'unknown' not found" in out


def test_cli_bootstrap_with_profile(wh):
    profiles.save_profile(wh.root, Profile(
        name="starter",
        description="Minimal posture",
        tier=0,
        applies_to=["vault", "codebase"],
        items=["protocol/agent-protocol@0.1", "protocol/working-memory@0.1"],
        settings={},
    ))

    p = wh.projects_dir / "fresh"
    p.mkdir()
    (p / "package.json").touch()

    # Default bootstrap uses starter profile
    code, out = wh.run("bootstrap", project=p)
    assert code == 0
    assert "auto_sync: true" in out
    assert "target: warehouse/" in out
    assert "protocol/agent-protocol@0.1" in out
    assert "protocol/working-memory@0.1" in out

    # Bootstrap with explicit --profile starter and --write
    code, out = wh.run("bootstrap", "--profile", "starter", "--write", project=p)
    assert code == 0
    manifest_path = p / ".warehouse.yml"
    assert manifest_path.exists()
    content = manifest_path.read_text(encoding="utf-8")
    assert "protocol/agent-protocol@0.1" in content
    assert "protocol/working-memory@0.1" in content

    # Bootstrap with unknown profile errors cleanly
    p2 = wh.projects_dir / "fresh2"
    p2.mkdir()
    (p2 / "package.json").touch()
    code, out = wh.run("bootstrap", "--profile", "nonexistent", project=p2)
    assert code == 2
    assert "profile 'nonexistent' not found" in out
