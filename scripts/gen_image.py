#!/usr/bin/env python3
import argparse
import base64
import json
import subprocess
import sys
from pathlib import Path


def build_payload(args: argparse.Namespace) -> dict:
    tool = {
        "type": "image_generation",
        "size": args.size,
        "quality": args.quality,
        "background": args.background,
    }

    if args.action:
        tool["action"] = args.action

    return {
        "model": args.model,
        "instructions": "Use the image_generation tool to create the requested image. Return the image generation result.",
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": args.prompt}],
            }
        ],
        "tools": [tool],
        "tool_choice": {"type": "image_generation"},
        "store": False,
        "stream": True,
    }


def extract_image(events_text: str, events_path: Path | None) -> str | None:
    image_b64 = None

    if events_path:
        events_path.write_text(events_text, encoding="utf-8")

    for line in events_text.splitlines():
        if not line.strip():
            continue

        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        item = event.get("item") or {}
        if (
            event.get("type") == "response.output_item.done"
            and item.get("type") == "image_generation_call"
        ):
            image_b64 = item.get("result") or image_b64

    return image_b64


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate an image through `codex responses` and save it to a file."
    )
    parser.add_argument("prompt", help="Image prompt")
    parser.add_argument("-o", "--output", default="image.png", help="Output image path")
    parser.add_argument("--model", default="gpt-5.4", help="Mainline model used to call the tool")
    parser.add_argument("--size", default="1024x1024", help="Image size, for example 1024x1024")
    parser.add_argument("--quality", default="high", choices=("auto", "low", "medium", "high"), help="Image quality")
    parser.add_argument("--background", default="auto", choices=("auto", "opaque", "transparent"), help="Image background")
    parser.add_argument(
        "--action",
        choices=("auto", "generate", "edit"),
        default="generate",
        help="Image tool action",
    )
    parser.add_argument(
        "--events",
        help="Optional path to save raw codex responses JSONL events",
    )
    args = parser.parse_args()

    payload = build_payload(args)
    proc = subprocess.run(
        ["codex", "responses"],
        input=json.dumps(payload),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        return proc.returncode

    events_path = Path(args.events) if args.events else None
    image_b64 = extract_image(proc.stdout, events_path)
    if not image_b64:
        sys.stderr.write("No image_generation_call result found.\n")
        if not args.events:
            sys.stderr.write("Re-run with --events image_events.jsonl to inspect raw events.\n")
        return 1

    output_path = Path(args.output)
    output_path.write_bytes(base64.b64decode(image_b64))
    print(f"Saved {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
