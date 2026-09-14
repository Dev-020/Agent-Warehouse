""".warehouse.yml load/validate and comment-preserving text edits (DESIGN §2.3)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .errors import UsageError
from .semver import Pin

MANIFEST_NAME = ".warehouse.yml"
LOCK_NAME = ".warehouse.lock"
ENTRY_RE = re.compile(r"^(?P<id>(architecture|protocol|convention|skill|tool)/[a-z0-9][a-z0-9-]*)"
                      r"(?:@(?P<pin>(?:0|[1-9]\d*)(?:\.(?:0|[1-9]\d*)){0,2}))?$")
TOP_KEYS = {"auto_sync", "target", "items", "settings"}


@dataclass
class ManifestEntry:
    id: str
    pin: Pin | None
    line_no: int


@dataclass
class Manifest:
    path: Path
    auto_sync: bool = True
    target: str = "warehouse"
    entries: list[ManifestEntry] = field(default_factory=list)
    settings: dict[str, str] = field(default_factory=dict)
    raw: str = ""

    @property
    def root(self) -> Path:
        return self.path.parent

    def entry(self, item_id: str) -> ManifestEntry | None:
        for e in self.entries:
            if e.id == item_id:
                return e
        return None

    @property
    def target_display(self) -> str:
        return self.target + "/"


def _err(msg: str) -> UsageError:
    return UsageError(f"manifest-invalid: {msg}")


def normalize_target(raw) -> str:
    if not isinstance(raw, str):
        raise _err("target must be a string")
    t = raw.replace("\\", "/").strip()
    if t.startswith("/") or re.match(r"^[A-Za-z]:", t):
        raise _err(f"target {raw!r} must be relative")
    parts = [p for p in t.split("/") if p not in ("", ".")]
    if not parts:
        raise _err(f"target {raw!r} must not be empty or '.'")
    for p in parts:
        if p == "..":
            raise _err(f"target {raw!r} must not contain '..'")
        if p.lower() in (MANIFEST_NAME, LOCK_NAME):
            raise _err(f"target {raw!r} must not name {p}")
    if parts[0].lower() == ".git":
        raise _err(f"target {raw!r} must not be inside .git")
    return "/".join(parts)


def _entry_lines(lines: list[str]) -> dict[str, int]:
    out = {}
    in_items = False
    for i, line in enumerate(lines):
        if re.match(r"^items:", line):
            in_items = True
            continue
        if in_items:
            m = re.match(r"^\s+-\s+['\"]?([^'\"\s#]+)", line)
            if m:
                out.setdefault(m.group(1).split("@")[0], i + 1)
            elif line.strip() and not line.lstrip().startswith("#") and not line[:1].isspace():
                in_items = False
    return out


def load_text(text: str, path: Path) -> Manifest:
    text = text.replace("\r\n", "\n")
    try:
        data = yaml.safe_load(text) if text.strip() else {}
    except yaml.YAMLError as e:
        raise _err(f"not valid YAML: {e}") from None
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise _err("must be a mapping")
    unknown = set(data) - TOP_KEYS
    if unknown:
        raise _err(f"unknown key '{sorted(unknown)[0]}'")
    m = Manifest(path=Path(path), raw=text)
    if "auto_sync" in data:
        if not isinstance(data["auto_sync"], bool):
            raise _err("auto_sync must be true or false")
        m.auto_sync = data["auto_sync"]
    if "target" in data:
        m.target = normalize_target(data["target"])
    raw_items = data.get("items")
    if raw_items is None:
        raw_items = []
    if not isinstance(raw_items, list):
        raise _err("items must be a list")
    lines = _entry_lines(text.split("\n"))
    seen = set()
    for it in raw_items:
        if not isinstance(it, str):
            raise _err(f"item {it!r} must be a string")
        if it.startswith("template/"):
            raise _err(f"{it}: templates are not synced; use `warehouse template`")
        mm = ENTRY_RE.match(it)
        if not mm:
            raise _err(f"invalid item entry {it!r}")
        pin = Pin.parse(mm.group("pin")) if mm.group("pin") is not None else None
        if mm.group("id") in seen:
            raise _err(f"duplicate item {mm.group('id')}")
        seen.add(mm.group("id"))
        m.entries.append(ManifestEntry(mm.group("id"), pin, lines.get(mm.group("id"), 0)))
    raw_settings = data.get("settings")
    if raw_settings is None:
        raw_settings = {}
    if not isinstance(raw_settings, dict):
        raise _err("settings must be a mapping")
    for k, v in raw_settings.items():
        if not isinstance(k, str):
            raise _err(f"setting name {k!r} must be a string")
        if isinstance(v, bool) or not isinstance(v, (str, int, float)):
            raise _err(f"setting {k}: value must be a string or number")
        if "\n" in str(v):
            raise _err(f"setting {k}: value must be a single line")
        m.settings[k] = str(v)
    return m


def load(project_root: Path) -> Manifest:
    path = Path(project_root) / MANIFEST_NAME
    if not path.is_file():
        raise UsageError(f"no {MANIFEST_NAME} in {project_root}")
    return load_text(path.read_bytes().decode("utf-8"), path)


def find_project_root(start: Path) -> Path:
    start = Path(start).resolve()
    for p in [start, *start.parents]:
        if (p / MANIFEST_NAME).is_file():
            return p
    raise UsageError(f"no {MANIFEST_NAME} found from {start} upward")


# --------------------------------------------------------------------------- text edits

def _split(text: str) -> list[str]:
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def _join(lines: list[str]) -> str:
    return "\n".join(lines) + "\n"


def _items_block(lines: list[str]) -> tuple[int | None, list[int]]:
    idx = None
    for i, line in enumerate(lines):
        if re.match(r"^items\s*:", line):
            idx = i
            break
    if idx is None:
        return None, []
    rest = lines[idx][lines[idx].index(":") + 1:].split("#")[0].strip()
    if rest:
        raise UsageError("items uses flow style; edit .warehouse.yml by hand")
    entries = []
    for j in range(idx + 1, len(lines)):
        line = lines[j]
        if re.match(r"^\s+-\s+", line):
            entries.append(j)
        elif not line.strip() or re.match(r"^\s+#", line):
            continue
        else:
            break
    return idx, entries


def _entry_id(line: str) -> str:
    m = re.match(r"^\s+-\s+['\"]?([^'\"\s#]+)", line)
    return m.group(1).split("@")[0] if m else ""


def _validated(new_text: str, m: Manifest) -> str:
    load_text(new_text, m.path)
    return new_text


def add_or_replace_entry(m: Manifest, item_id: str, pin: Pin | None) -> str:
    entry = item_id if pin is None else f"{item_id}@{pin.text}"
    lines = _split(m.raw)
    idx, entries = _items_block(lines)
    if idx is None:
        lines += ["items:", f"  - {entry}"]
        return _validated(_join(lines), m)
    for j in entries:
        if _entry_id(lines[j]) == item_id:
            mm = re.match(r"^(\s+-\s+)(['\"]?)([^'\"\s#]+)(['\"]?)(.*)$", lines[j])
            lines[j] = f"{mm.group(1)}{entry}{mm.group(5)}"
            return _validated(_join(lines), m)
    if entries:
        last = entries[-1]
        indent = re.match(r"^(\s+-\s+)", lines[last]).group(1)
        lines.insert(last + 1, f"{indent}{entry}")
    else:
        lines.insert(idx + 1, f"  - {entry}")
    return _validated(_join(lines), m)


def remove_entry(m: Manifest, item_id: str) -> str:
    lines = _split(m.raw)
    idx, entries = _items_block(lines)
    for j in entries:
        if _entry_id(lines[j]) == item_id:
            del lines[j]
            return _validated(_join(lines), m)
    raise UsageError(f"{item_id} is not in .warehouse.yml")


def ensure_settings_keys(m: Manifest, names_with_desc: dict[str, str]) -> str:
    missing = {n: d for n, d in names_with_desc.items() if n not in m.settings}
    if not missing:
        return m.raw
    lines = _split(m.raw)
    idx = None
    for i, line in enumerate(lines):
        if re.match(r"^settings\s*:", line):
            idx = i
            break
    new = [f'  {n}: ""  # {" ".join(str(d).split())}' for n, d in sorted(missing.items())]
    if idx is None:
        lines += ["settings:", *new]
    else:
        rest = lines[idx][lines[idx].index(":") + 1:].split("#")[0].strip()
        if rest in ("{}",):
            lines[idx] = "settings:"
        elif rest:
            raise UsageError("settings uses flow style; edit .warehouse.yml by hand")
        last = idx
        for j in range(idx + 1, len(lines)):
            if lines[j][:1].isspace() and lines[j].strip():
                last = j
            elif not lines[j].strip():
                continue
            else:
                break
        lines[last + 1:last + 1] = new
    return _validated(_join(lines), m)
