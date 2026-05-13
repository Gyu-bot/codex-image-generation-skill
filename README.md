# codex-image-generation

Dedicated Hermes skill for Codex OAuth + OpenAI hosted `image_generation`.

This repository is meant to be checked out directly at:

```text
~/.hermes/skills/creative/codex-image-generation
```

It gives Hermes a git-managed image generation workflow with:

- direct Codex OAuth Responses transport;
- `gpt-image-2` hosted image generation;
- fidelity-first prompt handling;
- `direct`, `fidelity`, and `enhanced` prompt modes;
- default `--moderation low`;
- exact visible text / language preservation policy;
- reference and edit image support;
- metadata and raw event capture;
- multiple candidate generation with `--count`.

## Files

```text
SKILL.md                  Hermes skill instructions
README.md                 Repository documentation
scripts/gen_image.py      Main CLI helper
scripts/test_gen_image.py Unit tests for payload, parsing, diagnostics
```

## Requirements

- Hermes source at `~/.hermes/hermes-agent`
- Hermes Codex OAuth credentials available
- Python environment with Hermes dependencies, including `openai`
- Optional: Pillow for compressing oversized reference images

Sanity check:

```bash
codex login status
```

The helper itself uses Hermes' Codex OAuth helpers directly. It does not call the removed `codex responses` CLI subcommand.

## Quick start

```bash
python ~/.hermes/skills/creative/codex-image-generation/scripts/gen_image.py \
  "A dreamy jellyfish library under the sea, painterly concept art" \
  --output ./jellyfish-library.png
```

Exact text / high-fidelity prompt:

```bash
python ~/.hermes/skills/creative/codex-image-generation/scripts/gen_image.py \
  "Create a clean event poster with the exact text 'FRI 11PM / HBC Rooftop', black background, silver typography, no extra text" \
  --prompt-mode fidelity \
  --output ./poster.png
```

Direct pass-through mode:

```bash
python ~/.hermes/skills/creative/codex-image-generation/scripts/gen_image.py \
  "Minimal red circle on a white background" \
  --prompt-mode direct \
  --output ./red-circle.png
```

Enhanced photoreal mode:

```bash
python ~/.hermes/skills/creative/codex-image-generation/scripts/gen_image.py \
  "A boutique hotel lobby in Seoul at night" \
  --prompt-mode enhanced \
  --enhancement-profile photoreal \
  --output ./hotel-lobby.png
```

Reference image:

```bash
python ~/.hermes/skills/creative/codex-image-generation/scripts/gen_image.py \
  "Create a luxury skincare ad using the attached bottle as the product reference" \
  --reference-image ./bottle.png \
  --output ./skincare-ad.png
```

Edit image:

```bash
python ~/.hermes/skills/creative/codex-image-generation/scripts/gen_image.py \
  "Replace the background with a rainy neon Tokyo street while keeping the subject intact" \
  --edit-image ./portrait.png \
  --action edit \
  --output ./portrait-tokyo.png
```

Multiple candidates:

```bash
python ~/.hermes/skills/creative/codex-image-generation/scripts/gen_image.py \
  "A cinematic sci-fi knight on a ruined moon" \
  --prompt-mode enhanced \
  --enhancement-profile cinematic \
  --count 3 \
  --output ./moon-knight.png
```

## Important options

- `--prompt-mode direct|fidelity|enhanced`
- `--enhancement-profile none|safe-polish|cinematic|photoreal|aggressive`
- `--moderation auto|low` — default `low`
- `--quality auto|low|medium|high`
- `--background auto|opaque|transparent`
- `--format png|jpeg|webp`
- `--reference-image PATH` — repeatable, max 5
- `--edit-image PATH`
- `--count N` — 1 to 8 candidates
- `--events PATH` — raw Responses JSONL
- `--metadata PATH` — output metadata JSON

## Prompt policy

### `direct`

Use when the user's exact prompt should be sent with minimal wrapper influence.

### `fidelity`

Default script mode. Preserves user wording, constraints, omissions, exact text, layout, and style choices.

### `enhanced`

Allows controlled prompt strengthening through one of the enhancement profiles.

Profiles:

- `safe-polish`: restrained clarity and finish
- `cinematic`: mood, lighting, atmosphere, composition
- `photoreal`: realism-oriented defaults
- `aggressive`: strongest intervention; opt-in only

## Testing

From this repository:

```bash
python -m pytest scripts/test_gen_image.py -q
python scripts/gen_image.py --help
```

## Git workflow

```bash
git status
git diff
python -m pytest scripts/test_gen_image.py -q
git add SKILL.md README.md scripts/gen_image.py scripts/test_gen_image.py .gitignore
git commit -m "feat: update codex image generation skill"
git push origin main
```

## Notes

- Successful runs write image metadata next to the output by default.
- Raw events are only written when `--events` is supplied.
- Generated images, metadata JSON, events JSONL, caches, and credentials should not be committed.
