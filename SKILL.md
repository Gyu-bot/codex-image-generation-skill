---
name: codex-image-generation
description: Use when generating or editing images through Codex OAuth and OpenAI hosted image_generation from Hermes, especially when prompt fidelity, exact visible text, low moderation mode, metadata, reference images, or direct control are important.
version: 2.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [codex, image-generation, oauth, creative, responses-api, prompt-fidelity]
    related_skills: [hermes-agent, multimodal-model-workflows]
---

# Codex Image Generation

## Overview

This skill is the dedicated Hermes-local image generation workflow for Codex OAuth + OpenAI hosted `image_generation`.

Use it when the user wants image generation with stronger control than the generic Hermes image tool provides: prompt fidelity, exact visible text preservation, optional prompt enhancement, reference/edit images, event capture, metadata, and explicit `moderation=low` support.

The helper script does **not** rely on the removed `codex responses` CLI subcommand. It builds a direct Codex OAuth Responses client using Hermes' existing Codex auth helpers, sends a streamed Responses request to the Codex backend, extracts the `image_generation_call`, saves the image, and writes metadata.

## When to Use

Use this skill when:

- the user asks for GPT/Codex-backed image generation;
- prompt faithfulness matters more than generic beautification;
- exact visible text, Korean/Japanese/Chinese script, slogans, UI copy, signs, or labels must be preserved;
- the request needs `--moderation low` rather than the stricter default surface of simpler image tools;
- the user provides reference images or edit targets;
- you need raw event logs or metadata for debugging;
- multiple candidates should be generated with consistent settings.

Do **not** use this skill for:

- simple throwaway image requests where Hermes' built-in `image_generate` is sufficient and no Codex/GPT-specific control is needed;
- tasks that need manual drawing or post-processing instead of generation;
- requests that require secrets, payments, account changes, or other side effects unrelated to image generation.

## Files

```text
~/.hermes/skills/creative/codex-image-generation/
  SKILL.md
  README.md
  scripts/
    gen_image.py
    test_gen_image.py
```

Main executable:

```bash
python ~/.hermes/skills/creative/codex-image-generation/scripts/gen_image.py --help
```

## Preconditions

1. Hermes source exists at `~/.hermes/hermes-agent` so the helper can import Codex OAuth helpers.
2. Codex/ChatGPT OAuth credentials are available to Hermes.
3. Python dependencies used by Hermes' image provider are installed, including `openai`.
4. For oversized reference-image compression, Pillow is useful; without Pillow, large reference images may fail validation.

Check Codex CLI state only as a sanity check:

```bash
codex login status
```

A working CLI status does not prove this helper will work, because the helper uses Hermes' Codex OAuth helpers directly. But an expired or missing Hermes OAuth token will still break generation.

## Core Design

### 1. Role-separated prompt policy

The helper separates execution policy from creative content:

- `developer` / top-level `instructions`: behavior policy, preservation rules, tool-use requirements, text-language policy, safety-intent cues.
- `user`: the user's image prompt and any reference/edit images.

The Codex backend currently requires a top-level `instructions` field, so the helper mirrors the developer policy there while keeping the developer/user split.

### 2. Fidelity-first defaults

Script defaults are conservative:

```bash
--prompt-mode fidelity
--enhancement-profile none
--moderation low
--quality medium
--size 1024x1024
--format png
--background auto
--reasoning-effort medium
```

This means the script tries to preserve the user's prompt rather than silently rewriting it into a generic image prompt.

### 3. Direct Codex OAuth transport

The helper uses:

```text
https://chatgpt.com/backend-api/codex
```

with Hermes' existing Codex OAuth token and Cloudflare headers. This avoids the old hidden CLI passthrough path that now falls into the interactive TUI and fails with `stdin is not a terminal`.

### 4. Metadata-first debugging

Every successful run writes metadata next to the image unless `--metadata` is explicitly set. Metadata includes:

- saved path;
- original prompt;
- orchestrator model and image model;
- prompt mode and enhancement profile;
- moderation, quality, size, background, format;
- reference/edit image diagnostics;
- revised prompt when returned;
- usage, event counts, partial image count, and web search count.

## CLI Options

Important options:

- `prompt` — required image or edit instruction.
- `--output` / `-o` — output file path or directory.
- `--overwrite` — overwrite instead of auto-versioning.
- `--model` — `gpt-5.5`, `gpt-5.4`, or `gpt-5.4-mini`; default `gpt-5.4`.
- `--reasoning-effort` — `none`, `low`, `medium`, `high`, `xhigh`.
- `--prompt-mode` — `direct`, `fidelity`, or `enhanced`.
- `--enhancement-profile` — `none`, `safe-polish`, `cinematic`, `photoreal`, or `aggressive`.
- `--research` — `off` or `auto`; enables `web_search` before image generation when useful.
- `--size` — image size, e.g. `1024x1024`.
- `--quality` — `auto`, `low`, `medium`, `high`.
- `--background` — `auto`, `opaque`, `transparent`.
- `--moderation` — `auto` or `low`; default `low`.
- `--format` — `png`, `jpeg`, or `webp`.
- `--compression` — compression for JPEG/WebP.
- `--action` — `auto`, `generate`, or `edit`.
- `--reference-image` — may be passed multiple times, max 5.
- `--edit-image` — primary image to edit.
- `--count` — number of candidates, 1-8.
- `--events` — save raw Responses events as JSONL.
- `--metadata` — custom metadata JSON path.

## Prompt Modes

### `direct`

Use when the exact user prompt should be passed as directly as possible.

Good for:

