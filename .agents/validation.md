# Validation contract — current Hermes recovery

Acceptance owner: parent coordinator/Alberto. Local implementation only. TOP, original immutable baseline and unchanged quality policy required; independent plan and candidate review required. Safe commands below make no paid image requests, external messages, active-home discovery, dependency installation or service changes. The separate narrow live-fix assignment authorized up to four sequential edit POSTs; three were used with redacted task receipts. It does not expand this safe validation lane.

## Runtime and isolation

Use installed `/opt/hermes/.venv/bin/python` (verified Python 3.14.7), installed `/opt/hermes` at upstream revision `e8c97320ac8691d4de92af49f98459f9ef9ddb08`. Do not use a newer checkout as installed-runtime proof. No Hermes upgrade required for the tested plugin/task/session seams. Tests create disposable homes, synthetic secrets and in-memory gateway store/adapter fixtures. An autouse fixture blocks socket connections. Native plugin admission uses its own isolated recording subprocess and is complemented by actual PluginManager/PluginContext registration, registry dispatch, supervised tasks and unload tests.

From repository root:

```sh
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=/opt/hermes
export TMPDIR=../tasks/recover-current-hermes/scratch
mkdir -p "$TMPDIR"
/opt/hermes/.venv/bin/python -m pytest -q -W error::RuntimeWarning --basetemp="$TMPDIR/pytest-final"
/opt/hermes/.venv/bin/python .agents/validate_admission.py
git diff 115868605716be75c86ee7b438f7e95367590e9f --check
```

Expected: namespaced tools and provider register without builtin replacement; image_gen toolset resolution includes all namespaced tools. Existing Discord toolsets alone do not expose them: parent must add `image_gen`, retaining existing entries. Current gateway scheduler/dispatcher is exercised from `gateway.run_inbound`, with in-memory sources/store and synthetic adapter; no real transport or SessionDB is constructed. Verify missing identity/stateless rejection, frozen key+ID status privacy, explicit durable origin key, same-key replacement ID routing, current authorization/missing-route refusal, each/batch, injection refusal, cancellation/unload, scheduling failures and restart interruption/no automatic retries. Worker context retains scoped home/key. `accepted` means a notification was scheduled, not delivered.

Image tests cover single image/repeated image[] multipart payloads, omitted fidelity on gpt-image-2 and structured local rejection of explicit fidelity (supporting models still forward), generation/edit payloads, refs, alpha masks, quality/fidelity/aspects, structured errors, no response_format, no redirect/retry on image POST, file-read denial before bytes, native URL safety with unsafe metadata URL and redirect rejection, and bounded stream/local/base64 reads. Mock HTTP transports do not prove the remote image protocol or native connect-time DNS enforcement. Legacy signed-in Codex mode must report unavailable on this host: no fabricated `plugin_provider_requests` module or credential-store fallback.

## Deterministic changed-code quality

External canonical dependency: Builder Assurance 1.1.0, natively discovered package `/opt/shared-skills/builder-assurance`; scripts resolved under that same canonical package, not copied. Existing vendored schema `.agents/quality-policy-v1.schema.json`, original policy and baseline retained without threshold/adapter/exclusion/exception changes.

```sh
/opt/hermes/.venv/bin/python /opt/shared-skills/builder-assurance/scripts/validate_quality_policy.py .agents/quality.yaml
/opt/hermes/.venv/bin/python /opt/shared-skills/builder-assurance/scripts/quality_report.py --repo . --base d77ba961bcf6547d27c8c5cf498f5b5742fcd675 --scope all --level top --config .agents/quality.yaml --output outputs/recovery-quality.json
```

Expected `QUALITY_PASS`, no exception; existing nonworsened debt remains visible. Task starting HEAD is separately `115868605716be75c86ee7b438f7e95367590e9f`. Quality is not endpoint, media or release acceptance.

## Still parent-owned / incomplete

- Upstream/account/billing ownership is unverified, but earlier metadata is not a functional blocker: approved managed gpt-image-2 generation and reference edit have real PNG/visual evidence. No openai/* or guessed Codex fallback.
- Three authorized live edit POSTs: reference edit low landscape passes PNG/dimensions/visual check; high square masked edit and one explicit corrected source-RGB mask probe return PNG but fail visual acceptance with black mask-region rectangles. Raw task receipts live-*-fixed.json and live-masked-edit-source-rgb.json. Parent must disposition masked functionality; no automatic retries.
- Actual target-client media attachment observed at an explicitly approved chat/thread, including refusal. Native scheduling acceptance is insufficient.
- Activation and five-home config delta, native reload readback, fresh-session tool visibility; see `outputs/parent-installation.md`.
- Dependency installation and lock regeneration only if separately necessary and authorized through the current package-security path. Existing installed versions satisfy declared ranges; stale historical uv.lock is not install proof.
- Independent candidate review and parent integrated acceptance before deployment/publication. No push or release authorized here.
