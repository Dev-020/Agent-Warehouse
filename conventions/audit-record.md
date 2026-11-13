---
id: convention/audit-record
version: 0.1.0
status: draft
summary: The record a codebase audit writes — one dated folder per run, pinned to a commit, with a header, a purpose-agnostic core of units and relations, and one section per lens that points into the core.
applies-to: [codebase]
settings:
  audit_folder:
    description: "Folder where audit records are kept, one subfolder per run"
    default: "docs/audits"
requires: []
replaces: null
---

# Audit Record Convention

The format of the record a codebase audit writes. How to run the audit is in [[codebase-audit]]
(`protocol/codebase-audit`); this convention says only what the record holds and how it is laid out.

The record has two layers:
- **The core** says what the codebase *is*: its units, how they relate, and what they use outside the
  code. It is the same whatever the audit is for.
- **Lenses** say what the audit *found* for one purpose (structure, health, debt, duplication, UI …).
  Each lens is its own item, and a project pulls only the ones it needs. A lens reads the core and never
  redefines it.

This split follows architecture reconstruction practice: facts extracted from the code (the core) are
turned into the views a given problem needs (the lenses).

## 1. Where records live

One folder per audit run, under {{audit_folder}}. History is kept: a new run never overwrites an old one.

```
{{audit_folder}}/
├── 2026-11-12-a1b2c3d/          <date>-<short commit>, one run
│   ├── 00_AUDIT.md              header, summary, verification, links
│   ├── core.md                  units, relations, outside things, history, gaps
│   ├── lens-structure.md        one file per lens run
│   └── lens-debt.md
└── 2026-12-02-f9e8d7c/          a later run (full or scoped)
```

- **Folder name:** `<YYYY-MM-DD>-<short commit>`, where the short commit is the first 7 characters of the
  audited commit. A second run on the same day and commit adds `-2`, `-3`.
- The folder name is the record's **audit id**.
- **Lens file name:** `lens-<name>.md`, where `<name>` is the lens item's name without the
  `audit-lens-` prefix (`protocol/audit-lens-debt` → `lens-debt.md`).

## 2. Format

Markdown with YAML. Each file has YAML frontmatter, and its data sections are fenced ` ```yaml ` blocks
under fixed headings, so people can read the file and tools can parse it. Prose may sit between blocks;
it is never the only place a fact is written.

Field rules that apply everywhere:
- **Evidence** is `path:line` or `path:start-end`, relative to the repository root, at the audited
  commit. For a fact from a tool, it is the measure id (§3.4) and the output file or command.
- **Confidence** is `CONFIRMED` (checked directly: code read at the evidence, tool output, a test run) or
  `INFERRED` (concluded from names, layout, docs or partial reading). Never leave it out.
- **Ids** are unique within a record. Unit ids stay the same from one record to the next while the unit
  exists (§4.1), so records can be compared and a codemap can be rebuilt from them.
- `null` means "not known"; an empty list `[]` means "checked, there are none".

## 3. `00_AUDIT.md`: the header

Frontmatter holds the header. The body holds the summary, the verification and the links.

### 3.1. Header fields

```yaml
---
type: audit
audit-id: 2026-11-12-a1b2c3d
repo: "notes-cli"                 # name, and remote URL if there is one
commit: a1b2c3d4e5f60718293a4b5c6d7e8f9012345678   # full SHA audited
branch: main
date: 2026-11-12
kind: full                        # full | scoped
previous: null                    # audit id this run builds on; required when kind: scoped
initiator:
  who: "the user"                 # who asked for the audit
  purpose: "Build a codemap before the storage rewrite"   # why, in one line
auditor:
  who: "Claude Code (claude-opus-5-5), orchestrator + 2 subagents"   # who or what did the work
scope:
  include: ["src/", "tests/"]
  exclude: ["vendor/", "docs/"]
depth: file                       # deepest unit kind listed: system | subsystem | module | file | symbol
history: { since: 2026-05-12, until: a1b2c3d }   # window of git history used, or null
lenses:
  - id: protocol/audit-lens-structure
    version: 0.1.0
    file: lens-structure.md
measures:                         # every tool whose output is evidence (§3.4)
  - id: M1
    tool: "pydeps"
    version: "1.12.20"
    command: "pydeps src/notes --show-deps --no-output"
    used-by: [core]
