---
id: protocol/codemap-upkeep
version: 0.1.0
status: draft
summary: When a codemap is stale and how to refresh it — by hand, by a subagent or by a script — through a scoped re-audit since the commit in the last record, then a rebuild of the map.
applies-to: [codebase]
settings:
  codemap_refresh:
    description: "When the project refreshes its codemap: phase-end, merge or schedule"
    default: "phase-end"
requires: [architecture/codemap@0.1, protocol/codebase-audit@0.1]
replaces: null
---

# Codemap Upkeep

How to keep a codemap ([[codemap]]) current. The map is only as fresh as the record it was built from,
so upkeep is always the same two moves: **re-audit what changed** ([[codebase-audit]] §4, the scoped
re-audit), then **rebuild the map** ([[codemap]] §4).

## 1. When the map is stale

The map is stale when either is true:

- the code changed since the map's commit, inside the record's scope:
  `git diff --name-only <map commit>..HEAD -- <scope include paths>` lists anything;
- a newer record exists in the audit folder (`audit_folder`, default `docs/audits`) than the map's `audit-id`.

Stale doesn't mean wrong: a change inside one function may leave every level the same. The refresh
decides that; the check only says it is due.

## 2. When to check and when to refresh

**Always check before relying on the map** for a task (one `git diff`). If it is stale and the task
touches the changed area, read the changed files directly, or refresh first.

**Refresh** on the trigger the project sets in `{{codemap_refresh}}`:

| Trigger | Refresh when | Suits |
|---|---|---|
| `phase-end` (default) | At the end of each phase ([[phased-implementation]]), if stale | Most projects; changes are batched |
| `merge` | After each merge to the main branch, if stale | Many agents working in parallel; the map is read all the time |
| `schedule` | On a fixed interval (for example weekly), if stale | Projects with no phases; long-running repos |

**Do a full re-audit instead of a scoped one** when any of these is true:
- a third or more of the record's units changed or were removed;
- the lenses or their versions changed since the last full record;
- five scoped records have been chained since the last full one.

## 3. Ways to refresh

All three run the same steps (§4); they differ in who does them.

| Way | Who | Good for | Limits |
|---|---|---|---|
| **By hand** | The agent working in the session | Small changes; phase end | Uses that session's context |
| **Subagent** | A fresh agent given the steps and the previous record ([[phase-staffing]]) | Larger changes; keeps the main session's context clean | Its report must still be checked (§5) |
| **Script** | A generator tool (later, optional) | Rebuilding the map from a record; listing files and symbols with tree-sitter or ctags | Can't judge purpose, confirm `INFERRED` relations or run lens criteria; those steps stay with an agent |

A script that builds part of the core is a measure: add it to the record's `measures` with its version
and command.

## 4. Steps

1. **Find the map and its record.** Read the map's header: `audit-id`, `commit`, `record`.
2. **Check staleness** (§1). If not stale, stop: the map is current.
3. **Re-audit.** Run the scoped re-audit ([[codebase-audit]] §4) from that record to `HEAD`, keeping its
   lenses (the structure lens at least), criteria, depth and measures. Use a full audit if §2 says so.
   Work in a worktree if other sessions are changing the code.
4. **Rebuild the map** from the new record ([[codemap]] §4). Rebuild it whole; don't patch it.
5. **Verify** (§5).
6. **Commit** the new record and the rebuilt map together, in one commit, for example
   `docs(codemap): refresh from audit 2026-11-20-d4e5f6a`. Findings from the re-audit go to the backlog
   as the audit protocol says.

## 5. Done when

- [ ] The map's header names the new record's audit id and commit.
- [ ] The new record is complete on its own (unchanged units carried, removed ones under Gaps).
- [ ] Every unit and relation in the map exists in the new record.
- [ ] Changed areas in the diff are covered by the new record, or listed under its Gaps.
- [ ] The record and the map are in the same commit.

## 6. Example

The `notes-cli` map was built from `2026-11-12-a1b2c3d`. A phase ends at commit `d4e5f6a`; the project
uses `codemap_refresh: phase-end`.

1. Header: `audit-id: 2026-11-12-a1b2c3d`, `commit: a1b2c3d`.
2. `git diff --name-only a1b2c3d..d4e5f6a -- src/ tests/` lists `src/notes/storage/db.py` and a new
   `src/notes/storage/format.py`: stale.
3. Scoped re-audit (2 of 7 units changed or added, so not full): `2026-11-20-d4e5f6a`, `previous:
   2026-11-12-a1b2c3d`. It adds the unit `src/notes/storage/format.py`, removes relations `R6` and `R7`
   (storage no longer imports cli), and carries the rest. The structure lens finds no cycle, so `Y1` is
   gone and the backlog entry for F1 is noted as fixed.
4. Rebuild: L1 loses the dotted `storage → cli` edge and the ⟳ marks; L3 gains `format.py`.
5. Checks pass.
6. One commit: `docs(codemap): refresh from audit 2026-11-20-d4e5f6a`.

## Changelog

### [Unreleased]
#### Added
- First draft: staleness check, three refresh triggers, three ways to refresh, when to do a full
  re-audit, six steps and a worked example.
