# Changelog

All notable changes to `tool/claude-cli-runner` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-09-24

### Added
- Initial release of `tool/claude-cli-runner`.
- Resident `ClaudeCliSession` class with bidirectional NDJSON `stream-json` handling.
- Thread-safe FIFO turn queuing with watchdog timer and timeout recovery.
- Automatic session recycling after configured turn thresholds.
- Profile manager: `check`, `profile setup`, `profile login`, `run`, and `chat` commands.
- Sandboxing enforcement: `CLAUDE_CONFIG_DIR`, `CLAUDE_CODE_DISABLE_CLAUDE_MDS=1`, and `--setting-sources project,local`.
- Background `stderr` draining with permission error pattern matching.
