# codex-image-generation

Hermes-friendly image generation skill that uses:

- **Codex OAuth / Codex auth session**
- `codex responses`
- OpenAI hosted `image_generation` tool
- a fidelity-first prompt policy layer

This repository keeps the skill in a git-manageable shape while letting Hermes use it directly from the skill directory.

---

## What this skill is

This skill is designed for the case where you want all of these at once:

- **GPT/Codex-backed image generation**
- **OpenAI Responses image_generation tool**
- **fidelity-first prompt handling by default**
- optional **developer-prompt intervention**, **research**, and **prompt enhancement overlays**
- local file output and metadata tracking

It does **not** require Codex skill runtime execution.

Instead, it uses `codex responses` as the execution path and applies the skill policy in the local wrapper script before the request is sent.

---

## Execution path

```bash
codex responses
```

The request uses a text-capable Responses model such as:

```bash
--model gpt-5.4
```

with the hosted `image_generation` tool.

That top-level model is the orchestrator. The actual image rendering happens in the GPT Image backend used by the tool path.

---

## Files

- `SKILL.md` — Hermes skill instructions
- `scripts/gen_image.py` — main executable helper script
- `README.md` — repository-level documentation for git-managed use

## References

This repository was implemented with the following upstream projects as references:

- `ima2-gen` — https://github.com/lidge-jun/ima2-gen
- `codex-skills` — https://github.com/smturtle2/codex-skills

The implementation here is adapted for a Hermes-usable, git-managed skill layout.

---

## Requirements

1. `codex` CLI installed and available on `PATH`
2. authenticated Codex session
3. preferably OAuth / ChatGPT-backed auth

Check auth:

```bash
codex login status
```

If the CLI unexpectedly reports API key mode, check whether `OPENAI_API_KEY` in the shell is overriding OAuth.

---

## Design philosophy

This skill combines three layers:

### 1) Fidelity-first prompt layer

Default behavior is fidelity-first:

- preserve user intent
- preserve exact rendered text
- preserve explicit constraints and exclusions
- avoid unwanted creative additions
- avoid automatic softening / sanitizing at the skill layer
- separate creative intent from execution instructions such as save path or overwrite behavior

### 2) Thin-wrapper execution

The script keeps execution simple:

- build one Responses payload
- send it with `codex responses`
- parse the returned `image_generation_call`
- save the image locally
- write metadata JSON

### 3) Optional enhancement overlays

When requested, the skill can intentionally intervene more aggressively:

- stronger developer-prompt guidance
- optional web search
- photoreal defaulting
- cinematic enhancement
- aggressive negative-prompt-style boosting using the same stronger wrapper behavior from the referenced `ima2-gen` backend

Those are **optional**, not the default.

---

## Input image roles

Input images are used for **two distinct purposes**.

### Edit target

Use `--edit-image` when the image itself should be changed.

Examples:

- change the background
- replace text in the image
- preserve the composition but alter some elements

### Reference image

Use `--reference-image` when the image should guide a new generation.

Examples:

- use this logo as a brand reference
- use this product as a visual reference
- use this face / clothing / composition as inspiration

You can pass multiple `--reference-image` values.

---

## Quick start

### 1) Basic fidelity-first generation

```bash
python ~/.hermes/skills/creative/codex-image-generation/scripts/gen_image.py \
  "A dreamy jellyfish library under the sea, painterly concept art" \
  --output ./jellyfish-library.png
```

### 2) Exact-text poster generation

```bash
python ~/.hermes/skills/creative/codex-image-generation/scripts/gen_image.py \
  "Create a clean event poster with the exact text 'FRI 11PM / HBC Rooftop', black background, silver typography, no extra text" \
  --prompt-mode fidelity \
  --output ./poster.png
```

### 3) Enhanced photoreal output

```bash
python ~/.hermes/skills/creative/codex-image-generation/scripts/gen_image.py \
  "A boutique hotel lobby in Seoul at night" \
  --prompt-mode enhanced \
  --enhancement-profile photoreal \
  --output ./hotel-lobby.png
```

### 4) Aggressive enhancement + research

