---
id: architecture/codemap
version: 0.1.0
status: draft
summary: A layered map of a codebase — system down to symbols, with how the parts interact — built from an audit record and read by people and agents.
applies-to: [codebase]
settings:
  codemap_file:
    description: Where the codemap is written in the project.
    default: "docs/CODEMAP.md"   # PROPOSED — to agree with the user (WH-16 #1)
requires: [convention/audit-record@0.1, protocol/audit-lens-structure@0.1]   # lens pending WH-15 release
replaces: null
---

# Codemap

<!-- SKELETON (WH-16). Sections marked DECIDE wait on the user (acceptance criterion #1).
     Sections marked LENS wait on the approved Results format of protocol/audit-lens-structure. -->

## 1. What a codemap is, and when to have one
<!-- Purpose; who reads it (people and agents); difference from an audit record (the record is the
     evidence, the map is the readable view); when it pays off (several subsystems, agents onboarding,
     before a rewrite); when not (tiny repos). -->

## 2. Source: always the latest audit record
<!-- The map is generated from the latest record under {{audit_folder}} (full or scoped — a scoped
     record is complete on its own, audit-record §7). Never hand-edited facts that aren't in a record.
     Header pins audit id + commit, so staleness is checkable. -->

## 3. Levels — DECIDE
<!-- Proposal: L0 system → L1 subsystems → L2 modules → L3 files → L4 symbols, matching core unit
     kinds. A project picks its deepest level (setting or header field?); the map can't go deeper
     than the record's `depth`. Per level: what is shown, which relation types, how big it may get. -->

### 3.1. What each level shows
<!-- Table: level | units (core kind) | interactions shown (relation types) | from layers/central (LENS) -->

### 3.2. Interactions
<!-- Relations rolled up to the level (a file→file import counts as subsystem→subsystem); evidence and
     confidence kept; INFERRED marked. Outside things (data stores, services, config) on L0/L1. -->

## 4. Building the map from a record
<!-- Step by step: read header → units by kind → roll up relations → overlay structure lens
     (layers[].name/units, central-units[].unit — the only fields safe so far) → write sections.
     LENS: boundaries, rank, fan-in/out, cycles once the lens format is approved. -->

## 5. Format — DECIDE
<!-- Proposal: one Markdown file, a header block (audit id, commit, date, levels), one section per
     level, Mermaid diagram for L0–L1 plus tables below; deeper levels as tables/trees only.
     Alternatives: one file per level; folder. -->

## 6. Keeping it current
<!-- Points to the upkeep protocol (protocol/codemap-upkeep, name to agree). -->

## 7. Out of scope
<!-- How a project's agents load the map (the project decides — AGENTS.md scope rule). Generator tool
     (later, optional). -->

## 8. Example
<!-- Built from audit-record §8's notes-cli record (core + lens-structure). -->

## Changelog

### [Unreleased]
#### Added
- First draft.
