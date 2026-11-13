---
id: protocol/audit-lens-ui
version: 0.1.0
status: draft
summary: Audit lens for a codebase's UI — every component, where it is used, its variants, states and key props, and every hard-coded style value; judged against the project's design system when it has one, otherwise an inventory to start one from.
applies-to: [codebase]
settings: {}
requires: [protocol/codebase-audit@0.1]
replaces: null
---

# UI Lens

A lens for [[codebase-audit]] (`protocol/codebase-audit`). It reads the audit's core and writes
`lens-ui.md` in the record, following [[audit-record]] §5 and the lens contract (§6). A project with
no UI never pulls it.

## 1. Purpose

**The question it answers:** what is the UI built from? Which components exist, where each one is
used, how it varies, and which raw style values (colours, sizes, timings) are written straight into
the code instead of coming from tokens.

It runs in one of two modes, set by whether the project has a design system ([[design-system]],
`convention/design-system`):

| Mode | When | What it produces |
|---|---|---|
| **judged** | The project has a design system document | The inventory, plus findings where the code drifts from the design system |
| **inventory** | No design system yet | The inventory only (`criteria: []`). It is the input for starting a design system from existing code (design-system §3.2) |

The lens does not require `convention/design-system`: a project without one still needs the
inventory to start one. A UI component list (`convention/ui-component-list`) is built from this
lens's results.

## 2. What it needs from the core

| Need | Value |
|---|---|
| Depth | `symbol` inside the UI subsystems: components are usually classes or functions. `file` is enough where each component is one file (`.vue`, `.svelte`, one component per module). |
| Relations | Every place a component is created or rendered, as a core relation of type `calls` with `note: renders` |
| History | not needed |

The lens file records `needs: { depth: symbol, history: false }` (or `depth: file`). Deepen the core
first if the UI subsystems aren't at that depth or the render relations are missing
([[codebase-audit]] Step 8). Usage facts live in the core, so the structure lens and the codemap see
them too; this lens points at them.

## 3. Criteria

**Inventory mode:** `criteria: []`. The lens only describes.

**Judged mode:** these defaults, from design-system §9, plus any rule the project's design system adds.

| Id | Source | Rule |
|---|---|---|
| U1 | convention/design-system §9 (token use) | UI code uses tokens; no raw style value outside the token file or theme module, except the design system's listed exceptions |
| U2 | convention/design-system §9 (completeness) | Every component in use has a spec in the design system |
| U3 | convention/design-system §7 (states, variants) | A component's code has the variants and states its spec defines, using the spec's tokens |
| U4+ | The project's design system | Its own rule, quoted in one line with its section |

Contrast and the other accessibility checks of design-system §9 are run on the design system
document itself. This lens reports the raw colours it finds, so those checks can include them.

## 4. The steps

1. **Check the needs** (§2) against `core.md`. Deepen the UI subsystems if needed.
2. **Find the design system and set the mode.** If the project pulls `convention/design-system`, the
   document is at its `design_system_file` setting; otherwise ask the initiator whether one exists.
   Record it under `design-system` in the results (`null` in inventory mode) and set the criteria (§3).
3. **Find the components.** A component is a reusable piece of UI defined in the project: a widget
   class, a function or file that renders UI, a screen or page. Search by the framework's patterns
   (subclasses of its widget base class, functions returning markup, component files). Each must be a
   core unit; add missing ones to the core first.
   - Give each a `kind`: `primitive` (button, input), `composite` (built from other components) or
     `screen` (a window, page or view).
   - **Framework widgets used directly** (a raw `QPushButton`, a raw `<button>`) are components in use
     too. List them with `outside:` pointing at the core's outside thing for the UI library, instead of
     `unit:`.
4. **Trace the uses.** Each place a component is created or rendered is a core relation (`calls`,
   `note: renders`). List those relation ids under `uses`. A component with no uses is still listed,
   with `uses: []`.
5. **Variants, states and key props.** From the code, with evidence:
   - **variants:** named alternatives (primary, compact), from parameters, subclasses or style classes;
   - **states:** which of `default`, `hover`, `pressed`, `focus`, `disabled`, `error`, `loading`,
     `selected` the code handles, each with the line that handles it. A state the code doesn't handle
     is left out, not guessed;
   - **key props:** the parameters that change what the user sees or does, not every argument.
6. **Collect raw values.** Search the UI code and stylesheets (CSS, QSS, inline styles) for literal
   style values, by category: `colour`, `typography`, `spacing`, `radius`, `elevation`, `border`,
   `breakpoint`, `motion`, `opacity`, `z-order` (design-system §5.3).
   - Leave out the token file and the generated theme files, and the values `0`, `none`, `auto` and
     `inherit`. In judged mode, also leave out the design system's listed exceptions.
   - Write one entry per distinct value, with every place it is used. Near-duplicates (five almost
     equal greys) stay separate entries; clustering them is design-system work (§3.2).
   - In judged mode, give the token whose value matches exactly, if any.
   - Record the search (tool, patterns) as a measure with `used-by: [protocol/audit-lens-ui]`.
7. **Compare with the design system** (judged mode). Give each component a `status`:
   - `matches`: it has a spec, and its code has the spec's variants and states with its tokens;
   - `drifts`: it has a spec, and the code differs (a missing state, another token, a raw value);
   - `not-covered`: it has no spec.
   In inventory mode, `status` is `null`.
8. **Findings** (judged mode).
   - Each raw value breaks U1. Write one finding per value, not per use. Its units are the units that
     use it.
   - Each `not-covered` component in use breaks U2.
   - Each `drifts` component breaks U3. Say what differs.
   - Label each finding through [[issue-triage]]. Starting points: a raw value that has a matching
     token is `Minor`, `Frequent` when it is used in many places; a missing `focus` or `disabled`
     state is `Major`, since it affects accessibility. Adjust for the project.
