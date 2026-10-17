"""Settings loading and manifest parsing for backlog-cli."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from backlog_cli import TaskError

LAYOUTS = ("single", "split", "folders")
VALID_LAYOUTS_DISPLAY = ", ".join(LAYOUTS)

BACKLOG_KEYS = ("backlog_layout", "backlog_file", "backlog_dir")


@dataclass(frozen=True)
class Settings:
    root: Path               # git top level of the current directory
    layout: str              # one of LAYOUTS
    backlog_file: Path       # absolute; used when layout == "single"
    backlog_dir: Path        # absolute; used when layout is "split" or "folders"
    worktree_root: Path      # absolute
    base_branch: str
    sources: dict[str, str]  # "layout" -> "default" | ".warehouse.yml" | "git config backlog.layout"
                             #             | "env BACKLOG_LAYOUT" | "--backlog-path"


def read_manifest_settings(root: Path) -> dict[str, str]:
    """Parse scalar settings from .warehouse.yml top-level settings: block."""
    manifest_path = root / ".warehouse.yml"
    if not manifest_path.is_file():
        return {}

    text = manifest_path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    in_settings = False
    result: dict[str, str] = {}

    for idx, line in enumerate(lines, start=1):
        if not in_settings:
            # Check for settings: at column 0
            if line.startswith("settings:"):
                rest = line[len("settings:") :].strip()
                if rest.startswith("{}"):
                    return {}
                if not rest or rest.startswith("#"):
                    in_settings = True
                continue
        else:
            # Inside settings block:
            # Ends at the next non-blank line at column 0 that isn't a comment
            if not line.strip() or line.startswith("#"):
                continue
            if not line.startswith(" ") and not line.startswith("\t"):
                # non-blank line at column 0 that isn't a comment
                break

            # Inside it, a line `  key: value` gives a scalar.
            m = re.match(r"^  ([A-Za-z0-9_-]+):(?:\s*(.*))?$", line)
            if not m:
                # Lines it can't read as a scalar (nested blocks, lists, deeper indentation) are skipped
                continue

            key = m.group(1)
            raw_val = m.group(2) if m.group(2) is not None else ""
            val_stripped = raw_val.strip()

            is_non_scalar = False
            if not val_stripped or val_stripped.startswith("#"):
                is_non_scalar = True
            elif val_stripped.startswith("[") or val_stripped.startswith("{"):
                is_non_scalar = True

            if is_non_scalar:
                if key in BACKLOG_KEYS:
                    raise TaskError(
                        f"Line {idx}: '{key}' in .warehouse.yml must have a scalar value"
                    )
                continue

            # Strip matching surrounding quotes " or '
            m_dquote = re.match(r'^"([^"]*)"(?:\s+#.*)?$', val_stripped)
            m_squote = re.match(r"^'([^']*)'(?:\s+#.*)?$", val_stripped)
            if m_dquote:
                val = m_dquote.group(1)
            elif m_squote:
                val = m_squote.group(1)
            else:
                # For an unquoted value, a ` #` starts a comment
                if " #" in val_stripped:
                    val_stripped = val_stripped.split(" #", 1)[0].rstrip()
                val = val_stripped
                if not val:
                    if key in BACKLOG_KEYS:
                        raise TaskError(
                            f"Line {idx}: '{key}' in .warehouse.yml must have a scalar value"
                        )
                    continue

            result[key] = val

    return result


def load_settings(
    root: Path,
    *,
    backlog_path: str | None = None,
    environ: Mapping[str, str] | None = None,
    git_config: Callable[[str], str | None] | None = None,
) -> Settings:
    """Load settings according to precedence rules."""
    root = Path(root).resolve()
    if environ is None:
        environ = os.environ
    if git_config is None:
        from backlog_cli.gitops import git

        def default_git_config(key: str) -> str | None:
            try:
                val = git("config", "--get", key, cwd=root, check=False)
                return val.strip() if val.strip() else None
            except Exception:
                return None

        git_config = default_git_config

    manifest = read_manifest_settings(root)
    sources: dict[str, str] = {}

    # 1. layout
    if environ.get("BACKLOG_LAYOUT"):
        layout = environ["BACKLOG_LAYOUT"]
        sources["layout"] = "env BACKLOG_LAYOUT"
    elif git_config("backlog.layout"):
        layout = git_config("backlog.layout")
        sources["layout"] = "git config backlog.layout"
    elif "backlog_layout" in manifest:
        layout = manifest["backlog_layout"]
        sources["layout"] = ".warehouse.yml"
    else:
        layout = "single"
        sources["layout"] = "default"

    if layout == "tracker":
        raise TaskError(
            "backlog_layout is 'tracker': this tool works only on file-based backlogs; use the tracker's own CLI."
        )
    if layout not in LAYOUTS:
        raise TaskError(
            f"Invalid layout '{layout}'. Valid layouts are: {VALID_LAYOUTS_DISPLAY}"
        )

    # 2. backlog_file
    if backlog_path:
        raw_file = backlog_path
        sources["backlog_file"] = "--backlog-path"
    elif environ.get("BACKLOG_FILE"):
        raw_file = environ["BACKLOG_FILE"]
        sources["backlog_file"] = "env BACKLOG_FILE"
    elif environ.get("BACKLOG_PATH"):
        raw_file = environ["BACKLOG_PATH"]
        sources["backlog_file"] = "env BACKLOG_PATH"
    elif git_config("backlog.file"):
        raw_file = git_config("backlog.file")
        sources["backlog_file"] = "git config backlog.file"
    elif "backlog_file" in manifest:
        raw_file = manifest["backlog_file"]
        sources["backlog_file"] = ".warehouse.yml"
    else:
        raw_file = "BACKLOG.md"
        sources["backlog_file"] = "default"

    bf = Path(raw_file)
    backlog_file = bf if bf.is_absolute() else (root / bf).resolve()

    # 3. backlog_dir
    if environ.get("BACKLOG_DIR"):
        raw_dir = environ["BACKLOG_DIR"]
        sources["backlog_dir"] = "env BACKLOG_DIR"
    elif git_config("backlog.dir"):
        raw_dir = git_config("backlog.dir")
        sources["backlog_dir"] = "git config backlog.dir"
    elif "backlog_dir" in manifest:
        raw_dir = manifest["backlog_dir"]
        sources["backlog_dir"] = ".warehouse.yml"
    else:
        raw_dir = "BACKLOG"
        sources["backlog_dir"] = "default"

    bd = Path(raw_dir)
    backlog_dir = bd if bd.is_absolute() else (root / bd).resolve()

    # 4. worktree_root
    if environ.get("WORKTREE_DIR"):
        raw_wroot = environ["WORKTREE_DIR"]
        sources["worktree_root"] = "env WORKTREE_DIR"
    elif git_config("vault.worktreeRoot"):
        raw_wroot = git_config("vault.worktreeRoot")
        sources["worktree_root"] = "git config vault.worktreeRoot"
    else:
        raw_wroot = str((root.parent / "worktrees").resolve())
        sources["worktree_root"] = "default"

    wr = Path(raw_wroot)
    worktree_root = wr if wr.is_absolute() else (root / wr).resolve()

    # 5. base_branch
    if git_config("backlog.baseBranch"):
        base = git_config("backlog.baseBranch")
        sources["base_branch"] = "git config backlog.baseBranch"
    else:
        from backlog_cli.gitops import git_ok

        sources["base_branch"] = "default"
        if git_ok("show-ref", "--verify", "--quiet", "refs/heads/main", cwd=root):
            base = "main"
        elif git_ok("show-ref", "--verify", "--quiet", "refs/heads/master", cwd=root):
            base = "master"
        else:
            base = "main"

    return Settings(
        root=root,
        layout=layout,
        backlog_file=backlog_file,
        backlog_dir=backlog_dir,
        worktree_root=worktree_root,
        base_branch=base,
        sources=sources,
    )
