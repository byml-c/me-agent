from __future__ import annotations

from backend.app.db.session import get_db
from backend.app.services import agent_runtime, graph_store


def test_agent_runtime_chat_persists_episode_messages_and_proposals(isolated_db, deterministic_llm):
    with get_db() as db:
        anchor = graph_store.create_node(db, title="CLI 开发", body="后端 CLI 与 API 兼容")

    with get_db() as db:
        result = agent_runtime.chat(
            db,
            message="记录一个 todo：给 CLI 加测试",
            session_id=None,
            anchor_node_ids=[anchor["id"]],
            workspace_id=None,
            allow_proposals=True,
            context_budget=12000,
        )

    with get_db() as db:
        session = graph_store.get_session(db, result["session_id"])
        proposals = graph_store.list_proposals(db, status="pending")
        events = graph_store.list_events(db)

    assert session is not None
    assert [message["role"] for message in session["messages"]] == ["user", "assistant"]
    assert result["episode_node"]["title"].startswith("Episode:")
    assert any(proposal["operation"] == "create_node" for proposal in proposals)
    assert {"EpisodeCreated", "ContextAssembled", "AgentResponseGenerated"} <= {event["type"] for event in events}


def test_prepare_and_finish_chat_match_streaming_lifecycle(isolated_db, deterministic_llm):
    with get_db() as db:
        prepared = agent_runtime.prepare_chat(
            db,
            message="准备流式对话",
            session_id=None,
            anchor_node_ids=[],
            workspace_id=None,
            context_budget=4000,
        )
        finished = agent_runtime.finish_chat(
            db,
            prepared["session"]["id"],
            "流式回复",
            prepared["context"],
            "准备流式对话",
            allow_proposals=False,
        )

    with get_db() as db:
        session = graph_store.get_session(db, prepared["session"]["id"])

    assert finished["proposals"] == []
    assert finished["auto_applied"] == []
    assert finished["graph_intent"]["should_edit"] is False
    assert session is not None
    assert [message["role"] for message in session["messages"]] == ["user", "assistant"]
