# steroids-openai-image-gen

Hermes provider `steroids-openai` and three namespaced advanced tools. Supports text-to-image generation, image edits/references, per-call quality and asynchronous jobs with origin-chat notification. Mask parameters are exposed but localized masked editing has a known endpoint defect; configurable input fidelity depends on the model. Built-in `image_generate` remains owned by Hermes.

## Version 1.0.0 — current-Hermes compatibility release

Locally validated against installed Hermes upstream revision `e8c97320ac8691d4de92af49f98459f9ef9ddb08`, without upgrading or patching Hermes. See `STATE.md` and `.agents/validation.md` for actual evidence and remaining gates. A protocol-compatible endpoint is **not** an OpenAI upstream selection and is **not** proof of Codex ownership. The approved managed `OPENAI_BASE_URL` + scoped `OPENAI_API_KEY`, model `gpt-image-2`, has now returned real generation and reference-edit PNGs. Earlier route metadata is not a functional blocker. Upstream/account/billing ownership remains unverified; do not infer it from protocol or use `openai/*`/guessed aliases as fallback. Authorized masked-edit POSTs returned PNGs but failed visual acceptance (black mask-region artifacts); masked functionality remains unaccepted. The plugin has since been enabled in the operator's default profile. An operator-reported smoke test passed generation, asynchronous editing and status lookup; automatic attachment delivery remains unconfirmed. The operator reports Codex routing and no API spend after checking their account. This is deployment-specific evidence, not an independently audited upstream/billing guarantee for arbitrary endpoints.

The maintained compatible transport requires an endpoint supporting JSON `/images/generations` and multipart `/images/edits`. GPT Image payloads omit `response_format`; the client does not retry a failed paid request or follow image-POST redirects. The native Codex image backend instead uses a different JSON-edit protocol. Do not select that protocol without approved endpoint-contract evidence.

`mode: codex-auth` is retained legacy source, not the selected recovery route. It requires the public host `credentialed_provider_request` helper, absent in this Hermes, and returns unavailable without reading Codex tokens. The manifest's old unknown `requires_auth` field was removed: it never provided an auth gate. No credential-store or vendor-client fallback exists.

## Installation / configuration — operator-managed

Place a reviewed source export under the selected home's `plugins/steroids-openai-image-gen`; `HERMES_HOME` already identifies the profile home. Native plugin enable/reload is a separate authorized parent operation. Current Hermes supports plugin reload; a restart is not assumed. Tools/prompts become visible on a fresh session. Detailed exact merge delta, admission, reload and rollback steps: `outputs/parent-installation.md`. Installing this source does not itself configure or enable any home.

