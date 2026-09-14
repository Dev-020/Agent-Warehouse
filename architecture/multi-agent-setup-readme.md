# README — Multi-Agent Coding Setup (Claude Code + Antigravity)

This folder sets up a Codebuff-style multi-agent architecture across **Claude Code** and
**Antigravity**, and explains how to run both tools together on the same repo. Hand this folder to
either agent and it can orient itself from here.

## What's in here

| File | What it is | Who reads it |
|---|---|---|
| `AGENTS.md` | Canonical source of truth: agent roster, core principles, symbol map, stack specifics. | Both tools. Antigravity natively; Claude Code via `@AGENTS.md`. |
| `claude-code-setup.md` | Setup instructions for a Claude Code session (subagents, hooks, mode commands, symbol map). | Claude Code |
| `antigravity-setup.md` | Setup mapping the architecture onto Antigravity's Agent Manager, indexing, browser verification. | Antigravity |
| `dual-agent-workflow.md` | How to run both tools at once without collisions (git worktrees, division of labor, handoffs). | You + both tools |
| `codebuff-source-links.md` | Indexed links to Codebuff's docs + repo with summaries, for cross-verifying claims. | Any agent |

## Reading order
1. **`AGENTS.md`** — start here; defines the shared model. Fill in "Stack specifics" first.
2. **Your tool's setup doc** — `claude-code-setup.md` OR `antigravity-setup.md`.
3. **`dual-agent-workflow.md`** — wire both sides together and run in parallel.
4. **`codebuff-source-links.md`** — verify any claim against the originals as needed.

## Fastest path to running
1. `AGENTS.md` at repo root; fill in test/typecheck/build commands.
2. Add `CLAUDE.md` with `@AGENTS.md`.
3. Claude Code: subagents in `.claude/agents/`, Stop hook in `.claude/settings.json`.
4. Antigravity: confirm it reads `AGENTS.md`, add operating rules, confirm indexing.
5. Create two git worktrees (one per tool).
6. Agree division of labor per feature; merge via PRs; CI runs the full suite.

## Principles that carry across both tools
- One shared brain, separate hands — architecture in `AGENTS.md`; git worktrees isolate edits.
- Toolless orchestrator, specialized subagents — delegate, don't crawl.
- Discover before editing — consult the symbol map / indexing, batch-read.
- Review every turn — typecheck + tests + diff review before "done."
- Best-of-N only for hard problems — it costs N× tokens.
- Depth vs breadth — Claude Code for deep reasoning/refactors; Antigravity for parallel/visual work.

## Caveats
- Codebuff's speed/benchmark numbers are self-reported — don't repeat as independent fact.
- Antigravity's feature names shift between releases; confirm in-product.
- Claude Code's subagent frontmatter and hook event names change between versions; sanity-check.