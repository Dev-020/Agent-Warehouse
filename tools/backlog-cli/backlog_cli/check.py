"""Pre-merge check executed before close merges into the base branch (Decision 44).

Checks:
- Blocking: new duplicate IDs introduced by the branch.
- Warning, never blocking: unticked acceptance criteria on the closing item.
- Generated sections: not checked in 0.2 (S19).
"""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
from typing import Any

from backlog_cli import TaskError
from backlog_cli.ids import parse_task_id
from backlog_cli.layouts import (
    get_layout,
    normalize_id,
    parse_frontmatter,
    split_lines_exact,
)
from backlog_cli.settings import load_settings


def check_unticked_criteria(raw_entry: str | list[str], task_id: str) -> str | None:
    """Check for unticked acceptance criteria in an item's entry (Decision 44).

    Returns a formatted warning string if unticked criteria exist, else None.
    Compact entries have no criteria list and get no warning.
    """
    lines = split_lines_exact(raw_entry) if isinstance(raw_entry, str) else list(raw_entry)
    in_code = False
    in_criteria = False
    unticked_count = 0
    criterion_numbers: list[str] = []

    for line in lines:
        sline = line.strip()
        if sline.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue

        if re.match(r"^#{1,4}\s+Acceptance Criteria\b", line, re.IGNORECASE):
            in_criteria = True
            continue

        if in_criteria:
            if re.match(r"^#{1,4}\s+", line):
                in_criteria = False
                continue

            if re.search(r"^\s*[-*]\s*\[\s*\]", line):
                unticked_count += 1
                m = re.search(r"^\s*[-*]\s*\[\s*\]\s*(#\d+)", line)
                if m:
                    criterion_numbers.append(m.group(1))

    if unticked_count == 0:
        return None

    clean_id = task_id.strip("'\"`").strip("[]")
    if criterion_numbers:
        nums_str = ", ".join(criterion_numbers)
        return f"Warning: [{clean_id}] closed with {unticked_count} unticked criteria: {nums_str}"
    return f"Warning: [{clean_id}] closed with {unticked_count} unticked criteria"


def check_duplicates(
    base_entries: list[tuple[str, str]],
    claim_entries: list[tuple[str, str]],
) -> dict[str, list[str]]:
    """Find new duplicate IDs introduced at claim tip.

    Returns dict mapping duplicate display ID to list of its locations at claim tip.
    An ID is a new duplicate when it appears more than once at the claim tip,
    and more often there than at the base tip (Decision 44).
    Duplicates that already exist on the base branch are ignored.
    """
    base_counts: dict[str, int] = {}
    for raw_id, _ in base_entries:
        norm = normalize_id(raw_id)
        base_counts[norm] = base_counts.get(norm, 0) + 1

    claim_counts: dict[str, int] = {}
    claim_locs: dict[str, list[str]] = {}
    claim_display: dict[str, str] = {}
    for raw_id, loc in claim_entries:
        norm = normalize_id(raw_id)
        claim_counts[norm] = claim_counts.get(norm, 0) + 1
        claim_locs.setdefault(norm, []).append(loc)
        if norm not in claim_display:
            claim_display[norm] = raw_id.strip().strip("'\"`").strip("[]")

    duplicates: dict[str, list[str]] = {}
    for norm, count in claim_counts.items():
        if count > 1 and count > base_counts.get(norm, 0):
            disp = claim_display.get(norm, norm)
            duplicates[disp] = claim_locs[norm]

    return duplicates


def format_duplicate_error(duplicates: dict[str, list[str]]) -> str:
    """Format duplicate IDs error message adhering to Decision 44."""
    lines = []
    for tid, locs in sorted(duplicates.items()):
        disp_id = f"[{tid.strip('[]')}]"
        lines.append(f"Duplicate ID {disp_id}:")
        for loc in locs:
            lines.append(f"  {loc}")
    lines.append("Fix the duplicate in the claim worktree, commit, and re-run close.")
    return "\n".join(lines)


