---
id: convention/design-system
version: 0.1.0
status: draft
summary: How a project with a UI records its design system — one agreed source of truth, three ways to start, required sections, tokens, component specs, accessibility minimums and checks.
applies-to: [codebase]
settings:
  design_system_file:
    description: "Where the project's design system document lives"
    default: "docs/DESIGN_SYSTEM.md"
requires: []
replaces: null
---

# Design System Convention

How a project with a user interface records its design system: the values, rules and component specs
its UI is built from and checked against. The document lives at `{{design_system_file}}`. Start it from
[[templates/design-system|template/design-system]] (`warehouse template template/design-system {{design_system_file}}`).

This convention fixes the **structure** and the **checkable minimum**. It never fixes how a project
looks: palette, typeface and mood are the owner's call.

## 1. Whether and when

- Having a design system is the project's own choice. Many projects work by eye; others want one so
  nobody has to keep re-checking which value or theme a widget uses. Both are valid.
- There is no fixed point to start. A project can start one before any UI exists, part-way through, or
  after the UI has grown and drifted (§3 covers all three).
- Start small and grow. §4 lists what is required from day one and what is added when needed.
- A project likely needs one when more than one person or agent ships UI, when the same component has
  been built more than once, or when the UI is coming to a second platform.

## 2. Source of truth

The design system has **exactly one source of truth**: the single reference the real UI is compared
against.

1. **Agree it before any UI design is done**, and record it in the document's header (§4). It is
   the reference for every later check (§9), so it has to exist before there is anything to check.
2. **One only.** Two sources give the app two reference points, and the UI will drift between them.
3. **Everything else is a copy**, made from the source or checked against it: theme files in code,
   stylesheets, a design tool's file, screenshots. A copy that disagrees with the source is wrong,
   and the difference is a finding (§9).
4. **A design tool export is an input, not a second truth.** When a project starts from a tool's
   export (§3.3), it decides once which side is the source:
   - **The repo** (the default): the export is imported into the document or the token file, and the
     tool's file becomes a copy that is updated to match.
   - **The design tool**: the repo's token file is generated from the tool's export and never edited
     by hand. The header names the tool file and who exports it.
5. **Inside the repo, values live in one place.**
   - With no token file, the document's token tables hold the values.
   - With a token file (§5.4), **the file holds the values** and the document's token tables list
     names and roles only, or are generated from the file. Never keep values in both by hand.
6. Changing the source of truth is a decision-log entry (§10) approved by the owner.

## 3. Three ways to start

### 3.1 From scratch (no UI yet)
1. Name the owner and the source of truth (§2).
2. Write 3–7 principles (§6).
3. Choose the core tokens: colour, typography and spacing (§5).
4. Set the accessibility minimums (§8) and check the core colour pairs against them.
5. Add component specs only as the first screens need them.

### 3.2 From existing code
For a UI that grew without a system. The input is the hard-coded style values in the code: colours,
sizes, radii, spacing, type and timings. An audit collects them (for example a UI audit lens, if the
project uses one), or an inventory made by hand.
1. **Inventory:** list every distinct value, with where it is used (`path:line`) and how often.
2. **Cluster:** group near-duplicates (five almost-identical greys are one decision).
3. **Name:** give each surviving value a token (§5). Values that are genuinely different keep separate
   tokens; accidents merge.
4. **Map:** keep a mapping table, old value → token, with its uses. The fix work follows it.

   | Old value | Uses | Token | Note |
   |---|---|---|---|
   | `#9184d9`, `#9285da`, `rgb(145,132,217)` | 14 | `color.accent` | merged near-duplicates |
   | `#1e2030` | 3 | `color.surface.raised` | |
5. **Specify** the components that exist, from what the code does, marking each spec's status
   (§7).
6. **Triage** each mismatch between the code and the new document as a finding (§9). Fixing is
   separate work.

### 3.3 From a design tool export
For a project that already has a design made in a tool (Figma, Penpot, Claude Design and the like).
1. Decide which side is the source of truth (§2.4), and record it.
2. Import the tool's tokens: into the token file if the project keeps one, or into the document's
   tables. Rename them to §5's rules where needed; record renames in the decision log.
3. Write what the export can't carry: principles, component usage rules, accessibility, the owner.
4. Check the imported colours against §8. Failing pairs are findings, not silent changes.

## 4. Document structure

Sections appear in this order. Mark a section not yet written as `Not yet defined`, so readers know
it was left out on purpose.

