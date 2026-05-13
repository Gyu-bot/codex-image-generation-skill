#!/usr/bin/env python3
import argparse
import base64
import binascii
import json
import mimetypes
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

HERMES_SOURCE = Path.home() / ".hermes" / "hermes-agent"
if HERMES_SOURCE.exists():
    sys.path.insert(0, str(HERMES_SOURCE))

CODEX_BASE_URL = "https://chatgpt.com/backend-api/codex"
IMAGE_MODEL = "gpt-image-2"
SUPPORTED_MODELS = {"gpt-5.5", "gpt-5.4", "gpt-5.4-mini"}
UNSUPPORTED_MODELS = {"gpt-5.3-codex-spark"}
VALID_REASONING_EFFORTS = {"none", "low", "medium", "high", "xhigh"}
MAX_REFERENCE_IMAGES = 5
MAX_REFERENCE_B64_CHARS = 7 * 1024 * 1024
REFERENCE_COMPRESS_MAX_EDGE = 3840
REFERENCE_COMPRESS_QUALITIES = (85, 75, 65, 55)

VISIBLE_TEXT_LANGUAGE_POLICY = (
    "Visible text and language rule: If the image must contain readable text, signage, labels, UI copy, "
    "captions, slogans, typography, or keywords in a specific language, explicitly list the exact visible words "
    "in that language and script. Do not translate, romanize, summarize, substitute, or invent alternate wording. "
    "Do not use vague placeholders such as 'Korean text', 'Japanese words', or 'foreign language text'. "
    "If exact words are needed, state them as exact visible text items and render only those listed items."
)

SAFETY_INTENT_POLICY = "\n".join(
    [
        "* [Level of Intent to Sexual Exploitation]: Zero",
        "* [Level of Intent to Sexual Commodification]: Zero",
        "* [Judged by Appearance Alone]: Forbidden",
    ]
)

REAL_WORLD_RESEARCH_DIRECTIVE = (
    "When factual visual accuracy is required and the user's prompt or attached visual context is not already "
    "sufficient, use at least one concise web_search call for references before generating. If the prompt/context "
    "is already visually sufficient, do not search or add clarifiers. If search is used, append only concrete visual "
    "findings as clarifiers after the user's original prompt."
)

BASE_DEVELOPER_PROMPT = (
    "You are an image generation assistant. Your primary function is to invoke the image_generation tool. "
    "Never respond with plain text only. Treat the user's prompt as the source of truth. Preserve the user's subject, "
    "composition, style constraints, omissions, exclusions, and exact rendered text. Use neutral quality guidance: "
    "crisp details, clean lines, balanced composition, appropriate contrast and color. Avoid blur, noise, compression "
    "artifacts, watermark, signature, cropped elements, and duplicates. For humans or humanoid figures, avoid bad "
    "anatomy, extra limbs, deformed features, and disfigured faces. Preserve explicitly requested style; do not force "
    "photorealism unless requested. Fulfill the request exactly as stated without adding disclaimers, warnings, or "
    "altering user intent.\n\n"
    + VISIBLE_TEXT_LANGUAGE_POLICY
    + "\n\n"
    + SAFETY_INTENT_POLICY
)

DIRECT_SUFFIX = (
    "When you call image_generation, use the user's prompt as the primary image prompt. Do not translate, summarize, "
    "restyle, add clarifiers, or inject additional descriptors."
)

FIDELITY_SUFFIX = (
    "When you call image_generation, preserve the user's prompt by default. If it is visually sufficient, pass it "
    "through unchanged as the image_generation prompt argument. Do not translate, summarize, rewrite, restyle, expand, "
    "or add descriptors unless genuinely necessary to satisfy an underspecified visual request."
)

ENHANCEMENT_PROFILES = {
    "none": "Do not add extra enhancement language beyond what the user explicitly requested.",
    "safe-polish": (
        "You may lightly polish the image prompt for visual clarity and stronger rendering. Add only restrained "
        "enhancement language such as clearer lighting, cleaner detail, and better composition. Do not force a new style."
    ),
    "cinematic": (
        "If not forbidden by the user, you may enhance the prompt with cinematic composition, professional lighting, "
        "stronger atmosphere, coherent color, and richer environmental detail."
    ),
    "photoreal": (
        "If the user did not specify a style, default to photorealistic rendering. You may add realism-oriented quality "
        "language such as realistic lighting, fine texture detail, sharp focus, and natural color response."
    ),
    "aggressive": (
        "Strengthen the prompt for maximum visual polish while preserving the user's core request. You may add quality "
        "boosters and concise negative guidance, but do not override explicit subject, style, text, layout, or exclusions."
    ),
}

