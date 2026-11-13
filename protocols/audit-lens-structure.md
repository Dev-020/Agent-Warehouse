---
id: protocol/audit-lens-structure
version: 0.1.0
status: draft
summary: Audit lens for how a codebase is arranged — its layers, the boundaries the core doesn't show, its most central units and its dependency cycles, with findings for cycles and dependencies that go the wrong way.
applies-to: [codebase]
settings: {}
requires: [protocol/codebase-audit@0.1]
replaces: null
---

# Structure Lens

A lens for [[codebase-audit]] (`protocol/codebase-audit`). It reads the audit's core and writes
`lens-structure.md` in the record, following [[audit-record]] §5 and the lens contract (§6).

## 1. Purpose

**The question it answers:** how is the codebase arranged? Which layers does it have, which
groupings cut across its subsystems, which units everything depends on, and where do dependencies go
round in circles or the wrong way?

Use it for a codemap (`architecture/codemap` reads its results), before a refactor or a split, and
whenever someone new needs the big picture. It mostly describes; its findings come from two default
criteria plus any rules the project declares.

## 2. What it needs from the core

| Need | Value |
|---|---|
| Depth | `module` at least; `file` for central units at file level (recommended) |
| Relations | `imports` and `calls`; `configures`, `sends`/`receives` and `reads`/`writes` between units count when present |
| History | not needed |

The lens file records this as `needs: { depth: module, history: false }`, or `depth: file` when the
core goes that deep. If the core is shallower than `module`, deepen it first ([[codebase-audit]] Step 8).

## 3. Criteria

Write these into the Criteria section. Keep the defaults unless the initiator drops one, and add the
project's own rules with their source.

| Id | Source | Rule | When |
|---|---|---|---|
| S1 | Acyclic Dependencies Principle (R. C. Martin); ISO/IEC 25010 maintainability: modularity | No dependency cycles between subsystems or between modules | Always |
| S2 | Layered architecture; ISO/IEC 5055 lists layer-skipping calls as a maintainability weakness | A unit depends only on units in its own layer or a lower one | Only when layers are `declared`, or `inferred` and confirmed by the initiator |
| S3+ | The project (architecture doc, ADR, import-linter or dependency-cruiser config) | The project's own rule, quoted in one line | When the project has such rules |

A project with no layers and no rules still gets S1.

## 4. The steps

1. **Check the needs** (§2) against `core.md`. Deepen the core if needed.
2. **Set the criteria** (§3). Look for declared rules first: architecture docs, ADRs, dependency-rule
   configs. Quote each one as a criterion with its source.
3. **Layers.**
   - If the project declares layers, map its units onto them: `source: declared`, with the document as
     evidence.
   - Otherwise infer them from the direction of the relations: order the subsystems so that as many
     relations as possible point downward. Mark them `source: inferred`, `confidence: INFERRED`, and
     ask the initiator to confirm when the result will be used (e.g. for a codemap).
   - Rank 1 is the top layer, closest to the user or the entry points. Higher numbers are lower layers.
   - No layering is a valid result: write `layers: []` and say so in the Summary line of the results.
