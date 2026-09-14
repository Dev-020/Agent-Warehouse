# AGENTS.md — Shared Agent Architecture (Canonical Knowledge File)

> This is the single source of truth for how AI coding agents operate in this repo.
> Antigravity reads `AGENTS.md` natively. Claude Code reads `CLAUDE.md` — so `CLAUDE.md`
> should `@import` this file (see `claude-code-setup.md`). Keep architecture decisions HERE,
> not duplicated across tools.

## Goal
Replicate Codebuff's multi-agent architecture on Claude Code and Antigravity: a toolless
orchestrator that delegates to specialized subagents, fast tree/symbol-based file discovery,
automatic review + tests every turn, optional best-of-N parallel editing, and a distributed
knowledge layer.

## The agent roster
| Role | Job | Model tier |
|---|---|---|
| Orchestrator | Plans, delegates, integrates. Does NOT read/edit files directly. | Strongest |
| File Picker | Returns ~10–15 relevant files + summaries. | Fast/cheap |
| Code Searcher | Pattern/grep search. | Fast/cheap |
| Researcher | Web/docs lookup. | Fast/cheap |
| Editor | The only role that edits code. | Strongest |
| Reviewer | Reviews the diff BEFORE the turn ends. | Strong |
| Runner | Runs tests/typecheck/build. | Fast/cheap |

## Core principles
1. Toolless orchestrator — delegate, don't crawl. Subagents return only final output.
2. Discover before editing — consult the symbol map, batch-read the full file set.
3. Review is not optional — every code turn ends with typecheck + tests + diff review.
4. Best-of-N only for hard problems (it costs N× tokens).
5. Knowledge lives next to code.
6. Minimal babysitting — pre-approve safe commands only.

## The symbol map
Maintain `repo-map.md`: a compact tree of dirs → files → exported symbol names. Agents read it
FIRST. Regenerate with tree-sitter or ctags.

## Stack specifics (FILL IN — agents should detect and populate)
- Language(s): <detect>
- Package manager: <detect>
- Test command: <e.g. npm test / pytest / go test ./...>
- Typecheck command: <e.g. tsc --noEmit / mypy>
- Lint command: <e.g. eslint . / ruff>
- Build command: <...>

## Dual-tool coordination (full detail in dual-agent-workflow.md)
- Git is the coordination substrate.
- Run both at once via separate git worktrees/branches.
- Antigravity = parallel/visual/exploratory; Claude Code = deep reasoning, refactors, hooks.