"""Version + dependency resolution -> list of ItemAction (DESIGN §4.1, §5)."""
from __future__ import annotations

from dataclasses import dataclass, field

from .errors import GitError, UsageError
from .lockfile import Lock
from .manifest import Manifest
from .semver import Pin, Version

MAX_PASSES = 50


@dataclass
class ItemAction:
    id: str
    from_v: Version | None
    to_v: Version | None
    pin: Pin | None
    source: str                      # manifest | dependency
    required_by: list[str] = field(default_factory=list)
    kind: str = "keep"               # install update downgrade keep blocked remove orphan not-installable pin-moved
    reason: str | None = None
    blocked_newer: str | None = None
    narrowed: bool = False           # manifest pin narrowed on the installed line (sync keeps; pull downgrades)
    via: str | None = None
    compatible: Version | None = None
    outside_pin: Version | None = None
    major: Version | None = None


class ResolveError(Exception):
    pass


def effective_pin(catalog, lock: Lock, item_id: str, explicit: Pin | None) -> tuple[Pin | None, str | None]:
    if explicit is not None:
        return explicit, None
    li = lock.items.get(item_id)
    if li and li.pin:
        try:
            return Pin.parse(li.pin), None
        except UsageError:
            pass
    vs = catalog.versions(item_id)
    if not vs:
        return None, f"no releases of {item_id}"
    canon = [v for v in vs if v.major >= 1]
    if canon:
        return Pin.default_for(canon[-1]), None
    return None, "draft item needs an explicit @0.MINOR pin"


def derived(catalog, item_id: str, pin: Pin | None, after: Version | None):
    if after is None or pin is None:
        return None, None, None
    vs = catalog.versions(item_id)
    comp = [v for v in vs if pin.matches(v) and v > after]
    outside = [v for v in vs if v.line == after.line and not pin.matches(v) and v > after]
    major = [v for v in vs if v.line > after.line]
    return (comp[-1] if comp else None, outside[-1] if outside else None, major[-1] if major else None)


def closure(lock: Lock, ids: set[str]) -> set[str]:
    """ids plus their installed dependencies (via lock required_by)."""
    out = set(ids)
    changed = True
    while changed:
        changed = False
        for iid, li in lock.items.items():
            if iid not in out and any(r in out for r in li.required_by):
                out.add(iid)
                changed = True
    return out


