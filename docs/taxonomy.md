---
type: guide
topic: agentic-taxonomy
created: 2026-09-16
status: canonical
tags: [taxonomy, terminology, rules, protocols, conventions, workflows, architecture, governance]
---

# Agentic Systems Taxonomy: Rules, Protocols, Conventions, and Workflows

> **Executive Summary:** In AI agent engineering, natural language acts as the runtime code. Ambiguity in terminology causes instruction dilution, prompt bloat, and behavioral drift. This document standardizes the definitions, boundary constraints, and warehouse placement for all operational terminology used across this vault and client projects.

---

## 1. The 2-Axis Taxonomy Matrix

Operational guidance is differentiated along two primary axes:
1. **Behavioral vs. Structural**: Does it govern actions occurring over time (sequence, handshakes, pipelines) or the shape and boundaries of static artifacts (schemas, formats, constraints)?
2. **Hard vs. Soft Rigidity**: Is it an absolute invariant with automated enforcement, or a contextual heuristic allowing reasoned deviation?

```
                 TEMPORAL / BEHAVIORAL                   STRUCTURAL / STATIC
              (Actions, sequences, handshakes)       (Formats, constraints, boundaries)
           ┌─────────────────────────────────────┬─────────────────────────────────────┐
           │                                     │                                     │
   HARD    │              PROTOCOL               │                RULE                 │
(Mandatory)│  Deterministic handshakes & safety  │  Inviolable constraints & limits    │
           │  (e.g., Safe-write, Git claim lock) │  (e.g., "Never commit to main")     │
           │                                     │                                     │
           ├─────────────────────────────────────┼─────────────────────────────────────┤
           │                                     │                                     │
   SOFT    │         PROCESS / WORKFLOW          │       CONVENTION / GUIDELINE        │
(Flexible/ │  Progression of steps & phases      │  Arbitrary formats & best-practices │
Heuristic) │  (e.g., TDD cycle, Release pipeline)│  (e.g., SemVer, commit messages)    │
           │                                     │                                     │
           └─────────────────────────────────────┴─────────────────────────────────────┘
```

---

## 2. Definitive Terminology Breakdown

### 1. Rule (Invariant / Boundary)
* **Definition:** A non-negotiable constraint or boundary condition. Rules define what an agent is strictly forbidden or required to do.
* **Core Question:** *"What are the inviolable boundaries?"*
* **Rigidity:** **Absolute.** Violating a rule represents a defect, security hazard, or hard abort.
* **RFC 2119 Equivalent:** `MUST` / `MUST NOT`.
* **Where it lives in Warehouse:** 
  * Project or Vault root: `AGENTS.md` / `CLAUDE.md`.
  * Encapsulated inside specific protocols as boundary conditions.
* **Examples:**
  * *"Never commit directly inside another project."*
  * *"Never include private tokens, keys, or credentials in prompt context or items."*
  * *"Never overwrite locally drifted files during sync."*

### 2. Guideline (Heuristic / Best Practice)
* **Definition:** A directional heuristic or recommendation intended to inform judgment when trade-offs exist. Guidelines direct preference without foreclosing reasoned exceptions.
* **Core Question:** *"How should I approach this decision when alternatives exist?"*
* **Rigidity:** **Soft / Heuristic.** Deviation is permissible if accompanied by rationale.
* **RFC 2119 Equivalent:** `SHOULD` / `RECOMMENDED`.
* **Where it lives in Warehouse:** Explanatory sections in protocols, documentation, and skills.
* **Examples:**
  * *"Write plainly: short sections, tables where they help, concrete examples."*
  * *"Default to Tier 0 (`starter`) profile unless multi-agent concurrency is actively required."*

### 3. Convention (Standard / Agreement on Form)
* **Definition:** An arbitrary choice made uniform across a project or fleet to eliminate friction, cognitive load, and parse ambiguity. It governs the **format, shape, schema, or naming** of artifacts.
* **Core Question:** *"How should this artifact look so that all systems can read it?"*
* **Rigidity:** **Strict for format consistency**, though the choice of standard was arbitrary.
* **Where it lives in Warehouse:** `conventions/` (synced item).
* **Examples:**
  * `convention/commits`: Conventional Commits standard (`feat:`, `fix:`, `chore:`).
  * `convention/frontmatter`: Closed-vocabulary YAML metadata schema for markdown notes.
  * `convention/backlog`: Structured markdown task lists with task statuses (`Open`, `In Progress`, `Closed`, `Rejected`, `Cancelled`) and lifecycle sections (In Progress, Backlog, Completed, Icebox).
  * `convention/versioning`: Semantic Versioning (`MAJOR.MINOR.PATCH`) guarantees.

### 4. Protocol (Contract / Verification Handshake)
* **Definition:** A formalized multi-step sequence governing interactions, state transitions, and mutual guarantees across operational boundaries (agent-to-disk, agent-to-agent, agent-to-environment).
* **Core Question:** *"What exact verification steps and invariants must occur before and after state changes?"*
* **Rigidity:** **High.** Skipping a step invalidates the transaction and enters an unsafe state.
* **Where it lives in Warehouse:** `protocols/` (synced item).
* **Examples:**
  * `protocol/safe-write`: 5-step sequence for modifying live files (verify target $\to$ read fresh $\to$ compute diff $\to$ write $\to$ verify write).
  * `protocol/worktree-claims`: Atomic branch claim, reservation lock, and merge gate protocol for parallel agent sessions.
  * `protocol/session-log`: Handoff protocol recording session goals, files modified, and next steps for subsequent agents.

