"""Item kinds, id <-> path mapping, metadata, working-tree discovery and lint (DESIGN §2.2)."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import changelog as changelog_mod
from . import frontmatter
from .errors import UsageError
from .semver import Pin, Version

KINDS = {"architecture": "architecture", "protocol": "protocols", "convention": "conventions",
         "template": "templates", "skill": "skills", "tool": "tools"}
KIND_ORDER = list(KINDS)
SYNCED_KINDS = {"architecture", "protocol", "convention", "skill", "tool"}
DOCUMENT_KINDS = {"architecture", "protocol", "convention", "template"}
FOLDER_KINDS = {"skill", "tool"}
ID_RE = re.compile(r"^(architecture|protocol|convention|template|skill|tool)/[a-z0-9][a-z0-9-]*$")
SETTING_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
REQUIRE_RE = re.compile(r"^(?P<id>(architecture|protocol|convention|template|skill|tool)/[a-z0-9][a-z0-9-]*)"
                        r"@(?P<pin>(?:0|[1-9]\d*)(?:\.(?:0|[1-9]\d*)){0,2})$")
REQUIRED_FIELDS = ["id", "version", "status", "summary", "applies-to", "settings", "requires", "replaces"]
TOOL_FIELDS = ["entrypoint", "requires-software", "platforms"]


@dataclass(frozen=True)
class Setting:
    description: str
    default: str | None = None     # None = required (no default)

    @property
    def has_default(self) -> bool:
        return self.default is not None


@dataclass
class ItemMeta:
    id: str
    version: Version
    status: str
    summary: str
    applies_to: list[str]
    settings: dict[str, Setting]
    requires: list[tuple[str, Pin]]
    replaces: str | None
    entrypoint: str | None = None
    requires_software: list[str] = field(default_factory=list)
    platforms: list[str] = field(default_factory=list)


@dataclass
class Problem:
    level: str   # error | warning
    code: str
    msg: str


def kind_of(item_id: str) -> str:
    return item_id.split("/", 1)[0]


def name_of(item_id: str) -> str:
    return item_id.split("/", 1)[1]


def is_document(item_id: str) -> bool:
    return kind_of(item_id) in DOCUMENT_KINDS


def item_rel_path(item_id: str) -> str:
    k, n = kind_of(item_id), name_of(item_id)
    return f"{KINDS[k]}/{n}.md" if k in DOCUMENT_KINDS else f"{KINDS[k]}/{n}"


def main_file_name(item_id: str) -> str:
    """Main file relative to the item folder (documents: the file itself)."""
    k = kind_of(item_id)
    if k in DOCUMENT_KINDS:
        return f"{name_of(item_id)}.md"
    return "SKILL.md" if k == "skill" else "TOOL.md"


def main_file(item_id: str) -> str:
    if is_document(item_id):
        return item_rel_path(item_id)
    return f"{item_rel_path(item_id)}/{main_file_name(item_id)}"


def changelog_file(item_id: str) -> str:
    return main_file(item_id) if is_document(item_id) else f"{item_rel_path(item_id)}/CHANGELOG.md"


def changelog_name(item_id: str) -> str:
    """Changelog file relative to the item folder."""
    return main_file_name(item_id) if is_document(item_id) else "CHANGELOG.md"


def target_rel_path(item_id: str) -> str:
    k, n = kind_of(item_id), name_of(item_id)
    if k in DOCUMENT_KINDS:
        return f"{n}.md"
    return f"{KINDS[k]}/{n}"


def target_file_path(item_id: str, rel_in_item: str) -> str:
    """Target-relative path of a file inside a release (rel_in_item from Catalog.files)."""
    if is_document(item_id):
        return rel_in_item
    return f"{target_rel_path(item_id)}/{rel_in_item}"


def parse_settings(raw) -> dict[str, Setting]:
    """settings: name -> "description" (required) | {description, default} (User decision 1)."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise UsageError("settings must be a mapping name -> description")
    out = {}
    for name, spec in raw.items():
        if not isinstance(name, str) or not SETTING_NAME_RE.match(name):
            raise UsageError(f"invalid setting name {name!r}")
        if isinstance(spec, str):
            out[name] = Setting(spec, None)
        elif isinstance(spec, dict):
            unknown = set(spec) - {"description", "default"}
            if unknown:
                raise UsageError(f"setting {name}: unknown keys {sorted(unknown)}")
            desc = spec.get("description")
            if not isinstance(desc, str):
                raise UsageError(f"setting {name}: description must be a string")
            default = None
            if "default" in spec:
                d = spec["default"]
                if isinstance(d, bool) or not isinstance(d, (str, int, float)) or "\n" in str(d):
                    raise UsageError(f"setting {name}: default must be a single-line string or number")
                default = str(d)
            out[name] = Setting(desc, default)
        else:
            raise UsageError(f"setting {name}: must be a description string or {{description, default}}")
    return out


