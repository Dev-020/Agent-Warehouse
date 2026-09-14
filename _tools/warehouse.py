#!/usr/bin/env python
"""Entry point for the AI warehouse tool. See _tools/README.md."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from warehouse_core.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
