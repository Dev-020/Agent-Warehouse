"""release <id> <major|minor|patch|initial> [--no-sync] [--message TEXT] (DESIGN §4.8)."""
from __future__ import annotations

import os
import subprocess
import sys

from .. import changelog, frontmatter, index, items
from ..discovery import find_projects
from ..errors import GitError, ReleaseCheckError, UsageError, WarehouseError
from ..fsops import WriteGuard, atomic_write
from ..report import Report
from ..semver import Version
from .sync import sync_projects


def _print_problems(probs) -> None:
    for p in probs:
        print(f"  {p.level:<8} {p.code:<24} {p.msg}")


def run(ctx, args) -> int:
    iid, level = args.id, args.level
    root = ctx.warehouse_root
    if not items.ID_RE.match(iid):
        raise UsageError(f"invalid id {iid!r}")
    if not ctx.git.is_clean_state():
        raise GitError("warehouse repo is mid-merge/rebase or HEAD is detached")
    with ctx.run_lock() as acquired:
        if not acquired:
            raise ctx.busy_error()
        return _release(ctx, args, iid, level, root)


def _release(ctx, args, iid, level, root) -> int:
    C = ctx.catalog
    probs = items.lint_item(root, iid, for_release=True, catalog=C)
    errors = [p for p in probs if p.level == "error"]
    if errors:
        print(f"release {iid}: checks failed")
        _print_problems(probs)
        raise ReleaseCheckError(f"{len(errors)} lint error(s) in {iid}")

    main_path = root / items.main_file(iid)
    cl_path = root / items.changelog_file(iid)
    is_doc = items.is_document(iid)
    main_text = items.normalize_text(main_path.read_bytes())
    meta = items.parse_meta(main_text, expected_id=iid)
    cur = meta.version
    tags = C.versions(iid)
    if level == "initial":
        if tags or C._raw.get(iid):
            raise ReleaseCheckError(f"{iid} already has releases; use major, minor or patch")
        new = cur
    else:
        if not tags:
            raise ReleaseCheckError(f"{iid} has no releases yet; use `release {iid} initial`")
        if tags[-1] != cur:
            raise ReleaseCheckError(f"frontmatter version {cur} is not the latest tag {tags[-1]}")
        new = cur.bump(level)
    if new in C._raw.get(iid, {}):
        raise GitError(f"tag {iid}@{new} already exists")

    cl_text = items.normalize_text(cl_path.read_bytes())
    secs = changelog.parse(cl_text, is_document=is_doc)
    unrel = changelog.unreleased(secs)
    n_bullets = len(changelog.bullets(unrel))
    existing_cur = any(s.version == cur for s in secs)
    edit_changelog = True
    if level == "initial" and existing_cur:
        if n_bullets:
            raise ReleaseCheckError(f"[{cur}] already exists in the changelog but [Unreleased] has entries; "
                                    "move them into a new version first")
        edit_changelog = False
    elif n_bullets == 0:
        raise ReleaseCheckError("[Unreleased] has no entries to release")

    if level == "major" and new.major >= 2:
        blocks = changelog.breaking(unrel)
        if not blocks:
            raise ReleaseCheckError("a MAJOR release needs at least one BREAKING: entry in [Unreleased]")
        missing = [b.split("\n")[0].strip() for b in blocks if "**Migration:**" not in b]
        if missing:
            raise ReleaseCheckError("BREAKING entries without **Migration:** steps: " + "; ".join(missing))

    item_dir = root / items.item_rel_path(iid)
    if items.kind_of(iid) == "tool" and (item_dir / "tests").is_dir():
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        cp = subprocess.run([sys.executable, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"],
                            cwd=item_dir, env=env, capture_output=True)
        if cp.returncode != 0:
            sys.stdout.write(cp.stdout.decode("utf-8", "replace")[-4000:])
            raise ReleaseCheckError(f"tool tests failed for {iid}; nothing modified")

    index_path = root / "00_INDEX.md"
    snapshot = {p: p.read_bytes() for p in {main_path, cl_path, index_path} if p.is_file()}
    extra = [main_path, cl_path, index_path]
    guard = WriteGuard(root, None, allow_lock=False, extra_files=extra)

    def restore():
        for p, data in snapshot.items():
            atomic_write(guard, p, data)

    try:
        if edit_changelog:
            cl_text = changelog.release_edit(cl_text, new, ctx.today, is_document=is_doc)
        if is_doc:
            main_text = cl_text
        main_new = frontmatter.set_scalar(main_text, "version", str(new))
        if cur.is_draft and not new.is_draft:
            main_new = frontmatter.set_scalar(main_new, "status", "canonical")
        atomic_write(guard, main_path, main_new.encode("utf-8"))
        if not is_doc:
            atomic_write(guard, cl_path, cl_text.encode("utf-8"))
        probs = [p for p in items.lint_item(root, iid, for_release=True, catalog=C) if p.level == "error"]
        if probs:
            restore()
            _print_problems(probs)
            raise ReleaseCheckError("checks failed after the release edit; files restored")
        _, idx_new = index.regenerate(root, C, ctx.today, pending=(iid, new, ctx.today))
        atomic_write(guard, index_path, idx_new)
    except ReleaseCheckError:
        raise
    except WarehouseError:
        restore()
        raise
    except Exception:
        restore()
        raise

    commit_paths = [items.item_rel_path(iid), "00_INDEX.md"]
    index_before = ctx.git.index_snapshot(commit_paths)
    try:
        ctx.git.commit_only(commit_paths, args.message or f"release: {iid}@{new}")
    except GitError as e:
        restore()
        try:
            ctx.git.restore_index(commit_paths, index_before)
        except GitError as e2:
            raise GitError(f"commit failed, files restored, but the index could not be restored: {e2}; "
                           f"run: git reset -- {' '.join(commit_paths)}") from None
        raise GitError(f"commit failed, files and index restored: {e}") from None
    try:
        ctx.git.tag(f"{iid}@{new}", f"{iid} {new}")
    except GitError as e:
        raise GitError(f"committed but tagging failed: {e}\n"
                       f"run: git tag -a {iid}@{new} -m \"{iid} {new}\"") from None

    print(f"released {iid}@{new}")
    if args.no_sync:
        return 0
    ctx.invalidate_catalog()
    report = Report("sync --auto", ctx.today, verbose=ctx.verbose)
    sync_projects(ctx, report, find_projects(ctx.config, ctx.warehouse_root), explicit=False, include_manual=False)
    print(report.render_json() if ctx.json else report.render_text(), end="")
    ctx.write_auto_state(ctx.catalog.tags_digest(), needs_retry=report.needs_retry)
    return report.exit_code()