status: complete                  # complete | partial (say what is missing in Gaps)
---
```

### 3.2. Initiator and auditor

The **initiator** is who asked for the audit and why; the **auditor** is who or what did it. They are
kept apart on purpose (IEEE 1028 does the same): the purpose decides the lenses, the criteria and the
depth, and a reader needs to know it to judge whether the record fits their own question. When an agent
audits at the user's request, the initiator is the user.

### 3.3. Scope and depth

`scope` lists what was included and excluded, as paths or globs. `depth` is the deepest unit kind the
core lists (§4.1). A lens that needs more depth than the core has deepens the core first (see the lens
contract, §6).

### 3.4. Measures

Every tool whose output is used as evidence is listed once with its version and the exact command or
settings. This is what makes a later run comparable: a scoped re-audit uses the same measures, or says
why not. Facts found by reading code need no measure; their evidence is the `path:line`.

### 3.5. Body sections

````markdown
## Summary
Three to ten lines: what the codebase is, what each lens found, what was not covered.

## Verification
```yaml
inferred-sampled:                 # INFERRED relations re-checked (codebase-audit step 9)
  total-inferred: 12
  sampled: 5
  upheld: 4
  changed: [R7]                   # ids whose confidence or content changed
evidence-missing: []              # relation or finding ids with no evidence (must be empty)
```

## Links
- Core: [[core]]
- Lenses: [[lens-structure]]
- Previous record: none
- Backlog entries opened: WH-31, WH-32
````

## 4. `core.md`: what the codebase is

Frontmatter: `type: audit-core` and `audit-id`. Then five sections, each one YAML block. History is
optional; the others are always present.

### 4.1. Units

The parts of the codebase, from the whole system down to the record's `depth`.

```yaml
units:
  - id: notes-cli                 # stable id (rules below)
    kind: system                  # system | subsystem | module | file | symbol
    path: "."
    parent: null
    purpose: "Command-line note taker with a SQLite store"
    entry: "src/notes/__main__.py:1"    # entry point, or null if not one
    confidence: CONFIRMED
```

| Kind | Means | Example |
|---|---|---|
| `system` | The whole codebase in scope. Exactly one. | the repo |
| `subsystem` | A part that could be explained on its own: a service, an app, a package with its own job. | `cli`, `storage` |
| `module` | A folder or package inside a subsystem. | `src/notes/storage/` |
| `file` | One source file. | `src/notes/storage/db.py` |
| `symbol` | A class, function or other named item that matters on its own. | `db.py:NoteStore` |

**Id rules:**
- `system` and `subsystem` ids are short names chosen by the auditor (`storage`).
- `module` and `file` ids are their path from the repository root (`src/notes/storage/db.py`).
- `symbol` ids are `<file path>:<name>` (`src/notes/storage/db.py:NoteStore`).
- A unit keeps its id in later records while it exists. A renamed or moved unit gets its new id and a
  `was: <old id>` field, so the history can be followed.

### 4.2. Relations

How units interact.

```yaml
relations:
  - id: R1
    from: cli
    to: storage
    type: calls
    evidence: "src/notes/cli/commands.py:42"
    confidence: CONFIRMED
    note: null                    # optional, one line
```

`type` is one of:

| Type | Means |
|---|---|
| `imports` | Source-level import or include. |
| `calls` | Runtime call: function, method, CLI, subprocess. |
| `reads` / `writes` | Reads from or writes to an outside thing or another unit's data. |
| `sends` / `receives` | Messages, events, queues, HTTP requests between units. |
| `configures` | Sets up or injects another unit (DI, plugin registration, config loading). |
| `tests` | A test unit exercising another unit. |
| `uses` | Depends on an outside thing (§4.3) in a way none of the above covers. |

Containment is not a relation: it is the unit's `parent`. A new type needs a MINOR release of this
convention; until then, use the nearest type and say what it is in `note`.

### 4.3. Outside things

What the code relies on that isn't part of it.

```yaml
outside:
  - id: X1
    kind: data-store              # data-store | service | library | config | env-var | file | tool
    name: "SQLite database"
    version: null                 # pinned version if one is declared, else null
    used-by: [storage]
    evidence: "src/notes/storage/db.py:12"
    confidence: CONFIRMED
