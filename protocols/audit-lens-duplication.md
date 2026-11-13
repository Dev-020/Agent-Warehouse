---
id: protocol/audit-lens-duplication
version: 0.1.0
status: draft
summary: Audit lens for repeated code — groups of copied or near-copied code with every location, the share of code that is duplicated per unit, and findings for large groups and for too much duplication.
applies-to: [codebase]
settings: {}
requires: [protocol/codebase-audit@0.1]
replaces: null
---

# Duplication Lens

A lens for [[codebase-audit]] (`protocol/codebase-audit`). It reads the audit's core and writes
`lens-duplication.md` in the record, following [[audit-record]] §5 and the lens contract (§6).

## 1. Purpose

**The question it answers:** where is code repeated, and how much of the codebase is repetition?

Duplicated code makes a system larger than it needs to be, and a fix made in one copy is easily
missed in the others. This lens finds the groups of copies and measures how much of each unit is
duplicated. It is the only lens that measures duplication: the health lens and the debt lens cite its
results instead of measuring it again, and the UI lens links components to its groups.

## 2. What it needs from the core

| Need | Value |
|---|---|
| Depth | `file`. Copies are located by `path:line` range inside a file unit. |
| Relations | none |
| History | not needed |

The lens file records `needs: { depth: file, history: false }`.

## 3. Criteria

Defaults. The project may change the numbers; the lens file records the values used.

| Id | Source | Rule | Default |
|---|---|---|---|
| P1 | SIG maintainability model (Heitlager, Kuipers, Visser 2007): "a well-designed system should not have more than 5% code duplication" | Duplicated production code is at most the limit, for the system and for each subsystem | 5% |
| P2 | The lens | No group of copies is at least the reporting size, or has at least the reporting number of copies | 12 lines, or 3 copies |

The 5% limit is a published threshold. The reporting size in P2 is this lens's own default, chosen so
small, common repeats don't flood the backlog. Smaller groups are still listed in the results.

## 4. The steps

1. **Check the needs** (§2) against `core.md`. Deepen the core to `file` if needed.
2. **Set the method.** Write it under `method` in the results so a later audit measures the same way:
   - **Minimum size:** 6 lines (SIG 2007: "equal code blocks of at least 6 lines").
   - **Clone types** (Roy, Cordy and Koschke 2009):

     | Type | Means | Default |
     |---|---|---|
     | 1 | Identical apart from whitespace, layout and comments | Measured |
     | 2 | Identical structure; names, literals or types differ | Measured |
     | 3 | Copies with statements added, removed or changed | Optional: needs a tool that supports it, or reading by hand |
     | 4 | Different code doing the same thing | Not measured; list it under Gaps if it matters |

   - **Ignored:** blank lines, comments and leading whitespace.
   - **Left out:** generated code, vendored code, lock files and data files. Name each left-out path.
   - **Test code** is measured separately (`code: test`). Repetition in tests is common and is often
     accepted; it doesn't count toward P1.
3. **Run the detector.** Use a clone detector for the project's languages (for example `jscpd`,
   PMD CPD or `simian`), set to the method. Add it to the record's `measures` with its version, the
   exact command and `used-by: [protocol/audit-lens-duplication]`. If no tool can run, compare by hand
   only the areas the initiator names, and list the rest under Gaps.
4. **Write the groups.** One entry per group of copies, with every copy's file unit and line range.
   Check a sample of groups by reading the code (at least 5, or all if there are fewer): a detector can
   match boilerplate that isn't real duplication, such as license headers or import blocks. Leave those
   out and say so in `method.excluded-patterns`.
5. **Compute the totals.** For the system and each subsystem, separately for production and test code:
   - **lines:** code lines in scope (non-blank, non-comment);
   - **duplicated:** lines that belong to any copy in a group, all copies counted, including the first;
   - **percent:** duplicated ÷ lines.
   Give a `rating` on SIG's 2007 scale: `++` 0–3%, `+` 3–5%, `o` 5–10%, `-` 10–20%, `--` 20–100%.
6. **Findings.**
   - A system or subsystem over the P1 limit breaks P1. Point the finding at that unit and name its
     largest groups.
   - A group at or above the P2 reporting size or number of copies breaks P2. One finding per group.
   - Label each finding through [[issue-triage]]. Starting points: a group of 3 or more copies is
     `Minor`, `Frequent` (a fix must be made in every copy); over 20% in a subsystem is `Major` (SIG 2007:
     past 20% "source code erosion is out of control"). Adjust for the project.
   - Don't record one finding per group when the groups share a cause (one copied module, one
     generator pattern). Record the cause once and list the groups in it.