def _str_list(raw, field_name) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list) or not all(isinstance(x, str) for x in raw):
        raise UsageError(f"{field_name} must be a list of strings")
    return list(raw)


def parse_requires(raw) -> list[tuple[str, Pin]]:
    out = []
    for entry in _str_list(raw, "requires"):
        m = REQUIRE_RE.match(entry)
        if not m:
            raise UsageError(f"invalid requires entry {entry!r}: expected <id>@<pin>")
        out.append((m.group("id"), Pin.parse(m.group("pin"))))
    return out


def meta_from_dict(data: dict, expected_id: str | None = None) -> ItemMeta:
    for f in REQUIRED_FIELDS:
        if f not in data:
            raise UsageError(f"frontmatter field '{f}' missing")
    item_id = data["id"]
    if not isinstance(item_id, str) or not ID_RE.match(item_id):
        raise UsageError(f"invalid id {item_id!r}")
    if expected_id is not None and item_id != expected_id:
        raise UsageError(f"id {item_id!r} does not match expected {expected_id!r}")
    if not isinstance(data["version"], str):
        raise UsageError(f"version {data['version']!r} must be a quoted string")
    version = Version.parse(data["version"])
    replaces = data["replaces"]
    if replaces is not None and not isinstance(replaces, str):
        raise UsageError("replaces must be an id or null")
    return ItemMeta(
        id=item_id, version=version, status=str(data["status"]), summary=str(data["summary"] or ""),
        applies_to=_str_list(data["applies-to"], "applies-to"),
        settings=parse_settings(data["settings"]), requires=parse_requires(data["requires"]),
        replaces=replaces, entrypoint=data.get("entrypoint"),
        requires_software=_str_list(data.get("requires-software"), "requires-software"),
        platforms=_str_list(data.get("platforms"), "platforms"),
    )


def normalize_text(b: bytes | str) -> str:
    if isinstance(b, bytes):
        b = b.decode("utf-8")
    return b.replace("\r\n", "\n")


def parse_meta(text: str, expected_id: str | None = None) -> ItemMeta:
    return meta_from_dict(frontmatter.parse(normalize_text(text)), expected_id)


def discover_working_tree(root: Path) -> dict[str, Path]:
    """id -> main file for every working-tree item (by location). Archive/reference/case-studies are not scanned."""
    root = Path(root)
    out: dict[str, Path] = {}
    for kind, folder in KINDS.items():
        d = root / folder
        if not d.is_dir():
            continue
        for entry in sorted(os.scandir(d), key=lambda e: e.name):
            if kind in DOCUMENT_KINDS:
                if entry.is_file() and entry.name.endswith(".md"):
                    out[f"{kind}/{entry.name[:-3]}"] = Path(entry.path)
            elif entry.is_dir() and not entry.name.startswith("."):
                main = Path(entry.path) / ("SKILL.md" if kind == "skill" else "TOOL.md")
                if main.is_file():
                    out[f"{kind}/{entry.name}"] = main
    return out


# --------------------------------------------------------------------------- lint

_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_PLACEHOLDER_RE = re.compile(r"\{\{([a-z][a-z0-9_]*)\}\}")


