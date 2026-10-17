---
id: protocol/agent-protocol
version: 0.1.0
status: draft
summary: "Core operating protocol for AI agents: capability matrix, source-of-truth hierarchy, loss-on-write precautions, working posture, and concurrency."
applies-to: [vault, codebase]
settings:
  memory_folder:
    description: "Folder for agent notes, working context, and operational guides"
    default: "AI"
  session_folder:
    description: "Folder where per-session agent hand-over logs live"
    default: "AI/session"
requires: []
replaces: null
---

# Agent Protocol

Binding rules and operational invariants for any AI agent working within this project across all environments (local CLI tools, IDE extensions, or sandboxed chat sessions).

Detailed procedures for specific workflows live in companion documents:
- External working memory: [[working-memory]]
- Session logging and hand-overs: [[session-log]]
- Safe writes to live or fragile data: [[safe-write]]
- Fact verification and citations: [[research-discipline]]

---

## 1. Environment capability matrix

Agent capability varies across execution environments. These distinctions are load-bearing operational constraints, not style preferences:

| Environment | Direct filesystem access? | Execution capability | Primary role |
|---|---|---|---|
| **Local CLI agents** (Claude Code, Gemini CLI, Agy CLI) | Yes (`.md`, code, scripts) | Arbitrary shell, compilers, package runners, git | Extraction, code changes, refactors, tests, cleanup |
| **IDE assistants & local subagents** (Antigravity, Cursor) | Yes (`.md`, code, scripts) | Sandboxed or approved terminal commands, background tasks | Interactive development, plan review, multi-turn implementation |
| **Sandboxed desktop/cowork agents** (Claude Cowork) | Yes (when mounted) | Restricted shell (proxy blocks package installs, UI blocks shell typing) | Inspection, read-heavy analysis; pass tasks requiring local pip/compilers to a local agent |
| **Web chats & mobile interfaces** (Gemini Chat/Spark, Claude Chat) | No direct disk write (or Drive create-only) | Sandboxed Python runner or none; emits Google Docs or chat prose | Discussion, high-level planning, exploratory search |

### Operational hand-over rule

Sandboxed web and mobile chat tools cannot execute native build tools or install missing local packages. Furthermore, web tools like Gemini Chat/Spark emit native Google Docs rather than markdown files, introducing severe format conversion risks (see §3).

**Hard rule:** For any task requiring native package environments, compiler execution, or in-place file modifications, execute with a local filesystem-capable agent or hand over cleanly via [[session-log]].

---

## 2. Source-of-truth hierarchy

When two artifacts, notes, or data sources disagree, the higher rung strictly supersedes the lower rung:

1. **Primary source artifacts & executable code** — Original raw captures (images, scans, recordings, raw sensor dumps) and version-controlled source code with passing automated tests. Never delete or overwrite primary sources.
2. **Durable, indexed markdown notes & documentation** — Structured notes in `{{memory_folder}}` and canonical project documentation. This is what project tooling, search, and knowledge graphs index.
3. **Untrusted intermediates & temporary exports** — Google Docs (`.gdoc`), exported `.xlsx` workbooks, ephemeral chat transcripts, and temporary memory caches. Convenient for quick viewing, but lossy to read back and never authoritative.

An intermediate export or document that contradicts a durable markdown note or codebase implementation is presumed wrong by default. Verify against primary source artifacts before altering durable files.

---

## 3. Loss-on-write precautions & round-trip traps

Data loss often occurs at write-time while appearing visually intact. Once written in a degraded format, the damage is unrecoverable on export.

### The Google Docs LaTeX corruption trap

Routing mathematical or scientific text through Google Docs silently destroys notation:
- Escaped set braces (`\{` and `\}`) lose backslashes on write, turning `\{0, 1, 2\}` into `{0, 1, 2}`.
- In LaTeX, bare braces `{}` are grouping operators that render invisibly without printing braces. In mathematical analysis or set theory, this produces semantic errors that render cleanly without warnings.
- Structured sizing tags like `\left\{ ... \right\}` become invalid `\left{ ... \right}`.
- Exporters (Drive API, rclone, UI download) return only what is in the document; the backslashes are erased at write time.

