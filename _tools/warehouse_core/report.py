"""Report model and text/json output (DESIGN §4)."""
from __future__ import annotations

import json
from dataclasses import dataclass

STATUSES = ("installed updated downgraded restored adopted removed unchanged compatible outside-pin major drift "
            "promoted blocked unfilled collision deprecated orphan not-installable missing-tag invalid-manifest "
            "untracked missing-software platform error needs-retry").split()
EXIT1 = {"drift", "blocked", "unfilled", "collision", "missing-tag", "invalid-manifest", "error", "not-installable", "needs-retry"}
CHECK_INFO = {"unchanged", "compatible", "outside-pin", "major", "untracked", "promoted"}


@dataclass
class ReportLine:
    project: str | None
    status: str
    id: str | None
    detail: str
    info: bool = False


class Report:
    def __init__(self, command: str, date: str, *, check_mode: bool = False, verbose: bool = False):
        self.command = command
        self.date = date
        self.lines: list[ReportLine] = []
        self.projects: dict[str, str] = {}      # project -> header suffix
        self.check_mode = check_mode
        self.verbose = verbose
        self.skipped_projects = 0
        self.preamble: list[str] = []
        self.forced_exit: int | None = None
        self.needs_retry = False     # an auto run must be retried even if tags are unchanged

    def project(self, name: str, suffix: str = "") -> None:
        self.projects.setdefault(name, suffix)

    def add(self, project, status, item_id=None, detail="", info=False) -> None:
        assert status in STATUSES, status
        if project is not None:
            self.projects.setdefault(project, "")
        line = ReportLine(project, status, item_id, detail, info)
        if line in self.lines:  # identical lines are reported once
            return
        self.lines.append(line)
        if status == "error" and not info:
            self.needs_retry = True

    def exit_code(self) -> int:
        if self.forced_exit is not None:
            return self.forced_exit
        for ln in self.lines:
            if ln.info:
                continue
            if ln.status in EXIT1:
                return 1
            if self.check_mode and ln.status not in CHECK_INFO:
                return 1
        return 0

    def summary(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for ln in self.lines:
            out[ln.status] = out.get(ln.status, 0) + 1
        return out

    def _fmt(self, ln: ReportLine) -> str:
        return f"  {ln.status:<11} {ln.id or '':<25} {ln.detail}".rstrip()

    def render_text(self) -> str:
        out = [f"warehouse {self.command} — {self.date}", *self.preamble]
        for ln in self.lines:
            if ln.project is None and (self.verbose or ln.status != "unchanged"):
                out.append(self._fmt(ln))
        for proj, suffix in self.projects.items():
            plines = [ln for ln in self.lines if ln.project == proj
                      and (self.verbose or ln.status != "unchanged")]
            out.append(f"{proj}  {suffix}".rstrip())
            out.extend(self._fmt(ln) for ln in plines)
        summ = self.summary()
        parts = [f"{n} {s}" for s, n in summ.items() if s != "unchanged" or self.verbose]
        if self.skipped_projects:
            parts.append(f"{self.skipped_projects} project{'s' if self.skipped_projects != 1 else ''} skipped")
        out.append("Summary: " + (" · ".join(parts) if parts else "nothing to do"))
        return "\n".join(out) + "\n"

    def render_json(self) -> str:
        return json.dumps({
            "command": self.command, "date": self.date, "exit_code": self.exit_code(),
            "lines": [{"project": l.project, "status": l.status, "id": l.id, "detail": l.detail}
                      for l in self.lines],
            "summary": self.summary(),
        }, indent=2) + "\n"