def placeholders_outside_code(text: str) -> set[str]:
    names = set()
    in_fence = False
    for line in text.split("\n"):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        names.update(_PLACEHOLDER_RE.findall(_INLINE_CODE_RE.sub("", line)))
    return names


def _item_files(root: Path, item_id: str) -> list[Path]:
    p = root / item_rel_path(item_id)
    if p.is_file():
        return [p]
    if p.is_dir():
        return [Path(dp) / f for dp, _, fs in os.walk(p) for f in fs
                if f.lower() != "desktop.ini" and "__pycache__" not in dp]
    return []


def archived_ids(root: Path) -> set[str]:
    """Exact ids of items under _archive/, read from their frontmatter (any depth)."""
    out = set()
    arch = Path(root) / "_archive"
    if not arch.is_dir():
        return out
    for f in arch.rglob("*.md"):
        try:
            data = frontmatter.parse(normalize_text(f.read_bytes()))
        except Exception:
            continue
        if isinstance(data.get("id"), str) and ID_RE.match(data["id"]):
            out.add(data["id"])
    return out


def _raw_requires_graph(root: Path, tree: dict[str, Path]) -> dict[str, list[str]]:
    g = {}
    for iid, path in tree.items():
        try:
            data = frontmatter.parse(normalize_text(path.read_bytes()))
            g[iid] = [m.group("id") for e in (data.get("requires") or []) if isinstance(e, str)
                      for m in [REQUIRE_RE.match(e)] if m]
        except Exception:
            g[iid] = []
    return g


