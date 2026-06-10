from __future__ import annotations

import os
import time

import pytest

from backend.app.core.config import get_settings
from backend.app.services import llm


@pytest.mark.skipif(
    os.getenv("RUN_LIVE_LLM_TESTS") != "1",
    reason="set RUN_LIVE_LLM_TESTS=1 to call the real Responses API",
)
def test_responses_chat_with_tools_live_streams_text_deltas():
    settings = get_settings()
    if not settings.openai_api_key:
        pytest.skip("OPENAI_API_KEY is not configured")

    deltas: list[tuple[float, str]] = []
    reasoning_deltas: list[tuple[float, str]] = []
    events: list[tuple[float, str]] = []
    start = time.monotonic()

    def on_stream_event(event: dict) -> None:
        elapsed = time.monotonic() - start
        event_type = str(event.get("type") or "")
        events.append((elapsed, event_type))
        if event_type != "response.output_text.delta":
            print(f"{elapsed:8.3f}s event={event_type}", flush=True)

    def on_text_delta(delta: str) -> None:
        elapsed = time.monotonic() - start
        deltas.append((elapsed, delta))
        print(f"{elapsed:8.3f}s delta_len={len(delta)} delta={delta!r}", flush=True)

    def on_reasoning_delta(delta: str) -> None:
        elapsed = time.monotonic() - start
        reasoning_deltas.append((elapsed, delta))
        print(f"{elapsed:8.3f}s reasoning_len={len(delta)} reasoning={delta!r}", flush=True)

    result = llm.responses_chat_with_tools(
        [{"role": "user", "content": "请用 10 个短句解释为什么真正的流式输出应该逐步返回。"}],
        [],
        lambda name, arguments: {"ok": False, "error": "tools disabled in live streaming test"},
        on_text_delta=on_text_delta,
        on_reasoning_delta=on_reasoning_delta,
        on_stream_event=on_stream_event,
        context={"context_summary": "这是一个流式输出诊断测试。", "context_nodes": []},
    )

    print("--- live stream summary ---", flush=True)
    print(f"event_count={len(events)}", flush=True)
    if events:
        print(f"first_event_at={events[0][0]:.3f}s type={events[0][1]}", flush=True)
    print(f"reasoning_delta_count={len(reasoning_deltas)}", flush=True)
    if reasoning_deltas:
        print(f"first_reasoning_delta_at={reasoning_deltas[0][0]:.3f}s", flush=True)
    print(f"delta_count={len(deltas)}", flush=True)
    print(f"total_chars={sum(len(delta) for _, delta in deltas)}", flush=True)
    if len(deltas) >= 2:
        print(f"first_delta_at={deltas[0][0]:.3f}s", flush=True)
        print(f"last_delta_at={deltas[-1][0]:.3f}s", flush=True)

    assert result["text"]
    assert events
    assert len(deltas) >= 2
