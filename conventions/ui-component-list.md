---
id: convention/ui-component-list
version: 0.1.0
status: draft
summary: A project's list of UI components — built ones from the latest audit record's UI lens, planned ones by hand — with where each is used, its variants, states and raw style values, and, when the project has a design system, how each compares with it.
applies-to: [codebase]
settings:
  component_list_file:
    description: "Where the component list is written in the project"
    default: "docs/COMPONENTS.md"
requires: [convention/audit-record@0.1, protocol/audit-lens-ui@0.1]
replaces: null
---

# UI Component List

The list of every component a project's UI is built from, or will be. Components that exist in code
come from the latest audit record's UI lens ([[audit-lens-ui]], [[audit-record]]): the record holds the
evidence, the list presents it. Components not built yet are written by hand. A design system
([[design-system]], `convention/design-system`) is **optional**: when the project has one, the list
also shows how each component compares with it.

## 1. What it is for, and when to have one

People and agents read the list to find a component before making a new one, to see where a change to
a component reaches, and to know which components are planned, specified, built or drifting.

| Have one when | Skip it when |
|---|---|
| The UI has more than a handful of components, or more than one screen | One screen with a few framework widgets |
| More than one person or agent builds UI | The UI is throwaway |
| A design system is planned or kept (the list feeds design-system §3.2 and §7) | The project has no UI; it never pulls this item |

How it relates to the other items:

| Item | Required? | What the list takes from it |
|---|---|---|
| `convention/audit-record` | yes | Unit ids, paths and purposes; render relations; the record's header and gaps |
| `protocol/audit-lens-ui` | yes | The component entries, their fields and the raw values |
| `convention/design-system` | **no** | The specs to compare with. Without one, the list still works: it is the inventory. |

The design system and the audit can be used without the list. The list can't be used without the
audit; a project that finds its components another way keeps its own list instead of pulling this item.

## 2. Two kinds of entry

| Kind | Where it comes from | Fields | Kept by |
|---|---|---|---|
| **Built** | A component in the latest record's UI lens results | The lens's fields (§4) | Rebuilt from the record (§5) |
| **Planned** | Written by hand before the code exists, or from a design system spec that has no code yet | Only the fields that need no code (§4) | Kept by hand; carried over on every rebuild |

A new project with no code has only planned entries and no record. An existing project starts with
built entries from its first audit and adds planned ones as screens are designed. When a planned
component is built, the next audit finds it and the entry becomes built, keeping its id (§5 step 4).

## 3. Status

Each entry has one status. It says how the component's code and its design system spec relate:

| Status | Code | Spec | UI lens word | Design-system §7 word |
|---|---|---|---|---|
| `planned` | no | no | — | — |
| `specified` | no | yes | — | `specified` |
| `matches` | yes | yes, the code agrees | `matches` | `built` |
| `drifts` | yes | yes, the code differs | `drifts` | `drifts` |
| `not-covered` | yes | no | `not-covered` | — |
| `null` | yes | not compared | `null` (inventory mode) | — |

The lens starts from the code and can't see a spec with no code; the design system starts from its
specs and can't hold code with no spec. The list sees both sides, so it uses all of them. `built` and
`matches` name the same case.

- **Without a design system** only `planned` and `null` are used.
- **With a design system**, built entries take the lens's status, which needs the UI lens to have run
  in judged mode. Planned entries are `specified` when the design system has a spec for them.
- **The list is behind the design system** when the design system changed after the record's
  comparison: its "Last reviewed" date is later than the `design-system.last-reviewed` in the lens
  results, or `git log <record commit>..HEAD -- <design system file>` lists a commit. Built statuses are
  then marked `(behind)` until the UI lens runs again in judged mode. A design system added after the
  last audit makes every built status `null (behind)`.
- Every spec in the design system has an entry. A spec with no entry is added as `specified`.

## 4. Entry fields

Field names are the UI lens's (§5 of [[audit-lens-ui]]), so the list and the record read the same.
Planned entries leave out what only code can give.

