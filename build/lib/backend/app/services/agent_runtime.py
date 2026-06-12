from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from typing import Any

from backend.app.services import context_reader, graph_store, graph_tools, graph_writer, graph_writer_agent, llm


def chat(
    db: sqlite3.Connection,
    message: str,
    session_id: str | None,
    anchor_node_ids: list[str] | None,
    workspace_id: str | None,
    allow_proposals: bool = True,
    context_budget: int = 12000,
) -> dict[str, Any]:
    prepared = prepare_chat(db, message, session_id, anchor_node_ids, workspace_id, context_budget)
    result = run_responses_agent(db, prepared["session"], prepared["context"], prepared["episode"], prepared["user_message"], allow_proposals=allow_proposals)
    return response_payload(prepared["session"], prepared["context"], prepared["episode"], result)


def prepare_chat(
    db: sqlite3.Connection,
    message: str,
    session_id: str | None,
    anchor_node_ids: list[str] | None,
    workspace_id: str | None,
    context_budget: int = 12000,
    parent_message_id: str | None = None,
    existing_user_message_id: str | None = None,
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
    if existing_user_message_id:
        user_message = graph_store.get_message(db, existing_user_message_id)
    else:
        user_message = graph_store.add_message(
            db,
            session["id"],
            "user",
            message,
            context["anchor_nodes"],
            parent_message_id=parent_message_id,
        )

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
    return {"session": session, "context": context, "episode": episode, "user_message": user_message}


def run_responses_agent(
    db: sqlite3.Connection,
    session: dict[str, Any],
    context: dict[str, Any],
    episode: dict[str, Any],
    user_message: dict[str, Any],
    allow_proposals: bool = True,
    variant_temperature: float = 0.4,
    source_message_id: str | None = None,
    variant_index: int = 0,
    on_tool_call=None,
    on_text_delta=None,
    on_reasoning_delta=None,
) -> dict[str, Any]:
    history = graph_store.active_messages(db, session["id"])
    previous_response_id = previous_assistant_response_id(history, user_message["id"])
    input_items = (
        current_turn_input(user_message)
        if previous_response_id
        else conversation_input(history, context, user_message["id"])
    )
    tool_events: list[dict[str, Any]] = []

    def execute(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if not allow_proposals:
            return {"ok": False, "error": "graph tools disabled"}
        result = graph_tools.execute_tool(db, name, arguments, context)
        tool_events.append({"name": name, "arguments": arguments, "result": result})
        return result

    output = llm.responses_chat_with_tools(
        input_items,
        graph_tools.TOOL_SCHEMAS if allow_proposals else [],
        execute,
        temperature=variant_temperature,
        on_tool_call=on_tool_call,
        on_text_delta=on_text_delta,
        on_reasoning_delta=on_reasoning_delta,
        previous_response_id=previous_response_id,
        context=context,
    )
    assistant_message = output["text"].strip()
    if should_force_create_node(user_message["content"]) and not proposals_from_tool_events(tool_events):
        previous_assistant = previous_assistant_content(history, user_message["id"])
        if previous_assistant:
            arguments = {
                "title": infer_node_title(previous_assistant),
                "body": previous_assistant,
                "summary": summarize_for_node(previous_assistant),
                "reason": "用户明确要求将当前讨论保存为节点。",
            }
            result = graph_tools.create_node(db, arguments, context)
            tool_events.append({"name": "create_node", "arguments": arguments, "result": result})
            if on_tool_call:
                on_tool_call({"name": "create_node", "arguments": arguments, "call_id": None})
    assistant = graph_store.add_message(
        db,
        session["id"],
        "assistant",
        assistant_message,
        [node["id"] for node in context["context_nodes"]],
        parent_message_id=user_message["id"],
        source_message_id=source_message_id,
        variant_index=variant_index,
        provider_response_id=output.get("response_id"),
    )
    graph_store.append_event(db, "AgentResponseGenerated", "agent", {"session_id": session["id"], "message_id": assistant["id"]})
    if output.get("fallback"):
        graph_intent = (
            llm.graph_writer_summary_intent(user_message["content"], assistant_message, output.get("fallback_control"))
            if allow_proposals
            else llm.no_graph_intent()
        )
        generated_proposals = generate_graph_proposals(
            db,
            user_message["content"],
            assistant_message,
            context,
            graph_intent,
            allow_proposals,
        )
        generated_proposals.extend(proposals_from_tool_events(tool_events))
        proposals, auto_applied = split_review_and_auto_apply(db, generated_proposals)
    else:
        graph_intent, proposals, auto_applied = summarize_tool_events(tool_events)
    return {
        "assistant_message": assistant_message,
        "user_message_record": user_message,
        "assistant_message_record": assistant,
        "graph_intent": graph_intent,
        "proposals": proposals,
        "auto_applied": auto_applied,
        "tool_events": tool_events,
    }


def conversation_input(history: list[dict[str, Any]], context: dict[str, Any], current_user_message_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "局部图上下文：\n"
                f"{context.get('context_summary') or '暂无'}\n\n"
                "可用上下文节点：\n"
                f"{compact_context_nodes(context)}"
            ),
        }
    ]
    for message in history[-18:]:
        if message["role"] not in {"user", "assistant"}:
            continue
        items.append({"role": message["role"], "content": message["content"]})
        if message["id"] == current_user_message_id:
            break
    return items


