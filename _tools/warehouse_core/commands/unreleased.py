"""unreleased [<rev>]: items whose content at <rev> is not a release (DESIGN §4.9b)."""
from __future__ import annotations

from .. import changelog, items
from ..errors import UsageError
from ..render import is_excluded
from ..report import Report
from . import emit


def ids_at(git, rev: str) -> list[str]:
    """Item ids in the tree of <rev>, found the way discover_working_tree finds them on disk."""
    folders = {folder: kind for kind, folder in items.KINDS.items()}
    cp = git.run("ls-tree", "-r", "-z", "--name-only", "--full-tree", f"{rev}^{{tree}}", "--", *folders)
    out = set()
    for path in cp.stdout.decode("utf-8").split("\x00"):
        parts = path.split("/")
        kind = folders.get(parts[0])
        if kind is None:
            continue
        if kind in items.DOCUMENT_KINDS:
            if len(parts) == 2 and parts[1].endswith(".md"):
                out.add(f"{kind}/{parts[1][:-3]}")
        elif (len(parts) == 3 and not parts[1].startswith(".")
              and parts[2] == ("SKILL.md" if kind == "skill" else "TOOL.md")):
            out.add(f"{kind}/{parts[1]}")
    return sorted(out)


def _synced_files(git, ref: str, item_id: str, exclude: list[str]) -> dict[str, str]:
    """rel-in-item -> blob id, for the files a release of this item would sync."""
    rel = items.item_rel_path(item_id)
    out = {}
    for path, oid in git.tree_files(ref, rel):
        if items.is_document(item_id):
            if path == rel:
                out[path.rsplit("/", 1)[-1]] = oid
        elif path.startswith(rel + "/"):
            name = path[len(rel) + 1:]
            if not is_excluded(name, exclude, item_id):
                out[name] = oid
    return out


def _unreleased_entries(git, rev: str, item_id: str) -> bool:
    cp = git.run("show", f"{rev}:{items.changelog_file(item_id)}", check=False)
    if cp.returncode != 0:
        return False
    try:
        sections = changelog.parse(items.normalize_text(cp.stdout), is_document=items.is_document(item_id))
        return bool(changelog.bullets(changelog.unreleased(sections)))
    except Exception:
        return False


def run(ctx, args) -> int:
    rev = args.rev or "HEAD"
    git = ctx.git
    if git.run("rev-parse", "-q", "--verify", f"{rev}^{{commit}}", check=False).returncode != 0:
        raise UsageError(f"not a commit: {rev}")
    C = ctx.catalog
    exclude = ctx.config.sync_exclude
    report = Report("unreleased", ctx.today, verbose=getattr(args, "verbose", False))
    for iid in ids_at(git, rev):
        versions = list(reversed(C.versions(iid)))  # newest first
        if not versions:
            report.add(None, "unreleased", iid, "never released")
            continue
        now = _synced_files(git, rev, iid, exclude)
        tags = {v: f"refs/tags/{C.tag_name(iid, v)}" for v in versions}
        # Any release counts: an older commit may hold an older release.
        match = next((v for v in versions if _synced_files(git, tags[v], iid, exclude) == now), None)
        if match is not None:
            report.add(None, "unchanged", iid, f"matches {match}")
            continue
        # Report against the newest release this commit contains.
        base = next((v for v in versions if git.run("merge-base", "--is-ancestor", tags[v], rev,
                                                    check=False).returncode == 0), None)
        if base is None:
            report.add(None, "unreleased", iid, "no release in this commit's history")
            continue
        then = _synced_files(git, tags[base], iid, exclude)
        changed = sorted(k for k in now.keys() | then.keys() if now.get(k) != then.get(k))
        why = "has [Unreleased] entries" if _unreleased_entries(git, rev, iid) else "no [Unreleased] entry"
        report.add(None, "unreleased", iid, f"differs from {base} ({why}): {', '.join(changed)}")
    return emit(ctx, report)