def collect_ids_with_locations(
    root: Path,
    ref: str | None,
    settings: Any,
) -> list[tuple[str, str]]:
    """Collect (raw_id, location) pairs from git ref or filesystem adhering to Decision 44."""
    if settings.layout == "single":
        try:
            rel = settings.backlog_file.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            rel = settings.backlog_file.name

        if ref is None:
            bf = (
                settings.backlog_file
                if settings.backlog_file.is_absolute()
                else root / settings.backlog_file
            )
            if not bf.is_file():
                return []
            text = bf.read_text(encoding="utf-8", errors="replace")
        else:
            proc = subprocess.run(
                ["git", "show", f"{ref}:{rel}"],
                cwd=str(root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if proc.returncode != 0:
                return []
            text = proc.stdout

        lines = split_lines_exact(text)
        in_code = False
        results: list[tuple[str, str]] = []
        for idx, line in enumerate(lines, start=1):
            sline = line.strip()
            if sline.startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                continue
            tid = parse_task_id(line)
            if tid:
                results.append((tid, f"{rel}:{idx}"))
        return results

    elif settings.layout == "split":
        try:
            rel_dir = settings.backlog_dir.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            rel_dir = settings.backlog_dir.name

        bdir = (
            settings.backlog_dir
            if settings.backlog_dir.is_absolute()
            else root / settings.backlog_dir
        )
        results = []
        for fname in ("Open.md", "Closed.md"):
            rel_p = f"{rel_dir}/{fname}"
            if ref is None:
                fpath = bdir / fname
                if not fpath.is_file():
                    continue
                text = fpath.read_text(encoding="utf-8", errors="replace")
            else:
                proc = subprocess.run(
                    ["git", "show", f"{ref}:{rel_p}"],
                    cwd=str(root),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                if proc.returncode != 0:
                    continue
                text = proc.stdout

            lines = split_lines_exact(text)
            in_code = False
            for idx, line in enumerate(lines, start=1):
                sline = line.strip()
                if sline.startswith("```"):
                    in_code = not in_code
                    continue
                if in_code:
                    continue
                tid = parse_task_id(line)
                if tid:
                    results.append((tid, f"{rel_p}:{idx}"))
        return results

    elif settings.layout == "folders":
        try:
            rel_dir = settings.backlog_dir.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            rel_dir = settings.backlog_dir.name

        bdir = (
            settings.backlog_dir
            if settings.backlog_dir.is_absolute()
            else root / settings.backlog_dir
        )
        results = []
        if ref is None:
            for sub in ("open", "closed"):
                sub_dir = bdir / sub
                if not sub_dir.is_dir():
                    continue
                for p in sub_dir.rglob("*.md"):
                    if p.name in ("00_BACKLOG.md", ".gitkeep"):
                        continue
                    if p.parent.name not in ("open", "closed") and p.name != f"{p.parent.name}.md":
                        continue
                    try:
                        rel_item = p.resolve().relative_to(root.resolve()).as_posix()
                    except ValueError:
                        rel_item = f"{rel_dir}/{sub}/{p.name}"
                    text = p.read_text(encoding="utf-8", errors="replace")
                    fields, _, _ = parse_frontmatter(text)
                    tid = str(fields.get("id", "")).strip()
                    if not tid:
                        fname = p.stem
                        m = re.match(r"^(\d+|[A-Za-z]+-\d+)(?:-|\.md$|/|$)", fname)
                        if m:
                            tid = f"#{m.group(1)}" if m.group(1).isdigit() else m.group(1)
                    if tid:
                        results.append((tid, rel_item))
            return results
        else:
            proc_ls = subprocess.run(
                ["git", "ls-tree", "-r", ref, "--", f"{rel_dir}/open", f"{rel_dir}/closed"],
                cwd=str(root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if proc_ls.returncode != 0:
                return []

            main_files: list[tuple[str, str]] = []
            folder_blobs: dict[str, list[tuple[str, str]]] = {}

            for line in proc_ls.stdout.split("\n"):
                line = line.strip()
                if not line or "\t" not in line:
                    continue
                meta, path_str = line.split("\t", 1)
                parts = meta.split()
                if len(parts) < 3 or parts[1] != "blob":
                    continue
                oid = parts[2]
                p = Path(path_str)
                if p.suffix != ".md" or p.name in ("00_BACKLOG.md", ".gitkeep"):
                    continue
                if p.parent.name in ("open", "closed"):
                    main_files.append((oid, path_str))
                elif p.parent.parent.name in ("open", "closed"):
                    folder_blobs.setdefault(str(p.parent), []).append((oid, path_str))

            for folder_path, blobs in folder_blobs.items():
                folder_name = Path(folder_path).name
                matched = [b for b in blobs if Path(b[1]).name == f"{folder_name}.md"]
                if matched:
                    main_files.append(matched[0])
                elif blobs:
                    main_files.append(blobs[0])

            if main_files:
                cat_input = b"".join(f"{oid}\n".encode("ascii") for oid, _ in main_files)
                cat_proc = subprocess.run(
                    ["git", "cat-file", "--batch"],
                    cwd=str(root),
                    input=cat_input,
                    capture_output=True,
                )
                if cat_proc.returncode == 0:
                    pos = 0
                    out = cat_proc.stdout
                    for oid, path_str in main_files:
                        nl = out.find(b"\n", pos)
                        if nl == -1:
                            break
                        hdr = out[pos:nl].decode("ascii", errors="replace")
                        pos = nl + 1
                        hdr_parts = hdr.split()
                        if len(hdr_parts) >= 3 and hdr_parts[1] == "blob":
                            size = int(hdr_parts[2])
                            content = out[pos : pos + size].decode("utf-8", errors="replace")
                            pos = pos + size + 1
                            fields, _, _ = parse_frontmatter(content)
                            tid = str(fields.get("id", "")).strip()
                            if not tid:
                                fname = Path(path_str).stem
                                m = re.match(r"^(\d+|[A-Za-z]+-\d+)(?:-|\.md$|/|$)", fname)
                                if m:
                                    tid = f"#{m.group(1)}" if m.group(1).isdigit() else m.group(1)
                            if tid:
                                results.append((tid, path_str))
            return results

    return []


def run_pre_merge_check(
    primary_root: Path,
    wt_path: Path,
    task_id: str,
    base_branch: str,
    claim_branch: str,
    settings: Any,
) -> None:
    """Pre-merge check executed by close before merging into base branch (Decision 44)."""
    # 1. Unticked criteria check (Warning, never blocking)
    try:
        wt_settings = load_settings(wt_path)
        wt_layout = get_layout(wt_settings)
        item = wt_layout.find(task_id)
        if item and item.raw:
            warn = check_unticked_criteria(item.raw, task_id)
            if warn:
                print(warn)
    except Exception:
        pass

    # 2. Duplicate IDs check (Blocking)
    base_entries = collect_ids_with_locations(primary_root, base_branch, settings)
    claim_entries = collect_ids_with_locations(primary_root, claim_branch, settings)

    duplicates = check_duplicates(base_entries, claim_entries)
    if duplicates:
        raise TaskError(format_duplicate_error(duplicates))
