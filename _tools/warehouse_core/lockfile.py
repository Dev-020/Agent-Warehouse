""".warehouse.lock load/save/journal (DESIGN §2.4, D3)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .errors import UsageError
from .fsops import WriteGuard, atomic_write
from .manifest import LOCK_NAME
from .semver import Version

LOCK_VERSION = 1


@dataclass
class LockItem:
    version: str = ""
    pin: str | None = None
    source: str = "manifest"
    required_by: list[str] = field(default_factory=list)
    settings_digest: str = ""
    synced: str = ""
    state: str = "ok"
    files: dict[str, str] = field(default_factory=dict)
    promoted: dict | None = None
    pending: dict | None = None

    @property
    def ver(self) -> Version | None:
        return Version.try_parse(self.version) if self.version else None


@dataclass
class Lock:
    items: dict[str, LockItem] = field(default_factory=dict)
    readme: str | None = None

    def version(self, item_id: str) -> Version | None:
        li = self.items.get(item_id)
        return li.ver if li else None

    def to_bytes(self) -> bytes:
        data = {"lock_version": LOCK_VERSION,
                "items": {k: asdict(v) for k, v in sorted(self.items.items())},
                "readme": self.readme}
        return (json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def load(project_root: Path) -> Lock:
    path = Path(project_root) / LOCK_NAME
    if not path.is_file():
        return Lock()
    try:
        data = json.loads(path.read_bytes().decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        raise UsageError(f"{LOCK_NAME} is not valid JSON: {e}") from None
    if not isinstance(data, dict) or data.get("lock_version") != LOCK_VERSION:
        raise UsageError(f"{LOCK_NAME} has unsupported lock_version {data.get('lock_version') if isinstance(data, dict) else None!r}; "
                         "refusing to overwrite (newer tool?)")
    lock = Lock(readme=data.get("readme"))
    known = set(LockItem.__dataclass_fields__)
    for k, v in (data.get("items") or {}).items():
        lock.items[k] = LockItem(**{f: val for f, val in v.items() if f in known})
    return lock


def save(project_root: Path, lock: Lock, guard: WriteGuard) -> bool:
    """Write only when bytes differ. Returns True if written."""
    path = Path(project_root) / LOCK_NAME
    data = lock.to_bytes()
    if path.is_file() and path.read_bytes() == data:
        return False
    if not path.is_file() and not lock.items and lock.readme is None:
        return False
    atomic_write(guard, path, data)
    return True
