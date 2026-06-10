from __future__ import annotations

from types import SimpleNamespace

from backend.app.services import llm


def test_stream_chat_yields_openai_sdk_stream_chunks(monkeypatch):
    calls = []

    class FakeCompletions:
        def create(self, **kwargs):
            calls.append(kwargs)
            return iter(
                [
                    SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="第一段"))]),
                    SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="第二段"))]),
                    SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=None))]),
                    SimpleNamespace(choices=[]),
                ]
            )

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    monkeypatch.setattr(
        llm,
        "get_settings",
        lambda: SimpleNamespace(
            openai_api_key="test-key",
            openai_base_model="test-model",
            openai_base_url="https://example.test/v1",
        ),
    )
    monkeypatch.setattr(llm, "openai_client", lambda timeout=90: fake_client)

    chunks = list(llm.stream_chat("你好", "上下文摘要"))

    assert chunks == ["第一段", "第二段"]
    assert calls == [
        {
            "model": "test-model",
            "messages": [
                {"role": "system", "content": llm.SYSTEM_PROMPT},
                {"role": "user", "content": "局部图上下文：\n上下文摘要\n\n用户消息：你好"},
            ],
            "temperature": 0.4,
            "stream": True,
        }
    ]


def test_responses_chat_with_tools_forwards_streaming_text_deltas(monkeypatch):
    calls = []

    class FakeResponses:
        def create(self, **kwargs):
            calls.append(kwargs)
            assert kwargs.pop("stream") is True
            return iter(
                [
                    {"type": "response.reasoning_summary_text.delta", "delta": "先判断"},
                    {"type": "response.output_text.delta", "delta": "第一段"},
                    {"type": "response.output_text.delta", "delta": "第二段"},
                    {
                        "type": "response.completed",
                        "response": {
                            "id": "resp_test",
                            "output": [
                                {
                                    "type": "message",
                                    "content": [{"type": "output_text", "text": "第一段第二段"}],
                                }
                            ],
                        },
                    },
                ]
            )

    fake_client = SimpleNamespace(responses=FakeResponses())
    monkeypatch.setattr(
        llm,
        "get_settings",
        lambda: SimpleNamespace(
            openai_api_key="test-key",
            openai_base_model="test-model",
            openai_base_url="https://example.test/v1",
        ),
    )
    monkeypatch.setattr(llm, "openai_client", lambda timeout=90: fake_client)

    deltas = []
    reasoning_deltas = []
    result = llm.responses_chat_with_tools(
        [{"role": "user", "content": "测试 Responses 流式"}],
        [],
        lambda name, arguments: {"ok": False},
        on_text_delta=deltas.append,
        on_reasoning_delta=reasoning_deltas.append,
        context={"context_summary": "测试上下文", "context_nodes": []},
    )

    assert deltas == ["第一段", "第二段"]
    assert reasoning_deltas == ["先判断"]
    assert result["text"] == "第一段第二段"
    assert result["response_id"] == "resp_test"
    assert calls == [
        {
            "model": "test-model",
            "instructions": llm.response_instructions({"context_summary": "测试上下文", "context_nodes": []}),
            "input": [{"role": "user", "content": "测试 Responses 流式"}],
            "tools": [],
            "store": True,
            "reasoning": {"effort": "minimal"},
        }
    ]