def resolve(catalog, manifest: Manifest, lock: Lock, *, mode: str, ids: set[str] | None = None,
            pin_overrides: dict[str, Pin] | None = None) -> list[ItemAction]:
    pin_overrides = pin_overrides or {}
    L = lock
    C = catalog
    manifest_ids = [e.id for e in manifest.entries]
    fixed: set[str] = set()
    scope = None
    if ids is not None:
        scope = closure(L, ids)
        fixed = {i for i in L.items if i not in scope}

    constraints: dict[str, list[tuple[Pin, str]]] = {}
    not_installable: dict[str, str] = {}
    manifest_pins: dict[str, Pin] = {}
    for e in manifest.entries:
        pin, reason = effective_pin(C, L, e.id, pin_overrides.get(e.id, e.pin))
        if pin is None:
            not_installable[e.id] = reason
            continue
        manifest_pins[e.id] = pin
        constraints[e.id] = [(pin, "manifest")]

    def allowed(iid: str, v: Version) -> bool:
        inst = L.version(iid)
        if inst is None:
            return True
        if iid in fixed:
            return v == inst
        if mode == "major" and scope is not None and iid in scope:
            # the named items and their installed dependency closure may cross MAJOR lines
            return v.line >= inst.line
        if mode == "sync":
            return v.line == inst.line and v >= inst
        return v.line == inst.line

    def safe_meta(iid, v):
        try:
            return C.meta(iid, v)
        except (GitError, UsageError):
            return None

    def deps_fail(iid: str, v: Version) -> str | None:
        meta = safe_meta(iid, v)
        if meta is None:
            return f"{iid} {v}: release unreadable"
        for rid, rpin in meta.requires:
            others = [p for p, s in constraints.get(rid, []) if s != iid]
            ok = any(rpin.matches(w) and all(p.matches(w) for p in others) and allowed(rid, w)
                     for w in C.versions(rid))
            if not ok:
                have = L.version(rid)
                msg = f"{iid} {v} needs {rid}@{rpin.text} (project has {have if have else 'none'})"
                if have is not None and rpin.line > have.line:
                    msg += f": warehouse pull {iid} --major"
                return msg
        return None

    chosen: dict[str, Version | None] = {}
    blocked: dict[str, str] = {}
    blocked_newer: dict[str, str] = {}
    pin_moved: set[str] = set()
    narrowed: set[str] = set()
    passes = 0
    while True:
        passes += 1
        if passes > MAX_PASSES:
            raise ResolveError("unresolvable requires")
        changed = False
        for iid in sorted(constraints):
            if iid not in constraints:
                continue
            pins = [p for p, _ in constraints[iid]]
            cands = sorted((v for v in C.versions(iid) if all(p.matches(v) for p in pins) and allowed(iid, v)),
                           reverse=True)
            pick = None
            first_fail = None
            for v in cands:
                f = deps_fail(iid, v)
                if f is None:
                    pick = v
                    break
                if first_fail is None:
                    first_fail = f
            blocked.pop(iid, None)
            blocked_newer.pop(iid, None)
            pin_moved.discard(iid)
            narrowed.discard(iid)
            inst = L.version(iid)
            if pick is None:
                pick = inst
                if first_fail:
                    blocked[iid] = first_fail
                elif inst is not None and not all(p.matches(inst) for p in pins):
                    if mode == "sync" or iid in fixed:
                        if all(p.line == inst.line for p in pins):
                            narrowed.add(iid)
                        else:
                            pin_moved.add(iid)
                    else:
                        blocked[iid] = f"no release of {iid} matches " + ", ".join("@" + p.text for p in pins) \
                            + f" on the installed line (has {inst}); use --major"
            elif first_fail:
                blocked_newer[iid] = first_fail
            if chosen.get(iid, "unset") != pick:
                chosen[iid] = pick
                changed = True
            # replace constraints sourced from iid with the requires of pick
            new_reqs: dict[str, Pin] = {}
            if pick is not None:  # incl. kept installs (pin moved/narrowed): their requires still hold
                meta = safe_meta(iid, pick)
                if meta is not None:
                    new_reqs = dict(meta.requires)
            old_reqs = {rid: p for rid, lst in constraints.items() for p, s in lst if s == iid}
            if old_reqs != new_reqs:
                changed = True
                for rid in list(constraints):
                    constraints[rid] = [(p, s) for p, s in constraints[rid] if s != iid]
                for rid, rpin in new_reqs.items():
                    constraints.setdefault(rid, []).append((rpin, iid))
                for rid in list(constraints):
                    if not constraints[rid] and rid not in manifest_ids:
                        del constraints[rid]
                        chosen.pop(rid, None)
        if not changed:
            break

    actions: list[ItemAction] = []
    all_ids = set(constraints) | set(not_installable) | set(L.items)
    for iid in sorted(all_ids):
        inst = L.version(iid)
        li = L.items.get(iid)
        if iid in not_installable:
            a = ItemAction(iid, inst, None, None, "manifest", kind="not-installable", reason=not_installable[iid])
            if inst is not None:
                a.kind, a.to_v = "keep", inst
            actions.append(a)
            continue
        if iid in constraints:
            required_by = sorted({s for _, s in constraints[iid] if s != "manifest"})
            source = "manifest" if iid in manifest_pins else "dependency"
            pin = manifest_pins.get(iid) or constraints[iid][0][0]
            pick = chosen.get(iid)
            a = ItemAction(iid, inst, pick, pin, source, required_by)
            if iid in pin_moved:
                a.kind = "pin-moved"
                a.to_v = inst
                a.reason = f"pin changed to @{pin.text}; run warehouse pull {iid} --major"
            elif iid in narrowed:
                a.kind = "keep"
                a.narrowed = True
                a.reason = (f"{inst} is outside pin @{pin.text}; sync never downgrades: "
                            f"run warehouse pull {iid}")
            elif iid in blocked:
                a.kind = "blocked" if inst is not None else "not-installable"
                a.reason = blocked[iid]
                a.to_v = inst
            elif pick is None:
                a.kind = "not-installable"
                a.reason = f"no release of {iid} matches @{pin.text}"
            elif inst is None:
                a.kind = "install"
            elif pick > inst:
                a.kind = "update"
            elif pick < inst:
                a.kind = "downgrade"
            else:
                a.kind = "keep"
            a.blocked_newer = blocked_newer.get(iid)
            a.compatible, a.outside_pin, a.major = derived(C, iid, pin, a.to_v)
            if a.major and a.source == "dependency" and a.required_by:
                a.via = a.required_by[0]
                for p, req_id in constraints[iid]:
                    if req_id != "manifest" and not p.matches(a.major):
                        a.via = req_id
                        break
            actions.append(a)
            continue
        # in lock, no longer constrained
        pin = Pin.parse(li.pin) if li and li.pin else None
        kind = "remove" if li.source == "manifest" else "orphan"
        actions.append(ItemAction(iid, inst, inst, pin, li.source, list(li.required_by), kind=kind,
                                  reason="removed from .warehouse.yml" if kind == "remove"
                                  else "no longer required; kept (warehouse remove --prune to delete)"))

    if scope is not None:
        in_scope = set(scope)
        grow = True
        while grow:
            grow = False
            for a in actions:
                if a.id not in in_scope and any(r in in_scope for r in a.required_by):
                    in_scope.add(a.id)
                    grow = True
        actions = [a for a in actions if a.id in in_scope]
    return actions
