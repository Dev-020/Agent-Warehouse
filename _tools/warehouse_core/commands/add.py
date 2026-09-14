"""add <id>[@pin] [--major] (DESIGN §4.6)."""
from __future__ import annotations

from .. import manifest as manifest_mod
from ..apply import apply_actions
from ..errors import GitError, UsageError
from ..fsops import WriteGuard, atomic_write
from ..report import Report
from ..resolve import ResolveError, resolve
from ..semver import Pin
from . import current_project, emit


def run(ctx, args) -> int:
    spec = args.spec
    if spec.startswith("template/"):
        raise UsageError(f"{spec}: templates are not synced; use `warehouse template`")
    mm = manifest_mod.ENTRY_RE.match(spec)
    if not mm:
        raise UsageError(f"invalid item {spec!r}: expected <kind>/<name>[@pin]")
    iid = mm.group("id")
    proj, lock = current_project(ctx)
    m = proj.manifest
    C = ctx.catalog
    versions = C.versions(iid)
    if not versions:
        raise UsageError(f"no released version of {iid}")
    if mm.group("pin") is not None:
        pin = Pin.parse(mm.group("pin"))
        if not any(pin.matches(v) for v in versions):
            raise UsageError(f"no release of {iid} matches @{pin.text}")
    else:
        canon = [v for v in versions if v.major >= 1]
        pin = Pin.default_for(canon[-1] if canon else versions[-1])

    li = lock.items.get(iid)
    inst = li.ver if li else None
    major_mode = False
    if inst is not None and pin.line != inst.line:
        if not args.major:
            raise UsageError(f"{iid} is installed at {inst}; @{pin.text} is another MAJOR line: use --major")
        major_mode = True

    report = Report(f"add {spec}", ctx.today, verbose=ctx.verbose)
    report.project(proj.name, "[auto]" if m.auto_sync else "[manual]")

    latest = C.latest(iid, pin)
    meta = C.meta(iid, latest)
    if meta.status == "deprecated":
        succ = C.successor(iid)
        report.add(proj.name, "deprecated", iid, f"deprecated: use {succ}" if succ else "deprecated")

    entry = m.entry(iid)
    text = m.raw
    if entry is None or entry.pin != pin:
        text = manifest_mod.add_or_replace_entry(m, iid, pin)
    cur = manifest_mod.load_text(text, m.path)
    required = {n: s.description for n, s in meta.settings.items() if not s.has_default}
    text = manifest_mod.ensure_settings_keys(cur, required)
    guard = WriteGuard(proj.root, m.target, allow_manifest=True)

    def write_manifest():
        if text != m.raw:
            atomic_write(guard, m.path, text.encode("utf-8"))

    if not major_mode:
        write_manifest()
    proj.manifest = manifest_mod.load_text(text, m.path)  # resolve against the new entry (in memory for --major)

    try:
        actions = resolve(C, proj.manifest, lock, mode="major" if major_mode else "pull", ids={iid})
        apply_actions(ctx, proj, lock, actions, report, today=ctx.today)
    except ResolveError as e:
        report.add(proj.name, "error", iid, str(e))
    if major_mode:
        # like pull --major: the pin moves only if the item was actually written on the new line
        li = lock.items.get(iid)
        if li is not None and li.ver is not None and pin.matches(li.ver):
            write_manifest()
        else:
            report.preamble.append(f"manifest unchanged: {iid} was not updated to @{pin.text}")
    return emit(ctx, report)
