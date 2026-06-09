from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from typing import Any

from backend.app.services import context_reader, graph_store, graph_writer, graph_writer_agent, llm


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

    assistant_raw = llm.complete_chat(message, context["context_summary"])
    assistant_message, conversation_control = llm.parse_conversation_control(assistant_raw)
    graph_store.add_message(
        db,
        session["id"],
        "assistant",
        assistant_message,
        [node["id"] for node in context["context_nodes"]],
    )
    graph_store.append_event(db, "AgentResponseGenerated", "agent", {"session_id": session["id"]})

    graph_intent = llm.graph_writer_summary_intent(message, assistant_message, conversation_control) if allow_proposals else llm.no_graph_intent()
    generated_proposals = (
        graph_writer_agent.generate_proposals(db, message, assistant_message, context, graph_intent)
        if allow_proposals
        else []
    )
    proposals, auto_applied = split_review_and_auto_apply(db, generated_proposals)
    return {
        "session_id": session["id"],
        "assistant_message": assistant_message,
        "used_context": context,
        "episode_node": episode,
        "graph_intent": graph_intent,
        "proposals": proposals,
        "auto_applied": auto_applied,
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
    graph_intent = (
        record_assistant_and_graph_intent(db, session_id, assistant_message, context, user_message)
        if allow_proposals
        else llm.no_graph_intent()
    )
    if not allow_proposals:
        record_assistant_message(db, session_id, assistant_message, context)
    generated_proposals = generate_graph_proposals(db, user_message, assistant_message, context, graph_intent, allow_proposals)
    proposals, auto_applied = split_review_and_auto_apply(db, generated_proposals)
    return {"proposals": proposals, "auto_applied": auto_applied, "graph_intent": graph_intent}


def record_assistant_and_graph_intent(
    db: sqlite3.Connection,
    session_id: str,
    assistant_message: str,
    context: dict[str, Any],
    user_message: str,
) -> dict[str, Any]:
    assistant_message, conversation_control = llm.parse_conversation_control(assistant_message)
    record_assistant_message(db, session_id, assistant_message, context)
    return llm.graph_writer_summary_intent(user_message, assistant_message, conversation_control)


def record_assistant_message(
    db: sqlite3.Connection,
    session_id: str,
    assistant_message: str,
    context: dict[str, Any],
) -> None:
    graph_store.add_message(
        db,
        session_id,
        "assistant",
        assistant_message,
        [node["id"] for node in context["context_nodes"]],
    )
    graph_store.append_event(db, "AgentResponseGenerated", "agent", {"session_id": session_id})


def generate_graph_proposals(
    db: sqlite3.Connection,
    user_message: str,
    assistant_message: str,
    context: dict[str, Any],
    graph_intent: dict[str, Any],
    allow_proposals: bool = True,
) -> list[dict[str, Any]]:
    if not allow_proposals:
        return []
    return graph_writer_agent.generate_proposals(db, user_message, assistant_message, context, graph_intent)


def stream_graph_proposals(
    db: sqlite3.Connection,
    user_message: str,
    assistant_message: str,
    context: dict[str, Any],
    graph_intent: dict[str, Any],
    allow_proposals: bool = True,
) -> Iterator[dict[str, Any]]:
    if not allow_proposals:
        return
    yield from graph_writer_agent.stream_proposals(db, user_message, assistant_message, context, graph_intent)


def split_review_and_auto_apply(db: sqlite3.Connection, proposals: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    review: list[dict[str, Any]] = []
    auto_applied: list[dict[str, Any]] = []
    for proposal in proposals:
        if proposal_requires_review(proposal):
            review.append(proposal)
            continue
        applied = graph_writer.apply_proposal(db, proposal)
        resolved = graph_store.resolve_proposal(db, proposal["id"], "accepted")
        auto_applied.append({"proposal": resolved or proposal, "applied": applied})
    return review, auto_applied


def proposal_requires_review(proposal: dict[str, Any]) -> bool:
    return proposal.get("operation") in {"create_node", "split_node", "delete_node", "move_node"}