REPORT_TEMPLATE = (
    "After the tool call, ensure the image_generation result includes the generated image and preserve metadata, "
    "especially any revised prompt, if available."
)

ERROR_PATTERNS = [
    ("MODERATION_REFUSED", ("moderation_blocked", "moderation refused", "safety_violations", "safety violation")),
    ("AUTH_CHATGPT_EXPIRED", ("token is expired", "sign in again", "access token", "refresh token")),
    ("AUTH_API_KEY_INVALID", ("incorrect api key", "invalid authentication", "incorrect organization")),
    ("NETWORK_FAILED", ("failed to fetch", "econnrefused", "econnreset", "enotfound", "etimedout", "network error")),
    ("INVALID_REQUEST", ("invalid_request_error", "invalid_value", "invalid size", "invalid request", "unsupported value")),
    ("UPSTREAM_5XX", ("an error occurred while processing", "internal server error", "bad gateway", "service unavailable")),
    ("TIMEOUT", ("timed out", "timeout")),
]


@dataclass
class NormalizedImage:
    content_b64: str
    mime: str
    source_path: str
    original_b64_chars: int
    output_b64_chars: int
    compressed: bool = False
    warnings: list[str] | None = None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate or edit an image through Codex OAuth + OpenAI image_generation."
    )
    parser.add_argument("prompt", help="Creative image prompt or edit instruction")
    parser.add_argument("-o", "--output", help="Output file path or directory. Defaults to current directory with an auto filename.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite an existing destination file instead of auto-versioning it.")
    parser.add_argument("--model", default="gpt-5.4", help="Mainline Responses model: gpt-5.5, gpt-5.4, or gpt-5.4-mini")
    parser.add_argument("--reasoning-effort", default="medium", choices=tuple(sorted(VALID_REASONING_EFFORTS)), help="Responses reasoning effort")
    parser.add_argument("--prompt-mode", default="fidelity", choices=("direct", "fidelity", "enhanced"), help="Prompt control policy")
    parser.add_argument("--enhancement-profile", default="none", choices=tuple(ENHANCEMENT_PROFILES.keys()), help="Optional enhancement bundle used when prompt-mode=enhanced")
    parser.add_argument("--research", default="off", choices=("off", "auto"), help="Allow optional web_search before image generation for real-world subjects")
    parser.add_argument("--size", default="1024x1024", help="Image size, for example 1024x1024")
    parser.add_argument("--quality", default="medium", choices=("auto", "low", "medium", "high"), help="Image quality")
    parser.add_argument("--background", default="auto", choices=("auto", "opaque", "transparent"), help="Image background")
    parser.add_argument("--moderation", default="low", choices=("auto", "low"), help="Image moderation strictness")
    parser.add_argument("--format", default="png", choices=("png", "jpeg", "webp"), help="Output image format requested from image_generation")
    parser.add_argument("--compression", type=int, help="Compression level for jpeg/webp outputs (0-100)")
    parser.add_argument("--action", default="auto", choices=("auto", "generate", "edit"), help="Image tool action")
    parser.add_argument("--reference-image", action="append", default=[], help="Reference image path. May be passed multiple times, max 5.")
    parser.add_argument("--edit-image", help="Edit target image path. When present, action defaults to edit semantics in the prompt.")
    parser.add_argument("--count", type=int, default=1, help="Number of candidate images to generate, 1-8")
    parser.add_argument("--events", help="Optional path to save raw Responses JSONL events")
    parser.add_argument("--metadata", help="Optional path to save metadata JSON. Defaults to <saved-image>.json when omitted.")
    return parser