def current_turn_input(user_message: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"role": "user", "content": user_message["content"]}]


def previous_assistant_response_id(history: list[dict[str, Any]], current_user_message_id: str) -> str | None:
    previous_response_id: str | None = None
    for message in history:
        if message["id"] == current_user_message_id:
            break
        if message["role"] == "assistant" and message.get("provider_response_id"):
            previous_response_id = message["provider_response_id"]
    return previous_response_id


def compact_context_nodes(context: dict[str, Any]) -> str:
    nodes = [
        {
            "id": node["id"],
            "title": node["title"],
            "summary": node.get("summary"),
            "include_level": node.get("include_level"),
            "activation_score": node.get("activation_score"),
        }
        for node in context.get("context_nodes", [])
    ]
    import json

    return json.dumps(nodes, ensure_ascii=False)


def summarize_tool_events(tool_events: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    proposals: list[dict[str, Any]] = []
    auto_applied: list[dict[str, Any]] = []
    operations: list[str] = []
    for event in tool_events:
        operations.append(event["name"])
        result = event["result"]
        proposal = result.get("proposal") if isinstance(result, dict) else None
        if proposal:
            proposals.append(proposal)
        elif isinstance(result, dict) and result.get("ok") and result.get("review_required") is False:
            auto_applied.append({"tool": event["name"], "applied": result})
    graph_intent = {
        "should_edit": bool(tool_events),
        "direction": "Conversation Agent 通过工具更新个人认知图。" if tool_events else "本轮未调用图工具。",
        "operations": operations,
        "suggested_anchor_node_id": None,
        "suggested_anchor_reason": "",
        "source": "responses_tools",
    }
    return graph_intent, proposals, auto_applied


def proposals_from_tool_events(tool_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    for event in tool_events:
        result = event.get("result")
        proposal = result.get("proposal") if isinstance(result, dict) else None
        if proposal:
            proposals.append(proposal)
    return proposals


def should_force_create_node(content: str) -> bool:
    text = content.strip().lower()
    return any(
        phrase in text
        for phrase in ["保存节点", "创建成节点", "创建节点", "存成节点", "记成节点", "记录下来", "保存一下", "save node"]
    )


def previous_assistant_content(history: list[dict[str, Any]], current_user_message_id: str) -> str:
    previous = ""
    for message in history:
        if message["id"] == current_user_message_id:
            break
        if message["role"] == "assistant" and message.get("content"):
            previous = message["content"]
    return previous


def infer_node_title(content: str) -> str:
    for raw_line in content.splitlines():
        line = raw_line.strip().strip("#*> -")
        if line:
            return line[:42]
    return "对话沉淀"


def summarize_for_node(content: str, limit: int = 180) -> str:
    clean = " ".join(content.split())
    return clean[:limit] + ("..." if len(clean) > limit else "")


def response_payload(session: dict[str, Any], context: dict[str, Any], episode: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_id": session["id"],
        "assistant_message": result["assistant_message"],
        "used_context": context,
        "episode_node": episode,
        "graph_intent": result["graph_intent"],
        "proposals": result["proposals"],
        "auto_applied": result["auto_applied"],
    }


def regenerate_assistant(
    db: sqlite3.Connection,
    assistant_message_id: str,
    variant_temperature: float = 0.75,
    context_budget: int = 12000,
    on_tool_call=None,
    on_text_delta=None,
    on_reasoning_delta=None,
) -> dict[str, Any] | None:
    assistant = graph_store.get_message(db, assistant_message_id)
    if not assistant or assistant["role"] != "assistant":
        return None
    user_message = graph_store.active_message_before(db, assistant["session_id"], assistant_message_id, role="user")
    if not user_message:
        return None
    graph_store.archive_messages_after(db, assistant["session_id"], assistant_message_id, include_self=True)
    session = graph_store.get_session(db, assistant["session_id"])
    anchors = user_message.get("context_node_ids") or session.get("current_anchor_node_ids", [])
    context = context_reader.read_context(db, user_message["content"], anchors, depth=2, limit=min(32, max(8, context_budget // 500)))
    episode = create_episode(db, session["id"], user_message["content"], context)
    variant_index = graph_store.next_variant_index(db, assistant.get("source_message_id") or assistant["id"])
    result = run_responses_agent(
        db,
        session,
        context,
        episode,
        user_message,
        allow_proposals=True,
        variant_temperature=variant_temperature,
        source_message_id=assistant.get("source_message_id") or assistant["id"],
        variant_index=variant_index,
        on_tool_call=on_tool_call,
        on_text_delta=on_text_delta,
        on_reasoning_delta=on_reasoning_delta,
    )
    return response_payload(session, context, episode, result)


def edit_user_message_and_regenerate(
    db: sqlite3.Connection,
    message_id: str,
    content: str,
    context_budget: int = 12000,
    on_tool_call=None,
    on_text_delta=None,
    on_reasoning_delta=None,
) -> dict[str, Any] | None:
    user_message = graph_store.update_message_content(db, message_id, content)
    if not user_message or user_message["role"] != "user":
        return None
    graph_store.archive_messages_after(db, user_message["session_id"], message_id, include_self=False)
    session = graph_store.get_session(db, user_message["session_id"])
    anchors = user_message.get("context_node_ids") or session.get("current_anchor_node_ids", [])
    context = context_reader.read_context(db, content, anchors, depth=2, limit=min(32, max(8, context_budget // 500)))
    episode = create_episode(db, session["id"], content, context)
    result = run_responses_agent(
        db,
        session,
        context,
        episode,
        user_message,
        allow_proposals=True,
        on_tool_call=on_tool_call,
        on_text_delta=on_text_delta,
        on_reasoning_delta=on_reasoning_delta,
    )
    return response_payload(session, context, episode, result)


def create_episode(db: sqlite3.Connection, session_id: str, message: str, context: dict[str, Any]) -> dict[str, Any]:
    episode = graph_store.create_node(
        db,
        title=f"Episode: {message[:36] or '对话'}",
        body=f"用户消息：{message}\n\n使用上下文：{context['context_summary']}",
        summary=message[:120],
        status="archived",
        actor="agent",
    )
    graph_store.append_event(db, "EpisodeCreated", "agent", {"node_id": episode["id"], "session_id": session_id})
    return episode


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
    return proposal.get("operation") in {"create_node", "edit_node", "split_node", "delete_node", "remove_edge", "move_node"}