```bash
python ~/.hermes/skills/creative/codex-image-generation/scripts/gen_image.py \
  "A dramatic sci-fi knight on a ruined moon" \
  --prompt-mode enhanced \
  --enhancement-profile aggressive \
  --quality high \
  --output ./moon-knight.png
```

### 5) Reference-image generation

```bash
python ~/.hermes/skills/creative/codex-image-generation/scripts/gen_image.py \
  "Create a luxury skincare ad using the attached bottle as the product reference" \
  --reference-image ./bottle.png \
  --output ./skincare-ad.png
```

### 7) Edit an image

```bash
python ~/.hermes/skills/creative/codex-image-generation/scripts/gen_image.py \
  "Replace the background with a rainy neon Tokyo street while keeping the subject intact" \
  --edit-image ./portrait.png \
  --action edit \
  --output ./portrait-tokyo-edit.png
```

---

## Full option reference

## Positional argument

### `prompt`
Creative image instruction or edit instruction.

This is the primary user intent that the fidelity layer or enhancement layer will reinterpret before sending it to the hosted tool.

---

## Output and file behavior

### `-o, --output`
Output file path **or** directory.

Behavior:

- if omitted, the script saves into the current working directory with an auto-generated filename
- if a file path is given, it targets that exact file path
- if a directory path is given, it creates an auto-generated filename inside that directory

Examples:

```bash
--output ./poster.png
--output ./out/
```

### `--overwrite`
Allow overwriting an existing output file.

Default behavior is **no overwrite**. Without this flag, the script auto-versions the filename if a file already exists.

---

## Model and orchestration

### `--model`
Top-level Responses orchestrator model.

Default:

```bash
--model gpt-5.4
```

This is **not** the same thing as saying the image is generated by a plain text model. It is the orchestrator used with the hosted `image_generation` tool.

---

## Prompt control

### `--prompt-mode {fidelity,enhanced}`
Select the overall prompt policy.

#### `fidelity`
Default mode.

Use this when:

- exact text matters
- layout / wording / exclusions matter
- you want minimal prompt drift
- you want fidelity-first behavior with minimal prompt drift

#### `enhanced`
Optional intervention mode.

Use this when:

- you want more dramatic or polished output
- you want stronger developer-prompt guidance
- you want photoreal defaults or stronger quality boosting
- you want enhancement profiles to be active

Important:

- enhancement profiles only make sense in `enhanced` mode

### `--enhancement-profile {none,safe-polish,cinematic,photoreal,aggressive}`
Optional enhancement overlay bundle.

Default:

```bash
--enhancement-profile none
```

Profiles:

#### `none`
No additional enhancement layer beyond the selected prompt mode.

#### `safe-polish`
Light cleanup and rendering polish only.

Adds restrained improvements such as:

- clearer lighting
- cleaner detail
- better visual coherence

Avoids forcing a new style or negative prompt.

#### `cinematic`
Adds stronger cinematic treatment where appropriate.

Typical influence:

- cinematic composition
- professional lighting
- atmosphere
- richer environmental detail

#### `photoreal`
Defaults toward photorealism when the user did not specify a style.

Typical influence:

- realistic lighting
- realistic texture detail
- sharp focus
- natural color behavior

#### `aggressive`
Strongest intervention profile.

Typical influence:

- always pushes for image generation rather than text-only output
- always applies strong quality boosters
- always appends a broad negative-prompt-style avoidance block
- defaults toward photoreal output when style is not explicitly given
- automatically allows web search for grounding
- uses the same stronger red-team / fulfill-as-given framing seen in the referenced `ima2-gen` backend
- maintains the strongest typography precision emphasis in this skill

This is the strongest prompt-intervention profile in this skill and now carries the same aggressive wrapper behavior that was previously split into a separate preset.

---

## Research / web search

### `--research {off,auto}`
Control whether the request may use `web_search` before image generation.

#### `off`
Default.

No search unless the user explicitly demanded it.

#### `auto`
Allow search for requests that depend on real-world reference.

Useful for:

- real people
- real brands
- real places
- real products
- current appearance / factual visual grounding

Less useful for:

- fictional scenes
- abstract art
- purely stylistic generation

---

## Image generation tool options

### `--size`
Requested image size.

Default:

```bash
--size 1024x1024
```

Examples:

