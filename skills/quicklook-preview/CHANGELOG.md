# Changelog

## [Unreleased]

## [0.1.0] - 2026-10-07
### Added
- Initial draft of `skill/quicklook-preview`: how agents show generated files to the user in QuickLook through the machine's `ql` command — only when the user asks, or after asking the user's permission for that file — with a fallback to giving the file path when `ql` is not available.
- Warning that the skill was tested only against the experimental QuickLook build `4.5.0-218-g3460ca3`, with steps to check the installed version and to report breakage with `warehouse issue skill/quicklook-preview`.