4. **Boundaries.** List only groupings **the core doesn't have**:
   - `process`: units that run in a separate process or executable (separate entry points, workers);
   - `deployable`: units shipped or deployed separately (packages, containers, plugins);
   - `ownership`: units owned by different people or teams (`CODEOWNERS`, the project's docs);
   - `other`: say what in `note`.
   Never repeat the core's subsystems as boundaries; the core's `parent` field already gives them.
5. **Central units.** At each counted level (default: `subsystem` and the core's deepest level up to
   `file`), count for every unit:
   - **fan-in:** distinct units with a relation *to* it;
   - **fan-out:** distinct units it has a relation *to*.
   Count only the relation types in §2, between in-scope units at the same level. Leave out `tests`
   relations and outside things. List the top 5 per level by fan-in, plus any unit in the top 5 by
   fan-out. Record the counting rules under `counting` so a later audit counts the same way.
6. **Cycles.** Find every strongly connected group of units at subsystem and module level (and file
   level when the core goes that deep), using the counted relation types. A tool may do this; add it to
   the record's `measures` with `used-by: [protocol/audit-lens-structure]`.
7. **Findings.**
   - Each cycle breaks S1. Cite the relations that close it as evidence.
   - Each relation from a lower layer to a higher one breaks S2. Skipping a layer breaks S2 only if the
     project's rule says layers must not be skipped (then it is an S3+ rule).
   - Each break of a project rule cites that rule.
   - Label each finding through [[issue-triage]]. Starting points: a cycle between subsystems is
     `Major`; a cycle inside one subsystem, or a single upward dependency, is `Minor`. Adjust for the
     project.
8. **Gaps.** In the [[audit-record]] §4.5 format, list what couldn't be judged: dynamic wiring the core marked `INFERRED`, layers left
   unconfirmed, levels not counted.

## 5. Results format

```yaml
layers:                           # [] when the codebase has no layering
  - { name: <name>, rank: <1 = top>, units: [<core unit ids>],
      source: declared | inferred, evidence: "<path:line or doc>", confidence: CONFIRMED | INFERRED }

boundaries:                       # only groupings the core lacks; [] if none
  - { id: B<n>, kind: process | deployable | ownership | other, name: "<name>",
      units: [<core unit ids>], evidence: "<path:line>", confidence: CONFIRMED | INFERRED, note: null }

counting:                         # how central-units were counted, for repeatable re-audits
  levels: [subsystem, file]
  types: [imports, calls, configures, sends, receives, reads, writes]
  excludes: [tests, outside]
  top: 5

central-units:
  - { unit: <core unit id>, level: <kind>, fan-in: <n>, fan-out: <n> }

cycles:                           # [] if none
  - { id: Y<n>, level: <kind>, units: [<core unit ids>], relations: [<core relation ids>] }
```

Every unit id is a core unit id and every relation id is a core relation id (lens contract rule 1).

## 6. Example

For the `notes-cli` record in [[audit-record]] §8, deepened with two more relations (`R6`: `storage`
imports `cli` for its formatting helpers; `R7`: `src/notes/storage/db.py` imports
`src/notes/cli/format.py`). The project's README declares two layers, interface over data.

````markdown
---
type: audit-lens
audit-id: 2026-11-12-a1b2c3d
lens: protocol/audit-lens-structure
lens-version: 0.1.0
needs: { depth: file, history: false }
---

## Criteria
```yaml
criteria:
  - { id: S1, source: "Acyclic Dependencies Principle; ISO/IEC 25010 modularity", rule: "No dependency cycles between subsystems or modules" }
  - { id: S2, source: "Layered architecture; README.md:12-16", rule: "A unit depends only on its own layer or a lower one" }
```

## Results
```yaml
layers:
  - { name: interface, rank: 1, units: [cli], source: declared, evidence: "README.md:14", confidence: CONFIRMED }
  - { name: data, rank: 2, units: [storage], source: declared, evidence: "README.md:15", confidence: CONFIRMED }
boundaries: []
counting: { levels: [subsystem, file], types: [imports, calls, configures, sends, receives, reads, writes], excludes: [tests, outside], top: 5 }
central-units:
  - { unit: storage, level: subsystem, fan-in: 1, fan-out: 1 }
  - { unit: src/notes/storage/db.py, level: file, fan-in: 1, fan-out: 1 }
cycles:
  - { id: Y1, level: subsystem, units: [cli, storage], relations: [R2, R6] }
```

## Findings
```yaml
findings:
  - id: F1
    units: [storage, cli]
    criterion: S1
    what: "cli and storage depend on each other: storage imports cli's formatting helpers"
    evidence: "R2 (src/notes/cli/commands.py:42), R6 (src/notes/storage/db.py:5)"
    confidence: CONFIRMED
    severity: Major
    likelihood: Occasional
    blocks: false
    backlog: WH-32
  - id: F2
    units: [src/notes/storage/db.py]
    criterion: S2
    what: "The data layer imports from the interface layer"
    evidence: "R7 (src/notes/storage/db.py:5)"
    confidence: CONFIRMED
    severity: Minor
    likelihood: Occasional
    blocks: false
    backlog: "not recorded: same fix as F1 (WH-32)"
```

## Gaps
```yaml
gaps:
  - { id: G1, area: "src/notes/plugins/", reason: "Plugins load by name from config at runtime", impact: "Plugin relations are not counted in central units or cycles" }
```
````

## 7. Done when

- [ ] The criteria list S1, S2 only if layers are declared or confirmed, and every project rule with its
  source.
- [ ] Every unit and relation id in the results exists in `core.md`.
- [ ] No boundary repeats a core subsystem.
- [ ] `counting` is filled in, and central units follow it.
- [ ] Every cycle has a finding that cites S1, and every upward dependency has one that cites S2.
- [ ] Every finding has triage labels and a backlog id or a reason it has none.
- [ ] Tools used are in the record's `measures` with `used-by` naming this lens.

## Changelog

### [Unreleased]
#### Added
- First draft.
