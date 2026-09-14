# Dual-Agent Workflow — Running Claude Code + Antigravity Together

## Why they can coexist
Both operate on the same filesystem + git repo. They don't talk directly, but git + a shared
`AGENTS.md` let them collaborate. The trick: ONE SHARED BRAIN, SEPARATE HANDS.
- Shared brain: `AGENTS.md` (Antigravity reads it; Claude Code via `@AGENTS.md`). Edit in one place.
- Separate hands: keep them out of each other's edits with git worktrees/branches.

## The collision fix — git worktrees
```bash
git worktree add ../proj-claude   feature/claude-work
git worktree add ../proj-antigrav feature/antigrav-work
```
Point Claude Code at `../proj-claude`, Antigravity at `../proj-antigrav`. They run truly in
parallel, isolated. Merge via PRs. (Lighter alternative: divide by directory/module in one checkout.)

## Division of labor
| Claude Code | Antigravity |
|---|---|
| Deep reasoning, tricky logic, big refactors | Parallel exploration, many agents at once |
| Hook-driven auto review + tests every turn | Visual/UI work with browser verification |
| Terminal-native, scriptable/headless | Frontend "see it working" loops, Artifacts |
| Surgical single-threaded edits | Breadth: independent tasks in parallel |

Rule of thumb: Claude Code = depth & rigor. Antigravity = breadth & visual verification.

## Two collaboration patterns
A) Plan in one, execute in the other: Claude Code Plan mode → spec in `plans/feature-x.md` →
   Antigravity runs parallel agents to implement → Claude Code `reviewer` reviews before merge.
B) Parallel tracks: Antigravity does UI in its worktree, Claude Code does API/logic in its
   worktree, each self-reviews, merge both branches, run full suite.

## Keeping them in sync
- One knowledge file (`AGENTS.md`). Commit often, small. Shared `plans/*.md` handoff channel.
- CI (or a local full-suite run) is the final referee after merging both branches.

## Quick start checklist
1. AGENTS.md filled in. 2. CLAUDE.md imports it. 3. Two git worktrees. 4. Claude Code subagents +
Stop hook. 5. Antigravity rules + indexing. 6. Agree division of labor per feature. 7. Merge via PRs; CI runs full suite.