```

Libraries are listed when a unit depends on them directly; their declared version comes from the
manifest or lock file named in `evidence`.

### 4.4. History (optional)

How often each unit changed, from git history over the window in the header. Present when a lens
declares it needs history (§6) or the initiator asks for it.

```yaml
history:
  window: { since: 2026-05-12, until: a1b2c3d }
  measure: M2                     # the git command used, listed in the header's measures
  units:
    - unit: src/notes/storage/db.py
      commits: 23
      last-changed: 2026-11-03
```

### 4.5. Gaps

What the core does not cover, and why. A gap is not a failure; an unlisted gap is.

```yaml
gaps:
  - id: G1
    area: "src/notes/sync/"
    reason: "Generated code from a protobuf schema; read the schema, not the output"
    impact: "Relations into sync are INFERRED from the schema"
```

## 5. `lens-<name>.md`: what one lens found

Frontmatter names the lens and what it relied on:

```yaml
---
type: audit-lens
audit-id: 2026-11-12-a1b2c3d
lens: protocol/audit-lens-structure
lens-version: 0.1.0
needs: { depth: file, history: false }
---
```

Then four sections:

| Section | Holds |
|---|---|
| **Criteria** | What the lens judges against. Each criterion has an `id`, a `source` (a standard, a project rule, or the lens itself) and the `rule` in one line. A lens that only describes, with nothing to judge against, says `criteria: []`. |
| **Results** | The lens's own data, in the YAML format its lens item defines. Every entry points at core unit ids. |
| **Findings** | Problems, each citing a criterion, with triage labels and a backlog id (§5.1). |
| **Gaps** | What this lens did not cover, as in §4.5. |

### 5.1. Findings

```yaml
findings:
  - id: F1
    units: [src/notes/storage/db.py]
    criterion: C2
    what: "db.py mixes SQL, migrations and note formatting (412 lines)"
    evidence: "src/notes/storage/db.py:1-412"
    confidence: CONFIRMED
    severity: Minor               # Nitpick | Minor | Major | Critical (convention/backlog §4.4)
    likelihood: Occasional        # Frequent | Occasional | Rare | Improbable
    blocks: false
    backlog: WH-31                # backlog id, or "not recorded: <reason>"
```

Findings are labelled and recorded through [[issue-triage]] (`protocol/issue-triage`). The record keeps
the backlog id; the backlog entry holds the discussion and the fix.

## 6. The lens contract

Every lens item, and every lens file it produces, follows these rules. They are what lets new lenses be
added without changing the core.

1. **Point, don't redefine.** Lens entries refer to core unit ids. A lens never lists its own units. If
   it needs a unit the core doesn't have, the core is deepened first (a new unit in `core.md`), then the
   lens points at it.
2. **Name itself.** The lens file records its lens id and version.
3. **Name its criteria.** Every criterion has a source and a rule; every finding cites one.
4. **Declare its needs.** The lens item states the core depth it needs and whether it needs history; the
   lens file records them in `needs`. The protocol checks them before the lens runs.
5. **Triage findings.** Findings carry severity, likelihood and blocks, and go to the backlog through
   [[issue-triage]]; the lens file keeps the backlog id.
6. **Use the record's measures.** A tool the lens relies on is added to the header's `measures`, with
   `used-by` naming the lens.
7. **Define its results format.** The lens item defines the YAML of its Results section, with an example.

## 7. Scoped records

A scoped re-audit (`kind: scoped`) re-examines only what changed since `previous`. Its record is still
**complete on its own**: units and relations that didn't change are carried forward from the previous
record with `carried: <previous audit id>`, so a reader or a codemap needs only the latest record.

```yaml
  - id: src/notes/cli/commands.py
    kind: file
    ...
    carried: 2026-11-12-a1b2c3d   # unchanged since that record; not re-checked