def lint_item(root: Path, item_id: str, *, for_release: bool = False, catalog=None) -> list[Problem]:
    root = Path(root)
    probs: list[Problem] = []

    def err(code, msg):
        probs.append(Problem("error", code, msg))

    def warn(code, msg):
        probs.append(Problem("warning", code, msg))

    main = root / main_file(item_id)
    if not ID_RE.match(item_id):
        err("id-path", f"invalid id {item_id!r}")
        return probs
    if not main.is_file():
        err("id-path", f"{main_file(item_id)} does not exist")
        return probs
    text = normalize_text(main.read_bytes())
    block, _ = frontmatter.split(text)
    if block is None:
        err("fm-missing", "file must start with '---' and have a closing '---' line")
        return probs
    try:
        data = frontmatter.parse(text)
    except UsageError as e:
        err("fm-missing", str(e))
        return probs
    fields = REQUIRED_FIELDS + (TOOL_FIELDS if kind_of(item_id) == "tool" else [])
    for f in fields:
        if f not in data:
            err("fm-field", f"required field '{f}' missing")
    if data.get("id") != item_id:
        err("id-path", f"id {data.get('id')!r} does not match location {item_rel_path(item_id)}")
    version = None
    if "version" in data:
        v = data["version"]
        if not isinstance(v, str):
            err("version", f"version {v!r} is not a string: quote it")
        else:
            version = Version.try_parse(v)
            if version is None:
                err("version", f"version {v!r} is not MAJOR.MINOR.PATCH")
    status = data.get("status")
    if version is not None and "status" in data:
        if version.is_draft and status != "draft":
            err("status", f"0.x version must have status draft (has {status!r})")
        if not version.is_draft and status not in ("canonical", "deprecated"):
            err("status", f"version >= 1.0.0 must be canonical or deprecated (has {status!r})")
    settings = {}
    if "settings" in data:
        try:
            settings = parse_settings(data["settings"])
        except UsageError as e:
            err("settings", str(e))
    # placeholders
    for f in _item_files(root, item_id):
        if f.suffix == ".md":
            try:
                body = normalize_text(f.read_bytes())
            except UnicodeDecodeError:
                err("encoding", f"{f.relative_to(root).as_posix()} is not valid UTF-8 (.md files are rendered as text)")
                continue
            for name in sorted(placeholders_outside_code(body) - set(settings)):
                err("placeholder-undeclared", f"{{{{{name}}}}} in {f.name} is not declared in settings")
    # requires
    tree = discover_working_tree(root)
    if "requires" in data:
        try:
            reqs = parse_requires(data["requires"])
        except UsageError as e:
            err("requires", str(e))
            reqs = []
        for rid, rpin in reqs:
            if rid == item_id:
                err("requires", "item requires itself")
                continue
            tagged = catalog.versions(rid) if catalog is not None else []
            if rid not in tree and not tagged:
                err("requires", f"required item {rid} does not exist")
            elif for_release and not any(rpin.matches(v) for v in tagged):
                err("requires", f"no release of {rid} matches @{rpin.text}")
            if status == "canonical" and tagged and not any(rpin.matches(v) and not v.is_draft for v in tagged):
                warn("requires", f"canonical item requires draft {rid}@{rpin.text}")
        # cycles
        graph = _raw_requires_graph(root, tree)
        graph[item_id] = [r for r, _ in reqs]
        stack, seen = [(item_id, [item_id])], set()
        while stack:
            node, path = stack.pop()
            for nxt in graph.get(node, []):
                if nxt == item_id:
                    err("requires", "dependency cycle: " + " -> ".join(path + [nxt]))
                    stack = []
                    break
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append((nxt, path + [nxt]))
    # replaces
    rep = data.get("replaces")
    if rep is not None:
        archived = isinstance(rep, str) and rep in archived_ids(root)
        tagged = catalog.versions(rep) if (catalog is not None and isinstance(rep, str)) else []
        if not isinstance(rep, str) or (rep not in tree and not archived and not tagged):
            err("replaces", f"replaces {rep!r} is not an existing or archived item")
    if status == "deprecated":
        replaced_by = False
        for oid, p in tree.items():
            try:
                if frontmatter.parse(normalize_text(p.read_bytes())).get("replaces") == item_id:
                    replaced_by = True
            except Exception:
                pass
        if not replaced_by:
            warn("deprecated-replacement", "deprecated item has no replacement (no item replaces it)")
    # name collision (documents share target <name>.md)
    if is_document(item_id) and kind_of(item_id) != "template":
        for oid in tree:
            if oid != item_id and is_document(oid) and kind_of(oid) != "template" and name_of(oid) == name_of(item_id):
                try:
                    orep = frontmatter.parse(normalize_text(tree[oid].read_bytes())).get("replaces")
                except Exception:
                    orep = None
                if orep != item_id and rep != oid:
                    err("name-collision", f"{oid} has the same target file {name_of(item_id)}.md")
    # case collision
    if not is_document(item_id):
        seen_lower: dict[str, str] = {}
        base = root / item_rel_path(item_id)
        for f in _item_files(root, item_id):
            rel = f.relative_to(base).as_posix()
            if rel.lower() in seen_lower and seen_lower[rel.lower()] != rel:
                err("case-collision", f"{rel} and {seen_lower[rel.lower()]} differ only by case")
            seen_lower[rel.lower()] = rel
    # entrypoint
    if kind_of(item_id) == "tool" and "entrypoint" in data:
        ep = data.get("entrypoint")
        if not isinstance(ep, str) or not (root / item_rel_path(item_id) / ep).is_file():
            err("entrypoint", f"entrypoint {ep!r} does not exist in the tool folder")
    # changelog
    cl_path = root / changelog_file(item_id)
    if not cl_path.is_file():
        err("changelog", f"{changelog_file(item_id)} missing")
    else:
        try:
            secs = changelog_mod.parse(normalize_text(cl_path.read_bytes()), is_document=is_document(item_id))
            for p in changelog_mod.validate(secs):
                err("changelog", p)
            rel = changelog_mod.released(secs)
            if version is not None:
                tagged = catalog.versions(item_id) if catalog is not None else []
                if rel:
                    if rel[0].version != version:
                        err("changelog", f"newest changelog version [{rel[0].name}] != frontmatter version {version}")
                elif tagged:
                    err("changelog", "no released changelog section but tags exist")
        except UsageError as e:
            err("changelog", str(e))
    return probs
