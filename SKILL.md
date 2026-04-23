---
name: codex-image-generation
description: Hermes-native Codex OAuth image creator skill using OpenAI Responses image_generation with fidelity-first prompt control and optional enhancement overlays.
version: 2.0.0
author: 솜
license: MIT
metadata:
  hermes:
    tags: [codex, image-generation, oauth, creative, responses-api, image-creator]
    related_skills: [codex, hermes-agent]
---

# Codex Image Creator

Use this skill when the user wants **GPT/Codex-backed image generation** while keeping **image-creator-style prompt control** inside a Hermes-usable workflow.

This skill does **not** require Codex skill runtime execution. Instead, it uses:

- **Codex OAuth / Codex auth session**
- `codex responses`
- OpenAI hosted `image_generation` tool
- a Hermes-local script that applies prompt-control policy before the request is sent

So the execution path is:

```bash
codex responses
```

while the **policy layer** stays under this skill's control.

## Core design

This skill combines three ideas:

1. **`image-creator` policy layer**
   - preserve user intent
   - preserve exact rendered text
   - avoid unwanted prompt drift
   - split execution instructions from creative content
   - default to no overwrite

2. **Existing thin-wrapper simplicity**
   - one clear entry script
   - easy to debug
   - git-friendly local files

3. **Selective `ima2-gen` style overlays**
   - optional developer-prompt strengthening
   - optional research / `web_search`
   - optional prompt enhancement profiles

## Script path

This skill ships a helper script at:

- `scripts/gen_image.py`

## Preconditions

1. `codex` CLI must be installed and on `PATH`
2. The user should be logged in with:
   ```bash
   codex login status
   ```
3. Prefer ChatGPT / OAuth auth when the goal is Codex-backed image generation
4. If `codex login status` unexpectedly shows API key mode, check whether `OPENAI_API_KEY` is overriding OAuth

## Runtime model note

The script sends a Responses request such as:

```bash
--model gpt-5.4
```

with the hosted `image_generation` tool.

Per current OpenAI docs, the **top-level model** is the text-capable orchestrator, while the **actual image rendering** is performed by a GPT Image backend. So this path is compatible with the goal of using the GPT Image family even though the Responses `model` field is `gpt-5.4`.

## Policy model

### Default: fidelity-first

The default behavior is intentionally close to `image-creator`:

- rewrite the request into model-friendly image prompt language
- preserve user meaning, explicit constraints, and omissions
- preserve exact rendered text
- avoid adding unrequested style/camera/lens/negative-prompt boilerplate
- avoid skill-layer sanitizing or softening

### Optional: enhancement overlays

If the user wants stronger intervention, the script can enable optional overlays:

- stronger developer-prompt guidance
- optional `web_search`
- photorealistic default behavior
- cinematic enhancement
- aggressive quality / negative-prompt style boosting

This is **off by default**.

## Supported parameters

- `prompt` — required text prompt
- `--output` — output file path or directory; defaults to current directory with auto filename
- `--overwrite` — explicitly overwrite an existing destination file
- `--model` — mainline Responses model (default `gpt-5.4`)
- `--prompt-mode` — `fidelity|enhanced` (default `fidelity`)
- `--enhancement-profile` — `none|safe-polish|cinematic|photoreal|aggressive` (default `none`)
- `--research` — `off|auto` (default `off`)
- `--size` — output size (default `1024x1024`)
- `--quality` — `auto|low|medium|high` (default `high`)
- `--background` — `auto|opaque|transparent`
- `--format` — `png|jpeg|webp` (default `png`)
- `--compression` — compression value for jpeg/webp
- `--action` — `auto|generate|edit` (default `auto`)
- `--reference-image` — reference image path; may be passed multiple times
- `--edit-image` — edit target image path
- `--events` — save raw `codex responses` JSONL events for debugging
- `--metadata` — save metadata JSON to a specific path; defaults to `<saved-image>.<ext>.json`

## Input images

Input images are **not only for image-to-image editing**.

Two main roles exist:

### Edit target

Use `--edit-image` when the existing image itself should be modified.

Examples:
- change the background
- replace text in the image
- preserve layout but alter details

### Reference image

Use `--reference-image` when the image should guide a new generation rather than be directly edited.

