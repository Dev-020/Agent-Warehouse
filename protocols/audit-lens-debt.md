---
id: protocol/audit-lens-debt
version: 0.1.0
status: draft
summary: Audit lens for technical debt — a ledger of debt items with a rough fix cost and the cost of leaving them, hotspots from git history, and which items to pay first; it reuses the other lenses' findings instead of repeating them.
applies-to: [codebase]
settings: {}
requires: [protocol/codebase-audit@0.1, protocol/issue-triage@0.1]
replaces: null
---

# Debt Lens

A lens for [[codebase-audit]] (`protocol/codebase-audit`). It reads the audit's core, including its
history, and writes `lens-debt.md` in the record, following [[audit-record]] §5 and the lens contract
(§6).

## 1. Purpose

**The question it answers:** what debt does the codebase carry, what would each item cost to fix,
what does leaving it cost, and which items should be paid first?

It follows two ideas:
- **SQALE** (Letouzey): every debt item has a **remediation cost** (the work to fix it) and a
  **non-remediation cost** (what leaving it costs). This lens calls the second one **interest**.
- **Hotspots** (Tornhill, *Your Code as a Crime Scene*): code that is both complex and changed often
  is where debt costs the most. Poor code that rarely changes is "debt with low interest".

So the lens needs git history: interest comes from how often the code is changed.

It **reuses other lenses' findings** from the same audit (structure, health, duplication, UI). Each one
that is debt becomes a ledger item pointing at the original finding, with no new finding and no second
backlog entry. The lens adds findings only for debt the other lenses don't cover.

## 2. What it needs from the core

| Need | Value |
|---|---|
| Depth | `file` |
| Relations | none |
| History | **needed**: commits per file unit over the window ([[audit-record]] §4.4). Default window: the last 12 months, or the whole history if it is shorter. |

The lens file records `needs: { depth: file, history: true }`. If `core.md` has no History section,
collect it first ([[codebase-audit]] Step 7).

## 3. Criteria

Defaults. The project may add its own rules, with their source.

| Id | Source | Rule |
|---|---|---|
| D1 | Hotspot analysis (Tornhill) | A hotspot is simple and small enough to change safely: no very-high complexity or size function in it (health lens bands) and no open structure or duplication finding on it |
| D2 | ISO/IEC 5055 (CISQ) maintainability and reliability weaknesses | The code has none of the weaknesses the auditor found by reading (e.g. dead code, empty error handlers, hard-coded secrets, unchecked return values) |
| D3 | The lens | Every debt marker (`TODO`, `FIXME`, `HACK`, `XXX`, a suppressed lint rule or type check) has a reason and a backlog entry |
| D4 | The lens | Dependencies are on versions their maintainers still support, and none is deprecated |
| — | Inherited | An item taken from another lens keeps that lens's criterion; it is cited, not repeated here |

## 4. The steps

