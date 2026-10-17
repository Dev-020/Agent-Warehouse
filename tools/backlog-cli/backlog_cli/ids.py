"""Task ID parsing, classification, and allocation."""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
from typing import Any



def parse_task_id(header_line: str) -> str | None:
    """Extract ID from ### [ID] or # [ID]. Drops legacy - [ ] **ID**."""
    line = header_line.strip()
    m = re.match(r"^#{1,3}\s+\[([^\]]+)\]", line)
    if m:
        return m.group(1).strip()
    return None


def id_matches(a: str, b: str) -> bool:
    """Check if two IDs match, ignoring quotes, brackets, and leading # differences."""
    clean_a = a.strip().strip("'\"").strip("[]")
    clean_b = b.strip().strip("'\"").strip("[]")
    if clean_a == clean_b:
        return True
    return clean_a.lstrip("#") == clean_b.lstrip("#")


def classify_id(raw_id: str) -> tuple[str, str, int, int]:
    """Classify an ID into (scheme_type, prefix_or_symbol, number, width).

    scheme_type is 'sequential', 'prefixed', or 'other'.
    """
    clean = raw_id.strip().strip("'\"").strip("[]")
    if clean.startswith("#") and clean[1:].isdigit():
        return ("sequential", "#", int(clean[1:]), len(clean[1:]))
    m = re.match(r"^([A-Za-z]+)-(\d+)$", clean)
    if m:
        return ("prefixed", m.group(1), int(m.group(2)), len(m.group(2)))
    return ("other", clean, 0, 0)


def extract_all_ids(text: str) -> list[str]:
    """Extract all task IDs from a text string."""
    ids = []
    for line in text.split("\n"):
        line = line[:-1] if line.endswith("\r") else line
        tid = parse_task_id(line)
        if tid:
            ids.append(tid)
    return ids


def allocate_id(
    existing_ids: list[str],
    prefix: str | None = None,
    new_prefix: bool = False,
) -> str:
    """Allocate the next task ID adhering to decision 13 (S7)."""
    from backlog_cli import TaskError

    seq_nums: list[int] = []
    seq_widths: list[int] = []
    prefix_map: dict[str, list[int]] = {}

    for raw_id in existing_ids:
        stype, pfix, num, width = classify_id(raw_id)
        if stype == "sequential":
            seq_nums.append(num)
            seq_widths.append(width)
        elif stype == "prefixed":
            prefix_map.setdefault(pfix, []).append(num)

    known_prefixes = sorted(prefix_map.keys())
    schemes_in_use: list[str] = []
    if seq_nums:
        schemes_in_use.append("#")
    schemes_in_use.extend(known_prefixes)

    if prefix is not None:
        p = prefix.strip()
        if p == "#":
            if not seq_nums and not new_prefix:
                prefixes_disp = ", ".join(schemes_in_use) or "none"
                raise TaskError(
                    f"Sequential ID scheme '#' is not in use. Prefixes in use: {prefixes_disp}. Use --new-prefix to introduce it."
                )
            nxt = (max(seq_nums) + 1) if seq_nums else 1
            width = max(max(seq_widths), 3) if seq_widths else 3
            return f"#{nxt:0{width}d}"
        else:
            if p not in prefix_map and not new_prefix:
                prefixes_disp = ", ".join(known_prefixes) or "none"
                raise TaskError(
                    f"Prefix '{p}' is not in use. Prefixes in use: {prefixes_disp}. Use --new-prefix to introduce it."
                )
            nxt = (max(prefix_map[p]) + 1) if p in prefix_map else 1
            return f"{p}-{nxt}"

    # Without --prefix
    if not schemes_in_use:
        return "#001"
    if len(schemes_in_use) == 1:
        scheme = schemes_in_use[0]
        if scheme == "#":
            nxt = max(seq_nums) + 1
            width = max(max(seq_widths), 3)
            return f"#{nxt:0{width}d}"
        else:
            nxt = max(prefix_map[scheme]) + 1
            return f"{scheme}-{nxt}"

    schemes_disp = ", ".join(schemes_in_use)
    raise TaskError(
        f"Multiple ID schemes in use: {schemes_disp}. Specify --prefix to allocate a new ID."
    )