Examples:
- use this logo as a reference
- use this face, outfit, or product as inspiration
- combine the vibe of these references into a new image

## Usage examples

### Basic fidelity-first generation

```bash
python ~/.hermes/skills/creative/codex-image-generation/scripts/gen_image.py \
  "A dreamy jellyfish library under the sea, painterly concept art" \
  --output ./jellyfish-library.png
```

### Fidelity mode with exact text constraints

```bash
python ~/.hermes/skills/creative/codex-image-generation/scripts/gen_image.py \
  "Create a clean event poster with the exact text 'FRI 11PM / HBC Rooftop', black background, silver typography, no extra text" \
  --prompt-mode fidelity \
  --output ./poster.png
```

### Enhanced mode with photoreal default

```bash
python ~/.hermes/skills/creative/codex-image-generation/scripts/gen_image.py \
  "A boutique hotel lobby in Seoul at night" \
  --prompt-mode enhanced \
  --enhancement-profile photoreal \
  --output ./hotel-lobby.png
```

### Enhanced mode with aggressive prompt strengthening

```bash
python ~/.hermes/skills/creative/codex-image-generation/scripts/gen_image.py \
  "A dramatic sci-fi knight on a ruined moon" \
  --prompt-mode enhanced \
  --enhancement-profile aggressive \
  --research auto \
  --quality high \
  --output ./moon-knight.png
```

### Reference-image guided generation

```bash
python ~/.hermes/skills/creative/codex-image-generation/scripts/gen_image.py \
  "Create a luxury skincare ad using the attached bottle as the product reference" \
  --reference-image ./bottle.png \
  --output ./skincare-ad.png
```

### Edit an existing image

```bash
python ~/.hermes/skills/creative/codex-image-generation/scripts/gen_image.py \
  "Replace the background with a rainy neon Tokyo street while keeping the subject intact" \
  --edit-image ./portrait.png \
  --action edit \
  --output ./portrait-tokyo-edit.png
```

## Output contract

The script:

1. calls `codex responses`
2. extracts the `image_generation_call` result
3. saves the image to the requested path
4. writes metadata JSON next to the output by default
5. prints the saved file path
6. prints the revised prompt when available

Metadata includes:

- original prompt
- prompt mode
- enhancement profile
- research mode
- revised prompt
- usage
- web search call count
- input image paths
- saved output path
- raw event count

## Revised prompt behavior

OpenAI's `image_generation` tool may automatically produce a `revised_prompt`.
This step happens inside the hosted tool path and is **not** something this skill fully disables.
It is not a Codex-runtime-only feature; the same behavior appears when using `codex responses` as a client to the hosted tool path.

What this skill controls is the **prompt policy before that step**:

- what gets preserved
- what gets excluded
- whether enhancement overlays are allowed

So the skill controls the **upper prompt layer**, while `revised_prompt` remains an observable downstream artifact.

## Troubleshooting

### `codex login status` shows API key mode

The current Codex auth state is not using ChatGPT/OAuth. Re-login:

```bash
codex logout
codex login
codex login status
```

If OAuth keeps disappearing, check whether `OPENAI_API_KEY` is present in the shell environment.

### `No image_generation_call result found`

Run again with:

```bash
--events image_events.jsonl
```

and inspect the raw event stream.

### Transparent background fails

Some GPT Image paths do not support transparent backgrounds. Retry with:

```bash
--background opaque
```

### `--enhancement-profile` errors in fidelity mode

Enhancement profiles only work when:

```bash
--prompt-mode enhanced
```

is enabled.

## Agent rule

When a user wants GPT/Codex-backed image generation, use this skill's script before Hermes' internal image tool.

### Use fidelity mode when

- exact text matters
- the user cares about prompt faithfulness
- layout / composition / brand constraints matter
- prompt drift would be harmful

### Use enhanced mode when

- the user explicitly wants stronger prompt intervention
- poster / ad / concept-art / cinematic polish is desired
- photoreal defaults or negative-prompt style boosting should be applied
- optional research-backed real-world grounding is useful

## Recommended default behavior for me

If the user does not specify otherwise:

- start with `--prompt-mode fidelity`
- keep `--research off`
- keep `--enhancement-profile none`
- only enable enhancement overlays when the user explicitly wants stronger intervention
