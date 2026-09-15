---
id: protocol/session-log
version: 0.1.0
status: draft
summary: "How and when agents write session handoff logs and maintain session indexes."
applies-to: [vault, codebase]
settings:
  session_folder:
    description: "Directory where session logs are written"
    default: "AI/session"
  session_index:
    description: "Path to the central session index file"
    default: "AI/session/00_SESSIONS.md"
requires: []
replaces: null
---

# Session Log Protocol

How and when agents record session handoff logs, capture architectural decisions, and maintain project continuity across agent turns.

Related protocols:
- Operating constraints and working posture: [[agent-protocol]]
- External working memory: [[working-memory]]
- Safe writes to live data: [[safe-write]]
- Verification discipline and citations: [[research-discipline]]

---

## Purpose and audience

**Session logs are written for future agents and human collaborators, not as chat transcripts.**

Human collaborators remember past interactions; incoming AI agents start each conversation cold with zero memory of prior sessions. While git history records *what* files changed, session logs record *why*:
- The architectural reasoning behind decisions.
- What alternatives were considered and rejected.
- False assumptions or subtle bugs caught during execution.
- Work deliberately left unfinished when the session concluded.

---

## When to write a session log

Do not write a log for every trivial prompt. Create a session log when a session:

1. **Changes project architecture or conventions:** Introduces a new directory, framework, workflow, schema, or invariant.
2. **Makes or reverses a non-trivial decision:** Decides an architectural direction or reverses a prior design (crucial for recording rejected alternatives).
3. **Establishes reasoning that is expensive to re-derive:** Records non-obvious calculations, performance tradeoffs, or complex domain rules.
4. **Catches an error or discovered gotcha:** Documents a failure mode, a subtle bug, and *how it was discovered*, so future agents do not repeat it.
5. **Generates an unapplied decision or handoff:** A sandboxed or chat-based agent proposes changes it cannot apply directly to disk.
6. **Involves multi-agent task handoffs:** Hands off work across agents or documents concurrent claim boundaries.

**When to skip:** Single-line bug fixes, routine commits with clear commit messages, minor typo corrections, or repetitive data logging already captured in specialized files.

---

## File naming convention

Session log files reside in `{{session_folder}}/` and follow this format:

```
{{session_folder}}/YYYY-MM-DD-short-slug.md
```

- `YYYY-MM-DD`: Current ISO date.
- `short-slug`: Lowercase, hyphen-separated description of the primary topic or change (e.g. `2026-09-15-auth-token-refresh.md`).
- If multiple distinct sessions occur on the same date, distinguish them with unique slugs.

---

## Frontmatter schema

Every session log carries this frontmatter contract:

```yaml
---
type: session-log
date: YYYY-MM-DD
written_by: claude-code          # Environment: claude-code, antigravity, gemini-cli, claude-chat, etc.
wired: true                      # true if indexed into {{session_index}}, false if pending integration
coordination_state: done         # Optional: claimed, in-progress, acked, handed-off, done
topics: [optional, topic-tags]
---
```

### Frontmatter fields

- `type`: Must be `session-log`.
- `date`: Immutable date of the session (`YYYY-MM-DD`).
- `written_by`: Identifies the writing environment. This is critical for trust layering:
  - Local CLI/IDE agents (`claude-code`, `antigravity`) have access to compilers, tests, and filesystem tools.
  - Web or chat agents (`claude-chat`, `gemini-chat`) operate without local test suites; their claims require verification.
- `wired`: Boolean indicating whether the log is integrated:
  - `true`: Linked into `{{session_index}}` and any referenced state changes or handoffs have been applied.
  - `false`: Written by an agent in a create-only environment, awaiting processing by a filesystem-capable agent.
- `coordination_state`: Optional tag used when coordinating concurrent agents or tracking multi-agent handoffs.

---

## Required sections

A session log should optimize for quick orientation by a cold agent:

### 1. `## Summary`
A concise paragraph stating the goal of the session, the environment used, and the headline outcome.

### 2. `## Decisions Made and Rejected Alternatives`
Document concrete outcomes and the reasoning behind them. **Always record rejected options**: without this, future agents will re-propose solutions that were already evaluated and ruled out.

### 3. `## Corrections & Discovered Gotchas`
Detail errors caught during the session:
- What was claimed or assumed vs what was actually verified.
- The failure mode and *how it was discovered* (compiler error, test failure, runtime trace).
- Actionable rules to prevent re-deriving the bug.

### 4. `## Changes & Artifacts`
Summary table or bullet list of modified files, git commits, new tools, and test results.

### 5. `## Open Threads & Pending Actions`
Tasks deliberately left incomplete, known edge cases deferred to future sessions, or manual steps required from the user.

### What to leave out
- Conversational narration ("First the user asked me to... then I replied...").
- Fluff or generic summaries of project purpose.
- Raw file dumps already visible in git diffs.

---

## Managing unwired logs and handoffs

Agents running in sandboxed or chat-only environments (e.g. Claude chat through cloud storage, web interfaces) often possess create-only filesystem access: they can generate a new session log file, but cannot edit existing source files, execute test suites, or modify `{{session_index}}`.

These agents write session logs with:
```yaml
wired: false
```

### Opening procedure for filesystem-capable agents

At the start of every session, local agents must:
1. Inspect `{{session_folder}}/` for any notes with `wired: false`.
2. Read the unwired log and identify any pending edits, decisions, or tests described.
3. Review and apply the requested changes, verifying them against the test suite.
4. Add the log entry to `{{session_index}}` (newest first).
5. Flip the log's frontmatter flag to `wired: true`.

---

## Session index maintenance

All session logs are registered in `{{session_index}}`.

- **Order:** Newest sessions listed first.
- **Entry format:**
  ```markdown
  - [[YYYY-MM-DD-short-slug|YYYY-MM-DD — Headline description]] — Brief 1-2 sentence summary of decisions, major bug fixes, and current project state.
  ```

Maintaining the index ensures that an agent opening a new session can scan recent history in a single read without opening dozens of individual log files.

---

## Correcting a log after the fact

> **Links may be repointed. Historical claims may not.**

A wikilink is navigation: if a referenced document moves or is renamed, repointing the link keeps the log functional.

However, the factual text and claims in a session log are immutable historical records of what was believed at that point in time. Never rewrite past logs to make past sessions look smarter or to erase documented mistakes:
- If a past conclusion was proven incorrect, record the correction in the current session log and link back to the original.
- Move non-obvious traps to permanent project gotchas documentation.

---

## Changelog

### [Unreleased]

### [0.1.0] - 2026-09-15
#### Added
- Initial draft of the canonical session log protocol.