def find_next_id(prefix: str, text: str) -> str:
    """Legacy helper: allocate next ID matching prefix from text."""
    existing = extract_all_ids(text)
    return allocate_id(existing, prefix=prefix, new_prefix=True)


def collect_branch_ids(root: Path, target_root: Path, settings: Any) -> list[str]:
    """Collect task IDs from the target tree, base branch tip, and claim/* branches adhering to Decision 23 (D1)."""
    from backlog_cli.gitops import claim_branches, git_ok
    from backlog_cli.layouts import get_layout

    seen_ids: set[str] = set()

    # 1. Backlog in target tree
    try:
        target_layout = get_layout(settings)
        for it in target_layout.items():
            seen_ids.add(it.id)
    except Exception:
        pass

    # 2. Base branch tip
    candidate_refs: list[str] = []
    base = settings.base_branch
    if git_ok("rev-parse", "--verify", f"refs/heads/{base}", cwd=root) or git_ok(
        "rev-parse", "--verify", base, cwd=root
    ):
        candidate_refs.append(base)

    # 3. Every claim/* branch
    for b in claim_branches(root):
        if b not in candidate_refs:
            candidate_refs.append(b)

    layout_type = settings.layout
    for ref in candidate_refs:
        if layout_type == "single":
            try:
                rel = settings.backlog_file.resolve().relative_to(target_root.resolve()).as_posix()
            except ValueError:
                rel = settings.backlog_file.name

            proc = subprocess.run(
                ["git", "show", f"{ref}:{rel}"],
                cwd=str(root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if proc.returncode != 0:
                continue
            for tid in extract_all_ids(proc.stdout):
                seen_ids.add(tid)

        elif layout_type == "split":
            try:
                rel_dir = settings.backlog_dir.resolve().relative_to(target_root.resolve()).as_posix()
            except ValueError:
                rel_dir = settings.backlog_dir.name

            # A branch without the backlog file is skipped
            proc_hdr = subprocess.run(
                ["git", "show", f"{ref}:{rel_dir}/00_BACKLOG.md"],
                cwd=str(root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if proc_hdr.returncode != 0:
                continue

            for fname in ("Open.md", "Closed.md"):
                proc = subprocess.run(
                    ["git", "show", f"{ref}:{rel_dir}/{fname}"],
                    cwd=str(root),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                if proc.returncode == 0:
                    for tid in extract_all_ids(proc.stdout):
                        seen_ids.add(tid)

        elif layout_type == "folders":
            try:
                rel_dir = settings.backlog_dir.resolve().relative_to(target_root.resolve()).as_posix()
            except ValueError:
                rel_dir = settings.backlog_dir.name

            # A branch without the backlog file is skipped
            proc_hdr = subprocess.run(
                ["git", "show", f"{ref}:{rel_dir}/00_BACKLOG.md"],
                cwd=str(root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if proc_hdr.returncode != 0:
                continue

            proc_ls = subprocess.run(
                ["git", "ls-tree", "-r", ref, "--", f"{rel_dir}/open", f"{rel_dir}/closed"],
                cwd=str(root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if proc_ls.returncode != 0:
                continue

            from backlog_cli.layouts import parse_frontmatter

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
                            if tid:
                                seen_ids.add(tid)
                            else:
                                fname = Path(path_str).stem
                                m = re.match(r"^(\d+|[A-Za-z]+-\d+)(?:-|\.md$|/|$)", fname)
                                if m:
                                    val = f"#{m.group(1)}" if m.group(1).isdigit() else m.group(1)
                                    seen_ids.add(val)

    return list(seen_ids)

