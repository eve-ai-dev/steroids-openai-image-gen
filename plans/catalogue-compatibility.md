# Catalogue compatibility 0.2

Classification: existing project task with minimal governance repair. Authority: complete-target local implementation and coherent local commits only. Coordinator owns independent review, real paid generation/media acceptance and publication. Sole write scope is this repository.

## Outcome and dependency order

1. Immutable baseline and public API reconnaissance → 2. namespaced registration + supported credentials → 3. supervised background work/notification → 4. synthetic/local admission and quality → 5. coordinator real integration + independent review → 6. coordinator publication if accepted.

0.2 promise: preserve provider registration and advanced sync/background/status workflows without builtin name collisions, private token access, vendor-client impersonation or fabricated delegation events. Compatibility/migration and disclosures are README-owned. No changes to active external skills, runtime configuration, profile/core or other plugins.

Acceptance owner: coordinator/Alberto. Observable criteria: provider and three prefixed tools register, core tools unchanged; masks/references/fidelity/quality/aspect controls survive; scoped keys stay profile-owned; Codex uses host signed-in route; background tasks outlive tool return, support each/batch, cancellation and restart reporting; injection receipt is distinct from delivery proof. Concrete checks and expected failures are solely in .agents/validation.md.

Recovery: revert the local compatibility commit to the baseline only if intentionally returning to the old private/colliding implementation; do not use that as a catalogue release. Retain job records; interrupted jobs are not retried. No auth/config migration is performed automatically.
