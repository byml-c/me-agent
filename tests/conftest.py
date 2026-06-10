from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.db.session import init_db
from backend.app.main import app, seed_if_empty
from backend.app.services import graph_writer_agent, llm


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "me_agent_test.sqlite3"
    monkeypatch.setenv("ME_AGENT_DB", str(db_path))
    init_db()
    seed_if_empty()
    return db_path


@pytest.fixture
def deterministic_llm(monkeypatch):
    def complete_chat(user_message: str, context_summary: str) -> str:
        should_create = "记录" in user_message or "todo" in user_message.lower()
        return (
            f"测试回复：{user_message} | 上下文长度={len(context_summary)}"
            f'<ME_AGENT_CONTROL>{{"should_create_nodes":{str(should_create).lower()},"reason":"测试控制"}}</ME_AGENT_CONTROL>'
        )

    def stream_chat(user_message: str, context_summary: str):
        yield "测试"
        yield "流式"
        yield user_message

    def graph_edit_intent(user_message: str, context_summary: str, assistant_message: str):
        return llm.fallback_graph_intent(user_message)

    def responses_chat_with_tools(
        input_items,
        tools,
        execute_tool,
        temperature=0.4,
        max_tool_rounds=4,
        on_tool_call=None,
        on_text_delta=None,
        on_reasoning_delta=None,
        on_stream_event=None,
        previous_response_id=None,
        context=None,
    ):
        user_message = next((item.get("content", "") for item in reversed(input_items) if item.get("role") == "user"), "")
        text = f"测试回复：{user_message}"
        if on_reasoning_delta:
            on_reasoning_delta("测试思考")
        for chunk in ["测试", "流式", user_message]:
            if on_text_delta:
                on_text_delta(chunk)
        return {
            "text": text if not on_text_delta else "测试流式" + user_message,
            "tool_results": [],
            "response": {"id": "resp_test"},
            "response_id": "resp_test",
        }

    def call_graph_writer_model(*args, **kwargs):
        raise ValueError("network disabled in tests")

    monkeypatch.setattr(llm, "complete_chat", complete_chat)
    monkeypatch.setattr(llm, "stream_chat", stream_chat)
    monkeypatch.setattr(llm, "graph_edit_intent", graph_edit_intent)
    monkeypatch.setattr(llm, "responses_chat_with_tools", responses_chat_with_tools)
    monkeypatch.setattr(graph_writer_agent, "call_graph_writer_model", call_graph_writer_model)


@pytest.fixture
def client(isolated_db, deterministic_llm):
    with TestClient(app) as test_client:
        yield test_client
