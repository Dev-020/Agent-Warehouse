"""install-hook [--force]: install post-commit, post-merge, pre-push and commit-msg hooks (DESIGN §4.13)."""
from __future__ import annotations

import os
import stat

from ..errors import UsageError
from ..fsops import WriteGuard, atomic_write

HOOKS = ("post-commit", "post-merge", "pre-push", "commit-msg")


def run(ctx, args) -> int:
    src_dir = ctx.warehouse_root / "_tools" / "hooks"
    hooks_dir = ctx.git.git_path("hooks")
    plan = []
    for name in HOOKS:
        src = src_dir / name
        if not src.is_file():
            raise UsageError(f"shipped hook missing: _tools/hooks/{name}")
        data = src.read_bytes().replace(b"\r\n", b"\n")
        dest = hooks_dir / name
        if dest.is_file():
            if dest.read_bytes() == data:
                plan.append((name, dest, data, "same"))
                continue
            if not args.force:
                raise UsageError(f"{dest} exists and differs; re-run with --force (it is backed up to {name}.bak)")
            plan.append((name, dest, data, "replace"))
        else:
            plan.append((name, dest, data, "new"))
    extra = [d for _, d, _, _ in plan] + [d.with_name(d.name + ".bak") for _, d, _, _ in plan]

    guard = WriteGuard(ctx.warehouse_root, None, allow_lock=False, extra_files=extra)
    hooks_dir.mkdir(parents=True, exist_ok=True)
    for name, dest, data, what in plan:
        if what == "same":
            print(f"{name}: already installed")
            continue
        if what == "replace":
            atomic_write(guard, dest.with_name(name + ".bak"), dest.read_bytes())
        atomic_write(guard, dest, data)
        try:
            os.chmod(dest, os.stat(dest).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        except OSError:
            pass
        print(f"{name}: installed" + (" (previous hook saved as .bak)" if what == "replace" else ""))
    ctx.state_dir.mkdir(parents=True, exist_ok=True)
    return 0
