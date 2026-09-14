"""00_INDEX.md generated regions (DESIGN §2.8)."""
from __future__ import annotations

import re
from pathlib import Path

from . import frontmatter, items
from .errors import UsageError

CAT_START, CAT_END = "<!-- warehouse:catalog:start -->", "<!-- warehouse:catalog:end -->"
REL_START, REL_END = "<!-- warehouse:releases:start -->", "<!-- warehouse:releases:end -->"
MAX_RELEASES = 15


def _esc(s: str) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def catalog_table(root: Path, catalog, pending: tuple | None = None) -> str:
    rows = ["| ID | Kind | Version | Released | Status | Summary | Applies to |",
            "|---|---|---|---|---|---|---|"]
    tree = items.discover_working_tree(root)
    order = {k: i for i, k in enumerate(items.KIND_ORDER)}
    for iid in sorted(tree, key=lambda i: (order[items.kind_of(i)], i)):
        link_path = items.main_file(iid)[:-3]
        link = f"[[{link_path}\\|{iid}]]"
        latest = catalog.latest(iid) if catalog is not None else None
        if pending and pending[0] == iid and (latest is None or pending[1] > latest):
            latest = pending[1]
        released = str(latest) if latest else "—"
        try:
            meta = items.parse_meta(tree[iid].read_bytes(), expected_id=iid)
            rows.append(f"| {link} | {items.kind_of(iid)} | {meta.version} | {released} | {_esc(meta.status)} | "
                        f"{_esc(meta.summary)} | {_esc(', '.join(meta.applies_to))} |")
        except (UsageError, UnicodeDecodeError):
            rows.append(f"| {link} | {items.kind_of(iid)} | — | {released} | invalid | | |")
    return "\n".join(rows)


def releases_list(catalog, pending: tuple | None = None) -> str:
    rels = [(r.date, r.version, r.id) for r in (catalog.all_releases() if catalog is not None else [])]
    if pending:
        iid, v, date = pending
        rels.append((date, v, iid))
    rels.sort(key=lambda t: (t[0], t[1], t[2]), reverse=True)
    if not rels:
        return "No releases yet."
    return "\n".join(f"- {d} — {i} {v}" for d, v, i in rels[:MAX_RELEASES])


def _replace_region(text: str, start: str, end: str, content: str) -> str:
    si, ei = text.find(start), text.find(end)
    if si == -1 or ei == -1 or ei < si:
        raise UsageError("00_INDEX.md: add the warehouse:* markers "
                         f"({start} ... {end}) before running warehouse index")
    return text[:si + len(start)] + "\n" + content + "\n" + text[ei:]


def regenerate(root: Path, catalog, today: str, pending: tuple | None = None) -> tuple[bytes, bytes]:
    """Returns (old_bytes, new_bytes). Raises UsageError if markers are missing."""
    path = Path(root) / "00_INDEX.md"
    if not path.is_file():
        raise UsageError("00_INDEX.md not found")
    old = path.read_bytes()
    text = old.decode("utf-8").replace("\r\n", "\n")
    text = _replace_region(text, CAT_START, CAT_END, catalog_table(root, catalog, pending))
    text = _replace_region(text, REL_START, REL_END, releases_list(catalog, pending))
    try:
        text = frontmatter.set_scalar(text, "updated", today)
    except UsageError:
        pass
    return old, text.encode("utf-8")