7. **Gaps.** In the [[audit-record]] §4.5 format: languages the detector doesn't support, Type 3 or 4
   clones not measured, areas left out.

## 5. Results format

```yaml
method:
  min-lines: 6
  types: [1, 2]
  ignores: [blank lines, comments, leading whitespace]
  left-out: ["<path>", ...]              # generated, vendored, data
  excluded-patterns: ["<what>", ...]     # boilerplate matches removed after review
  measure: M<n>                          # the detector, in the header's measures
  reporting: { min-lines: 12, min-copies: 3 }   # P2 values used
  limit: 5                               # P1 value used, in percent

totals:
  - { unit: <core unit id>, code: production | test, lines: <n>, duplicated: <n>, percent: <n.n>, rating: "++" | "+" | "o" | "-" | "--" }

groups:
  - id: D<n>
    type: 1 | 2 | 3
    lines: <lines per copy>
    code: production | test
    copies:
      - { unit: <core file unit id>, at: "<path:start-end>" }
    note: null                            # optional, e.g. what the copied code does
```

## 6. Example

For the `notes-cli` record in [[audit-record]] §8, with a third file unit,
`src/notes/cli/export.py`.

````markdown
---
type: audit-lens
audit-id: 2026-11-12-a1b2c3d
lens: protocol/audit-lens-duplication
lens-version: 0.1.0
needs: { depth: file, history: false }
---

## Criteria
```yaml
criteria:
  - { id: P1, source: "SIG maintainability model (Heitlager et al. 2007)", rule: "Duplicated production code is at most 5%, per system and subsystem" }
  - { id: P2, source: "protocol/audit-lens-duplication", rule: "No group of 12+ lines or 3+ copies" }
```

## Results
```yaml
method:
  min-lines: 6
  types: [1, 2]
  ignores: [blank lines, comments, leading whitespace]
  left-out: ["src/notes/storage/migrations/"]
  excluded-patterns: ["import blocks"]
  measure: M3
  reporting: { min-lines: 12, min-copies: 3 }
  limit: 5
totals:
  - { unit: notes-cli, code: production, lines: 1840, duplicated: 64, percent: 3.5, rating: "+" }
  - { unit: cli, code: production, lines: 610, duplicated: 46, percent: 7.5, rating: "o" }
  - { unit: storage, code: production, lines: 1230, duplicated: 18, percent: 1.5, rating: "++" }
  - { unit: notes-cli, code: test, lines: 420, duplicated: 60, percent: 14.3, rating: "-" }
groups:
  - id: D1
    type: 2
    lines: 23
    code: production
    copies:
      - { unit: src/notes/cli/commands.py, at: "src/notes/cli/commands.py:80-102" }
      - { unit: src/notes/cli/export.py, at: "src/notes/cli/export.py:15-37" }
    note: "Note-to-text formatting, with different variable names"
```

## Findings
```yaml
findings:
  - id: F1
    units: [cli]
    criterion: P1
    what: "cli is 7.5% duplicated; most of it is D1"
    evidence: "D1 (src/notes/cli/commands.py:80-102, src/notes/cli/export.py:15-37)"
    confidence: CONFIRMED
    severity: Minor
    likelihood: Occasional
    blocks: false
    backlog: WH-33
```

## Gaps
```yaml
gaps:
  - { id: G1, area: "whole repo", reason: "Type 3 and 4 clones not measured", impact: "Near-copies with edited lines may be missed" }
```
````

F1 covers D1 too: they share one cause, so D1 has no finding of its own (step 6).

## 7. Done when

- [ ] `method` is filled in, and the detector is in the record's `measures`.
- [ ] Every copy points at a core file unit with a line range.
- [ ] A sample of groups was checked by reading the code, and false matches were removed.
- [ ] Totals cover the system and each subsystem, with production and test code apart.
- [ ] Every unit over the P1 limit and every group at the P2 size has a finding, or is covered by one
  that names its shared cause.
- [ ] Every finding has triage labels and a backlog id, or a reason it has none.

## Changelog

### [Unreleased]
#### Added
- First draft.
