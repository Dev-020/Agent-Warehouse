---
id: tool/claude-cli-runner
version: 0.1.0
status: draft
summary: Resident CLI driver, profile isolator, and NDJSON session manager for Claude Code.
applies-to: [codebase, vault]
entrypoint: claude_cli_runner.py
requires-software: [python>=3.10, claude]
platforms: [windows, macos, linux]
settings: {}
requires: []
replaces: null
---

# `tool/claude-cli-runner`: Resident Claude Code CLI Session Manager

A robust, dependency-free Python runner and library for managing resident Claude Code CLI (`claude`)
processes over bidirectional NDJSON (`stream-json`) streams.

Used with [[skill/claude-code-engine]], this tool provides full process lifecycle supervision, profile
isolation, FIFO turn queueing, watchdog timeouts, automatic session recycling, and streaming chunk parsing.

---

## 1. Prerequisites

- **Python** $\ge$ 3.10 on system `PATH`.
- **Claude Code CLI** (`claude`) installed globally via npm (`npm install -g @anthropic-ai/claude-code`).
- Valid Anthropic subscription or API credentials.

---

## 2. CLI Usage

The tool can be executed directly from the terminal for environment diagnostics, profile management, and interactive or scripted runs:

```bash
# Verify environment, PATH, and authentication
python tools/claude-cli-runner/claude_cli_runner.py check [--json]

# Initialize or inspect an isolated profile directory
python tools/claude-cli-runner/claude_cli_runner.py profile setup [--profile-dir DIR]

# Trigger a one-time browser login scoped to the isolated profile
python tools/claude-cli-runner/claude_cli_runner.py profile login [--profile-dir DIR]

# Run a single turn against the resident engine
python tools/claude-cli-runner/claude_cli_runner.py run --prompt "Summarize recent commits" [--profile-dir DIR] [--model MODEL]

# Start an interactive CLI chat session powered by the resident engine
python tools/claude-cli-runner/claude_cli_runner.py chat [--profile-dir DIR] [--model MODEL]
```

---

## 3. Core Commands Reference

| Command | Arguments | Purpose |
|---|---|---|
| `check` | `[--profile-dir DIR] [--json]` | Verifies `claude` binary on `PATH`, checks profile configuration, and probes authentication status. |
| `profile setup` | `[--profile-dir DIR]` | Scaffolds an isolated profile directory with sandbox settings and parent `CLAUDE.md` exclusions. |
| `profile login` | `[--profile-dir DIR]` | Executes `claude login` scoped specifically to the target profile directory (`CLAUDE_CONFIG_DIR`). |
| `run` | `--prompt PROMPT [--profile-dir DIR] [--workspace DIR] [--model MODEL] [--effort EFFORT] [--timeout SEC] [--json]` | Dispatches a prompt to a warm engine session, streams chunks to stdout, and exits with code 0 on success. |
| `chat` | `[--profile-dir DIR] [--workspace DIR] [--model MODEL]` | Interactive terminal conversation loop maintaining resident session continuity. |

---

## 4. Python Library Integration

Any Python project can import `ClaudeCliSession` to drive Claude Code natively:

```python
from claude_cli_runner import ClaudeCliSession, EngineConfig

config = EngineConfig(
    claude_bin="claude",
    profile_dir="./.claude-engine",
    model="claude-sonnet-5",
    effort="medium",
    turn_timeout_sec=180.0,
    turns_per_session=10,
)

session = ClaudeCliSession(config)
session.start()

# Event hooks
session.on_chunk = lambda delta: print(delta, end="", flush=True)
session.on_status = lambda status: print(f"[{status}]", flush=True)

# Submit a turn and wait for result
result = session.send_and_wait("Analyze project architecture and list entrypoints.")
if result.success:
    print(f"\nFinal response: {result.text}")
    print(f"Usage: {result.usage}, Duration: {result.duration_api_ms}ms")
else:
    print(f"\nTurn failed: {result.error}")

session.stop()
```

---

## 5. Architectural Safeguards

- **Isolation Barrier:** Automatically injects `CLAUDE_CONFIG_DIR` pointing to the designated profile and sets `CLAUDE_CODE_DISABLE_CLAUDE_MDS=1` to guarantee local instructions cannot be subverted by parent directory rules.
- **Pipe Deadlock Prevention:** Background worker thread continuously drains `proc.stderr`, preventing pipe buffer saturation while logging permission errors.
- **Watchdog Recovery:** Spawns a background timer per turn. If Claude Code hangs or fails to emit a `result` frame within `turn_timeout_sec`, the process is terminated and automatically refreshed.
- **Session Recycling:** Transparently restarts the resident process after `turns_per_session` turns to keep KV cache size bounded and prevent context degradation.