| § | Section | Required from day one? |
|---|---|---|
| 1 | Header | **Yes** |
| 2 | Principles | **Yes** |
| 3 | Tokens: colour, typography, spacing | **Yes** |
| 4 | Tokens: radius, elevation, breakpoints, others | When needed |
| 5 | Themes | When the UI has more than one |
| 6 | Motion | When the UI animates |
| 7 | Components | As components are built |
| 8 | Patterns | When a composition repeats |
| 9 | Accessibility | **Yes** (at least §8's minimums) |
| 10 | Changes and decision log | **Yes** |

**The header** holds:

| Field | Example |
|---|---|
| Owner | the person who approves changes |
| Source of truth | `this document` / `tokens/tokens.json` / `Figma file "App UI", exported by <owner>` |
| Token file | `tokens/tokens.json` (DTCG 2025.10), or `none` |
| Platforms | `desktop (Qt/PySide)`, `web (CSS)` |
| Started from | `scratch` / `existing code` / `design tool export` |
| Status | `draft` or `in use` |
| Last reviewed | `YYYY-MM-DD` |

## 5. Tokens

A **token** is a named design decision: a name used everywhere in place of a raw value.
`color.accent = #9184d9`; a button's border uses `color.accent`, never `#9184d9`. Changing the token
changes every use.

### 5.1 Tiers
| Tier | Example | Holds |
|---|---|---|
| Primitive | `violet.400 = #9184d9` | a raw value with no meaning |
| Semantic | `color.accent = {violet.400}` | a purpose |
| Component (optional) | `button.border = {color.accent}` | one component's use |
- UI code uses semantic or component tokens, never primitives directly.
- A small system can use two tiers (primitive and semantic). Don't add a fourth.

### 5.2 Names
- Name semantic tokens by **purpose, not appearance**: `color.text.muted`, not `color.grey.light`.
- Write names platform-neutral, lowercase, dot-separated: `category.role[.variant][.state]`, e.g.
  `color.text.muted`, `space.200`, `color.action.primary.hover`.
- Each platform derives its own form mechanically and the document states the rule once:
  `--color-text-muted` (CSS), `COLOR_TEXT_MUTED` (Python), `colorTextMuted` (TypeScript).
- A token name is never reused for a different meaning. Retire it instead (§10).

### 5.3 Categories
Colour, typography (family, size, weight, line height), spacing, radius, elevation (shadow), border  
width, breakpoints, motion (duration, easing), opacity and z-order. A project defines only the  
categories it uses.

### 5.4 The token file (optional)
- Projects that want tooling keep the values in one machine-readable file in the **W3C Design Tokens
  (DTCG) 2025.10** format, named in the header. Themes use the DTCG Resolver module.
- When it exists it holds the values (§2.5). Build steps generate the platform files from it
  (CSS variables, a Python theme module, a TypeScript theme) and those outputs are never edited by
  hand.

### 5.5 Recording tokens in the document
| Token | Value | Role |
|---|---|---|
| `color.text.primary` | `{neutral.50}` → `#e9e9ed` | body text on `color.surface.base` |

With a token file, drop the Value column, or generate the table from the file.

## 6. Principles and rationale

Taste can't be checked, but it can be made shared and explicit.
- **3–7 principles**, each specific enough to settle a real choice ("Quiet by default: the accent marks
  one thing per view"), not a general quality ("intuitive"). Larger sets get forgotten.
- Each principle says what it **wins over** when two conflict.
- Every significant choice gets a decision-log entry (§10) with its **reason**: which principle it
  follows, or what it was compared against.

## 7. Component specs

One spec per component, in this order. Leave out sections that don't apply; keep the order.

1. **Purpose:** what it is for, in one or two sentences.
2. **When to use / when not to use**, naming the alternative.
3. **Anatomy:** its parts, with the tokens each uses.
4. **Variants:** e.g. primary, secondary, compact.
5. **States:** default, hover, pressed, focus, disabled, plus error, loading or selected where they
   apply. Each state names its token changes.
6. **Behaviour:** interaction, keyboard, motion.
7. **Accessibility:** contrast pairs, focus, labels, keyboard path.
8. **Status:** `specified` (spec only), `built` (code matches the spec) or `drifts` (code
   differs; link the finding). If the project keeps a UI component list, link the entry.

## 8. Accessibility minimums

At least WCAG 2.2 level AA:
- **Text contrast:** 4.5:1 for normal text, 3:1 for large text (18pt, or 14pt bold) (SC 1.4.3).
- **Non-text contrast:** 3:1 for UI component boundaries, icons that carry meaning, and focus
  indicators, against adjacent colours (SC 1.4.11).
- **Focus is always visible** on every interactive component, and a focus ring meets 3:1.
- **Reduced motion:** when the OS or browser asks for reduced motion, non-essential animation stops
  or is replaced by a fade.
- **Colour alone never carries meaning**; pair it with text, shape or an icon (SC 1.4.1).
Record each foreground/background token pair and its measured ratio in the accessibility section.
A project may set a higher bar; it may not set a lower one without a decision-log entry saying why.

## 9. Checks

What makes a design system good is checkable, whatever it looks like:

| Check | Pass when |
|---|---|
| Source of truth | exactly one, named in the header |
| Token use | UI code uses tokens, with no raw values outside the token file or theme module, except listed exceptions |
| Completeness | every component in use has a spec, and every spec defines its states |
| Accessibility | every recorded token pair meets §8 |
| Ownership | an owner is named and the decision log is current |
| Drift | each mismatch between the UI and the source of truth is recorded as a finding |

- Run the checks when the document is first written, before a release that changes the UI, and
  when a UI audit runs.
- Record each mismatch as a finding in the project's backlog, labelled per [[issue-triage]] if the
  project uses it. The check reports; it doesn't fix.

## 10. Changes

- The owner approves changes to the source of truth.
- Each change gets a decision-log entry: date, what changed, why, and who approved it.

  | Date | Change | Why | Approved |
  |---|---|---|---|
  | 2026-11-13 | `color.accent` `#7a6dc9` → `#9184d9` | contrast on `color.surface.base` was 4.1:1; accent text needs 4.5:1, now 5.4:1 | owner |
- **Retire, don't delete.** A token or component that is replaced is marked `deprecated`, names its
  replacement, and is removed only when nothing uses it.
- Renaming a token is a change; record the old name, so the code can be searched for it.

## 11. Out of scope

- How the UI looks. The convention sets structure and the minimum bar, never a style.
- Build tooling for the token file; the project chooses it.
- Wireframes and screen layouts; they are a separate concern and link to this document when both
  exist.

## Worked example

A minimal design system, started from scratch, for a dark desktop app with no token file.

> **Header** — Owner: the project owner · Source of truth: this document · Token file: none ·
> Platforms: desktop (Qt/PySide) · Started from: scratch · Status: draft · Last reviewed: 2026-11-13
>
> **Principles**
> 1. *Quiet by default.* The accent marks one thing per view. Wins over *Visible state*, except for
>    errors.
> 2. *Visible state.* Every interactive part shows hover, focus and disabled clearly.
>
> **Tokens: colour** (Python names: `COLOR_TEXT_PRIMARY` …)
>
> | Token | Value | Role |
> |---|---|---|
> | `neutral.900` | `#161826` | primitive |
> | `neutral.50` | `#e9e9ed` | primitive |
> | `violet.400` | `#9184d9` | primitive |
> | `color.surface.base` | `{neutral.900}` | window background |
> | `color.text.primary` | `{neutral.50}` | body text |
> | `color.accent` | `{violet.400}` | focus ring, primary outline |
>
> **Tokens: typography** — `font.family.base` = Inter · `font.size.body` = 13px · `font.weight.body` = 500
>
> **Tokens: spacing** — `space.100` = 4px · `space.200` = 8px · `space.300` = 12px
>
> **Component: Button**
> 1. Purpose: starts an action.
> 2. Use for actions; for navigation, use a link.
> 3. Anatomy: label (`color.text.primary`, `font.size.body`); 1px border (`color.accent`);
>    padding `space.100` × `space.300`.
> 5. States: hover, background `color.accent` at 12% opacity; focus, a 2px `color.accent` ring;
>    disabled, label and border at 40% opacity.
> 7. Accessibility: `color.text.primary` on `color.surface.base` = 14.5:1 (passes 4.5:1);
>    `color.accent` ring on `color.surface.base` = 5.4:1 (passes 3:1).
> 8. Status: specified.
>
> **Accessibility** — the pairs above, with reduced motion: hover fades are turned off.
>
> **Decision log**
>
> | Date | Change | Why | Approved |
> |---|---|---|---|
> | 2026-11-13 | First version | — | owner |

## Changelog

### [Unreleased]
#### Added
- First draft: one source of truth agreed before UI design, three ways to start, document structure
  with a day-one minimum, token tiers and naming, the optional DTCG 2025.10 token file, principles
  and rationale, component specs, WCAG 2.2 AA minimums, checks, changes, and a worked example.
