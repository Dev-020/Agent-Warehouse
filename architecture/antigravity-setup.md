# Antigravity Setup — Build the Codebuff-style Architecture

> Hand to an Antigravity session: "Read this and set up my repo to match. Confirm which features
> exist in the current version before relying on them."
>
> ACCURACY NOTE: Antigravity evolves fast. This maps the architecture onto its known building
> blocks (Agent Manager, parallel agents, AGENTS.md, built-in indexing, browser verification,
> Artifacts). Confirm current capabilities in-product and adapt names where changed.

## 1. Shared knowledge
Antigravity reads `AGENTS.md` natively — it's canonical. Don't duplicate architecture elsewhere.
Ensure the "Stack specifics" section is filled in.

## 2. Map roles onto Antigravity
| Role | Antigravity implementation |
|---|---|
| Orchestrator | You, driving the Agent Manager: spin task-scoped agents, review their Artifacts. |
| File Picker/Searcher | Built-in codebase indexing; prompt agents to gather the file set first. |
| Editor | A task-scoped agent. |
| Reviewer | Standing rule: self-review diff + run tests before "done". |
| Researcher | Browser/web use for docs + verification. |
| Runner | Agent terminal access. |

## 3. Operating rules (add to AGENTS.md)
```markdown
## Antigravity operating rules
- Gather the full relevant file set (built-in indexing) BEFORE editing.
- After edits: run typecheck + tests, self-review the diff, fix before reporting done.
- Use browser verification for UI/behavior changes.
- Produce an Artifact (task list / walkthrough) so the change is auditable.
```

## 4. Best-of-N via parallel agents
Launch 2–3 agents on the same task with different strategies, compare diffs/Artifacts, keep/merge
the best via git. (Native fit for Antigravity's parallel workspaces.)

## 5. Verification loop
implement → run tests → open the app in the browser → confirm behavior → report.

## 6. Verify setup
Agent reads AGENTS.md (state the test command); trivial task gathers files then runs tests;
parallel agents isolated via git worktrees (see dual-agent-workflow.md).