For parent-owned activation of the tested managed compatible endpoint, merge (do not overwrite unrelated config); this example is not activation permission:

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
```

The model is the exact live-tested selector, not proof of upstream ownership. The key name refers to Hermes's approved managed layer, not OpenAI billing selection. Do not copy `.env`, tokens or credentials. The plugin uses public profile-scoped `agent.secret_scope.get_secret`; nested `${NAME}` resolution preserves that scope. No `CUSTOM_1_API_KEY` is introduced. Manifest declares the endpoint key as an optional secret. Add `image_gen` to the existing platform toolsets while retaining existing entries; provider registration alone does not expose advanced tools on Discord.

Dependencies have bounded ranges. Reuse approved installed versions when satisfied. Historical `uv.lock` is stale, not authoritative for this candidate; installation/lock changes require the approved package-security route, not an environment-copy workaround.

This is a substantial compatibility adaptation, not a total rewrite: the existing provider, transport and supervised background architecture are retained. Old unprefixed override calls must migrate to the namespaced tools. See [CHANGELOG.md](CHANGELOG.md) for the 1.0.0 scope and known limitations.

## Advanced calls

Tools:
- `steroids_image_generate`
- `steroids_image_generate_background`
- `steroids_image_generate_background_status`

Old unprefixed plugin overrides have no shims. Remove an old override grant only if it was solely for this plugin; update your own saved calls. Active external skills are not edited by this repository.

```json
{
  "prompt": "make the red square blue",
  "aspect_ratio": "square",
  "quality": "medium",
  "image_url": "/path/source.png",
  "reference_image_urls": ["/path/ref.png"]
}
```

Aspect: `landscape|square|portrait`, default follows Hermes provider default; standard sizes 1536x1024, 1024x1024, 1024x1536, configurable under `sizes`. Quality: `low|medium|high|auto`; configurable fidelity: `low|high` on supporting models only. Exact `gpt-image-2` does **not** support `input_fidelity`: omit it. Explicit requests fail locally with `invalid_input_fidelity_model`, never silently dropped or retried; capabilities report false. Inherent backend fidelity is not configurable fidelity support. Invalid controls fail before backend calls. Model and quality are separate controls.

Edits send `image` for a single source, repeated `image[]` for all sources when multiple, plus optional `mask` and supported fidelity. **Known limitation in 1.0.0:** avoid masked edits on the tested endpoint until the black-region defect is resolved. Source and alpha mask must be same-size PNGs; transparent pixels designate editable regions in the protocol. Current managed gpt-image-2 live masks produced black rectangles matching transparent regions, including a corrected source-RGB mask probe; do not claim reliable localized editing or exact outside-mask preservation on this endpoint. Prompt coordinates alone do not enforce boundaries. The total source count includes the primary image and defaults to 16; overflow is an explicit error, never silent truncation. Reference bytes default to 25 MiB each; local reads apply native credential-file protection, remote reads apply native URL/website/redirect policy and streaming limits, base64 decoding is bounded. `allow_remote_images: false` disables remote inputs.

Backend errors/size rejection are surfaced without silently changing aspect or retrying. Responses accept `data[0].b64_json` or URL, retaining revised prompt and actual size when available. A response URL is not independently confirmed media delivery.

## Background lifecycle and privacy

Supply the same controls plus `delivery_mode: each|batch`, or a `jobs` array. Omit `jobs` for a single prompt; empty `jobs` plus prompt is also accepted. Max batch defaults to 4 (`STEROIDS_IMAGE_BG_MAX_JOBS`, range 1–32); concurrency defaults to 2 (`STEROIDS_IMAGE_BG_MAX_CONCURRENT`, range 1–16). These are nonsecret process tuning controls, not paid-call approval.

The plugin runs a lazy event-loop thread and public `ctx.spawn_task` supervision. A calling session key and ID are mandatory before persistence; explicitly stateless channels are rejected with public `async_delivery_supported()`. That capability does not guarantee a live injector; host refusal remains a failed delivery receipt. Worker profile/home/secret context is inherited, not replaced by the ambient session at completion.

Status is private to the frozen submitting **key+ID**. Foreign keys, replacement IDs, missing identity and ownerless legacy records fail closed. Records live in the active home's `steroids_openai_image_gen/jobs/<job_id>/`, with status and optional result JSON. Old queued/running records report `interrupted` after restart and are never automatically retried. Duplicate submissions are distinct potentially paid work.

Notifications use the captured explicit **durable origin-chat key**, not a current/keyless route. Installed Hermes resolves that key's current source and ID and rechecks current authorization. A conversation reset may therefore notify the same origin chat/thread under its replacement ID, while that new ID cannot inspect the old job with the status tool. This is origin-chat binding, **not frozen-conversation-ID delivery**. Missing routes/current authorization denial are handled by the native dispatcher. Do not claim a synchronous injection return proves eventual dispatch.

`delivery.status=accepted` means only that Hermes accepted a notification turn containing `MEDIA:<path>`. `confirmed` stays false: no proof the model forwarded it or the platform attached it. Injection may trigger a separately billed model turn and requires the operator's gateway-injection grant. Unload cancels jobs and stops the loop; already-running blocking HTTP may finish but will not notify after cancellation. Scheduling rejection terminalizes created records and returns their IDs. No private queue/table manipulation is used.

## Risks / recovery

Generation sends prompt and selected reference/mask bytes to the configured endpoint. Source/result URLs may cause downloads. Prompts, selected paths, errors and generated output persist under the active profile; operator owns retention. Native guards are policy controls, not a filesystem sandbox. No telemetry, self-update, shell execution, OAuth/token reads or auth writes occur in this runtime path.

Do not rerun interrupted jobs automatically; inspect records first to avoid duplicate charges. Parent rollback disables/unloads this candidate, restores only the reviewed config delta and preserves jobs/output. No runtime or vault rollback is implied. Scripts `scripts/probe_*` make paid requests and are excluded from safe validation; never run without separate approval.