| Field | Built | Planned | From |
|---|---|---|---|
| `id` | yes | yes | The list's own `C<n>` (below) |
| `name`, `kind` | yes | yes | Lens; by hand for planned |
| `purpose` | yes | yes | The core unit's `purpose`; by hand for planned |
| `unit` or `outside` | yes | — | Lens |
| `path` | yes | — | The core unit's `path`; `—` for outside things |
| `uses` | yes | — | Lens: render relation ids, with one evidence `path:line` each; `[]` if unused |
| `variants`, `states` | yes, with evidence | as wanted, no evidence | Lens; by hand or the spec for planned |
| `props` | yes | as wanted | Lens; by hand for planned |
| `raw-values` | yes | — | The lens's raw values whose `units` include this component's unit |
| `spec` | when a design system exists | when a spec exists | Lens; the design system for planned |
| `status` | yes | yes | §3 |
| `duplicates` | when the duplication lens ran | — | Lens |
| `confidence` | yes | — | Lens |
| `planned-as` | when it was planned first | — | The date it was planned, kept for history |

**Ids.** The lens's `C<n>` ids are unique only within one record, so the list keeps its own: an entry
keeps its `C<n>` for as long as it is in the list, matched to each new record by its `unit` or
`outside` id (following `was:` when a unit was renamed or moved). The lens's id for the entry in the
current record is kept as `record-id`. New entries take the next free number; a removed entry's number
is never reused.

## 5. Building the list

1. **Find the latest record** in the audit folder (`audit_folder`, default `docs/audits`) whose
   `lenses` include `protocol/audit-lens-ui`. If there is none and the UI has code, run the audit with
   the UI lens first ([[codebase-audit]]). If there is no code yet, skip to step 5.
2. **Write the header** (§6): the record's audit id, commit and date, and the design system the lens
   compared with (or `null`).
3. **Read the previous list**, if any: its entries and ids.
4. **Built entries.** For each component in the lens results:
   - match it to a previous built entry by `unit` or `outside` id, and keep that entry's `C<n>`;
   - otherwise, if a planned entry is the same component (same name and purpose, checked by reading the
     code), it becomes built: keep its `C<n>`, set `planned-as`, and replace its fields with the lens's;
   - otherwise give it a new `C<n>`.
   Fill the fields (§4) from the lens and the core. A previous built entry the record no longer has is
   removed and listed once under Removed.
5. **Planned entries.** Carry every planned entry over unchanged. If the project has a design system,
   add an entry for each spec that has none, and set `specified` where a spec exists.
6. **Status** (§3), including the behind check.
7. **Raw values:** copy the lens's raw values as a table (they are rebuilt whole each time, so they keep
   the record's `V<n>`).
8. **Not shown:** copy the UI lens's gaps.
9. **Check** (§7), then save to `{{component_list_file}}`.

The built part is generated: hand edits to it are lost on the next build, so correct the record
instead. The planned part is the only part kept by hand.

## 6. Format

One Markdown file at `{{component_list_file}}`:

````markdown
---
type: component-list
audit-id: <record audit id, or null if no code yet>
commit: <record commit, short, or null>
record: "<path to the record folder, or null>"
date: <YYYY-MM-DD the list was built>
design-system: { path: "<path>", last-reviewed: <date compared with> }   # or null
built-by: "<who or what built it>"
---

# <repo> components

Built from audit <audit-id> at commit <commit>. To check freshness:
`git diff --name-only <commit>..HEAD`

## Summary
| Id | Name | Kind | Path | Uses | Status |

## Built
### C<n> <name>
<one fenced YAML block with the entry's fields>

## Planned
### C<n> <name>
<one fenced YAML block with the entry's fields>

## Raw values
| Id | Category | Value | Count | Used by | Token |

## Removed
## Not shown
````

- Entries are sorted by `kind` (screen, composite, primitive), then name, in every section.
- Past 40,000 characters (`wc -m`), each kind's entries move to their own file next to it
  (`docs/components/<kind>.md`, same header); the main file keeps the Summary, Raw values, Removed and
  Not shown, and links to each part.

## 7. Done when

- [ ] The header's audit id and commit match the latest record with the UI lens, or are `null` with
  only planned entries.
- [ ] Every built entry is a component in that record's UI lens results, and every component there has
  a built entry.
- [ ] No id was reused or renumbered; matched entries kept their `C<n>`.
- [ ] Every `uses` entry and every variant and state of a built entry has evidence.
- [ ] Every status follows §3; with a design system, every spec has an entry, and behind statuses are
  marked.
