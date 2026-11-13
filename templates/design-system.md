---
id: template/design-system
version: 0.1.0
status: draft
summary: Copyable design system document — header naming the one source of truth, principles, tokens, themes, motion, component specs, patterns, accessibility and a decision log, in the order convention/design-system sets.
applies-to: [codebase]
settings: {}
requires: []
replaces: null
---

<!-- Copy with `warehouse template template/design-system docs/DESIGN_SYSTEM.md` (or to the path in convention/design-system's `design_system_file` setting). Fill the header first: the owner and the source of truth are agreed before any UI design is done. Fill every `[change me]` marker in the day-one sections (Header, Principles, core Tokens, Accessibility, Decision log); leave other sections as "Not yet defined" until the UI needs them. Follow [[conventions/design-system|convention/design-system]]. Delete this comment when done. -->

# Design System — [change me: Project name]

> **Follows:** `convention/design-system`. The header's source of truth is the single reference the
> UI is checked against; anything that disagrees with it is a finding.

## 1. Header

| Field | Value |
|---|---|
| Owner | [change me: who approves changes] |
| Source of truth | [change me: `this document` / `<token file path>` / `<design tool file>, exported by <who>`] |
| Token file | [change me: `<path>` (DTCG 2025.10), or `none`] |
| Platforms | [change me: e.g. `desktop (Qt/PySide)`, `web (CSS)`] |
| Started from | [change me: `scratch` / `existing code` / `design tool export`] |
| Status | draft |
| Last reviewed | [change me: YYYY-MM-DD] |

**Platform names.** Token `color.text.muted` is written as [change me: e.g. `--color-text-muted` in
CSS, `COLOR_TEXT_MUTED` in Python].

## 2. Principles

3–7 principles, each specific enough to settle a choice, each saying what it wins over.

1. **[change me: Name].** [change me: what it means in practice]. Wins over [change me: principle],
   except [change me: when].
2. **[change me: Name].** [change me]. Wins over [change me].

## 3. Tokens: core

<!-- With a token file, the file holds the values: drop the Value column, or generate these tables from it. -->

### Colour

| Token | Value | Role |
|---|---|---|
| [change me: `neutral.900`] | [change me: `#hex`] | primitive |
| [change me: `color.surface.base`] | [change me: `{neutral.900}`] | [change me: window/page background] |
| [change me: `color.text.primary`] | [change me] | [change me: body text] |
| [change me: `color.accent`] | [change me] | [change me] |

### Typography

| Token | Value | Role |
|---|---|---|
| [change me: `font.family.base`] | [change me] | [change me] |
| [change me: `font.size.body`] | [change me] | [change me] |
| [change me: `font.weight.body`] | [change me] | [change me] |

### Spacing

| Token | Value |
|---|---|
| [change me: `space.100`] | [change me: e.g. 4px] |
| [change me: `space.200`] | [change me: e.g. 8px] |

## 4. Tokens: other

Not yet defined. <!-- radius, elevation, border width, breakpoints, opacity, z-order: only those the UI uses. -->

## 5. Themes

Not yet defined. <!-- Each theme gives new values to the same semantic tokens. Name each theme and list only the tokens it changes. -->

## 6. Motion

Not yet defined. <!-- Duration and easing tokens, what animates, and what happens under the OS/browser reduced-motion setting. -->

## 7. Components

Not yet defined. <!-- One spec per component. Copy this block for each:

### [Component name]
1. **Purpose:**
2. **When to use / when not to use:**
3. **Anatomy:** (parts and the tokens each uses)
4. **Variants:**
5. **States:** default, hover, pressed, focus, disabled (+ error, loading, selected where they apply)
6. **Behaviour:** (interaction, keyboard, motion)
7. **Accessibility:** (contrast pairs, focus, labels)
8. **Status:** specified / built / drifts (link the finding)
-->

## 8. Patterns

Not yet defined. <!-- Repeated compositions (forms, navigation, empty/loading/error states), each with when to use it and why. -->

## 9. Accessibility

Minimum: WCAG 2.2 AA (text 4.5:1, large text 3:1; UI parts and focus rings 3:1; focus always
visible; reduced motion respected; colour never the only signal). [change me: keep, or state a higher bar]

| Foreground | Background | Ratio | Needs | Pass |
|---|---|---|---|---|
| [change me: `color.text.primary`] | [change me: `color.surface.base`] | [change me: e.g. 14.5:1] | 4.5:1 | [change me] |
| [change me: `color.accent`] | [change me: `color.surface.base`] | [change me] | 3:1 | [change me] |

## 10. Changes and decision log

Changes to the source of truth are approved by the owner. Retired tokens and components are marked
`deprecated` with their replacement, and removed only when nothing uses them.

| Date | Change | Why | Approved |
|---|---|---|---|
| [change me: YYYY-MM-DD] | First version | [change me: started from scratch / existing code / export] | [change me: owner] |

<!-- Started from existing code? Add the mapping table here:

### Value mapping

| Old value | Uses | Token | Note |
|---|---|---|---|
-->

## Changelog

### [Unreleased]
#### Added
- First draft.
