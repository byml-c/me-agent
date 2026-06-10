from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.core.config import get_settings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Test Responses API with the official OpenAI Python SDK.")
    parser.add_argument("--mode", choices=["both", "non-stream", "stream"], default="both")
    parser.add_argument("--message", default="Say hello in three short sentences.")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--dump", action="store_true", help="Print full SDK objects as JSON.")
    args = parser.parse_args()

    try:
        from openai import OpenAI
    except ImportError:
        print("Missing dependency: openai", file=sys.stderr)
        print("Install it with: pip install openai", file=sys.stderr)
        return 2

    settings = get_settings()
    if not settings.openai_api_key:
        print("OPENAI_API_KEY is not configured.", file=sys.stderr)
        return 2

    client = OpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        timeout=args.timeout,
    )
    print(f"base_url={settings.openai_base_url}")
    print(f"model={settings.openai_base_model}")

    if args.mode in {"both", "non-stream"}:
        print("\n=== responses.create non-stream ===", flush=True)
        test_non_stream(client, settings.openai_base_model, args.message, args.dump)

    if args.mode in {"both", "stream"}:
        print("\n=== responses.create stream=True ===", flush=True)
        test_stream(client, settings.openai_base_model, args.message, args.dump)

    return 0


def test_non_stream(client: Any, model: str, message: str, dump: bool) -> None:
    start = time.monotonic()
    try:
        response = client.responses.create(
            model=model,
            input=message,
        )
    except Exception as exc:
        print_exception(exc)
        return

    elapsed = time.monotonic() - start
    output_text = getattr(response, "output_text", "") or ""
    print(f"elapsed={elapsed:.3f}s")
    print(f"id={getattr(response, 'id', None)}")
    print(f"status={getattr(response, 'status', None)}")
    print(f"output_text_len={len(output_text)}")
    if output_text:
        print(f"output_text={output_text}")
    if dump:
        print_json(response)


def test_stream(client: Any, model: str, message: str, dump: bool) -> None:
    start = time.monotonic()
    previous = start
    event_count = 0
    delta_count = 0
    delta_chars = 0
    text_parts: list[str] = []

    try:
        stream = client.responses.create(
            model=model,
            input=message,
            stream=True,
        )
        for event in stream:
            now = time.monotonic()
            event_count += 1
            event_type = getattr(event, "type", type(event).__name__)
            gap = now - previous
            previous = now

            if event_type == "response.output_text.delta":
                delta = getattr(event, "delta", "") or ""
                delta_count += 1
                delta_chars += len(delta)
                text_parts.append(delta)
                print(
                    f"{now - start:8.3f}s +{gap:.3f}s event={event_type} "
                    f"delta_len={len(delta)} delta={preview(delta)!r}",
                    flush=True,
                )
            else:
                print(f"{now - start:8.3f}s +{gap:.3f}s event={event_type}", flush=True)
                if dump:
                    print_json(event)
    except Exception as exc:
        print_exception(exc)
        return

    elapsed = time.monotonic() - start
    print("\n--- summary ---")
    print(f"events={event_count} deltas={delta_count} delta_chars={delta_chars} elapsed={elapsed:.3f}s")
    if text_parts:
        print(f"text={''.join(text_parts)}")
    if delta_count > 1:
        print("diagnosis=streaming_deltas_observed")
    elif delta_count == 1:
        print("diagnosis=single_delta_observed")
    elif event_count:
        print("diagnosis=events_without_text_deltas")
    else:
        print("diagnosis=no_events_observed")


def print_exception(exc: Exception) -> None:
    print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
    status_code = getattr(exc, "status_code", None)
    if status_code is not None:
        print(f"status_code={status_code}", file=sys.stderr)
    response = getattr(exc, "response", None)
    if response is not None:
        request_id = getattr(response, "headers", {}).get("x-request-id")
        if request_id:
            print(f"x-request-id={request_id}", file=sys.stderr)
    body = getattr(exc, "body", None)
    if body:
        print("body=", file=sys.stderr)
        print(json.dumps(body, ensure_ascii=False, indent=2) if isinstance(body, dict) else body, file=sys.stderr)


def print_json(value: Any) -> None:
    if hasattr(value, "model_dump"):
        payload = value.model_dump(mode="json")
    elif hasattr(value, "dict"):
        payload = value.dict()
    else:
        payload = value
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def preview(text: str, limit: int = 80) -> str:
    clean = text.replace("\n", "\\n")
    return clean if len(clean) <= limit else clean[: limit - 3] + "..."


if __name__ == "__main__":
    raise SystemExit(main())
