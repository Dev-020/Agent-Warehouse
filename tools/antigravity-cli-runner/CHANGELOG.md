# Changelog

All notable changes to `tool/antigravity-cli-runner` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-09-24

### Added
- Initial release of `tool/antigravity-cli-runner`.
- Resident `AntigravityCliSession` class with bidirectional NDJSON `stream-json` handling.
- Ready-on-init gating to ensure prompt turns are dispatched only after CLI initialization.
- Glog log recovery parser to surface actual error messages from `cli-*.log`.
- Unfinished tool detection for diagnosing headless auto-denials.
- Profile sandbox generator: `USERPROFILE`, `HOME`, `TEMP`/`TMP` isolation, and bare-path recursive permission grants.
- Watchdog timer and timeout recovery.
- CLI commands: `check`, `profile setup`, `run`, `chat`, and `log-diagnostics`.
