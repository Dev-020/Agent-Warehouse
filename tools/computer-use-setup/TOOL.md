---
id: tool/computer-use-setup
version: 0.1.0
status: draft
summary: Diagnostic, configuration, and skill-link CLI for cua-driver desktop automation.
applies-to: [vault, codebase]
entrypoint: computer_use_setup.py
requires-software: [python>=3.10, cua-driver>=0.28]
platforms: [windows, macos, linux]
settings: {}
requires: []
replaces: null
---

# `tool/computer-use-setup`: cua-driver Environment & MCP Setup Tool

A harness-agnostic CLI tool to inspect the local `cua-driver` installation, verify the running daemon,
diagnose system accessibility permissions, generate Model Context Protocol (MCP) server configurations
with privacy protections, and link upstream skill packs.

Used in conjunction with [[skill/computer-use]] to provide safe, reproducible desktop automation across projects.

---

## 1. Prerequisites

- **Python** $\ge$ 3.10 on system `PATH`.
- **cua-driver** $\ge$ 0.28.0 installed on the system and running in daemon mode (`cua-driver serve`).

---

## 2. Commands & Usage

```bash
# Check if cua-driver is installed, meets the version floor (>= 0.28.0), and the daemon is active
python tools/computer-use-setup/computer_use_setup.py check [--json]

# Run system diagnostic probe (verifies accessibility tree and screen capture permissions)
python tools/computer-use-setup/computer_use_setup.py doctor [--json]

# Preview project-level MCP configuration (.mcp.json) with telemetry disabled
python tools/computer-use-setup/computer_use_setup.py configure --client generic

# Write project-level MCP configuration to .mcp.json
python tools/computer-use-setup/computer_use_setup.py configure --client generic --write

# Print Claude Code registration command
python tools/computer-use-setup/computer_use_setup.py configure --client claude-cmd

# Link the canonical cua-driver skill pack into detected agent directories
python tools/computer-use-setup/computer_use_setup.py skills install

# Inspect current skill linking status across agent harnesses
python tools/computer-use-setup/computer_use_setup.py skills status
```

---

## 3. Core Commands Reference

| Command | Arguments | Purpose |
|---|---|---|
| `check` | `[--json] [--driver-path PATH]` | Verifies binary presence, version floor ($\ge$ 0.28.0), daemon socket connectivity, and telemetry state. Exit code 0 if ready, 1 if not. |
| `doctor` | `[--json] [--driver-path PATH]` | Invokes the driver's native diagnostic report to check OS accessibility (UIA/AX/AT-SPI) and screen capture grants. |
| `configure` | `[--client CLIENT] [--target FILE] [--write] [--dry-run]` | Emits or merges MCP server configuration for the target agent harness. Enforces `CUA_DRIVER_RS_TELEMETRY_ENABLED=0`. |
| `skills` | `<status\|install\|update\|path>` | Manages the upstream versioned skill pack, symlinking or copying it to supported agent harnesses (Claude Code, Antigravity, OpenClaw, Codex, etc.). |

---

## 4. Privacy & Telemetry Standards

`cua-driver` enables telemetry by default. Whenever `configure` generates or modifies an MCP configuration,
it automatically injects:

```json
"env": {
  "CUA_DRIVER_RS_TELEMETRY_ENABLED": "0"
}
```

This enforces the warehouse rule that agent tool executions remain private and do not emit usage telemetry.
