# Changelog

All notable changes to `skill/antigravity-engine` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-09-24

### Added
- Initial draft of the Antigravity headless CLI engine operating protocol.
- Stream-JSON NDJSON protocol specification for inbound envelopes and outbound event frames (`init`, `step_update`, `result`).
- Profile sandboxing guidelines: `USERPROFILE`, `HOME`, and `%TEMP%` redirection.
- Permission grant schema documentation for `.gemini/antigravity-cli/settings.json` (bare path rules, no globs).
- Glog log recovery pattern for recovering true error diagnostics from `cli-*.log`.
- Ready-on-init timing invariant documentation.
- Grounding conventions: normalized 0-1000 coordinate grid vs pixel coordinates.
