---
id: tool/antigravity-cli-runner
version: 0.1.0
status: draft
summary: Resident CLI driver, profile isolator, glog error parser, and NDJSON session manager for Antigravity CLI.
applies-to: [codebase, vault]
entrypoint: antigravity_cli_runner.py
requires-software: [python>=3.10, agy]
platforms: [windows, macos, linux]
settings: {}
requires: []
replaces: null
---

# `tool/antigravity-cli-runner`: Resident Antigravity CLI Session Manager

A robust, dependency-free Python runner and library for managing resident Antigravity CLI (`agy`)
processes over bidirectional NDJSON (`stream-json`) streams.

Used with [[skill/antigravity-engine]], this tool provides full process lifecycle supervision, profile
sandboxing, ready-on-init synchronization, glog error recovery from internal log files, watchdog timeouts,
and streaming progress parsing.

---

## 1. Prerequisites

- **Python** $\ge$ 3.10 on system `PATH`.
- **Antigravity CLI** (`agy` or `agy.exe`) installed on the system and authenticated with a Google account.

---

## 2. CLI Usage

The runner can be used directly from the command line for environment diagnostics, sandbox setup, and running single or interactive turns:

```bash
# Verify binary presence, profile setup, and log directory access
python tools/antigravity-cli-runner/antigravity_cli_runner.py check [--json]

# Initialize an isolated profile directory with sandbox settings and grants
python tools/antigravity-cli-runner/antigravity_cli_runner.py profile setup [--profile-dir DIR] [--workspace DIR]

# Run a single turn against the resident Antigravity engine
python tools/antigravity-cli-runner/antigravity_cli_runner.py run --prompt "Verify database schema" [--model MODEL]

# Start an interactive CLI chat session with streaming responses
python tools/antigravity-cli-runner/antigravity_cli_runner.py chat [--model MODEL]

# Inspect and parse the most recent glog error from Antigravity logs
python tools/antigravity-cli-runner/antigravity_cli_runner.py log-diagnostics [--workspace DIR]
```

---

## 3. Core Commands Reference

| Command | Arguments | Purpose |
|---|---|---|
| `check` | `[--bin BIN] [--profile-dir DIR] [--json]` | Verifies `agy` binary, checks profile existence, and probes log directory. |
| `profile setup` | `[--profile-dir DIR] [--workspace DIR]` | Configures `.gemini/config/config.json`, permissions in `settings.json`, and redirects `TEMP`. |
| `run` | `--prompt PROMPT [--workspace DIR] [--model MODEL] [--timeout SEC] [--json]` | Sends a turn to a resident `agy` session, waits for `init`, streams text deltas, and outputs result. |
| `chat` | `[--workspace DIR] [--model MODEL]` | Interactive terminal conversation loop maintaining resident session continuity. |
| `log-diagnostics`| `[--workspace DIR] [--log-dir DIR]` | Scans the latest Antigravity CLI log file and extracts root-cause glog error lines. |

---

## 4. Python Library Integration

Any Python project can import `AntigravityCliSession` to embed Antigravity natively:

```python
from antigravity_cli_runner import AntigravityCliSession, EngineConfig

config = EngineConfig(
    agy_bin="agy",
    profile_dir="./.agy-engine",
    workspace_dir="./project",
    model="gemini-3.8-flash-medium",
    turn_timeout_sec=120.0,
    turns_per_session=15,
)

session = AntigravityCliSession(config)
session.start()

# Event hooks
session.on_chunk = lambda delta: print(delta, end="", flush=True)
session.on_status = lambda status: print(f"[{status}]", flush=True)

# Submit a turn and wait for result
result = session.send_and_wait("Review the recent pull request diff.")
if result.success:
    print(f"\nFinal response: {result.text}")
    print(f"Tokens: {result.usage}, Duration: {result.duration_seconds}s")
else:
    print(f"\nTurn failed: {result.error}")

session.stop()
```

---

## 5. Architectural Safeguards

- **Ready-on-Init Synchronization:** Guarantees turns are queued and held until `{"event":"init"}` is parsed from stdout, avoiding early-dispatch message loss.
- **Glog Diagnostic Fallback:** Automatically tails `cli-*.log` when a turn returns a generic error (`"Agent execution terminated due to error."`), recovering true exception details.
- **Unfinished Tool Detection:** Detects tool steps that remain `ACTIVE` without a `DONE` event when `result` arrives, surfacing auto-denied operations immediately.
- **Temp Sandbox Protection:** Injects isolated `TEMP` and `TMP` paths to prevent accidental writes or reads to the host temporary directory.
- **Watchdog Timeout:** Background watchdog restarts the session if a model call or tool hangs beyond `turn_timeout_sec`.