**Rule:** Never route LaTeX-bearing content through Google Docs. Any tool converting external document stubs into `.md` must detect math delimiters (`$...$`, `$$...$$`) and halt for human review.

### The spreadsheet formula freeze trap

Exporting live spreadsheets (such as Google Sheets) to local `.xlsx` files replaces dynamic formulas (`XLOOKUP`, `IMPORTRANGE`, custom functions) with frozen string literals and cached values:
```
=IFERROR(__xludf.DUMMYFUNCTION("XLOOKUP(...)"), "<cached value>")
```
Re-importing a local `.xlsx` back over a master sheet overwrites working formulas with frozen junk, destroys data validation rules, and revokes external permissions.

**Rule:** Edits to live spreadsheets must occur through dedicated APIs, cell by cell, using the safety sequence in [[safe-write]]. Never overwrite a master sheet via full file upload.

---

## 4. Never fabricate content or state

- **Transcribe accurately:** When transcribing or ingesting source documents, transcribe what is actually present. Mark illegible handwriting or corrupted sections as `[illegible]` rather than inventing plausible text.
- **Do not invent plausible state:** Never synthesize a missing record, lecture note, or test result from a topic title or syllabus outline.
- **Empty markers are intentional:** Empty dated folders, blank sections, or absence markers often signify deliberate state (e.g. attended session with no notes, no-op events, or intentional boundaries). Do not "clean up" or invent synthetic content to populate empty containers.

---

## 5. Working posture

Five cardinal principles govern every agent action:

1. **Surface assumptions instead of resolving them silently.** Where requirements or source readings are ambiguous, explicitly state the interpretation taken and the justification.
2. **Touch only what the request implies.** Do not format adjacent files, reorder unrelated keys, normalize whitespace in untouched functions, or restructure directories unasked. Match existing project style.
3. **Report what you notice; do not act on it unilaterally.** When discovering dead links, stale comments, technical debt, or stray files, log them in project tracking or the session log; do not fix them unprompted.
4. **Verify against source, code, and tests, not memory.** Never trust model recall or an unverified tool summary. Re-read source lines, check timestamps, and execute the automated test suite.
5. **Every change must trace back to something asked for.** If a diff hunk cannot be tied directly to a user request, bug report, or agreed task plan, it does not belong in the commit.

---

## 6. Concurrency and session realities

Multiple agents, human collaborators, or background processes frequently operate on the same repository:

- **Check modified timestamps:** Inspect file modification times before and after reading or writing critical shared files.
- **Recompute plans from live data:** Never execute an implementation plan derived from an earlier turn without verifying that underlying files have not shifted.
- **Respect recent writes:** Never delete or overwrite files created moments prior by another session. Prefer localized edits over file replacement.
- **Record session hand-overs:** Document non-trivial changes, open threads, and environment flags in `{{session_folder}}` following [[session-log]].

---

## 7. Tool gotchas & platform realities

- **Ignore operating system and sync artifacts:** Always ignore `desktop.ini`, `.DS_Store`, and temporary sync conflict files (`.sb-*`, `.gdoc` stubs).
- **CRLF vs LF line endings:** Windows environments frequently check out files with CRLF endings. Byte-level equality checks and git porcelain commands can report spurious modifications; ensure tools normalize line endings.
- **Path escaping:** Ensure shell commands avoid path expansion surprises when traversing paths with spaces or special symbols.

---

## Changelog

### [Unreleased]
#### Changed
- Wording: "handoff" is now "hand-over" (state passed between sessions), matching
  `protocol/phased-implementation`'s terms. No setting, rule or step changed; only the `session_folder`
  description reads differently.

### [0.1.0] - 2026-09-15
#### Added
- Initial draft of the canonical agent operating protocol.