- [ ] The lens's gaps are under Not shown.

## 8. Keeping it current

The list goes stale the same ways as the record it is built from, plus one:

- the UI code changed since the list's commit: `git diff --name-only <commit>..HEAD -- <UI paths>` lists
  anything;
- a newer record with the UI lens exists;
- the design system changed since the comparison (§3, behind).

**Check before relying on the list** for a task. **Refresh** at the end of each phase if stale, and
after any change to the design system. To refresh: run the scoped re-audit ([[codebase-audit]] §4)
with the UI lens, then rebuild the list (§5). Planned entries can be added or edited by hand at any
time; that needs no refresh.

If the project also pulls `protocol/codemap-upkeep` ([[codemap-upkeep]]), it may refresh the list the
same way and on the same trigger as its codemap (`codemap_refresh`): one scoped re-audit then rebuilds
both. Commit the record, the map and the list together.

## 9. Out of scope

- **How components look or should be built.** That is the design system's job.
- **Finding components another way** (a design tool, a hand count): use [[audit-lens-ui]] and record the
  tools as measures, or keep a list outside this item.
- **How a project's agents load the list.** The project decides.

## 10. Example

`tasks-desktop` (PySide), built from the UI lens example in [[audit-lens-ui]] §6, judged against the
design system in [[design-system]]'s worked example. A toast was planned before the audit; it has no
spec yet.

````markdown
---
type: component-list
audit-id: 2026-11-13-9f3e2a1
commit: 9f3e2a1
record: "docs/audits/2026-11-13-9f3e2a1/"
date: 2026-11-13
design-system: { path: "docs/DESIGN_SYSTEM.md", last-reviewed: 2026-11-13 }
built-by: "Claude Code (claude-opus-5-5), by hand"
---

# tasks-desktop components

Built from audit 2026-11-13-9f3e2a1 at commit 9f3e2a1. To check freshness:
`git diff --name-only 9f3e2a1..HEAD`

## Summary
| Id | Name | Kind | Path | Uses | Status |
|---|---|---|---|---|---|
| C1 | Button | primitive | `src/app/widgets/button.py` | 2 | drifts |
| C2 | QComboBox (used directly) | primitive | — | 1 | not-covered |
| C3 | Toast | primitive | — | — | planned |

## Built
### C1 Button
```yaml
record-id: C1
unit: src/app/widgets/button.py:Button
path: "src/app/widgets/button.py"
purpose: "Push button with the app's border and states"
kind: primitive
uses: [{ id: R20, evidence: "src/app/screens/main_window.py:31" }, { id: R21, evidence: "src/app/screens/settings.py:44" }]
variants: [{ name: primary, evidence: "src/app/widgets/button.py:14" }]
states: [{ name: hover, evidence: "src/app/widgets/button.py:30" }, { name: disabled, evidence: "src/app/widgets/button.py:38" }]
props: [{ name: label, note: "button text" }]
raw-values: []
spec: "docs/DESIGN_SYSTEM.md#component-button"
status: drifts            # no focus state (lens finding F1)
confidence: CONFIRMED
```

### C2 QComboBox (used directly)
```yaml
record-id: C2
outside: X4
path: "—"
purpose: "Qt's combo box, used without a project wrapper"
kind: primitive
uses: [{ id: R23, evidence: "src/app/screens/settings.py:60" }]
variants: []
states: []
props: []
raw-values: []
spec: null
status: not-covered
confidence: CONFIRMED
```

## Planned
### C3 Toast
```yaml
name: Toast
kind: primitive
purpose: "Short message after an action, closes by itself"
states: [default, error]
spec: null
status: planned
```

## Raw values
| Id | Category | Value | Count | Used by | Token |
|---|---|---|---|---|---|
| V1 | colour | `#9184d9` | 2 | `src/app/screens/settings.py:SettingsScreen` | `color.accent` |

## Removed
None.

## Not shown
- G1 `src/app/theme/loader.py`: user themes load at runtime; their values aren't in Raw values.
````

## Changelog

### [Unreleased]

### [0.1.0] - 2026-11-13
#### Added
- First draft: built and planned entries, six statuses mapped to the UI lens and design-system §7, an
  optional design system with a behind check, list-owned ids, build steps, format, upkeep with the
  codemap option, and a worked example from the UI lens example.