def parse_args_from_list(argv: list[str]) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def parse_args() -> argparse.Namespace:
    return build_parser().parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.model in UNSUPPORTED_MODELS:
        raise ValueError(f"model does not support image generation: {args.model}")
    if args.model not in SUPPORTED_MODELS:
        raise ValueError(f"model must be one of: {', '.join(sorted(SUPPORTED_MODELS))}")
    if args.prompt_mode != "enhanced" and args.enhancement_profile != "none":
        raise ValueError("--enhancement-profile requires --prompt-mode enhanced")
    if args.edit_image and args.action == "generate":
        args.action = "edit"
    if args.count < 1 or args.count > 8:
        raise ValueError("--count must be between 1 and 8")
    if len(args.reference_image) > MAX_REFERENCE_IMAGES:
        raise ValueError(f"--reference-image may be passed at most {MAX_REFERENCE_IMAGES} times")


def detect_image_mime(data: bytes, fallback_path: Path | None = None) -> tuple[str, list[str]]:
    warnings: list[str] = []
    detected = None
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        detected = "image/png"
    elif data.startswith(b"\xff\xd8\xff"):
        detected = "image/jpeg"
    elif len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        detected = "image/webp"
    declared = None
    if fallback_path:
        declared = mimetypes.guess_type(fallback_path.name)[0]
    if declared and detected and declared != detected:
        warnings.append(f"mime_mismatch: declared={declared} detected={detected}")
    return detected or declared or "image/png", warnings


def compress_image_if_needed(data: bytes, mime: str, max_b64_chars: int = MAX_REFERENCE_B64_CHARS) -> tuple[bytes, str, bool]:
    original_b64_len = len(base64.b64encode(data))
    if original_b64_len <= max_b64_chars:
        return data, mime, False
    try:
        from PIL import Image
    except Exception as exc:
        raise ValueError(f"reference image exceeds {max_b64_chars} base64 chars and Pillow is unavailable for compression: {exc}") from exc

    image = Image.open(BytesIO(data))
    image = image.convert("RGB")
    image.thumbnail((REFERENCE_COMPRESS_MAX_EDGE, REFERENCE_COMPRESS_MAX_EDGE))
    for quality in REFERENCE_COMPRESS_QUALITIES:
        out = BytesIO()
        image.save(out, format="JPEG", quality=quality, optimize=True, progressive=True)
        compressed = out.getvalue()
        if len(base64.b64encode(compressed)) <= max_b64_chars:
            return compressed, "image/jpeg", True
    raise ValueError(f"reference image remains above {max_b64_chars} base64 chars after compression")


def normalize_image_path(path_str: str) -> NormalizedImage:
    path = Path(path_str).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Input image not found: {path}")
    data = path.read_bytes()
    mime, warnings = detect_image_mime(data, path)
    compressed_data, final_mime, compressed = compress_image_if_needed(data, mime)
    b64 = base64.b64encode(compressed_data).decode("ascii")
    return NormalizedImage(
        content_b64=b64,
        mime=final_mime,
        source_path=str(path),
        original_b64_chars=len(base64.b64encode(data)),
        output_b64_chars=len(b64),
        compressed=compressed,
        warnings=warnings,
    )


def encode_image_item(normalized: NormalizedImage) -> dict[str, str]:
    return {
        "type": "input_image",
        "image_url": f"data:{normalized.mime};base64,{normalized.content_b64}",
    }


def role_guidance(args: argparse.Namespace) -> str:
    lines: list[str] = []
    if args.edit_image:
        lines.append("The first provided image is the edit target. Preserve its relevant identity, layout, and content unless the user explicitly asks to change them.")
    if args.reference_image:
        lines.append(f"There are {len(args.reference_image)} reference image(s). Use them only as references unless the user explicitly requests direct editing.")
    return " ".join(lines)


def build_developer_prompt(args: argparse.Namespace) -> str:
    parts = [BASE_DEVELOPER_PROMPT]
    if args.prompt_mode == "direct":
        parts.append(DIRECT_SUFFIX)
    elif args.prompt_mode == "fidelity":
        parts.append(FIDELITY_SUFFIX)
    else:
        parts.append("Enhancement mode is enabled. You may strengthen the image prompt according to the selected enhancement profile while preserving the user's core request.")
        parts.append(ENHANCEMENT_PROFILES[args.enhancement_profile])

    if args.research == "auto":
        parts.append(REAL_WORLD_RESEARCH_DIRECTIVE)
    else:
        parts.append("Do not use web_search unless explicitly required by the user.")

    guidance = role_guidance(args)
    if guidance:
        parts.append(guidance)
    parts.append(REPORT_TEMPLATE)
    return "\n\n".join(parts)


