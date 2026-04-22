---
name: codex-image-generation
description: Generate images through Codex CLI's `codex responses` entrypoint using the image_generation tool under the current Codex auth session (preferably ChatGPT/OAuth).
version: 1.0.0
author: 솜
license: MIT
metadata:
  hermes:
    tags: [codex, image-generation, oauth, creative, responses-api]
    related_skills: [codex, hermes-agent]
---

# Codex Image Generation

Use this skill when the user wants image generation to go through **Codex CLI** instead of Hermes' built-in image generation tool.

This workflow sends a raw Responses-style payload into:

```bash
codex responses
```

and extracts the `image_generation_call` result into a local image file.

## When to use

- The user explicitly wants **Codex-based image generation**
- The user wants to use the **current Codex auth session** (ideally ChatGPT/OAuth)
- You want a reproducible scriptable path instead of the built-in Hermes image tool

## Preconditions

1. `codex` CLI must be installed and on `PATH`
2. The user should be logged in with:
   ```bash
   codex login status
   ```
3. Prefer **ChatGPT/OAuth** login for subscription-backed usage
4. If `codex login status` shows API key mode unexpectedly, check whether `OPENAI_API_KEY` is interfering or whether `~/.codex/auth.json` is still in `apikey` mode

## Script path

This skill ships a helper script at:

- `scripts/gen_image.py`

## Supported parameters

The helper script currently supports:

- `prompt` — required text prompt
- `--model` — mainline model used to invoke the tool (default `gpt-5.4`)
- `--size` — for example `1024x1024` (default `1024x1024`)
- `--quality` — `auto|low|medium|high` (default `high`)
- `--background` — `auto|opaque|transparent`
- `--action` — `auto|generate|edit`
- `--output` — output path
- `--events` — save raw JSONL event stream for debugging

## Basic usage

```bash
python ~/.hermes/skills/creative/codex-image-generation/scripts/gen_image.py \
  "A dreamy jellyfish library under the sea, painterly concept art" \
  -o /tmp/jellyfish_library.png
```

## Example with explicit options

```bash
python ~/.hermes/skills/creative/codex-image-generation/scripts/gen_image.py \
  "A cinematic red fox mage in a moonlit forest, detailed fantasy illustration" \
  --model gpt-5.4 \
  --size 1024x1024 \
  --quality high \
  --background opaque \
  --action generate \
  --output /tmp/fox_mage.png \
  --events /tmp/fox_mage_events.jsonl
```

## Expected result

- The script prints:
  ```
  Saved /path/to/output.png
  ```
- The image file exists at the requested output path
- The raw JSONL events file can be inspected if extraction fails

## Troubleshooting

### `codex login status` shows API key mode

The current Codex auth state is not using ChatGPT/OAuth. Re-login:

```bash
codex logout
codex login
codex login status
```

### `No image_generation_call result found`

Run again with `--events` and inspect the raw event stream. The output item format may have changed.

### Transparent background fails

Per current docs, some model/tool combinations do not support transparent background. Retry with:

```bash
--background opaque
```

## Agent rule

When a user asks for image generation and prefers the Codex path, use this skill's script first rather than Hermes' internal image generation tool.
