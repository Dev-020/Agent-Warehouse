"""Placeholder substitution and synced-copy header (DESIGN §2.6, D4)."""
from __future__ import annotations

import fnmatch
import hashlib
import json
import re
from dataclasses import dataclass, field

from . import frontmatter, items
from .errors import UsageError

PLACEHOLDER_RE = re.compile(r"\{\{([a-z][a-z0-9_]*)\}\}")
HEADER_RE = re.compile(r"\n> \[!info\] Warehouse item — (\S+) v(\d+\.\d+\.\d+) \(synced \d{4}-\d{2}-\d{2}\)\n"
                       r"> Maintained in the AI warehouse\.[^\n]*\n")
_STAMP_RE = re.compile(rb"\(synced \d{4}-\d{2}-\d{2}\)")


@dataclass
class RenderResult:
    files: dict[str, bytes] = field(default_factory=dict)
    unfilled: list[str] = field(default_factory=list)


def sha256(b: bytes) -> str:
    return "sha256:" + hashlib.sha256(b).hexdigest()


def header_text(item_id: str, version, today: str) -> str:
    return (f"\n> [!info] Warehouse item — {item_id} v{version} (synced {today})\n"
            f"> Maintained in the AI warehouse. Edit it there, or run `warehouse promote {item_id}` "
            f"to send a change upstream.\n")


def insert_header(text: str, item_id: str, version, today: str) -> str:
    off = frontmatter.end_offset(text)
    if off is None:
        raise UsageError(f"{item_id}: main file has no frontmatter")
    return text[:off] + header_text(item_id, version, today) + text[off:]


def strip_header(text: str) -> str:
    return HEADER_RE.sub("", text, count=1)


def normalize_stamp(b: bytes) -> bytes:
    return _STAMP_RE.sub(b"(synced -)", b)


def effective_settings(meta: items.ItemMeta, manifest_settings: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """Project value if set and non-empty, else the item's default, else unfilled (User decision 1)."""
    values, missing = {}, []
    for name, spec in meta.settings.items():
        v = manifest_settings.get(name)
        if v is not None and str(v) != "":
            values[name] = str(v)
        elif spec.has_default:
            values[name] = spec.default
        else:
            missing.append(name)
    return values, sorted(missing)


def settings_digest(values: dict[str, str]) -> str:
    return sha256(json.dumps({k: str(v) for k, v in values.items()}, sort_keys=True).encode("utf-8"))


def is_excluded(rel: str, patterns: list[str], item_id: str) -> bool:
    pats = list(patterns)
    if items.kind_of(item_id) == "tool" and "tests/**" not in pats:
        pats.append("tests/**")
    for p in pats:
        if fnmatch.fnmatchcase(rel, p):
            return True
        if p.startswith("**/") and fnmatch.fnmatchcase(rel, p[3:]):
            return True
        if rel.split("/")[-1].lower() == "desktop.ini" and p.endswith("desktop.ini"):
            return True
    return False


def render_release(meta: items.ItemMeta, files: dict[str, bytes], settings: dict[str, str], today: str,
                   *, exclude: list[str]) -> RenderResult:
    values, missing = effective_settings(meta, settings)
    res = RenderResult(unfilled=missing)
    main_name = items.main_file_name(meta.id)
    for rel, data in sorted(files.items()):
        if is_excluded(rel, exclude, meta.id):
            continue
        if rel.endswith(".md"):
            try:
                text = data.decode("utf-8").replace("\r\n", "\n")
            except UnicodeDecodeError:
                raise UsageError(f"{meta.id} {meta.version}: {rel} is not valid UTF-8; item not synced") from None
            text = PLACEHOLDER_RE.sub(lambda m: values[m.group(1)] if m.group(1) in values else m.group(0), text)
            if rel == main_name:
                text = insert_header(text, meta.id, meta.version, today)
            data = text.encode("utf-8")
        res.files[items.target_file_path(meta.id, rel)] = data
    return res
