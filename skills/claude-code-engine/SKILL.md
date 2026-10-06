---
id: skill/claude-code-engine
version: 0.1.0
status: draft
summary: Operating protocol and headless patterns for driving projects using Claude Code CLI.
applies-to: [codebase, vault]
settings: {}
requires: [tool/claude-cli-runner@0.1]
replaces: null
---

# Claude Code Engine Skill: Headless CLI Orchestration Protocol

A comprehensive operating protocol for applications and agent harnesses driving the Claude Code CLI (`claude`)
as their primary autonomous runtime engine.

Built from battle-tested production implementations in `discord-bot` (Orion engine) and `shadow-cursor`
(resident desktop pointing engine), this skill documents the lifecycle contracts, stream-json NDJSON wire
format, profile isolation guarantees, and supervisory controls required to embed Claude Code reliably into any project.

Requires [[tool/claude-cli-runner]] for resident process management, NDJSON stream handling, and profile sandboxing.

---

## 1. Architectural Philosophy: The Resident Engine Model

Invoking a fresh `claude` process per prompt is an anti-pattern for embedded engines:
- **Cold start penalty:** Each spawn takes 5–15 seconds to load Node.js, plugins, and verify authentication.
- **Lost cache benefits:** Resident sessions leverage prompt caching and context continuity across turns.
- **Process thrashing:** Repeated spawns incur file lock contention and orphan process leaks.

Embedded engines must run a **resident warm process** over bidirectional NDJSON streams (`--input-format stream-json --output-format stream-json --verbose`),
gated by a FIFO queue where each turn begins at message dispatch and completes strictly upon receiving the `result` event frame.

---

## 2. Stream-JSON Wire Protocol

Claude Code communicates over `stdin` and `stdout` using single-line newline-delimited JSON (NDJSON).

### 2.1. Inbound Envelope (Host $\to$ Claude)
Every turn is written to `stdin` as a single line:
```json
{"type": "user", "message": {"role": "user", "content": "Your task prompt here..."}}
```
For multimodal requests (e.g. image + prompt), `content` is an array of content blocks:
```json
{
  "type": "user",
  "message": {
    "role": "user",
    "content": [
      {
        "type": "image",
        "source": {
          "type": "base64",
          "media_type": "image/png",
          "data": "<base64_data>"
        }
      },
      {
        "type": "text",
        "text": "Analyze this screenshot and report status."
      }
    ]
  }
}
```

### 2.2. Outbound Event Frames (Claude $\to$ Host)
Claude emits line-delimited events on `stdout`:

| Event Type | Subtype | Meaning | Key Payload Fields |
|---|---|---|---|
| `system` | `init` | Session metadata announced with the first turn. | `session_id`, `model`, `tools`, `mcp_servers` |
| `assistant` | — | Streaming model reasoning, text responses, or tool calls. | `message.content` (text chunks, `tool_use` blocks) |
| `result` | `success` | Turn finished successfully. | `result` (final text), `duration_api_ms`, `usage` |
| `result` | `error` | Turn failed or aborted. | `result` or `errors` array, `is_error: true` |

> [!IMPORTANT] Ready on Spawn Timing Invariant
> Unlike traditional daemons, Claude Code in `stream-json` mode **does not emit an `init` event upon process spawn**.
> When spawned with open pipes and empty stdin, it produces 0 bytes of stdout.
> The `init` frame arrives only **after the first message is written to stdin**.
> The host process must mark Claude as "ready to accept turns" immediately upon successful process spawn (`stdin.writable`). Waiting for `init` before dispatching will cause a permanent deadlock.

---

## 3. Profile Isolation & Sandboxing

When embedding Claude Code into a project, the engine must never inherit the developer's personal configuration,
uncontrolled global skills, unvetted MCP servers, or parent instruction files.

### 3.1. Dedicated Configuration Directory
Always launch with a project-owned `CLAUDE_CONFIG_DIR`:
```bash
export CLAUDE_CONFIG_DIR="$PROJECT_ROOT/.claude-engine"
```
Within this profile directory, Claude maintains its own isolated `.credentials.json` and session database.

### 3.2. Suppressing Parent `CLAUDE.md` Traversal
By default, Claude walks up the filesystem tree reading every `CLAUDE.md` and `.claude/CLAUDE.md` file up to the user home or filesystem root.
To prevent parent rules from polluting the embedded engine:
1. Export `CLAUDE_CODE_DISABLE_CLAUDE_MDS=1` in the engine process environment.
2. Launch with `--setting-sources project,local` to skip user-level global configuration.
3. Pass `--disable-slash-commands` to prevent interactive commands from hijacking turn execution.

### 3.3. One-Time Profile Authentication
Before resident operation, the isolated profile must be authenticated once:
```bash
python tools/claude-cli-runner/claude_cli_runner.py profile login --profile-dir <dir>
```
This launches `claude login` scoped specifically to `CLAUDE_CONFIG_DIR`.

---

## 4. Execution Flags & Parameter Reference

When spawning resident Claude Code engine processes, enforce the canonical flag matrix:

```bash
claude \
  -p \
  --input-format stream-json \
  --output-format stream-json \
  --verbose \
  --model claude-sonnet-5 \
  --effort medium \
  --setting-sources project,local \
  --disable-slash-commands \
  --no-session-persistence \
  --tools "" \
  --strict-mcp-config \
  --system-prompt "Your embedded system prompt..."
```

- `-p`: Headless prompt mode.
- `--verbose`: **Mandatory.** Without `--verbose`, Claude Code fails to emit stream-json frames.
- `--tools ""`: Strips built-in filesystem and bash tools when driving Claude as a pure inference/vision/pointing engine.
- `--strict-mcp-config`: Prevents automatic loading of globally installed MCP servers.
- `--add-dir <path>`: Whitelists specific directories outside the working tree when tool file operations are required.

---

## 5. Supervisory Control & Fault Recovery

Embedded runners must implement four hard supervisory controls:

1. **Watchdog Timer:** Track wall-clock elapsed time per turn. If no `result` frame is received after `turn_timeout_sec` (e.g. 180s), terminate the process (`SIGKILL`), report `OUTCOME_TIMEOUT`, and spawn a fresh replacement.
2. **Session Recycling:** Recycle the process every $N$ turns (recommended: 10–20 turns) to clear accumulated context memory, reset KV caches, and reclaim memory.
3. **Background Stderr Drain:** Read `stderr` in a non-blocking thread to prevent operating system pipe buffer deadlocks. Scan for headless permission denials and authentication expiration.
4. **Turn Queuing:** Enforce strict single-turn concurrency using a thread-safe FIFO queue. Never write a second turn to `stdin` while a turn is pending.
