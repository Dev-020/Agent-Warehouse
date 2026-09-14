"""Versions, pins, lines and matching (DESIGN §3)."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import UsageError

_VERSION_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
_PIN_RE = re.compile(r"^(0|[1-9]\d*)(?:\.(0|[1-9]\d*))?(?:\.(0|[1-9]\d*))?$")


@dataclass(frozen=True, order=True)
class Version:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, s) -> "Version":
        if not isinstance(s, str):
            raise UsageError(f"invalid version {s!r}: must be a quoted string MAJOR.MINOR.PATCH")
        m = _VERSION_RE.match(s)
        if not m:
            raise UsageError(f"invalid version {s!r}: expected MAJOR.MINOR.PATCH")
        return cls(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    @classmethod
    def try_parse(cls, s) -> "Version | None":
        try:
            return cls.parse(s)
        except UsageError:
            return None

    @property
    def line(self) -> tuple:
        return (self.major,) if self.major >= 1 else (0, self.minor)

    @property
    def is_draft(self) -> bool:
        return self.major == 0

    def bump(self, level: str) -> "Version":
        if level == "major":
            return Version(self.major + 1, 0, 0)
        if level == "minor":
            return Version(self.major, self.minor + 1, 0)
        if level == "patch":
            return Version(self.major, self.minor, self.patch + 1)
        raise UsageError(f"unknown bump level {level!r}")

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


@dataclass(frozen=True)
class Pin:
    major: int
    minor: int | None = None
    patch: int | None = None

    @classmethod
    def parse(cls, s) -> "Pin":
        s = str(s)
        m = _PIN_RE.match(s)
        if not m:
            raise UsageError(f"invalid pin {s!r}")
        major = int(m.group(1))
        minor = int(m.group(2)) if m.group(2) is not None else None
        patch = int(m.group(3)) if m.group(3) is not None else None
        if major == 0 and minor is None:
            raise UsageError("pin @0 is not allowed: draft pins need @0.MINOR or an exact version")
        return cls(major, minor, patch)

    @property
    def is_exact(self) -> bool:
        return self.patch is not None

    def matches(self, v: Version) -> bool:
        if self.patch is not None:
            return v == Version(self.major, self.minor, self.patch)
        if self.minor is not None:
            return v.major == self.major and v.minor == self.minor
        return v.major == self.major

    @property
    def line(self) -> tuple:
        if self.patch is not None:
            return Version(self.major, self.minor, self.patch).line
        if self.major >= 1:
            return (self.major,)
        return (0, self.minor)

    @property
    def text(self) -> str:
        parts = [str(self.major)]
        if self.minor is not None:
            parts.append(str(self.minor))
        if self.patch is not None:
            parts.append(str(self.patch))
        return ".".join(parts)

    def __str__(self) -> str:
        return self.text

    @classmethod
    def default_for(cls, v: Version) -> "Pin":
        return cls(v.major) if v.major >= 1 else cls(0, v.minor)

    def moved_to(self, v: Version) -> "Pin":
        if self.patch is not None:
            return Pin(v.major, v.minor, v.patch)
        if self.major == 0:  # draft pin 0.m
            return Pin(v.major) if v.major >= 1 else Pin(0, v.minor)
        if self.minor is not None:
            return Pin(v.major, v.minor)
        return Pin(v.major) if v.major >= 1 else Pin(0, v.minor)
