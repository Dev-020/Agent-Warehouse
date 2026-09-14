"""Released versions from annotated tags (D1, invariant I7)."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from . import items
from .errors import GitError, UsageError
from .gitrepo import Git
from .semver import Pin, Version

TAG_RE = re.compile(r"^refs/tags/(?P<id>(architecture|protocol|convention|template|skill|tool)/[a-z0-9][a-z0-9-]*)"
                    r"@(?P<v>(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*))$")


@dataclass
class Release:
    id: str
    version: Version
    tag: str
    commit: str
    date: str


class Catalog:
    def __init__(self, git: Git):
        self.git = git
        self._tags = git.tags()
        self._raw: dict[str, dict[Version, object]] = {}
        self.malformed: list[str] = []      # refs that are not <id>@<version> annotated tags
        self.invalid: dict[tuple[str, Version], str] = {}
        self._files: dict[tuple[str, Version], dict[str, bytes]] = {}
        self._meta: dict[tuple[str, Version], items.ItemMeta] = {}
        for t in self._tags:
            m = TAG_RE.match(t.refname)
            if not m or t.objecttype != "tag":
                self.malformed.append(t.refname + (" (lightweight tag)" if m else ""))
                continue
            self._raw.setdefault(m.group("id"), {})[Version.parse(m.group("v"))] = t

    def _valid(self, item_id: str, v: Version) -> bool:
        try:
            self.meta(item_id, v)
            return True
        except (UsageError, GitError, UnicodeDecodeError) as e:
            self.invalid[(item_id, v)] = str(e)
            return False

    def versions(self, item_id: str) -> list[Version]:
        return sorted(v for v in self._raw.get(item_id, {}) if (item_id, v) not in self.invalid
                      and self._valid(item_id, v))

    def has_tag(self, item_id: str, v: Version) -> bool:
        return v in self.versions(item_id)

    def latest(self, item_id: str, pin: Pin | None = None) -> Version | None:
        vs = [v for v in self.versions(item_id) if pin is None or pin.matches(v)]
        return vs[-1] if vs else None

    def tag_name(self, item_id: str, v: Version) -> str:
        return f"{item_id}@{v}"

    def release(self, item_id: str, v: Version) -> Release:
        t = self._raw.get(item_id, {}).get(v)
        if t is None:
            raise GitError(f"missing-tag: {item_id}@{v} does not exist")
        return Release(item_id, v, t.refname, t.objectname, t.date)

    def files(self, item_id: str, v: Version) -> dict[str, bytes]:
        key = (item_id, v)
        if key not in self._files:
            if v not in self._raw.get(item_id, {}):
                raise GitError(f"missing-tag: {item_id}@{v} does not exist")
            rel = items.item_rel_path(item_id)
            ref = f"refs/tags/{item_id}@{v}"
            out = {}
            for path, oid in self.git.tree_files(ref, rel):
                if items.is_document(item_id):
                    if path != rel:
                        continue
                    key_name = path.rsplit("/", 1)[-1]
                else:
                    if not path.startswith(rel + "/"):
                        continue
                    key_name = path[len(rel) + 1:]
                out[key_name] = self.git.blob(oid)
            self._files[key] = out
        return self._files[key]

    def meta(self, item_id: str, v: Version) -> items.ItemMeta:
        key = (item_id, v)
        if key not in self._meta:
            files = self.files(item_id, v)
            main = files.get(items.main_file_name(item_id))
            if main is None:
                raise UsageError(f"tag {item_id}@{v} has no {items.main_file_name(item_id)}")
            meta = items.parse_meta(main, expected_id=item_id)
            if meta.version != v:
                raise UsageError(f"tag {item_id}@{v} contains version {meta.version}")
            self._meta[key] = meta
        return self._meta[key]

    def changelog_text(self, item_id: str, v: Version) -> str:
        return items.normalize_text(self.files(item_id, v)[items.changelog_name(item_id)])

    def all_ids(self) -> list[str]:
        return sorted(i for i in self._raw if self.versions(i))

    def all_releases(self) -> list[Release]:
        out = []
        for iid, vs in self._raw.items():
            for v, t in vs.items():
                out.append(Release(iid, v, t.refname, t.objectname, t.date))
        return out

    def successor(self, item_id: str) -> str | None:
        for other in self.all_ids():
            latest = self.latest(other)
            if latest is not None and self.meta(other, latest).replaces == item_id:
                return other
        return None

    def tags_digest(self) -> str:
        data = "".join(sorted(f"{t.refname} {t.objectname}\n" for t in self._tags))
        return "sha256:" + hashlib.sha256(data.encode()).hexdigest()
