# R1–R3 implementation evidence

Review source: /opt/data/profiles/reviewer/cache/scratch/steroids-4bd5053/REVIEW.md. Original reproduction greens were not counted as acceptance. New regressions change the expected outcomes.

## Public identity contract

Primary source retrieved read-only: https://hermes-agent.nousresearch.com/docs/developer-guide/plugins/ , section "Where handlers run", states: "Read session identity with gateway.session_context.get_session_env(\"HERMES_SESSION_PLATFORM\") and the other HERMES_SESSION_* names, not os.environ."

The plugin reads HERMES_SESSION_KEY and HERMES_SESSION_ID once on tool submission into a frozen SessionOwner. It imports no private plugin_session helper and accepts no model-supplied owner. Status captures the same host context independently. Both fields must match the persisted owner; missing context, missing owner and replacement session id fail closed. The profile-scoped job directory remains the profile boundary. Explicit ctx.inject_message(session_key=...) replaces keyless routing for all submissions.

Upstream admission at source 2e83e2a935ee04f606aab58e498d34ca58d84c07 warns on gateway.session_context.get_session_env because its static allowlist omits this documented name. Warning is retained in outputs/admission.json; no scanner/core changes or suppression were made. Independent review must reconcile it with the primary public guide, not mistake the admission ok flag for warning-free approval.

## Lifecycle invariant

Runner RLock serializes loop acquisition, persistence and supervised task acquisition with close. Reentrant close after loop acquisition is detected before persistence. Shutdown rejects subsequent admissions; concurrent close calls serialize. Enqueue/spawn failures close unscheduled coroutine objects, terminalize created records and return their identifiers. Cancellation remains on the owning loop; unload callback acquisition follows the task lease so reverse teardown closes first. No automatic paid retry or keyless fallback added.

## Regression scope

- Actual registered background/status tools, Discord/local and each/batch, run through upstream keyed admission policy with synthetic session store/authorities. Keyless path still uses upstream refusal policy, so the old implementation fails this regression. No live platform dispatch is claimed.
- Allowed owner, different session, replacement id, missing context and legacy ownerless records.
- Exact reviewer interleaving (close after loop acquisition), enqueue/spawn rejection, concurrent close and actual manager unload during paused admission, queued/running cancellation. RuntimeWarning treated as error.
- Existing provider controls and public-boundary tests remain exercised.

## Released-host inspection (read-only)

`git ls-remote --tags https://github.com/NousResearch/hermes-agent.git 'refs/tags/v0.*'` found latest stable tag v0.22.2, peeled commit d923a5eb487a17c0a68801bba9ef0f56c81040a8. Tagged raw plugin_provider_requests.py exists; tagged hermes_cli/plugin_session.py returns 404. This does not prove every current required seam at a released host. No requires_hermes floor invented; released-host compatibility remains blocked. No shared checkout mutation or tag fetch performed.

Dependency installation/lock regeneration, real endpoint/Codex generation and actual target media remain incomplete and unauthorized here. No install retry, credential access, external send, runtime/profile/core modification, push or nested review performed.
