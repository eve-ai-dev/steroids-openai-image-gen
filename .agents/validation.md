# Validation contract

Acceptance owner: coordinator/Alberto. Implementation is local only, quality TOP because credentials and asynchronous effects are involved. Required independent review is commissioned by coordinator, not nested here.

## Safe local checks

Runtime: existing `/opt/hermes/.venv/bin/python` (3.14). Repo .venv (3.13) cannot import pygments; do not install to bypass prior security denial. `UPSTREAM` below is the read-only admission checkout verified at `2e83e2a935ee04f606aab58e498d34ca58d84c07`; it supplies current public APIs absent from installed Hermes. Do not mutate it. `PYTHONDONTWRITEBYTECODE` prevents shared checkout bytecode writes.

```sh
export UPSTREAM=/opt/data/profiles/builder/cache/scratch/node-search-upstream-slim
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=$UPSTREAM:/opt/hermes
mkdir -p cache
/opt/hermes/.venv/bin/python -m pytest -q --basetemp=cache/pytest -W error::RuntimeWarning
/opt/hermes/.venv/bin/python .agents/validate_admission.py
git diff d77ba961bcf6547d27c8c5cf498f5b5742fcd675 --check
```

Expected: tests pass; actual PluginContext registers provider and all three namespaced tools without modifying built-ins; scoped secrets cannot inherit a foreign profile key; real signed-in helper rejects untrusted origin before auth/network; supervised background tasks survive tool return, preserve originating context, distinguish each/batch notification, record refusal, cancel on actual manager unload, and report interrupted jobs after restart.
Session/lifecycle regressions in tests/test_session_lifecycle.py dispatch registered tools against actual upstream keyed local/messaging policy, refuse cross-session/replaced-id/ownerless reads, reproduce close immediately after loop acquisition, force enqueue and spawn rejection, and overlap admission with concurrent close/unload. Run with `-W error::RuntimeWarning` to reject coroutine leaks. Tests use synthetic session authorities and transports, never a live gateway. The documented session reader triggers an upstream admission allowlist warning; see outputs/session-lifecycle-evidence.md for the primary-source contract, not a suppression or private adapter. Synthetic bytes/results and host test injectors prove these local boundaries, not paid generation or real platform media transport. Old queue-event/parser tests were removed with their private implementation; new boundary tests replace that protection rather than retaining fabricated events.

Admission script invokes current upstream `validate_plugin_dir`: manifest/capability parity, no collisions, security scan and no core rebinding. Expected ok; the single documented-session-reader allowlist warning must be reviewed against the cited public contract. It does NOT install dependencies. `--install-deps` is blocked pending changed security-service evidence/approval following prior OSV/deps.dev/ecosyste.ms timeouts; do not repeat equivalent blocked installation.

## Deterministic changed-code quality

External canonical dependency: Builder Assurance 1.1.0, resolved at `/opt/data/profiles/builder/skills/software-development/builder-assurance`; schema vendored at `.agents/quality-policy-v1.schema.json`. Immutable Git baseline is `d77ba961bcf6547d27c8c5cf498f5b5742fcd675`; same policy and Python AST adapter before/after. No JS/TS adapter applies to this Python-only plugin.

```sh
/opt/hermes/.venv/bin/python /opt/data/profiles/builder/skills/software-development/builder-assurance/scripts/validate_quality_policy.py .agents/quality.yaml
/opt/hermes/.venv/bin/python /opt/data/profiles/builder/skills/software-development/builder-assurance/scripts/quality_report.py --repo . --base d77ba961bcf6547d27c8c5cf498f5b5742fcd675 --scope all --level top --config .agents/quality.yaml --output outputs/quality-final.json
```

Expected QUALITY_PASS; untouched or nonworsened strong debt remains visible. No exception authorized. Baseline evidence is outputs/quality-baseline.json. Quality does not establish feature or release acceptance.

## Coordinator-owned incomplete gates

- Real text generation and reference/masked edits on an approved endpoint, across aspects and controls; inspect output bytes and backend errors. No paid API calls authorized here.
- Real Codex supported-route generation/edit/aspect acceptance without vendor impersonation. Auth refresh/network writes not authorized here.
- Actual target-client media delivery: approve synthetic media to a specified safe session/platform first; observe attachment at that exact target, including failure and cross-session isolation. An injection receipt is insufficient. Then separately approve real generation if required.
- Dependency install under current Hermes core constraints and approved package-security path; regenerate stale uv.lock only through that path.
- Independent security/concurrency review of candidate and quality policy; fix blocking findings before publication.

No live runtime restart/config/auth changes, external sends, pushes or catalogue PR creation are performed by Builder. Keep release blocked until these applicable checks have actual evidence.
