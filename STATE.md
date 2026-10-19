# Current state

0.2.0 catalogue-compatibility candidate; **blocked for release**. First independent review rejected R1–R3 at 4bd5053; this continuation implements the linked session identity/lifecycle fixes and awaits coordinator-owned re-review. Authority: complete-target local implementation/commits only. No publication, push, runtime restart/configuration, external messages, credential changes or paid requests authorized/performed.

## Implemented

- Provider remains `steroids-openai`; advanced tools now `steroids_image_generate`, `steroids_image_generate_background`, `steroids_image_generate_background_status`. Built-in tools are untouched, with no old-name shims.
- Scoped secret resolver and host-owned signed-in Codex requests replace direct env/Codex-store access and vendor impersonation.
- Public supervised tasks and explicit captured-session message injection replace fabricated async delegation queue events. Frozen route/session-id ownership authorizes status; ownerless legacy records fail closed. Admission/persistence/scheduling serialize with shutdown, with failed scheduling terminalizing created records and returning IDs. Each/batch modes, persistence, interruption reporting and unload cancellation remain. Accepted notification is never confirmed media delivery.
- Existing endpoint generation/edit, mask/reference/fidelity/quality/aspect behavior retained; invalid controls rejected before requests. Migration, operational limits and risks documented in README.

## Verified locally

Baseline: `d77ba961bcf6547d27c8c5cf498f5b5742fcd675`, 31 baseline tests passed. Revised candidate: 48 tests passed in 1.19s with RuntimeWarning as error, using existing Hermes Python and upstream APIs at `2e83e2a935ee04f606aab58e498d34ca58d84c07`. Real builtin/provider registration/unload, public origin rejection before auth, scoped secret isolation, task supervision, synthetic each/batch outcomes, actual keyed messaging/local admission policy, status-owner denial, deterministic shutdown interleavings, scheduling rejection and restart reporting exercised. Test injectors are not platform delivery. Directly tested upstream files are at the cited commit; unrelated pre-existing dirty ACP files in the shared checkout were not modified.

Upstream admission: ok, no collisions/core rebinding detected; one retained static allowlist warning for gateway.session_context.get_session_env, explicitly documented by the current primary plugin guide. See outputs/session-lifecycle-evidence.md for exact contract and release-tag inspection; independent review must assess the warning. Report: outputs/admission.json. TOP deterministic quality: QUALITY_PASS, no exception; outputs/quality-final.json. Baseline report: outputs/quality-baseline.json. Existing nonworsened complexity debt remains visible; this is not a general refactor. Canonical executable commands and required incomplete checks are .agents/validation.md.

Self-review examined replacement consumers: register entry point, provider, advanced handlers, probe scripts and tests. Private queue implementation/tests retired together; public boundary tests replace their protection. No shipped skills; external active skills unchanged. No graph analyzer adopted; dynamic Hermes integration coverage is limited to those explicit entry points and upstream admission.

## Remaining gates and recovery

1. Coordinator independent review (security, concurrency, compatibility and quality-policy baseline).
2. Approved dependency installation under Hermes constraints; prior security service timeout denial was not retried. uv.lock is stale and not a 0.2 install proof.
3. Real Codex and endpoint generation/edit acceptance with approved paid calls, plus actual media attachment observed in coordinator-specified safe target. None performed. Installed Hermes lacks the tested newer public seams; upstream checkout testing is not runtime upgrade/installation evidence.
4. Coordinator alone may push and propose catalogue entry after applicable gates pass; maintainer merge remains separate.

Recovery: no automatic job retry or auth migration; inspect persisted interrupted jobs before resubmission to avoid duplicate charges. Rollback information is in plans/catalogue-compatibility.md. Proposed catalogue pin will identify the implementation commit, not an unreviewed moving branch.
