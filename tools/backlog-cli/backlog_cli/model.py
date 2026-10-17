"""Data models for backlog items."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Item:
    """A backlog item."""

    id: str = ""
    title: str = ""
    status: str = ""
    priority: str = ""
    fields: dict[str, Any] = field(default_factory=dict)
    body: str = ""
    raw: str = ""
    path: Path | None = None
    span: tuple[int, int] | None = None
