# Claude Code Setup — Build the Codebuff-style Architecture

> Hand this to a Claude Code session: "Read this and set it up in my repo. Detect my stack and
> fill in commands. Ask before running anything destructive."

## 1. Make CLAUDE.md point at shared knowledge
Create `CLAUDE.md` at repo root:

```markdown
# CLAUDE.md
@AGENTS.md

## Claude Code operating rules
- You are the ORCHESTRATOR. Delegate to subagents; don't read/edit files directly when a
  subagent can. Keep your context focused on planning and integration.
- Before any edit: read `repo-map.md`, delegate to `file-picker`, then batch-read those files.
- End every code-producing turn by invoking `reviewer` + running tests/typecheck.
```

## 2. Create subagents (`.claude/agents/*.md`)
Each has its OWN context window and returns only results (Claude Code's "clean orchestrator").

`.claude/agents/file-picker.md`
```markdown
---
name: file-picker
description: Given a task, return 10-15 relevant files with summaries. Use PROACTIVELY before editing.
tools: Read, Grep, Glob
model: haiku
---
1. Read `repo-map.md`. 2. Confirm with Grep/Glob. 3. Return ranked `path — reason`. No edits. Max 15.
```

`.claude/agents/editor.md`
```markdown
---
name: editor
description: Write/modify code for a well-specified change. The only role that edits files.
tools: Read, Edit, Write, Grep, Glob
model: opus
---
Implement the smallest correct change. Match existing style. Don't expand scope. Report changes.
```

`.claude/agents/reviewer.md`
```markdown
---
name: reviewer
description: Review the current diff for bugs and convention violations. Invoke at end of every code turn.
tools: Read, Grep, Glob, Bash
model: opus
---
Review the working-tree diff (correctness first, then style). Run the AGENTS.md test/typecheck
commands and include failures. Recommend concrete fixes.
```

(Also create `code-searcher.md`, `researcher.md`, `runner.md` on the same pattern — cheap models,
narrow tools, no edits.)

## 3. Auto-review + test hook (`.claude/settings.json`)
```json
{
  "hooks": {
    "Stop": [
      { "matcher": "*", "hooks": [
        { "type": "command", "command": "npm run typecheck --silent && npm test --silent" }
      ]}
    ]
  },
  "permissions": {
    "allow": [
      "Bash(npm test:*)", "Bash(npm run typecheck:*)",
      "Bash(git status:*)", "Bash(git diff:*)", "Bash(rg:*)"
    ]
  }
}
```
Adjust commands to the detected stack. Never blanket-allow destructive ops.

## 4. Mode commands (`.claude/commands/*.md`)
`max.md`: "Best-of-N: spawn 3 editor subagents in parallel (minimal diff / refactor-friendly /
edge-case-first), then reviewer picks or merges the best. Hard changes only — ~3× tokens."
`quick.md`: "Lite: single editor pass + one review."
(Plan mode already exists natively via Shift+Tab.)

## 5. Build the symbol map
Generate `repo-map.md` (ctags -R or a tree-sitter script), formatted `dir/ → file → symbols`.

## 6. Verify
`/agents` loads all subagents; a trivial task delegates file-picker→editor; Stop hook runs tests;
agent can state the test command from `@AGENTS.md`.