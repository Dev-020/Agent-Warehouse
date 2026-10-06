# Changelog

All notable changes to `skill/claude-code-engine` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-09-24

### Added
- Initial draft of the Claude Code headless CLI engine operating protocol.
- Stream-JSON NDJSON protocol specification for inbound envelopes and outbound event frames.
- Profile isolation architecture (`CLAUDE_CONFIG_DIR`, `CLAUDE_CODE_DISABLE_CLAUDE_MDS=1`, `--setting-sources project,local`).
- Ready-on-spawn timing invariant documentation.
- Supervisory control rules: watchdog timeouts, turn recycling, stderr draining, and FIFO turn gating.
