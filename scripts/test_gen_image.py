import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).with_name("gen_image.py")
spec = importlib.util.spec_from_file_location("gen_image", SCRIPT)
gen_image = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen_image)


def test_build_payload_preserves_image_controls_and_required_tool_choice():
    args = gen_image.parse_args_from_list([
        "draw a precise poster",
        "--prompt-mode", "enhanced",
        "--enhancement-profile", "safe-polish",
        "--size", "1024x1024",
        "--quality", "high",
        "--background", "transparent",
        "--format", "png",
        "--moderation", "auto",
        "--reasoning-effort", "high",
    ])
    gen_image.validate_args(args)

    payload = gen_image.build_payload(args, {"edit": None, "references": []})
    image_tool = payload["tools"][-1]

    assert image_tool["type"] == "image_generation"
    assert image_tool["model"] == gen_image.IMAGE_MODEL
    assert image_tool["size"] == "1024x1024"
    assert image_tool["quality"] == "high"
    assert image_tool["background"] == "transparent"
    assert image_tool["output_format"] == "png"
    assert image_tool["moderation"] == "auto"
    assert payload["tool_choice"] == "required"
    assert payload["reasoning"] == {"effort": "high"}
    assert payload["instructions"] == payload["input"][0]["content"]
    assert payload["input"][0]["role"] == "developer"
    assert payload["input"][1]["role"] == "user"
    assert "Visible text and language rule" in payload["input"][0]["content"]
    assert "Level of Intent to Sexual Exploitation" in payload["input"][0]["content"]


def test_defaults_are_fidelity_low_moderation_and_medium_reasoning():
    args = gen_image.parse_args_from_list(["고양이 수채화"])
    gen_image.validate_args(args)
    payload = gen_image.build_payload(args, {"edit": None, "references": []})

    assert args.prompt_mode == "fidelity"
    assert args.moderation == "low"
    assert args.reasoning_effort == "medium"
    assert payload["tools"][-1]["moderation"] == "low"
    user_text = payload["input"][1]["content"][-1]["text"]
    assert "pass it through unchanged" in user_text
    assert "Do not translate" in user_text


def test_direct_mode_instructs_no_modifications():
    args = gen_image.parse_args_from_list(["정확한 문구 '안녕'이 있는 포스터", "--prompt-mode", "direct"])
    gen_image.validate_args(args)
    payload = gen_image.build_payload(args, {"edit": None, "references": []})
    developer = payload["input"][0]["content"]
    user_text = payload["input"][1]["content"][-1]["text"]

    assert "Do not translate, summarize" in developer
    assert "no modifications" in user_text
    assert "안녕" in user_text


def test_model_validation_rejects_unknown_and_unsupported():
    args = gen_image.parse_args_from_list(["x", "--model", "gpt-5.3-codex-spark"])
    try:
        gen_image.validate_args(args)
    except ValueError as exc:
        assert "does not support image generation" in str(exc)
    else:
        raise AssertionError("unsupported model should fail")

    args = gen_image.parse_args_from_list(["x", "--model", "gpt-unknown"])
    try:
        gen_image.validate_args(args)
    except ValueError as exc:
        assert "model must be one of" in str(exc)
    else:
        raise AssertionError("unknown model should fail")


def test_reference_limit_validation():
    argv = ["x"]
    for idx in range(gen_image.MAX_REFERENCE_IMAGES + 1):
        argv += ["--reference-image", f"ref{idx}.png"]
    args = gen_image.parse_args_from_list(argv)
    try:
        gen_image.validate_args(args)
    except ValueError as exc:
        assert "at most" in str(exc)
    else:
        raise AssertionError("too many references should fail")


def test_detect_image_mime_magic_bytes_over_extension(tmp_path):
    path = tmp_path / "fake.png"
    data = bytes([0xff, 0xd8, 0xff, 0xd9])
    path.write_bytes(data)

    mime, warnings = gen_image.detect_image_mime(data, path)

    assert mime == "image/jpeg"
    assert warnings
    assert "mime_mismatch" in warnings[0]


def test_build_user_content_uses_normalized_input_images(tmp_path):
    edit = gen_image.NormalizedImage(
        content_b64="ZmFrZQ==",
        mime="image/jpeg",
        source_path=str(tmp_path / "edit.jpg"),
        original_b64_chars=8,
        output_b64_chars=8,
    )
    ref = gen_image.NormalizedImage(
        content_b64="ZmFrZTI=",
        mime="image/png",
        source_path=str(tmp_path / "ref.png"),
        original_b64_chars=8,
        output_b64_chars=8,
    )
    args = gen_image.parse_args_from_list(["edit this", "--edit-image", "edit.jpg", "--reference-image", "ref.png"])
    content = gen_image.build_user_content(args, {"edit": edit, "references": [ref]})

    assert content[0]["image_url"].startswith("data:image/jpeg;base64,")
    assert content[1]["image_url"].startswith("data:image/png;base64,")
    assert content[-1]["type"] == "input_text"


def test_run_codex_uses_direct_client(monkeypatch):
    class FakeEvent:
        def __init__(self, payload):
            self.payload = payload
        def model_dump_json(self):
            return json.dumps(self.payload)

    class FakeFinal:
        def model_dump(self):
            return {"id": "resp_fake", "usage": {"input_tokens": 1}}

    class FakeStream:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False
        def __iter__(self):
            yield FakeEvent({
                "type": "response.output_item.done",
                "item": {
                    "type": "image_generation_call",
                    "result": "ZmFrZQ==",
                    "revised_prompt": "fake revised",
                },
            })
        def get_final_response(self):
            return FakeFinal()

    class FakeResponses:
        captured = None
        def stream(self, **kwargs):
            FakeResponses.captured = kwargs
            return FakeStream()

    class FakeClient:
        responses = FakeResponses()

    monkeypatch.setattr(gen_image, "_build_codex_client", lambda: FakeClient())

    payload = {
        "model": "gpt-5.4",
        "input": [{"role": "user", "content": [{"type": "input_text", "text": "x"}]}],
        "tools": [{"type": "image_generation", "model": gen_image.IMAGE_MODEL}],
        "tool_choice": "required",
        "stream": True,
        "store": False,
    }

    proc = gen_image.run_codex(payload)

    assert proc.returncode == 0
    assert "image_generation_call" in proc.stdout
    assert "response.completed" in proc.stdout
    assert "stream" not in FakeResponses.captured
    assert FakeResponses.captured["tools"][0]["model"] == gen_image.IMAGE_MODEL


def test_extract_generation_info_collects_diagnostics(tmp_path):
    events = "\n".join([
        json.dumps({"type": "response.output_item.partial", "item": {"partial_image": "abc"}}),
        json.dumps({"type": "response.output_item.done", "item": {"type": "web_search_call"}}),
        json.dumps({"type": "response.output_item.done", "item": {"type": "image_generation_call", "result": "ZmFrZQ==", "revised_prompt": "rev"}}),
        json.dumps({"type": "response.completed", "response": {"usage": {"input_tokens": 1}, "tool_usage": {"web_search": {"num_requests": 2}}}}),
    ])
    path = tmp_path / "events.jsonl"

    info = gen_image.extract_generation_info(events, path)

    assert path.exists()
    assert info["image_b64"] == "ZmFrZQ=="
    assert info["revised_prompt"] == "rev"
    assert info["web_search_calls"] == 2
    assert info["partial_images"] == 1
    assert info["event_types"]["response.completed"] == 1
