"""Profiles (loadouts) management: list, get, save, delete (Progressive Context Disclosure)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
import yaml

from .errors import UsageError


@dataclass
class Profile:
    name: str
    description: str = ""
    tier: int = 0
    applies_to: list[str] = field(default_factory=list)
    items: list[str] = field(default_factory=list)
    settings: dict[str, str] = field(default_factory=dict)
    path: Path | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "tier": self.tier,
            "applies_to": self.applies_to,
            "items": self.items,
            "settings": self.settings,
        }


def _clean_name(name: str) -> str:
    clean = name[:-4] if name.endswith(".yml") else name
    if clean.endswith(".yaml"):
        clean = clean[:-5]
    if not clean or Path(clean).name != clean or "/" in clean or "\\" in clean:
        raise UsageError(f"invalid profile name: {name!r}")
    return clean


def load_profile_file(path: Path) -> tuple[Profile | None, str | None]:
    """Loads a profile file. Returns (Profile, None) on success, or (None, reason) on failure."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as e:
        return None, str(e)
    if not isinstance(data, dict):
        return None, "not a mapping"

    name = str(data.get("name") or path.stem)
    if name.endswith(".yml"):
        name = name[:-4]
    elif name.endswith(".yaml"):
        name = name[:-5]

    desc = str(data.get("description", "") or "")
    try:
        tier = int(data.get("tier", 0))
    except (ValueError, TypeError):
        tier = 0

    applies_raw = data.get("applies-to")
    if applies_raw is None:
        applies_raw = data.get("applies_to", [])
    if not isinstance(applies_raw, list):
        applies_to = [str(applies_raw)] if applies_raw else []
    else:
        applies_to = [str(x) for x in applies_raw]

    items_raw = data.get("items") or []
    if not isinstance(items_raw, list):
        items_list = [str(items_raw)] if items_raw else []
    else:
        items_list = [str(x) for x in items_raw]

    settings_raw = data.get("settings") or {}
    settings = {}
    if isinstance(settings_raw, dict):
        for k, v in settings_raw.items():
            settings[str(k)] = str(v)

    return Profile(
        name=name,
        description=desc,
        tier=tier,
        applies_to=applies_to,
        items=items_list,
        settings=settings,
        path=path,
    ), None


def _load_profile_file(path: Path) -> Profile | None:
    prof, _ = load_profile_file(path)
    return prof


def list_profiles_for_check(warehouse_root: Path) -> tuple[list[Profile], list[tuple[Path, str]]]:
    """Loads all profiles/*.yml and *.yaml for check.
    Returns (valid_profiles, [(path, error_reason), ...]).
    """
    profiles_dir = Path(warehouse_root) / "profiles"
    if not profiles_dir.is_dir():
        return [], []
    valid: list[Profile] = []
    unreadable: list[tuple[Path, str]] = []
    candidates = sorted(
        [p for p in profiles_dir.iterdir() if p.is_file() and p.name != "README.md" and p.suffix in (".yml", ".yaml")],
        key=lambda p: p.name,
    )
    for p in candidates:
        prof, err = load_profile_file(p)
        if prof is not None:
            valid.append(prof)
        else:
            unreadable.append((p, err or "unknown error"))
    valid.sort(key=lambda x: (x.tier, x.name))
    return valid, unreadable


def list_profiles(warehouse_root: Path) -> list[Profile]:
    """Loads all profiles/*.yml (sorted by tier, then name)."""
    profiles_dir = Path(warehouse_root) / "profiles"
    if not profiles_dir.is_dir():
        return []
    results = []
    for p in sorted(profiles_dir.glob("*.yml")):
        if p.is_file():
            prof = _load_profile_file(p)
            if prof is not None:
                results.append(prof)
    results.sort(key=lambda x: (x.tier, x.name))
    return results


def get_profile(warehouse_root: Path, name: str) -> Profile | None:
    """Retrieves a profile by name."""
    try:
        clean = _clean_name(name)
    except UsageError:
        return None
    path = Path(warehouse_root) / "profiles" / f"{clean}.yml"
    if not path.is_file():
        return None
    return _load_profile_file(path)


def save_profile(warehouse_root: Path, profile: Profile) -> Path:
    """Writes <warehouse>/profiles/<name>.yml."""
    clean = _clean_name(profile.name)
    profiles_dir = Path(warehouse_root) / "profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    target = profiles_dir / f"{clean}.yml"

    data = {
        "name": clean,
        "description": profile.description,
        "tier": profile.tier,
        "applies-to": profile.applies_to,
        "items": profile.items,
        "settings": profile.settings,
    }
    content = yaml.safe_dump(data, sort_keys=False, default_flow_style=False)
    target.write_text(content, encoding="utf-8")
    profile.path = target
    return target


def delete_profile(warehouse_root: Path, name: str) -> bool:
    """Deletes <warehouse>/profiles/<name>.yml. Returns True if deleted, False if not found."""
    try:
        clean = _clean_name(name)
    except UsageError:
        return False
    target = Path(warehouse_root) / "profiles" / f"{clean}.yml"
    if target.is_file():
        target.unlink()
        return True
    return False