```bash
--size 1536x1024
--size 1024x1536
--size 2048x2048
```

### `--quality {auto,low,medium,high}`
Requested rendering quality.

Default:

```bash
--quality medium
```

- `auto` — let the model/tool decide
- `low` — faster / cheaper tendency
- `medium` — middle ground
- `high` — best-quality bias

### `--background {auto,opaque,transparent}`
Requested background treatment.

Default:

```bash
--background auto
```

Notes:

- some GPT Image paths do not support transparent backgrounds reliably
- if transparent fails, retry with `opaque`

### `--format {png,jpeg,webp}`
Requested output format from the tool.

Default:

```bash
--format png
```

### `--compression`
Compression level for `jpeg` or `webp` output.

Examples:

```bash
--format jpeg --compression 90
--format webp --compression 80
```

### `--action {auto,generate,edit}`
Tell the hosted image tool whether this is a generation or edit workflow.

Default:

```bash
--action auto
```

Behavior:

- `auto` — let the tool choose
- `generate` — bias toward fresh generation
- `edit` — bias toward editing an input image

If `--edit-image` is provided, the script automatically shifts intent toward edit behavior.

---

## Input image options

### `--reference-image`
Add one or more reference images.

May be passed multiple times:

```bash
--reference-image ./a.png --reference-image ./b.png
```

Use this when the image should act as:

- visual inspiration
- logo reference
- character / outfit reference
- product reference
- composition or style hint

### `--edit-image`
Provide the main edit target image.

Use this when the existing image itself should be modified rather than merely referenced.

Examples:

- swap background
- replace text
- alter styling while preserving layout

---

## Debugging and metadata

### `--events`
Save raw `codex responses` JSONL events.

Useful for:

- debugging parsing failures
- inspecting raw tool-call outputs
- checking whether `revised_prompt` was returned

Example:

```bash
--events ./debug/events.jsonl
```

### `--metadata`
Write metadata JSON to a custom path.

If omitted, metadata is written next to the saved image using:

```text
<image-file>.<ext>.json
```

Metadata includes:

- original prompt
- selected prompt mode
- enhancement profile
- research mode
- model
- size / quality / background / format / action
- input image paths
- revised prompt
- usage
- web search call count
- output path
- raw event count

---

## Revised prompt

The hosted `image_generation` tool may produce a `revised_prompt`.

Important distinction:

- this repository controls the **upper-layer prompt policy**
- the hosted OpenAI tool may still apply its own internal prompt revision afterward

So this repo does **not** promise that the final internal revised prompt will equal the exact wrapper prompt byte-for-byte.

What it does guarantee is that the **policy before tool invocation** is controlled here.

---

## Recommended usage patterns

### Use `fidelity` when

- posters contain exact text
- brand constraints matter
- layout / exclusions matter
- the user cares about prompt faithfulness

### Use `enhanced + photoreal` when

- photoreal output is desired
- the user did not specify style but wants realistic rendering

### Use `enhanced + cinematic` when

- atmosphere, drama, and composition matter
- concept art / scene framing matters

### Use `enhanced + aggressive` when

- maximum intervention is acceptable
- prompt boosting and negative-prompt-style cleanup are wanted
- fidelity is less important than pushing output quality hard

### Use `research auto` when

- real-world identity or factual appearance matters
- products / brands / places should reflect reality more closely

---

## Troubleshooting

### `codex login status` shows API key mode

Re-login with Codex OAuth:

```bash
codex logout
codex login
codex login status
```

Also check whether `OPENAI_API_KEY` in the environment is overriding the OAuth state.

### `No image_generation_call result found`

Run again with:

```bash
--events image_events.jsonl
```

and inspect the raw event stream.

### Transparent output fails

Retry with:

```bash
--background opaque
```

### Enhancement profile not accepted

Use:

```bash
--prompt-mode enhanced
```

when setting a non-`none` enhancement profile.

---

## Git workflow hint

Because this skill is kept in its own git-connected directory, a typical update loop is:

```bash
git status
git diff
python scripts/gen_image.py --help
git add SKILL.md README.md scripts/gen_image.py
git commit -m "feat: update codex image creator skill"
```

That keeps the Hermes skill definition and the executable helper script versioned together.
