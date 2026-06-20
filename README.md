# steroids-openai-image-gen

Hermes image generation provider for two practical paths:

1. `openai-compatible` — call any endpoint that implements OpenAI-compatible `/v1/images/generations` and `/v1/images/edits` routes.
2. `codex-auth` — use Hermes' existing Codex/OpenAI OAuth token directly and call the Codex backend Responses image-generation flow.

The plugin also overrides Hermes' `image_generate` tool schema so agents can pass `quality`, `image_url`, and `reference_image_urls` explicitly.

## Install

Clone/copy this repo into your Hermes plugin root, then enable it:

```bash
cd "${HERMES_HOME:-$HOME/.hermes}/plugins"
git clone https://github.com/eve-ai-dev/steroids-openai-image-gen.git
hermes plugins enable steroids-openai-image-gen
```

Restart Hermes/gateway after enabling.

For profile-specific installs, use that profile's plugin root instead:

```bash
cd "${HERMES_HOME:-$HOME/.hermes}/profiles/<profile>/plugins"
```

## Config: OpenAI-compatible endpoint mode

Use this for OpenAI itself, a reverse proxy, or any provider that accepts OpenAI-style image routes.

```yaml
image_gen:
  provider: steroids-openai
  model: gpt-image-2
  steroids-openai:
    mode: openai-compatible
    base_url: ${OPENAI_BASE_URL}
    api_key_env: OPENAI_API_KEY
    model: gpt-image-2
    quality: medium
    max_reference_images: 16
```

Secrets stay in env. Non-secrets stay in YAML.

The plugin sends:

- text-only: `POST {base_url}/images/generations`
- edits/references: `POST {base_url}/images/edits` multipart with `image` for the primary source and `image[]` for extra refs

Expected response shape:

```json
{
  "data": [
    {
      "b64_json": "...",
      "revised_prompt": "optional"
    }
  ]
}
```

URL responses are also accepted and cached locally when possible.

## Config: direct Codex Auth mode

Use this for Hermes users who already have Codex/OpenAI OAuth configured and do not use an OpenAI-compatible image endpoint.

```yaml
image_gen:
  provider: steroids-openai
  model: gpt-image-2
  steroids-openai:
    mode: codex-auth
    model: gpt-image-2
    quality: medium
    max_reference_images: 16
```

The plugin reads Hermes' Codex token via Hermes' internal Codex auth helper and sends a Responses-style request with the `image_generation` tool.

## Tool arguments

The plugin registers an enhanced `image_generate` schema:

```json
{
  "prompt": "make the red square blue",
  "aspect_ratio": "square",
  "quality": "medium",
  "image_url": "/path/source.png",
  "reference_image_urls": ["/path/ref.png"]
}
```

`input_fidelity` is exposed for forward compatibility but omitted/ignored for `gpt-image-2`.

## Compatibility notes

- Use `model: gpt-image-2`, not `gpt-image-2-medium`; quality is a separate parameter.
- OpenAI-compatible edit endpoints should support multipart `image` + `image[]` and return `b64_json`.
- Nested `${ENV_VAR}` values in this plugin's config are expanded by the plugin itself, because some Hermes versions do not expand nested plugin config before providers read it.