- already-polished prompts;
- prompts where wrapper language has caused moderation or fidelity issues;
- exact scene descriptions that should not be expanded;
- debugging the transport layer.

### `fidelity`

Default mode. Use when the user prompt is detailed and should be preserved, but light instruction framing is acceptable.

Good for:

- exact text rendering;
- layout constraints;
- brand/product constraints;
- detailed art direction;
- prompts where drift would be harmful.

### `enhanced`

Use when the user prompt is short or casual and would benefit from visual polish. Requires `--enhancement-profile` for any non-default enhancement.

Good for:

- concept art;
- posters;
- cinematic scenes;
- photoreal product/interior/travel imagery;
- requests where beauty/polish matters more than strict prompt byte-level fidelity.

## Enhancement Profiles

- `none` — no extra enhancement.
- `safe-polish` — restrained clarity, lighting, and detail improvements.
- `cinematic` — stronger mood, composition, lighting, atmosphere.
- `photoreal` — realism-oriented defaults when style is unspecified.
- `aggressive` — strongest enhancement; use only when the user wants maximal polish and accepts more prompt intervention.

Do **not** silently choose `aggressive` for normal requests.

## Reference and Edit Images

Use `--edit-image` when the image itself should be modified:

```bash
python ~/.hermes/skills/creative/codex-image-generation/scripts/gen_image.py \
  "Replace the background with a rainy neon Tokyo street while keeping the subject intact" \
  --edit-image ./portrait.png \
  --action edit \
  --output ./portrait-tokyo.png
```

Use `--reference-image` when the image should guide a new generation:

```bash
python ~/.hermes/skills/creative/codex-image-generation/scripts/gen_image.py \
  "Create a luxury skincare ad using the attached bottle as the product reference" \
  --reference-image ./bottle.png \
  --output ./skincare-ad.png
```

The helper validates image existence, detects MIME type from magic bytes where possible, limits references to 5, and compresses overly large inputs when Pillow is available.

## Usage Recipes

### Fidelity-first generation

```bash
python ~/.hermes/skills/creative/codex-image-generation/scripts/gen_image.py \
  "A dreamy jellyfish library under the sea, painterly concept art" \
  --output ./jellyfish-library.png
```

### Exact visible text

```bash
python ~/.hermes/skills/creative/codex-image-generation/scripts/gen_image.py \
  "Create a clean event poster with the exact text 'FRI 11PM / HBC Rooftop', black background, silver typography, no extra text" \
  --prompt-mode fidelity \
  --output ./poster.png
```

### Direct mode

```bash
python ~/.hermes/skills/creative/codex-image-generation/scripts/gen_image.py \
  "Minimal red circle on a white background" \
  --prompt-mode direct \
  --output ./red-circle.png
```

### Enhanced photoreal

```bash
python ~/.hermes/skills/creative/codex-image-generation/scripts/gen_image.py \
  "A boutique hotel lobby in Seoul at night" \
  --prompt-mode enhanced \
  --enhancement-profile photoreal \
  --output ./hotel-lobby.png
```

### Multiple candidates

```bash
python ~/.hermes/skills/creative/codex-image-generation/scripts/gen_image.py \
  "A dramatic sci-fi knight on a ruined moon" \
  --prompt-mode enhanced \
  --enhancement-profile cinematic \
  --count 3 \
  --output ./moon-knight.png
```

This saves `moon-knight-1.png`, `moon-knight-2.png`, and `moon-knight-3.png` unless existing files force auto-versioning.

## Agent Option Selection

For ordinary casual image requests, use:

```bash
--prompt-mode enhanced --enhancement-profile safe-polish --quality medium
```

For detailed prompts or exact constraints, use:

```bash
--prompt-mode fidelity --enhancement-profile none
```

For prompts that are failing because the wrapper appears to be interfering, try:

```bash
--prompt-mode direct
```

Use `--research auto` only when real-world visual grounding matters: real products, places, people, brands, uniforms, landmarks, or current appearances.

## Troubleshooting

### `stdin is not a terminal`

This usually means an old implementation tried to run a removed `codex responses` CLI subcommand and accidentally entered the interactive Codex TUI. This skill's current script should not call that CLI path. Verify the script path points to:

```text
~/.hermes/skills/creative/codex-image-generation/scripts/gen_image.py
```

### Auth failures

Common signs:

- `AUTH_CHATGPT_EXPIRED`
- `AUTH_API_KEY_INVALID`
- `No Codex/ChatGPT OAuth credentials available`

Check Hermes/Codex auth and make sure Hermes is not sharing rotating tokens with other clients.

### Moderation refusal

The helper exposes `--moderation low`, but the hosted tool can still refuse. If the script reports `MODERATION_REFUSED`, treat it as an upstream policy refusal rather than a local script bug.

### Empty result

If no `image_generation_call` result is found, rerun with events:

```bash
python ~/.hermes/skills/creative/codex-image-generation/scripts/gen_image.py \
  "your prompt" \
  --events ./image-events.jsonl
```

Then inspect event types and errors from the metadata/events file.

### Transparent output fails

Some image paths do not support transparency reliably. Retry with:

```bash
--background opaque
```

### Enhancement profile rejected

Non-`none` profiles require:

```bash
--prompt-mode enhanced
```

## Verification Checklist

- [ ] `python scripts/gen_image.py --help` works.
- [ ] `python -m pytest scripts/test_gen_image.py -q` passes.
- [ ] `git remote -v` points to the dedicated skill repository.
- [ ] README and SKILL.md mention the current direct Codex OAuth transport, not the removed CLI passthrough.
- [ ] No generated images, metadata, events, `__pycache__`, or credentials are committed.
