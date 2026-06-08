from __future__ import annotations

import sqlite3
from typing import Any

from backend.app.services import context_reader, graph_store, graph_writer, llm


def chat(
    db: sqlite3.Connection,
    message: str,
    session_id: str | None,
    anchor_node_ids: list[str] | None,
    workspace_id: str | None,
    allow_proposals: bool = True,
    context_budget: int = 12000,
) -> dict[str, Any]:
    anchors = context_reader.resolve_anchors(db, message, anchor_node_ids, workspace_id)
    session = graph_store.ensure_session(
        db,
        session_id=session_id,
        title=message[:48] or "新对话",
        anchor_ids=anchors,
        workspace_id=workspace_id,
    )
    context = context_reader.read_context(db, message, anchors, depth=2, limit=min(32, max(8, context_budget // 500)))
    graph_store.add_message(db, session["id"], "user", message, context["anchor_nodes"])

    episode = graph_store.create_node(
        db,
        title=f"Episode: {message[:36] or '对话'}",
        body=f"用户消息：{message}\n\n使用上下文：{context['context_summary']}",
        summary=message[:120],
        status="archived",
        actor="agent",
    )
    graph_store.append_event(db, "EpisodeCreated", "agent", {"node_id": episode["id"], "session_id": session["id"]})
    graph_store.append_event(
        db,
        "ContextAssembled",
        "agent",
        {"session_id": session["id"], "context_node_ids": [node["id"] for node in context["context_nodes"]]},
    )

    assistant_message = llm.complete_chat(message, context["context_summary"])
    graph_store.add_message(
        db,
        session["id"],
        "assistant",
        assistant_message,
        [node["id"] for node in context["context_nodes"]],
    )
    graph_store.append_event(db, "AgentResponseGenerated", "agent", {"session_id": session["id"]})

    proposals = graph_writer.propose_updates(db, message, assistant_message, context) if allow_proposals else []
    return {
        "session_id": session["id"],
        "assistant_message": assistant_message,
        "used_context": context,
        "episode_node": episode,
        "proposals": proposals,
        "auto_applied": [],
    }


def prepare_chat(
    db: sqlite3.Connection,
    message: str,
    session_id: str | None,
    anchor_node_ids: list[str] | None,
    workspace_id: str | None,
    context_budget: int = 12000,
) -> dict[str, Any]:
    anchors = context_reader.resolve_anchors(db, message, anchor_node_ids, workspace_id)
    session = graph_store.ensure_session(
        db,
        session_id=session_id,
        title=message[:48] or "新对话",
        anchor_ids=anchors,
        workspace_id=workspace_id,
    )
    context = context_reader.read_context(db, message, anchors, depth=2, limit=min(32, max(8, context_budget // 500)))
    graph_store.add_message(db, session["id"], "user", message, context["anchor_nodes"])

    episode = graph_store.create_node(
        db,
        title=f"Episode: {message[:36] or '对话'}",
        body=f"用户消息：{message}\n\n使用上下文：{context['context_summary']}",
        summary=message[:120],
        status="archived",
        actor="agent",
    )
    graph_store.append_event(db, "EpisodeCreated", "agent", {"node_id": episode["id"], "session_id": session["id"]})
    graph_store.append_event(
        db,
        "ContextAssembled",
        "agent",
        {"session_id": session["id"], "context_node_ids": [node["id"] for node in context["context_nodes"]]},
    )
    return {"session": session, "context": context, "episode": episode}


def finish_chat(
    db: sqlite3.Connection,
    session_id: str,
    assistant_message: str,
    context: dict[str, Any],
    user_message: str,
    allow_proposals: bool = True,
) -> dict[str, Any]:
    graph_store.add_message(
        db,
        session_id,
        "assistant",
        assistant_message,
        [node["id"] for node in context["context_nodes"]],
    )
    graph_store.append_event(db, "AgentResponseGenerated", "agent", {"session_id": session_id})
    proposals = graph_writer.propose_updates(db, user_message, assistant_message, context) if allow_proposals else []
    return {"proposals": proposals, "auto_applied": []}
