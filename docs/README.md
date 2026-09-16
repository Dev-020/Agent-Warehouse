# Warehouse Documentation (`docs/`)

This directory contains the **meta-documentation** for the AI Agent Warehouse itself—explaining how the warehouse is architected, how to operate it, its underlying context engineering philosophy, and the terminology that governs agent behavior.

> [!NOTE]
> **Difference between `docs/` and Catalog Folders:**
> * `docs/`: Explains how the warehouse operates. These files are **never synced** to client projects.
> * `protocols/`, `conventions/`, `architecture/`, `skills/`, `tools/`: The **reusable product items** synced into client projects via `warehouse sync`.

---

## Document Index

| Document | Topic | Summary |
|---|---|---|
| **[`taxonomy.md`](taxonomy.md)** | Conceptual Taxonomy | Definitive definitions for *Rules*, *Protocols*, *Conventions*, *Workflows*, *Skills*, and *Tools*, including the classification decision tree. |
| **[`quickstart.md`](quickstart.md)** | Project Onboarding | A 3-minute, step-by-step walkthrough for onboarding a new codebase or Obsidian vault to the warehouse. |
| **[`cli-reference.md`](cli-reference.md)** | CLI Manual | Complete command-line manual for `_tools/warehouse.py` (`bootstrap`, `sync`, `status`, `release`, etc.) with full option breakdowns. |
| **[`warehouse-architecture.md`](warehouse-architecture.md)** | System Design | Architectural specifications, invariants, phase rollout, and synchronization contracts. |
| **[`progressive-context-disclosure.md`](progressive-context-disclosure.md)** | Context Engineering | Empirical research on instruction bloat, LLM attention saturation, and the tiered profile system. |

---

## Related Directories

* **`00_INDEX.md`**: Master catalog listing all available reusable items, versions, and statuses.
* **`profiles/`**: Curated loadouts (`starter`, `standard`, `concurrency`, `academic`) implementing progressive context disclosure.
* **`reference/`**: External research, historical audits (`workspace-audit.md`), and trial notes (never synced).
* **`_tools/`**: Implementation of the sync CLI engine, pytest test suite, and git hooks.