### 5. Workflow (Operational Pipeline / Task Graph)
* **Definition:** A directed sequence or graph of execution steps transforming inputs into outputs. Workflows coordinate tools, subagents, and human reviews to achieve a specific functional goal.
* **Core Question:** *"What sequence of tasks and automated steps achieves this outcome?"*
* **Rigidity:** **Procedural.** Can branch, loop, or require human intervention based on intermediate outputs.
* **Where it lives in Warehouse:** Orchestrated within `skills/` or executed via `tools/`.
* **Examples:**
  * Anthropic Agentic Workflow Patterns: *Prompt Chaining*, *Routing*, *Parallelization*, *Orchestrator-Workers*, *Evaluator-Optimizer*.
  * The release workflow in `_tools/warehouse.py release`: Lint $\to$ run tests $\to$ bump version $\to$ finalize changelog $\to$ commit $\to$ git tag.

### 6. Process (Organizational Lifecycle)
* **Definition:** The macro-level, end-to-end operational lifecycle that fulfills a strategic goal over time. A process encompasses multiple workflows, roles, tools, and governing policies.
* **Core Question:** *"What is the complete lifecycle from onboarding to retirement?"*
* **Rigidity:** **Strategic / Systemic.**
* **Where it lives in Warehouse:** Documented in `docs/` and architectural plans.
* **Examples:**
  * The *Warehouse Item Lifecycle*: Draft (`0.x.y`) $\to$ Canonical (`1.0.0+`) $\to$ Deprecated $\to$ Archived.
  * The *Project Onboarding Process*: Select Profile $\to$ Bootstrap Manifest $\to$ Initial Sync $\to$ Agent Wiring $\to$ Fleet Verification.

---

## 3. Capabilities, Tools, and Architecture

In addition to regulatory terms, the warehouse differentiates executable and structural assets:

| Term | What It Represents | Format in Warehouse | Synced? | Example |
|---|---|---|---|---|
| **Architecture** | System design, agent relationship topologies, and scaling models. | Single file in `architecture/` | Yes | `architecture/codebuff-orchestration` |
| **Skill** | An encapsulated agent capability bundle (instructions + private helper scripts + assets). | Folder in `skills/<name>/` with `SKILL.md` | Yes | `skill/latex-pdf`, `skill/backlog-governance` |
| **Tool** | Standalone executable program, CLI, or script with test coverage. | Folder in `tools/<name>/` with `TOOL.md` + code + tests | Yes (tests stay in warehouse) | `tool/backlog-cli`, `tool/tex-compile` |
| **Template** | Boilerplate starting point copied once; the client project takes permanent ownership. | Single file in `templates/` | Copied once | `template/plan-document` |

---

## 4. "Where Does It Belong?" — The Decision Tree

When authoring a new piece of agentic knowledge, use this flowchart to determine its classification:

```mermaid
graph TD
    Start["New Concept or Artifact"] --> Q1{"Is it executable code<br/>or an agent capability?"}
    
    Q1 -->|Executable CLI / Script| Tool["tool/<name>/<br/>(Folder: code + tests + TOOL.md)"]
    Q1 -->|Capability bundle<br/>(instructions + helper scripts)| Skill["skill/<name>/<br/>(Folder: SKILL.md + private helpers)"]
    Q1 -->|No, it is pure documentation / text| Q2{"Is it intended to be synced<br/>into other projects?"}
    
    Q2 -->|No, warehouse-internal only| Q3{"Is it about warehouse operations<br/>or external research?"}
    Q3 -->|Warehouse manual, CLI, taxonomy| Docs["docs/<br/>(Internal Warehouse Meta-Docs)"]
    Q3 -->|Historical audit, landscape research| Ref["reference/<br/>(Background Notes & Research)"]
    
    Q2 -->|Yes, synced to projects| Q4{"What is its primary function?"}
    Q4 -->|Static schema, format, naming standard| Conv["conventions/<name>.md<br/>(Convention)"]
    Q4 -->|Deterministic multi-step handshake / safety| Proto["protocols/<name>.md<br/>(Protocol)"]
    Q4 -->|System design / agent topology| Arch["architecture/<name>.md<br/>(Architecture)"]
    Q4 -->|One-time starting scaffold| Templ["templates/<name>.md<br/>(Template)"]
```

---

## 5. Industry Alignment & External References

The taxonomy established here unifies established standards from computer science, systems engineering, and AI agent frameworks:

1. **IETF RFC 2119 / RFC 8174 (Requirement Levels)**:
   * Provides the bedrock for separating **Rules** (`MUST`, `MUST NOT`) from **Guidelines** (`SHOULD`, `MAY`).
2. **Anthropic: Building Effective Agents & Model Context Protocol (MCP)**:
   * Establishes the boundary between deterministic **Workflows** (fixed orchestration graphs) and autonomous **Agents** (dynamic tool use).
   * Defines **Protocols** (such as MCP) as the open, standard transport interface across agent boundaries.
3. **ISO/IEC 2382 & ITIL Frameworks**:
   * Distinguishes high-level **Process** (lifecycle governance) from task-specific **Procedure / Workflow** (step-by-step instructions).
4. **Progressive Context Disclosure**:
   * Codifies that rules, conventions, and protocols must be tiered into modular loadouts to avoid token exhaustion and the well-documented "lost-in-the-middle" attention degradation of Large Language Models.
