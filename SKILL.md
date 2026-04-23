---
name: codex-image-generation
description: Hermes-native Codex OAuth image creator skill using OpenAI Responses image_generation with fidelity-first prompt control and optional enhancement overlays.
version: 2.0.0
author: 솜
license: MIT
metadata:
  hermes:
    tags: [codex, image-generation, oauth, creative, responses-api]
    related_skills: [codex, hermes-agent]
---

# Codex Image Creator

Use this skill when the user wants **GPT/Codex-backed image generation** with **fidelity-first prompt control** inside a Hermes-usable workflow.

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

1. **Fidelity-first policy layer**
   - preserve user intent
   - preserve exact rendered text
   - avoid unwanted prompt drift
   - split execution instructions from creative content
   - default to no overwrite

2. **Thin-wrapper simplicity**
   - one clear entry script
   - easy to debug
   - git-friendly local files

3. **Optional enhancement overlays**
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

The default behavior is:

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
- aggressive quality / negative-prompt style boosting with the same stronger wrapper behavior used in the referenced `ima2-gen` project

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
- `--quality` — `auto|low|medium|high` (default `medium`)
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

Note: if the request is rejected very early by the hosted safety system, the run may fail before any `image_generation_call` event or events file is produced.

### Safety rejection on sexualized prompts

OpenAI's hosted `image_generation` path can reject prompts that sexualize a young-looking adult, emphasize body lines, or combine bikini/swimwear wording with appearance-focused posing. In that case the script may return an error like:

```text
safety_violations=[sexual]
```

This is an upstream policy refusal, not necessarily a bug in the skill, the prompt mode, or Codex OAuth.

### Generic processing errors on borderline prompts

Some borderline prompts do **not** come back with an explicit safety label. Instead, `codex responses` may fail early with a generic upstream error such as:

```text
retryable error: An error occurred while processing your request.
```

Observed behavior:

- the same prompt can succeed on one run and fail on another
- failures may happen before any `image_generation_call` result is emitted
- when that happens, the script may not save an `--events` file even if one was requested
- `response.rate_limits.credits.has_credits=false` can appear even on successful runs, so that field alone is **not** enough to diagnose the failure as a credit issue

Practical interpretation:

- if a request fails this way but similar requests sometimes succeed, suspect an upstream transient or moderation/admission-stage failure rather than a local script bug
- this is more likely with sexualized swimwear or body-emphasis prompts that sit near policy boundaries
- retrying can change the outcome, but it does **not** guarantee stable repeatability

### Transparent background fails

In `--prompt-mode enhanced --enhancement-profile aggressive`, borderline sexualized prompts may behave inconsistently across repeated runs:

- one run may succeed and save an image
- the next run may fail with a generic retryable processing error
- the failure may appear without an explicit `safety_violations=[sexual]` surface

Treat this as an upstream hosted-tool instability / policy edge case rather than proof that the local wrapper is broken.

### Multiple images

The current script interface does not expose a dedicated `--count` / `--num-images` flag. If the user wants two or more candidates, run the script multiple times with distinct output paths.

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

The agent should choose options **autonomously by default** unless the user explicitly asks for a specific mode, profile, quality, size, format, or research behavior.

## Agent option-selection policy

### Baseline default

If the user does not specify otherwise, start from this baseline:

- `--prompt-mode enhanced`
- `--enhancement-profile safe-polish`
- `--research off`
- `--quality medium`
- `--size 1024x1024`
- `--format png`
- `--background auto`
- `--action auto`

Reasoning: for ordinary lightweight image generation, a small amount of prompt enhancement usually produces better results than strict fidelity-first handling.

### Choose `--prompt-mode fidelity` when

- exact text matters
- prompt faithfulness matters more than extra polish
- layout / composition / brand constraints matter
- the user already wrote a detailed prompt
- the request includes detailed scene direction, instruction-heavy composition notes, or precise do/don't constraints
- prompt drift would be harmful

### Choose `--prompt-mode enhanced` when

- the user did not provide a highly constrained prompt
- the prompt is short, casual, or underspecified
- the user wants the model to beautify, interpret, or flesh out the scene
- poster / ad / concept-art / cinematic polish is desired
- photoreal defaults or stronger rendering bias are desirable
- the user asks for a more stylized, dramatic, premium, or production-like result

For normal casual image generation, prefer `enhanced` over `fidelity`.

### Choose enhancement profiles like this

#### `none`

Use when:

- fidelity is the goal
- the user already provided enough detail
- you do not want extra aesthetic drift

#### `safe-polish`

Use when:

- the user wants a small visual upgrade without major reinterpretation
- clarity, lighting, and finish should improve a little
- you want the lightest enhancement overlay

#### `cinematic`

Use when:

- the user wants mood, atmosphere, dramatic lighting, or film-like composition
- concept art, posters, key art, and scene illustration are the goal
- you want enhancement, but not the strongest possible intervention

#### `photoreal`

Use when:

- the user wants realism or photo-like rendering
- the prompt is visual but style-unspecified, and realism is the safest helpful assumption
- product shots, interiors, portraits, travel imagery, architecture, or editorial-looking results are desired

#### `aggressive`

Use only when:

- the user explicitly wants the strongest possible prompt enhancement
- maximal polish is preferred over strict prompt fidelity
- stronger quality-boosting and negative-prompt-style bias are acceptable
- occasional upstream instability is acceptable

Do **not** choose `aggressive` silently for normal requests. It is an opt-in stronger mode.

### Choose `--research auto` when

- the subject depends on current real-world facts
- the prompt references a real person, real brand, real location, real product, or current appearance
- accurate product details, architecture, landmarks, uniforms, logos, or public-figure appearance matter
- better grounding is worth extra tool use

Even though the flag default is `off`, the agent should actively switch to `auto` whenever real-world grounding is likely to improve the result in a meaningful way.

Keep `--research off` when:

- the request is fictional, self-contained, or purely stylistic
- web lookup would not materially improve the image prompt
- the user is clearly asking for an imagined or transformed version rather than factual grounding

### Choose quality like this

- `medium` — default for normal use
- `high` — when the user explicitly prioritizes best quality over speed/cost, or the image is important enough to justify it
- `low` — only for intentionally cheap/fast draft generation
- `auto` — only when you intentionally want the hosted tool to decide

### Choose image count like this

The script has no dedicated multi-image flag right now. If the user asks for multiple candidates:

- run the script multiple times
- use distinct output paths
- report which attempts succeeded or failed

### Choose output/action options like this

- use `--format png` by default
- use `--background transparent` only when the user clearly wants cutout / compositing behavior
- use `--action edit` with `--edit-image` when modifying an existing image
- use `--reference-image` for guidance/reference, not direct editing

### Ask vs choose

The agent should choose on its own when the user's intent is clear.
Only ask when the decision materially changes the result and there is no strong default signal from the user's request.