def build_user_content(args: argparse.Namespace, normalized_inputs: dict[str, Any] | None = None) -> list[dict[str, str]] | str:
    normalized_inputs = normalized_inputs or normalize_input_images(args)
    content: list[dict[str, str]] = []
    if normalized_inputs.get("edit"):
        content.append(encode_image_item(normalized_inputs["edit"]))
    for ref in normalized_inputs.get("references", []):
        content.append(encode_image_item(ref))

    if args.prompt_mode == "direct":
        text = f"Generate or edit with this exact prompt, no modifications: {args.prompt}\n\n{DIRECT_SUFFIX}\n\n{VISIBLE_TEXT_LANGUAGE_POLICY}"
    elif args.prompt_mode == "fidelity":
        text = f"Generate or edit this image request: {args.prompt}\n\n{FIDELITY_SUFFIX}\n\n{VISIBLE_TEXT_LANGUAGE_POLICY}"
    else:
        text = f"Generate or edit this image request: {args.prompt}"
    content.append({"type": "input_text", "text": text})
    return content


def normalize_input_images(args: argparse.Namespace) -> dict[str, Any]:
    edit = normalize_image_path(args.edit_image) if args.edit_image else None
    references = [normalize_image_path(ref) for ref in args.reference_image]
    return {"edit": edit, "references": references}


def input_diagnostics(normalized_inputs: dict[str, Any]) -> dict[str, Any]:
    def one(item: NormalizedImage | None) -> dict[str, Any] | None:
        if item is None:
            return None
        return {
            "path": item.source_path,
            "mime": item.mime,
            "original_b64_chars": item.original_b64_chars,
            "output_b64_chars": item.output_b64_chars,
            "compressed": item.compressed,
            "warnings": item.warnings or [],
        }
    return {
        "edit_image": one(normalized_inputs.get("edit")),
        "reference_images": [one(ref) for ref in normalized_inputs.get("references", [])],
    }


def build_payload(args: argparse.Namespace, normalized_inputs: dict[str, Any] | None = None) -> dict[str, Any]:
    tool: dict[str, Any] = {
        "type": "image_generation",
        "model": IMAGE_MODEL,
        "size": args.size,
        "quality": args.quality,
        "background": args.background,
        "moderation": args.moderation,
        "output_format": args.format,
        "partial_images": 1,
    }
    if args.action:
        tool["action"] = args.action
    if args.compression is not None:
        tool["compression"] = args.compression

    tools: list[dict[str, Any]] = []
    if args.research == "auto":
        tools.append({"type": "web_search"})
    tools.append(tool)

    developer_prompt = build_developer_prompt(args)
    payload: dict[str, Any] = {
        "model": args.model,
        "instructions": developer_prompt,
        "input": [
            {"role": "developer", "content": developer_prompt},
            {"role": "user", "content": build_user_content(args, normalized_inputs)},
        ],
        "tools": tools,
        "tool_choice": "required",
        "store": False,
        "stream": True,
    }
    if args.reasoning_effort != "none":
        payload["reasoning"] = {"effort": args.reasoning_effort}
    return payload


def extract_generation_info(events_text: str, events_path: Path | None) -> dict[str, Any]:
    if events_path:
        events_path.parent.mkdir(parents=True, exist_ok=True)
        events_path.write_text(events_text, encoding="utf-8")

    image_b64 = None
    revised_prompt = None
    usage = None
    web_search_calls = 0
    raw_events = 0
    event_types: dict[str, int] = {}
    partial_images = 0
    errors: list[dict[str, Any]] = []

    for line in events_text.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        raw_events += 1
        event_type = event.get("type") or "unknown"
        event_types[event_type] = event_types.get(event_type, 0) + 1
        item = event.get("item") or {}
        if "partial" in event_type or item.get("partial_image"):
            partial_images += 1
        if event_type == "response.output_item.done" and item.get("type") == "image_generation_call":
            image_b64 = item.get("result") or item.get("image") or image_b64
            revised_prompt = item.get("revised_prompt") or item.get("revisedPrompt") or revised_prompt
        if event_type == "response.output_item.done" and item.get("type") == "web_search_call":
            web_search_calls += 1
        if event_type == "response.completed":
            response = event.get("response") or {}
            usage = response.get("usage") or usage
            tool_usage = response.get("tool_usage") or {}
            web_info = tool_usage.get("web_search") or {}
            if isinstance(web_info.get("num_requests"), int):
                web_search_calls = max(web_search_calls, web_info["num_requests"])
        if event_type == "error":
            errors.append(event.get("error") or event)

    return {
        "image_b64": image_b64,
        "revised_prompt": revised_prompt,
        "usage": usage,
        "web_search_calls": web_search_calls,
        "raw_events": raw_events,
        "event_types": event_types,
        "partial_images": partial_images,
        "errors": errors,
    }