1. **Check the needs** (§2). The History section must exist and its window be stated.
2. **Hotspots.** For every production file unit in History, take its `commits` and its code lines (the
   health lens's volume if it ran; otherwise count them and add the command to `measures`).
   - Score: `(commits ÷ highest commits) × (lines ÷ highest lines)`, so the top file scores near 1.
     Lines predict about as well as complexity (Tornhill), and they are always available.
   - List the top 10 by score. Record the method under `hotspots-method`.
   - Leave out generated files, lock files and files with only data.
3. **Collect inherited items.** Read the findings of the other lens files in this audit. Each one that
   is debt (it makes future change slower or riskier) becomes a ledger item with `from:` naming the
   lens file and finding id. Failing builds and failing tests are defects, not debt; leave them out.
4. **Find new items.**
   - **Markers** (D3): search for debt markers in production and test code. Record the search as a
     measure. Group markers by file; a marker with a backlog id in its text is already tracked.
   - **Weaknesses** (D2): read the top hotspots for the weaknesses in D2. Reading every file is not
     expected; say which files were read.
   - **Dependencies** (D4): compare the dependency versions in the core's outside things with their
     supported versions. Record the source used (the maintainer's site, a lock-file audit tool).
5. **Price every item.**
   - **Remediation:** `S` (under an hour), `M` (under a day) or `L` (more than a day). These are rough
     size classes, not estimates to plan with.
   - **Interest**, from the item's units' change frequency in History: `high` if any unit is in the
     top 10 hotspots; `medium` if any unit changed in the window; `low` if none did.
6. **Pay first.** Order the ledger by interest (high first), then by remediation (smaller first). The
   first five are `pay-first`. An item with `high` interest and `S` remediation always goes first.
7. **Findings.** One finding per **new** item (D1–D4 or a project rule). Inherited items keep their
   original finding. Label each through [[issue-triage]]:
   - **likelihood** follows interest: `high` → `Frequent`, `medium` → `Occasional`, `low` → `Rare`;
   - **severity** is the auditor's call. Starting points: an unsupported dependency with known security
     fixes is `Major`; a marker with no reason is `Nitpick`.
   - A D1 breach (a hotspot that is also complex or flagged) is usually covered by inherited items.
     Record it as its own finding only when no other lens flagged the unit.
8. **Gaps.** In the [[audit-record]] §4.5 format: history shorter than the window, files not read for
   D2, dependency support status unknown.

## 5. Results format

```yaml
hotspots-method:
  window: "<as in core.md History>"
  score: "commits/max × lines/max"
  lines-from: lens-health | M<n>
  top: 10

hotspots:
  - { unit: <core file unit id>, commits: <n>, lines: <n>, score: <0.00-1.00>, rank: <n> }

ledger:
  - id: T<n>
    units: [<core unit ids>]
    kind: design | code | test | dependency | documentation | marker
    what: "<one line>"
    from: "<lens file> <finding id>"     # inherited item; null for a new one
    finding: F<n>                         # this lens's finding for a new item; null when inherited
    remediation: S | M | L
    interest: high | medium | low

pay-first: [T<n>, ...]

totals:
  items: <n>
  by-interest: { high: <n>, medium: <n>, low: <n> }
  by-remediation: { S: <n>, M: <n>, L: <n> }
```

## 6. Example

For the `notes-cli` record in [[audit-record]] §8, whose History covers 12 months, run with the
structure, health and duplication lenses.

````markdown
---
type: audit-lens
audit-id: 2026-11-12-a1b2c3d
lens: protocol/audit-lens-debt
lens-version: 0.1.0
needs: { depth: file, history: true }
---

## Criteria
```yaml
criteria:
  - { id: D1, source: "Hotspot analysis (Tornhill)", rule: "Hotspots have no very-high functions and no open structure or duplication finding" }
  - { id: D3, source: "protocol/audit-lens-debt", rule: "Every debt marker has a reason and a backlog entry" }
  - { id: D4, source: "protocol/audit-lens-debt", rule: "Dependencies are on supported versions" }
```

## Results
```yaml
hotspots-method: { window: "2025-11-12..a1b2c3d", score: "commits/max × lines/max", lines-from: lens-health, top: 10 }
hotspots:
  - { unit: src/notes/storage/db.py, commits: 23, lines: 412, score: 1.00, rank: 1 }
  - { unit: src/notes/cli/commands.py, commits: 17, lines: 260, score: 0.47, rank: 2 }
ledger:
  - { id: T1, units: [cli, storage], kind: design, what: "cli and storage depend on each other", from: "lens-structure.md F1", finding: null, remediation: M, interest: high }
  - { id: T2, units: [src/notes/storage/db.py], kind: code, what: "NoteStore.migrate is 94 lines", from: "lens-health.md F2", finding: null, remediation: S, interest: high }
  - { id: T3, units: [src/notes/cli/commands.py, src/notes/cli/export.py], kind: code, what: "Formatting copied in two files", from: "lens-duplication.md F1", finding: null, remediation: S, interest: high }
  - { id: T4, units: [src/notes/storage/db.py], kind: marker, what: "TODO with no reason: 'fix this properly'", from: null, finding: F1, remediation: S, interest: high }
pay-first: [T2, T3, T4, T1]
totals: { items: 4, by-interest: { high: 4, medium: 0, low: 0 }, by-remediation: { S: 3, M: 1, L: 0 } }
```

## Findings
```yaml
findings:
  - { id: F1, units: [src/notes/storage/db.py], criterion: D3, what: "TODO with no reason or backlog id", evidence: "src/notes/storage/db.py:203", confidence: CONFIRMED, severity: Nitpick, likelihood: Frequent, blocks: false, backlog: "not recorded: fixed with WH-35 (same function)" }
```

## Gaps
```yaml
gaps:
  - { id: G1, area: "D2 weaknesses", reason: "Only the top 2 hotspots were read", impact: "Weaknesses in other files are not in the ledger" }
```
````

## 7. Done when

- [ ] `core.md` has History, and `hotspots-method` states the window and scoring.
- [ ] Every other lens's debt finding is in the ledger with `from:`, and none was re-recorded as a new
  finding.
- [ ] Every ledger item has units, kind, remediation and interest, and interest follows History.
- [ ] `pay-first` follows the ordering in step 6.
- [ ] Every new item has a finding with a criterion, triage labels and a backlog id, or a reason it has
  none.
- [ ] The marker search and any dependency check are in the record's `measures`.

## Changelog

### [Unreleased]

### [0.1.0] - 2026-11-13
#### Added
- First draft.
