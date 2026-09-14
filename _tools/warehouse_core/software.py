"""requires-software / platforms checks (DESIGN §4.9)."""
from __future__ import annotations

import os
import re
import subprocess
import sys

ENTRY_RE = re.compile(r"^(?P<name>[A-Za-z0-9_.-]+)\s*(?:(?P<op>>=|<=|==|>|<)\s*(?P<ver>\d+(?:\.\d+)*))?$")
PLATFORM_NAMES = {"win32": "windows", "linux": "linux", "darwin": "macos"}


def _cmp(have: tuple, op: str, want: tuple) -> bool:
    n = max(len(have), len(want))
    have = have + (0,) * (n - len(have))
    want = want + (0,) * (n - len(want))
    return {">=": have >= want, "<=": have <= want, "==": have == want, ">": have > want, "<": have < want}[op]


def check(entry: str) -> tuple[str, str]:
    """Returns (result, detail); result in ok | missing | info."""
    m = ENTRY_RE.match(entry.strip())
    if not m:
        return "missing", f"unparseable requirement {entry!r}"
    name, op, ver = m.group("name"), m.group("op"), m.group("ver")
    want = tuple(int(x) for x in ver.split(".")) if ver else None
    if name.lower() == "python":
        if want and not _cmp(tuple(sys.version_info[:3]), op, want):
            return "missing", f"python {op}{ver} required (have {sys.version.split()[0]})"
        return "ok", ""
    exe = which_on_path(name)
    if not exe:
        return "missing", f"{name} not found on PATH"
    if not want:
        return "ok", ""
    try:
        cp = subprocess.run([exe, "--version"], capture_output=True, timeout=5)
        out = (cp.stdout + cp.stderr).decode("utf-8", "replace")
        vm = re.search(r"\d+(\.\d+)+", out)
    except (OSError, subprocess.TimeoutExpired):
        vm = None
    if not vm:
        return "info", f"{name}: version unknown"
    have = tuple(int(x) for x in vm.group(0).split("."))
    if not _cmp(have, op, want):
        return "missing", f"{name} {op}{ver} required (have {vm.group(0)})"
    return "ok", ""


def which_on_path(name: str) -> str | None:
    """Like shutil.which, but only searches absolute PATH entries (never the current directory)."""
    if os.sep in name or (os.altsep and os.altsep in name):
        return None
    exts = [""]
    if sys.platform == "win32":
        exts = [e.lower() for e in os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD").split(";") if e]
        if os.path.splitext(name)[1].lower() in exts:
            exts = [""]
    for d in os.environ.get("PATH", "").split(os.pathsep):
        d = d.strip().strip('"')
        if not d or not os.path.isabs(d):
            continue
        for ext in exts:
            cand = os.path.join(d, name + ext)
            if os.path.isfile(cand) and (sys.platform == "win32" or os.access(cand, os.X_OK)):
                return cand
    return None


def current_platform() -> str:
    return PLATFORM_NAMES.get(sys.platform, sys.platform)


def platform_ok(platforms: list[str]) -> bool:
    return not platforms or current_platform() in platforms
