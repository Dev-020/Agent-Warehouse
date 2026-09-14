"""Batch-2 commands (promote, discard, detach, template, bootstrap): not implemented yet."""
from __future__ import annotations

import sys

EXIT_NOT_IMPLEMENTED = 2


def make(name: str):
    def run(ctx, args) -> int:
        print(f"warehouse {name}: not implemented (batch 2)", file=sys.stderr)
        return EXIT_NOT_IMPLEMENTED
    return run
