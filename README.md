# steroids-openai-image-gen

Hermes provider `steroids-openai` and three namespaced advanced tools. Preserves text generation, image edits/references, alpha masks, per-call quality and input fidelity, plus asynchronous jobs with origin-chat notification. Built-in `image_generate` remains owned by Hermes.

## Current-Hermes candidate, not deployed

Locally validated against installed Hermes upstream revision `e8c97320ac8691d4de92af49f98459f9ef9ddb08`, without upgrading or patching Hermes. See `STATE.md` and `.agents/validation.md` for actual evidence and remaining gates. A protocol-compatible endpoint is **not** an OpenAI upstream selection and is **not** proof of Codex ownership. No accepted managed Codex image route is established yet; do not use the advertised `openai/gpt-image-2` or bare alias as a supposed Codex fallback. No paid calls or live messages were made for recovery.

The maintained compatible transport requires an endpoint supporting JSON `/images/generations` and multipart `/images/edits`. GPT Image payloads omit `response_format`; the client does not retry a failed paid request or follow image-POST redirects. The native Codex image backend instead uses a different JSON-edit protocol. Do not select that protocol without approved endpoint-contract evidence.

`mode: codex-auth` is retained legacy source, not the selected recovery route. It requires the public host `credentialed_provider_request` helper, absent in this Hermes, and returns unavailable without reading Codex tokens. The manifest's old unknown `requires_auth` field was removed: it never provided an auth gate. No credential-store or vendor-client fallback exists.

## Installation / configuration — parent only

Place a reviewed source export under the selected home's `plugins/steroids-openai-image-gen`; `HERMES_HOME` already identifies the profile home. Native plugin enable/reload is a separate authorized parent operation. Current Hermes supports plugin reload; a restart is not assumed. Tools/prompts become visible on a fresh session. Detailed exact merge delta, admission, reload and rollback steps: `outputs/parent-installation.md`. This candidate does not modify active homes.

After the parent establishes the exact Codex-owned endpoint/model and compatible image protocol, merge (do not overwrite unrelated config):

```yaml
image_gen:
  provider: steroids-openai
  model: <verified-exact-image-model-id>
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

The model placeholder is deliberately **not executable configuration**. The key name refers to Hermes's approved managed layer, not OpenAI billing selection. Do not copy `.env`, tokens or credentials. The plugin uses public profile-scoped `agent.secret_scope.get_secret`; nested `${NAME}` resolution preserves that scope. No `CUSTOM_1_API_KEY` is introduced. Manifest declares the endpoint key as an optional secret. Add `image_gen` to the existing platform toolsets while retaining existing entries; provider registration alone does not expose advanced tools on Discord.

Dependencies have bounded ranges. Reuse approved installed versions when satisfied. Historical `uv.lock` is stale, not authoritative for this candidate; installation/lock changes require the approved package-security route, not an environment-copy workaround.

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
  "reference_image_urls": ["/path/ref.png"],
  "mask_url": "/path/mask.png",
  "input_fidelity": "high"
}
```

Aspect: `landscape|square|portrait`, default follows Hermes provider default; standard sizes 1536x1024, 1024x1024, 1024x1536, configurable under `sizes`. Quality: `low|medium|high|auto`; fidelity: `low|high`. Invalid controls fail before backend calls. Model and quality are separate controls.

Edits send primary `image`, extra `image[]`, optional `mask` and fidelity. Source and alpha mask must be same-size PNGs; transparent pixels are editable. Prompt coordinates alone do not enforce boundaries. The total source count includes the primary image and defaults to 16; overflow is an explicit error, never silent truncation. Reference bytes default to 25 MiB each; local reads apply native credential-file protection, remote reads apply native URL/website/redirect policy and streaming limits, base64 decoding is bounded. `allow_remote_images: false` disables remote inputs.

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
