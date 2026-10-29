# Parent-only installation / rollback delta

**Prepared, not executed; no activation permission granted here.** Real approved managed calls now demonstrate `gpt-image-2` generation and multi-reference editing. Earlier catalog/openapi metadata is not a functional route blocker and does not prove upstream/account/billing ownership. Masked POSTs succeed as transport but visual acceptance remains failed (black transparent-region artifacts); parent must resolve or explicitly disposition this limitation before claiming full functionality. Redacted receipts: `../tasks/recover-current-hermes/evidence/live-*-fixed.json` and `live-masked-edit-source-rgb.json`.

## Resolve before activation

Use the already-tested managed `OPENAI_BASE_URL` + profile-scoped `OPENAI_API_KEY`, exact model `gpt-image-2`. JSON generation and multipart edits now have live functional evidence. Multiple sources use repeated `image[]`; single source uses `image`. Omit `input_fidelity` for this model: explicit requests fail locally with `invalid_input_fidelity_model`; no silent drop/retry. Supporting models retain forwarding. Native Hermes Codex uses a different protocol/private resolver which this plugin does not call. Do not guess a `codex/...` alias, select `openai/*`, reuse native Codex tokens, mutate Route or enable a fallback. No Hermes upgrade is needed for this correction. Ownership evidence remains separately unverified, not disproven by metadata.

## Exact target homes

| Profile | Home | New plugin destination |
|---|---|---|
| default | `/opt/data` | `/opt/data/plugins/steroids-openai-image-gen` |
| work | `/opt/data/profiles/work` | `/opt/data/profiles/work/plugins/steroids-openai-image-gen` |
| coach | `/opt/data/profiles/coach` | `/opt/data/profiles/coach/plugins/steroids-openai-image-gen` |
| fiscal | `/opt/data/profiles/fiscal` | `/opt/data/profiles/fiscal/plugins/steroids-openai-image-gen` |
| reviewer | `/opt/data/profiles/reviewer` | `/opt/data/profiles/reviewer/plugins/steroids-openai-image-gen` |

Recheck destination vacancy/config state immediately before writes. Preserve any intervening foreign state. Parent exports the accepted commit using `git archive <accepted-commit>` into an inspected **vacant** destination, not `cp -a` from old or working homes. No .venv/caches/jobs/credentials are copied. Source provenance: historical RO repository `/mnt/old-hermes/plugins/steroids-openai-image-gen`, starting HEAD `115868605716be75c86ee7b438f7e95367590e9f`, historical remote `github.com/eve-ai-dev/steroids-openai-image-gen.git`; local checkout retains that history. No release/push implied.

## Config merge (all five homes, preserve unrelated keys)

Usable tested selector and scoped binding (parent-owned merge only):

```yaml
image_gen:
  provider: steroids-openai
  model: gpt-image-2
  steroids-openai:
    mode: openai-compatible
    base_url: ${OPENAI_BASE_URL}
    api_key_env: OPENAI_API_KEY
    quality: medium
    max_reference_images: 16
plugins:
  entries:
    steroids-openai-image-gen:
      allow_gateway_injection: true
platform_toolsets:
  discord: [connections, hermes-discord, image_gen]
```

This is a merge delta, not a full replacement config. `${OPENAI_BASE_URL}` refers to the approved live-tested managed endpoint, not proof of Codex ownership. No endpoint values or credentials are included here. No new secret variable/key or credential copy. Native enable resolves/merges the plugins.enabled selection; do not replace existing enabled/disabled lists. Keep builtin image_generate and other providers/tools untouched. Source tests show `image_gen` resolution includes all three namespaced tools, while current Discord `[connections, hermes-discord]` does not.

## Parent-authorized activation procedure

1. Snapshot the five config files privately with owner/restore paths; record the exact pre-change keys and destination vacancy. Do not include secret files in evidence. Validate the accepted source with `.agents/validation.md` and dependency-range checks; no installation if already satisfied.
2. Export source, merge the above reviewed deltas, then use native `hermes plugins enable steroids-openai-image-gen` with `HERMES_HOME` set to each exact home. This is an active operation, **not authorized in the candidate task**. Inspect consent/dependency/security prompts; do not bypass them or accept an install retry from historical denial without changed evidence/authority.
3. Inspect native activation output. Current `activate_plugin_now` nudges the control socket; `reload_gateway_plugins(gateway_home, profile_home=target_home)` is the actual supported targeted reload helper if the parent needs an explicit refresh. It rejects homes not served by this gateway. Recheck plugin activation and reload response; no successful reload -> report the blocker, not automatic restart. `gateway/run_plugin_rewire.py` rewires handlers; tools/prompts wait for a fresh session.
4. In separately approved fresh sessions for all five homes verify three namespaced tools visible with existing Discord tools intact and builtin image_generate untouched. Confirm scoped credentials by availability only; never print values. Registration/admission does not prove this live visibility.
5. Separately authorize a synthetic notification/media test to an explicit safe chat/thread; inspect actual attachment. Reuse the authorized generation/reference-edit receipts where candidate-bound; masked visual acceptance is still failed and needs parent disposition. Any further paid calls require applicable remaining/new authority; upstream ownership is not proved. Inspect response bytes and upstream routing receipts, no automatic retry. `delivery.accepted` is not media confirmation.

## Rollback (parent-owned; preserve data)

- Stop new submissions, record in-flight IDs, disable/unload this plugin with native `hermes plugins disable steroids-openai-image-gen` in each affected home and verify reload/unload. In-flight blocking HTTP may still finish; unload prevents later plugin notification, not backend billing reversal.
- Restore **only** the added image_gen selection/subconfig, injection grant and appended platform toolset element from the private pre-change snapshot if still unchanged by others. Keep foreign edits/enabled plugins. Do not restore whole runtime state or credential files.
- Retain plugin source and `steroids_openai_image_gen/jobs`/images for operator inspection. Remove a newly installed tree only after parent ownership/retention approval and proven unload. Do not delete old-home sources or job records. Queued/running records from prior instances report interrupted; resubmission is manual and may bill again.
- No Hermes upgrade/downgrade/restart, profile restoration or vault rollback is part of this delta.
