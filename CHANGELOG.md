# Changelog

## 1.0.0

First stable release, explicitly accepted by the maintainer with the limitations below. A substantial current-Hermes compatibility adaptation, not a total rewrite.

### Changed
- Three namespaced tools preserve Hermes's built-in image tool.
- Current public plugin, scoped-secret, guarded-reference and session APIs.
- Supervised background generation/editing, persisted status, origin-chat notifications, cancellation and restart interruption without automatic retries.
- Correct multipart edits: one `image` field for one source; repeated `image[]` fields for multiple sources.
- Explicit local rejection of unsupported configurable `input_fidelity` for `gpt-image-2`; supporting models retain the control.
- Bounded local/remote references, native URL/file guards, no automatic paid retry or redirect following for image POSTs.

### Verification
- 60 local tests, isolated native admission and independent source review passed on the tested Hermes revision; see `.agents/validation.md`.
- Real generation and multi-reference editing visually verified during recovery.
- Maintainer-reported smoke test passed direct generation, asynchronous editing and status lookup.
- Maintainer reports Codex routing and no API spend after checking their account; routing/billing depends on the configured server, not the tool name.

### Known limitations / migration
- Masked edits on the tested endpoint produce black mask-region artifacts. Do not rely on localized masked edits; correction deferred.
- Background `accepted` means the host accepted the notification, not that the transport confirmed an attachment.
- Direct legacy `codex-auth` mode is unavailable on the tested Hermes without its public credentialed request helper; no token-store fallback exists. The tested route uses the managed OpenAI-compatible endpoint.
- Replace old unprefixed plugin overrides with the three `steroids_image_*` tools; keep built-in tools untouched.
- Historical `uv.lock` is not an authoritative install lock for this release. Use the declared bounded dependencies and the host's approved dependency mechanism.
- Source release does not imply activation in every profile. Multi-profile activation remains an operator task.