```

Removed units are listed once under Gaps with `reason: "removed since <previous>"` and are not carried
further.

## 8. Example

A small, complete record for a made-up repository, `notes-cli`: the core plus one lens. The structure
lens's Results format here is illustrative; `protocol/audit-lens-structure` defines the real one.

**`docs/audits/2026-11-12-a1b2c3d/00_AUDIT.md`**

````markdown
---
type: audit
audit-id: 2026-11-12-a1b2c3d
repo: "notes-cli"
commit: a1b2c3d4e5f60718293a4b5c6d7e8f9012345678
branch: main
date: 2026-11-12
kind: full
previous: null
initiator: { who: "the user", purpose: "Build a codemap before the storage rewrite" }
auditor: { who: "Claude Code (claude-opus-5-5), single session" }
scope: { include: ["src/", "tests/"], exclude: [] }
depth: file
history: null
lenses:
  - { id: protocol/audit-lens-structure, version: 0.1.0, file: lens-structure.md }
measures:
  - { id: M1, tool: pydeps, version: "1.12.20", command: "pydeps src/notes --show-deps --no-output", used-by: [core] }
status: complete
---

## Summary
notes-cli is a Python CLI with two subsystems: `cli` (argument parsing and commands) and `storage`
(a SQLite note store). `cli` calls `storage`; nothing calls back. The structure lens found one Minor
finding: `storage/db.py` holds three jobs. No gaps.

## Verification
```yaml
inferred-sampled: { total-inferred: 1, sampled: 1, upheld: 1, changed: [] }
evidence-missing: []
```

## Links
- Core: [[core]] · Lens: [[lens-structure]] · Previous: none · Backlog: WH-31
````

**`core.md`**

````markdown
---
type: audit-core
audit-id: 2026-11-12-a1b2c3d
---

## Units
```yaml
units:
  - { id: notes-cli, kind: system, path: ".", parent: null, purpose: "CLI note taker with a SQLite store", entry: "src/notes/__main__.py:1", confidence: CONFIRMED }
  - { id: cli, kind: subsystem, path: "src/notes/cli/", parent: notes-cli, purpose: "Parses arguments and runs commands", entry: null, confidence: CONFIRMED }
  - { id: storage, kind: subsystem, path: "src/notes/storage/", parent: notes-cli, purpose: "Stores and queries notes in SQLite", entry: null, confidence: CONFIRMED }
  - { id: src/notes/cli/commands.py, kind: file, path: "src/notes/cli/commands.py", parent: cli, purpose: "One function per command", entry: null, confidence: CONFIRMED }
  - { id: src/notes/storage/db.py, kind: file, path: "src/notes/storage/db.py", parent: storage, purpose: "NoteStore class, schema migrations, note formatting", entry: null, confidence: CONFIRMED }
  - { id: tests/test_db.py, kind: file, path: "tests/test_db.py", parent: notes-cli, purpose: "Tests for NoteStore", entry: null, confidence: CONFIRMED }
```

## Relations
```yaml
relations:
  - { id: R1, from: src/notes/cli/commands.py, to: src/notes/storage/db.py, type: imports, evidence: "src/notes/cli/commands.py:3", confidence: CONFIRMED }
  - { id: R2, from: cli, to: storage, type: calls, evidence: "src/notes/cli/commands.py:42", confidence: CONFIRMED }
  - { id: R3, from: storage, to: X1, type: writes, evidence: "src/notes/storage/db.py:88", confidence: CONFIRMED }
  - { id: R4, from: tests/test_db.py, to: src/notes/storage/db.py, type: tests, evidence: "tests/test_db.py:1-60", confidence: CONFIRMED }
  - { id: R5, from: cli, to: X2, type: reads, evidence: "src/notes/cli/config.py:9", confidence: INFERRED, note: "Path built at runtime; read from the default only" }
```

## Outside things
```yaml
outside:
  - { id: X1, kind: data-store, name: "SQLite database file", version: null, used-by: [storage], evidence: "src/notes/storage/db.py:12", confidence: CONFIRMED }
  - { id: X2, kind: config, name: "~/.notes.toml", version: null, used-by: [cli], evidence: "src/notes/cli/config.py:9", confidence: CONFIRMED }
```

## Gaps
```yaml
gaps: []
```
````

**`lens-structure.md`**

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
  - { id: C1, source: "ISO/IEC 25010 maintainability: modularity", rule: "Dependencies between subsystems go one way" }
  - { id: C2, source: "ISO/IEC 25010 maintainability: modularity", rule: "A file has one job" }
```

## Results
```yaml
layers:
  - { name: interface, units: [cli] }
  - { name: data, units: [storage] }
central-units: [src/notes/storage/db.py]   # most incoming relations
```

## Findings
```yaml
findings:
  - id: F1
    units: [src/notes/storage/db.py]
    criterion: C2
    what: "db.py holds the store, the migrations and note formatting"
    evidence: "src/notes/storage/db.py:1-412"
    confidence: CONFIRMED
    severity: Minor
    likelihood: Occasional
    blocks: false
    backlog: WH-31
```

## Gaps
```yaml
gaps: []
```
````

## Changelog

### [Unreleased]

### [0.1.0] - 2026-11-13
#### Added
- First draft.
