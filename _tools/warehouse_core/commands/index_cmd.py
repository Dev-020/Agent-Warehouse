"""index: regenerate the 00_INDEX.md regions (DESIGN §4.11). No commit."""
from __future__ import annotations

from .. import index
from ..fsops import WriteGuard, atomic_write


def run(ctx, args) -> int:
    old, new = index.regenerate(ctx.warehouse_root, ctx.catalog, ctx.today)
    path = ctx.warehouse_root / "00_INDEX.md"
    if old != new:
        atomic_write(WriteGuard(ctx.warehouse_root, None, allow_lock=False, extra_files=[path]), path, new)
        print("updated 00_INDEX.md")
    else:
        print("00_INDEX.md is up to date")
    return 0