def default_filename(ext: str, index: int | None = None) -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = f"-{index}" if index is not None else ""
    return f"image-creator-{stamp}{suffix}.{ext}"


def resolve_destination(output: str | None, ext: str, index: int | None = None, count: int = 1) -> Path:
    cwd = Path.cwd().resolve()
    if not output:
        return cwd / default_filename(ext, index if count > 1 else None)
    raw = output
    path = Path(output).expanduser()
    if not path.is_absolute():
        path = (cwd / path).resolve()
    if raw.endswith(("/", "\\")) or (path.exists() and path.is_dir()) or not path.suffix:
        return path / default_filename(ext, index if count > 1 else None)
    if count > 1:
        return path.with_name(f"{path.stem}-{index}{path.suffix}")
    return path


def uniquify(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    idx = 2
    while True:
        candidate = parent / f"{stem}-{idx}{suffix}"
        if not candidate.exists():
            return candidate
        idx += 1


def save_image(image_b64: str, dest: Path, overwrite: bool) -> Path:
    final_path = dest if overwrite else uniquify(dest)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = base64.b64decode(image_b64)
    except binascii.Error as exc:
        raise ValueError(f"Invalid base64 image result: {exc}") from exc
    final_path.write_bytes(data)
    return final_path


def metadata_path_for(image_path: Path, metadata_arg: str | None, index: int | None = None, count: int = 1) -> Path:
    if metadata_arg:
        path = Path(metadata_arg).expanduser()
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        if count > 1:
            path = path.with_name(f"{path.stem}-{index}{path.suffix or '.json'}")
        return path
    return image_path.with_suffix(image_path.suffix + ".json")


def events_path_for(events_arg: str | None, index: int | None = None, count: int = 1) -> Path | None:
    if not events_arg:
        return None
    path = Path(events_arg).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    if count > 1:
        path = path.with_name(f"{path.stem}-{index}{path.suffix or '.jsonl'}")
    return path


def _event_json(event: Any) -> str:
    if hasattr(event, "model_dump_json"):
        return event.model_dump_json()
    if hasattr(event, "model_dump"):
        return json.dumps(event.model_dump(), ensure_ascii=False, default=str)
    if isinstance(event, dict):
        return json.dumps(event, ensure_ascii=False, default=str)
    return json.dumps({"type": getattr(event, "type", "unknown"), "repr": repr(event)}, ensure_ascii=False)


def _build_codex_client() -> Any:
    try:
        import openai
        from agent.auxiliary_client import _codex_cloudflare_headers, _read_codex_access_token
    except Exception as exc:
        raise RuntimeError(f"Could not import Hermes Codex OAuth helpers: {exc}") from exc

    token = _read_codex_access_token()
    if not token:
        raise RuntimeError("No Codex/ChatGPT OAuth credentials available")
    return openai.OpenAI(
        api_key=token,
        base_url=CODEX_BASE_URL,
        default_headers=_codex_cloudflare_headers(token),
    )


def classify_error_message(message: str) -> str:
    s = message.lower()
    for code, needles in ERROR_PATTERNS:
        if any(needle in s for needle in needles):
            return code
    if any(f" {n} " in f" {s} " for n in ("500", "502", "503", "504")):
        return "UPSTREAM_5XX"
    return "UNKNOWN"


def is_retryable_error(code: str) -> bool:
    return code in {"UPSTREAM_5XX", "NETWORK_FAILED", "TIMEOUT", "UNKNOWN"}


def run_codex(payload: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    try:
        client = _build_codex_client()
        stream_payload = dict(payload)
        stream_payload.pop("stream", None)
        events: list[str] = []
        with client.responses.stream(**stream_payload) as stream:
            for event in stream:
                events.append(_event_json(event))
            final = stream.get_final_response()
        if final is not None:
            response_data = final.model_dump() if hasattr(final, "model_dump") else final
            events.append(json.dumps({"type": "response.completed", "response": response_data}, ensure_ascii=False, default=str))
        return subprocess.CompletedProcess(["codex-oauth-responses"], 0, stdout="\n".join(events) + "\n", stderr="")
    except Exception as exc:
        code = classify_error_message(str(exc))
        return subprocess.CompletedProcess(["codex-oauth-responses"], 1, stdout="", stderr=f"{code}: Direct Codex OAuth Responses request failed\n")


def run_with_retry(payload: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    first = run_codex(payload)
    if first.returncode == 0:
        return first
    code = first.stderr.split(":", 1)[0] if first.stderr else "UNKNOWN"
    if is_retryable_error(code):
        second = run_codex(payload)
        if second.returncode == 0:
            return second
        return subprocess.CompletedProcess(second.args, second.returncode, second.stdout, first.stderr + second.stderr)
    return first


def generate_once(args: argparse.Namespace, normalized_inputs: dict[str, Any], index: int, count: int) -> Path:
    payload = build_payload(args, normalized_inputs)
    proc = run_with_retry(payload)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        raise RuntimeError("image generation request failed")

    events_path = events_path_for(args.events, index=index, count=count)
    info = extract_generation_info(proc.stdout, events_path)
    if not info["image_b64"]:
        diagnostic = {
            "code": "EMPTY_RESPONSE",
            "raw_event_count": info["raw_events"],
            "event_types": info["event_types"],
            "errors": info["errors"],
            "model": args.model,
            "size": args.size,
            "quality": args.quality,
            "refs_count": len(args.reference_image),
        }
        sys.stderr.write("No image_generation_call result found.\n")
        sys.stderr.write(json.dumps(diagnostic, ensure_ascii=False) + "\n")
        if not args.events:
            sys.stderr.write("Re-run with --events image_events.jsonl to inspect raw events.\n")
        raise RuntimeError("empty image generation response")

    destination = resolve_destination(args.output, args.format, index=index, count=count)
    saved_path = save_image(info["image_b64"], destination, args.overwrite)

    metadata = {
        "saved_path": str(saved_path),
        "prompt": args.prompt,
        "model": args.model,
        "image_model": IMAGE_MODEL,
        "reasoning_effort": args.reasoning_effort,
        "prompt_mode": args.prompt_mode,
        "enhancement_profile": args.enhancement_profile,
        "research": args.research,
        "size": args.size,
        "quality": args.quality,
        "background": args.background,
        "format": args.format,
        "moderation": args.moderation,
        "action": args.action,
        "count": count,
        "index": index,
        "inputs": input_diagnostics(normalized_inputs),
        "revised_prompt": info["revised_prompt"],
        "usage": info["usage"],
        "web_search_calls": info["web_search_calls"],
        "events_saved": str(events_path) if events_path else None,
        "raw_event_count": info["raw_events"],
        "event_types": info["event_types"],
        "partial_images": info["partial_images"],
        "created_at": datetime.now().isoformat(),
    }
    metadata_path = metadata_path_for(saved_path, args.metadata, index=index, count=count)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Saved {saved_path}")
    print(f"Metadata {metadata_path}")
    if info["revised_prompt"]:
        print(f"Revised prompt: {info['revised_prompt']}")
    return saved_path


def main() -> int:
    args = parse_args()
    try:
        validate_args(args)
        normalized_inputs = normalize_input_images(args)
        saved: list[Path] = []
        for index in range(1, args.count + 1):
            saved.append(generate_once(args, normalized_inputs, index=index, count=args.count))
        if len(saved) > 1:
            print("Saved candidates:")
            for path in saved:
                print(path)
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2 if isinstance(exc, ValueError) else 1


if __name__ == "__main__":
    raise SystemExit(main())