9. **Duplicates.** If the duplication lens runs in the same audit, list under `duplicates` the ids of
   its groups that contain this component. Otherwise leave the field out. This lens doesn't judge
   duplicates itself.
10. **Gaps.** In the [[audit-record]] §4.5 format: styles computed at runtime, themes loaded from
    outside the repository, generated UI code, components the search patterns may have missed.

## 5. Results format

```yaml
design-system:                    # null in inventory mode
  path: "<path to the document>"
  source-of-truth: "<as named in its header>"
  last-reviewed: <YYYY-MM-DD>

components:
  - id: C<n>
    unit: <core unit id>          # or outside: <core outside-thing id> for framework widgets used directly
    name: "<name>"
    kind: primitive | composite | screen
    uses: [<core relation ids>]   # renders relations; [] if unused
    variants: [{ name: <name>, evidence: "<path:line>" }]
    states: [{ name: <state>, evidence: "<path:line>" }]
    props: [{ name: <name>, note: "<what it changes>" }]
    spec: "<path#section>"        # null if none, or in inventory mode
    status: matches | drifts | not-covered   # null in inventory mode
    duplicates: [<duplication lens group ids>]   # only when the duplication lens ran
    confidence: CONFIRMED | INFERRED

raw-values:
  - id: V<n>
    category: colour | typography | spacing | radius | elevation | border | breakpoint | motion | opacity | z-order
    value: "<literal as written>"
    count: <number of places>
    at: ["<path:line>", ...]
    units: [<core unit ids>]
    token: <matching token name>  # null if none, or in inventory mode
```

## 6. Example

A small dark desktop app, `tasks-desktop` (PySide), whose design system is the worked example in
[[design-system]]. The core lists `src/app/widgets/button.py:Button`,
`src/app/screens/main_window.py:MainWindow` and `src/app/screens/settings.py:SettingsScreen`; render
relations `R20`–`R23`; and the Qt library as outside thing `X4`.

````markdown
---
type: audit-lens
audit-id: 2026-11-13-9f3e2a1
lens: protocol/audit-lens-ui
lens-version: 0.1.0
needs: { depth: symbol, history: false }
---

## Criteria
```yaml
criteria:
  - { id: U1, source: "convention/design-system §9 token use", rule: "No raw style values outside the theme module" }
  - { id: U2, source: "convention/design-system §9 completeness", rule: "Every component in use has a spec" }
  - { id: U3, source: "convention/design-system §7", rule: "Code has the spec's variants and states, with its tokens" }
```

## Results
```yaml
design-system: { path: "docs/DESIGN_SYSTEM.md", source-of-truth: "this document", last-reviewed: 2026-11-13 }
components:
  - id: C1
    unit: src/app/widgets/button.py:Button
    name: Button
    kind: primitive
    uses: [R20, R21]
    variants: [{ name: primary, evidence: "src/app/widgets/button.py:14" }]
    states:
      - { name: hover, evidence: "src/app/widgets/button.py:30" }
      - { name: disabled, evidence: "src/app/widgets/button.py:38" }
    props: [{ name: label, note: "button text" }]
    spec: "docs/DESIGN_SYSTEM.md#component-button"
    status: drifts
    confidence: CONFIRMED
  - id: C2
    outside: X4
    name: "QComboBox (used directly)"
    kind: primitive
    uses: [R23]
    variants: []
    states: []
    props: []
    spec: null
    status: not-covered
    confidence: CONFIRMED
raw-values:
  - id: V1
    category: colour
    value: "#9184d9"
    count: 2
    at: ["src/app/screens/settings.py:51", "src/app/screens/settings.py:77"]
    units: [src/app/screens/settings.py:SettingsScreen]
    token: color.accent
```

## Findings
```yaml
findings:
  - { id: F1, units: [src/app/widgets/button.py:Button], criterion: U3, what: "Button has no focus state; the spec defines a 2px color.accent ring", evidence: "src/app/widgets/button.py:22-40", confidence: CONFIRMED, severity: Major, likelihood: Frequent, blocks: false, backlog: WH-40 }
  - { id: F2, units: [src/app/screens/settings.py:SettingsScreen], criterion: U1, what: "Raw #9184d9 instead of color.accent (2 places)", evidence: "src/app/screens/settings.py:51", confidence: CONFIRMED, severity: Minor, likelihood: Occasional, blocks: false, backlog: WH-41 }
  - { id: F3, units: [src/app/screens/settings.py:SettingsScreen], criterion: U2, what: "QComboBox is used directly and has no spec", evidence: "R23 (src/app/screens/settings.py:60)", confidence: CONFIRMED, severity: Minor, likelihood: Occasional, blocks: false, backlog: WH-42 }
```

## Gaps
```yaml
gaps:
  - { id: G1, area: "src/app/theme/loader.py", reason: "Loads a user theme file at runtime", impact: "Values in user themes are not in raw-values" }
```
````

## 7. Done when

- [ ] The mode is set: `design-system` names the document, or is `null` with `criteria: []`.
- [ ] Every component is a core unit, or points at a core outside thing for framework widgets used
  directly.
- [ ] Every `uses` entry is a core `calls` relation with `note: renders`.
- [ ] Every variant and state has evidence; nothing is guessed.
- [ ] Raw values are one entry per distinct value, with every place it is used.
- [ ] In judged mode, every component has a `status`, and every raw value, `not-covered` component and
  `drifts` component has a finding citing U1, U2 or U3.
- [ ] Tools and search patterns are in the record's `measures` with `used-by` naming this lens.

## Changelog

### [Unreleased]

### [0.1.0] - 2026-11-13
#### Added
- First draft.
