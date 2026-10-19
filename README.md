# steroids-openai-image-gen

Hermes provider `steroids-openai` and three advanced tools for generation, image edits, references, alpha masks, per-call quality and input fidelity. Built-in `image_generate` remains owned by Hermes and can still select this provider; advanced arguments use the namespaced tools.

## 0.2 migration (breaking tool names)

| Old plugin tool | New tool |
| --- | --- |
| `image_generate` override | `steroids_image_generate` |
| `image_generate_background` | `steroids_image_generate_background` |
| `image_generate_background_status` | `steroids_image_generate_background_status` |

There are no old-name shims. Remove the former `allow_tool_override` grant if it was only for this plugin. Change calls in your own prompts, saved workflows and installed external skills to the new names; this repository ships no skills and does not edit active external skills. Arguments are unchanged. `token_env` is removed: Codex sign-in is exclusively host-owned. Existing completed job JSON remains inspectable; old running/queued jobs become `interrupted` rather than pretending to resume. New jobs persist `status.json` and optional `result.json`, not fabricated delegation events.

## Installation and compatibility

Install this directory under the selected profile's `${HERMES_HOME}/plugins/steroids-openai-image-gen`, enable with `hermes plugins enable steroids-openai-image-gen`, then restart Hermes when authorized. `HERMES_HOME` already points at the selected profile: do not append another profiles directory.

Requires Hermes with public `agent.secret_scope.get_secret`, `credentialed_provider_request`, `ctx.spawn_task`, `ctx.on_unload`, `ctx.session_surface` and **keyless calling-session-aware `ctx.inject_message`**. Tested against upstream source `2e83e2a935ee04f606aab58e498d34ca58d84c07`, not a claimed released SemVer floor. Older hosts need an upgrade; no internal compatibility adapter is provided. Actual generation and target-chat media delivery have not been accepted for this candidate. See STATE.md and .agents/validation.md before release.

Dependencies have bounded API-compatible ranges; install under Hermes's constraints. The existing uv.lock predates 0.2 and is not authoritative for installation until regenerated through the approved package-security path. No install workaround is supported.

## Configuration

```yaml
image_gen:
  provider: steroids-openai
  model: gpt-image-2
  steroids-openai:
    mode: openai-compatible
    base_url: https://api.openai.com/v1
    api_key_env: OPENAI_API_KEY
    quality: medium
    max_reference_images: 16
plugins:
  entries:
    steroids-openai-image-gen:
      allow_gateway_injection: true  # required for background notification turns
```

Store `OPENAI_API_KEY` through Hermes's secret settings. The manifest declares it as an optional secret so Codex-only installations are not disabled. A custom `api_key_env` must also be declared as a secret in your reviewed manifest; prefer the declared default. Nested `${NAME}` expansion uses Hermes's profile-scoped secret resolver, never another profile's process credentials.

For Codex use `mode: codex-auth`. The manifest declares `requires_auth: [openai-codex]`. Hermes's public signed-in request API attaches the credential, owns refresh, restricts origins and refuses redirects. This plugin never reads or receives the Codex token and does not impersonate a vendor CLI. Codex's Responses SSE is buffered by the host API then parsed locally; no streaming preview is promised. Quality remains a prompt instruction in this route, not a guaranteed backend quality tier. Codex masks remain unsupported; use an OpenAI-compatible image-edit endpoint for masks. Output is padded/resized to the requested dimensions using Pillow when necessary; metadata records the original size. Real backend acceptance remains untested.

## Advanced calls

Call `steroids_image_generate` with:

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

Aspect is `landscape`, `square` or `portrait`; default follows Hermes's provider default. Sizes default to 1536x1024, 1024x1024 and 1024x1536 respectively and can be configured under `sizes`. Quality is `low|medium|high|auto`; fidelity is `low|high`. Invalid controls fail before backend requests. `model: gpt-image-2` uses separate quality, not virtual model tier suffixes.

OpenAI-compatible text requests POST `/images/generations`; edits POST multipart `/images/edits` with primary `image`, extra `image[]`, optional `mask` and fidelity. The primary and alpha mask must be same-size PNGs; transparent mask pixels are editable. Prompt coordinates do not enforce a boundary. The endpoint must actually support this protocol. Errors and size rejection codes are surfaced, never silently downgraded to square. Responses accept `data[0].b64_json` or a URL cached locally when possible; `revised_prompt` and `actual_size` are retained.

## Background work

Call `steroids_image_generate_background` with the same arguments plus `delivery_mode: each|batch`, or a `jobs` array of individual argument objects. Omit `jobs` for a single prompt; `[]` plus a prompt is also a shortcut. Maximum batch defaults to 4 (`STEROIDS_IMAGE_BG_MAX_JOBS`, 1–32); one shared runner limits concurrency to 2 (`STEROIDS_IMAGE_BG_MAX_CONCURRENT`, 1–16). These are nonsecret process tuning values.

The plugin maintains a lazy event-loop thread and uses `ctx.spawn_task` for supervised work. Session/profile context is captured at submission and propagated to workers. Unload cancels tasks and stops the loop. Already-running blocking HTTP may finish but will not deliver after cancellation. Restart does not retry jobs automatically: avoid duplicate paid work. Duplicate tool submissions are separate requests, not idempotent retries.

Results live under the active profile's `steroids_openai_image_gen/jobs/<job_id>/`. Use `steroids_image_generate_background_status` with `job_id` to inspect them. Completion calls public `ctx.inject_message` with a `MEDIA:<path>` line. On messaging hosts the operator must permit gateway injection. `delivery.status=accepted` means only that the host accepted a notification turn; **it does not mean the model forwarded the image or that a platform delivered media**. `confirmed` remains false. Refusal is recorded as `failed`. Injection may cause a separately billed model turn. No private queue event or direct platform send is used.

## Risk disclosure

Generation sends prompts and selected source/mask bytes to your configured image endpoint or ChatGPT Codex service. Remote source URLs and result URLs can cause HTTP downloads. Local source paths are read outside this repository when requested. Generated images and job records (including prompts, source paths and errors) persist in the active profile's data directory; apply your own retention policy. No telemetry, shell execution, self-update, credential-store reads or OAuth writes occur at runtime. Background notification is a model turn, not a guaranteed media transport. Scripts under `scripts/probe_*` make paid requests when explicitly run; they are not part of safe validation and must not be run without approval.
