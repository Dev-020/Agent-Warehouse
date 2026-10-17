---
id: protocol/research-discipline
version: 0.1.1
status: draft
summary: "Research discipline and the provenance ladder: look it up, do not reason it out."
applies-to: [vault, codebase]
settings: {}
requires: []
replaces: null
---

# Research Discipline

Rigorous fact-checking, verification methodology, and citation discipline for AI agents.

Related protocols:
- Operating constraints and working posture: [[agent-protocol]]
- External working memory: [[working-memory]]
- Safe writes to live data: [[safe-write]]
- Session logging and hand-overs: [[session-log]]

---

## Core Principle

**Look it up. Do not reason it out.**

Never answer numeric, version-sensitive, architectural, or empirical questions from intuition, physical analogy, or internalized model training. LLMs naturally generate plausible-sounding explanations that collapse upon inspection. Every factual assertion must be grounded in an auditable source.

---

## The Provenance Ladder

When two sources disagree, the higher rung on the provenance ladder strictly wins. Always record which rung settled an assertion:

| Rung | Source Tier | Trust Level | Description |
|---|---|---|---|
| **1** | **Primary Source Data & Installed Code** | Exact & Definitive | Resolved configuration dumps, schema exports, ASTs, and the installed source code itself. Nothing overrides this tier on a concrete value. |
| **2** | **Runtime Observation & Measurement** | Empirical Ground Truth | Live test suite outputs, compiler diagnostics, profiling metrics, debug screenshots, and live system logs. |
| **3** | **Official Documentation & Specs** | Authoritative | Official API reference manuals, specification documents, language standards, and upstream docs. (May occasionally lag a patch). |
| **4** | **Community Consensus & Guides** | Advisory Only | Forum threads, issue tracker comments, community calculators, blog tutorials. Useful for patterns and tips; unreliable for version-sensitive numbers. |
| **5** | **Chat Transcripts & Model Recall** | Weakest | Prior LLM chat transcripts, unverified conversation summaries, and raw model weights. Reverses easily under conversational pressure. |

### Rung 1: The two primary sources divide by question type

Within Rung 1, data dumps and source code do not compete—they answer fundamentally different questions:

| Question Type | Authoritative Source | Rationale |
|---|---|---|
| Concrete values (constants, schemas, configurations, entity dimensions, resolved recipes) | **The Data Dump / Compiled Config** | Represents *resolved* state after all overrides, inheritance, and build-time computations have executed. |
| Dynamic behavior (algorithms, state machine transitions, timing rules, event hooks) | **The Source Code** | Configuration dumps contain no executable logic. The implementation lives in the script files. |

> [!important] Read the installed local copy, not upstream repository HEAD
> Upstream git repositories reflect the latest development head, which often introduces breaking changes, unreleased features, or altered defaults. Always inspect the local pinned package or installed dependency on disk to verify what your environment is actively executing.

---

## The Fetch-Summary Trap

> **A tool or web fetch returns a summary or interpretation, not raw ground truth.**

When an agent retrieves an external document via an automated tool, quoted fragments inside the response are primary evidence. However, **the connective prose surrounding the quotes represents the summarization model's interpretation**, which frequently inverts the meaning of the quoted source.

### Anti-trap procedure
1. **Cite only visible verbatim quotes:** Never cite the connective summary text as an authoritative source.
2. **Fetch the specific page on conflict:** If a summary appears to contradict a high-rung source, fetch the specific raw page or file before declaring the claim contested.
3. **Acknowledge unresolved status:** If a verbatim quotation cannot be retrieved, state that the question remains unresolved rather than guessing.

---

## Switching tools, not sources

> **A tool error (e.g. HTTP 403, SSL failure, timeout) is a statement about your client tool, not about the source.**

Failing to fetch a URL or parse a document via one CLI tool does not mean the source is missing, dead, or deprecated.

### Tool escalation order when access fails
1. **Headless HTTP fetch:** Standard fast text/markdown conversion.
2. **Rendered browser / DOM inspection:** When content is rendered via client-side JavaScript or behind anti-bot proxies, use an in-app browser or evaluate DOM properties directly.
3. **Inspect local archives / installed files:** Check local package caches, downloaded documentation bundles, or test fixtures.
4. **Ask the operator for a paste or screenshot:** A human collaborator can often access authenticated or intranet resources in seconds.
5. **Mark as unresolved:** A documented missing read is legitimate. Downgrading to an unverified web search summary is forbidden.

---

## Truncation and partial reads

> **A partial read is not a read.**

Tool outputs frequently truncate silently at length limits, buffer caps, or token thresholds:
- Check file size or line counts before reading.
- Treat an excerpt ending mid-sentence or without an EOF marker as a truncation signal.
- Paginate or slice through large documents systematically.
- **Never claim a feature or topic is undocumented without reading the complete file.** An absence observed in a truncated view is an artifact of the view, not the source.

---

## The Explanation Trap

A subtle and dangerous failure mode: **fabricating a plausible causal story to explain a correct number or observation.**

Example failure mode: An agent correctly measures that an API batch takes 200 ms, but invents an explanation that "the server is throttling requests due to an internal rate-limiter," when in fact network latency alone accounted for the duration.

**Discipline:** When data is verified but the underlying cause is unknown, state the measured data and stop. An unrequested causal story borrows false credibility from the real number beside it and misleads future investigations.

---

## Handling uncertainty ("When you don't know")

When encountering an unknown value or behavior, escalate strictly in this order:

1. **Read Rung 1 (the local dump or source code).**
2. **Execute a test or measurement (Rung 2).**
3. **Ask the operator for primary evidence (log output, screenshot, or exact version).**
4. **Consult official documentation (Rung 3).**
5. **Explicitly document the item as unresolved (`status: needs-verification`).**

Guessing or extrapolating by analogy is never permitted.

---

## Recording outcomes

- **Discovered a bug or false assumption?** Document it in project gotchas notes, detailing *how the error was detected* so the failure mode transfers to other agents.
- **Verified an empirical fact?** Record the finding with an explicit citation to the resolving authority (e.g. `reference: "dump/vanilla-2.0.77"` or `reference: "auth/tokens.py:L104"`).
- **Unresolved item remaining?** Record the task in project backlog tracking with an explicit `needs-verification` flag.

---

## Changelog

### [Unreleased]

### [0.1.1] - 2026-10-17
#### Changed
- Wording: "handoff" is now "hand-over" (state passed between sessions), matching
  `protocol/phased-implementation`'s terms. No rule changed.

### [0.1.0] - 2026-09-15
#### Added
- Initial draft of the canonical research discipline protocol.
