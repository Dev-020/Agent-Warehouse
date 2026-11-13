---
id: protocol/codemap-upkeep
version: 0.1.0
status: draft
summary: When a codemap is stale and how to refresh it — by script, subagent or by hand — through a scoped re-audit since the commit in the last record.
applies-to: [codebase]
settings: {}   # DECIDE: e.g. upkeep trigger default
requires: [architecture/codemap@0.1, protocol/codebase-audit@0.1]
replaces: null
---

# Codemap Upkeep

<!-- SKELETON (WH-16). Name `protocol/codemap-upkeep` still to agree with the user. -->

## 1. When the map is stale
<!-- Stale = the map's commit (from its record) is behind the branch on files in the audit scope.
     Check: git diff --name-only <map commit>..HEAD -- <scope>. -->

## 2. When to check — DECIDE
<!-- Options: every merge to main; at every phase end; on a schedule; before a task that reads the map.
     Proposal: phase end by default, plus "before relying on it" check. -->

## 3. Ways to refresh — DECIDE
<!-- (a) script: generator tool for machine-buildable levels (later); (b) subagent after each change /
     merge; (c) by hand at phase end. Each runs protocol/codebase-audit §4 (scoped re-audit) since the
     record's commit, then rebuilds the map (architecture/codemap §4). -->

## 4. Steps
<!-- 1 find latest record → 2 stale check → 3 scoped re-audit → 4 rebuild map → 5 verify header points
     at the new record → 6 commit map + record together. -->

## 5. Done when
<!-- Map header commit = record commit; no unit in the map missing from the record; gaps carried. -->

## Changelog

### [Unreleased]
#### Added
- First draft.
