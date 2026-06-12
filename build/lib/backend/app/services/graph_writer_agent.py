from __future__ import annotations

import json
import sqlite3
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import Any

from backend.app.core.config import get_settings
from backend.app.services import graph_store, graph_writer
from backend.app.services.llm import parse_json_object


GRAPH_WRITER_SYSTEM_PROMPT = """你是 Me.Agent 的 Graph Writer Agent。
你负责阅读用户消息、Conversation Agent 的完整回复和局部图上下文，总结其中值得沉淀到个人认知图的内容。
不要回答用户问题，不要执行操作，只输出 JSON。
如果本轮没有值得沉淀或编辑的内容，输出 {"proposals": []}。

允许的 operation:
- create_node
- edit_node
- create_edge
- split_node
- promote_to_workspace

创建节点标题规则:
- 如果用户说“在/到/给 X 下/下面/里新建 Y 节点”，X 是父节点或挂载位置，不要写进新节点标题。
- create_node 的 payload.title 只写新节点自身名称。例如“在 Tactile 下面新建一个文献整理节点”应输出 title="文献整理"，target_ids 指向 Tactile 对应节点。
- 不要为了表达层级关系把父节点名拼成 “X Y” 或 “X：Y”；层级关系由 target_ids 和边表达。

输出 JSON schema:
{
  "proposals": [
    {
      "operation": "create_node",
      "target_ids": ["node_id"],
      "payload": {"title": "节点标题", "body": "节点正文", "is_workspace": false},
      "reason": "为什么建议这样编辑",
      "confidence": 0.0,
      "risk_level": "low" | "medium" | "high"
    }
  ]
}
"""

GRAPH_WRITER_STREAM_SYSTEM_PROMPT = """你是 Me.Agent 的 Graph Writer Agent。
你负责阅读用户消息、Conversation Agent 的完整回复和局部图上下文，总结其中值得沉淀到个人认知图的内容。
不要回答用户问题，不要执行操作。
如果本轮没有值得沉淀或编辑的内容，不输出任何 JSON。

你必须以流式 NDJSON 输出：每一行都是一个完整、有效、独立的 JSON object。
不要输出 Markdown，不要输出数组，不要输出外层 {"proposals": ...}。

每个 JSON object schema:
{
  "operation": "create_node" | "edit_node" | "create_edge" | "split_node" | "promote_to_workspace",
  "target_ids": ["node_id"],
  "payload": {"title": "节点标题", "body": "节点正文", "is_workspace": false},
  "reason": "为什么建议这样编辑",
  "confidence": 0.0,
  "risk_level": "low" | "medium" | "high"
}

创建节点标题规则:
- 如果用户说“在/到/给 X 下/下面/里新建 Y 节点”，X 是父节点或挂载位置，不要写进新节点标题。
- create_node 的 payload.title 只写新节点自身名称。例如“在 Tactile 下面新建一个文献整理节点”应输出 title="文献整理"，target_ids 指向 Tactile 对应节点。
- 不要为了表达层级关系把父节点名拼成 “X Y” 或 “X：Y”；层级关系由 target_ids 和边表达。
"""


def generate_proposals(
    db: sqlite3.Connection,
    user_message: str,
    assistant_message: str,
    context: dict[str, Any],
    graph_intent: dict[str, Any],
) -> list[dict[str, Any]]:
    if graph_intent.get("should_edit") is False:
        return []

    settings = get_settings()
    if settings.openai_api_key:
        try:
            raw = call_graph_writer_model(settings, user_message, assistant_message, context, graph_intent)
            specs = normalize_proposal_specs(raw.get("proposals", []), context)
            if specs:
                return [create_proposal_from_spec(db, spec) for spec in specs]
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError, ValueError):
            pass

    return graph_writer.propose_updates(db, user_message, assistant_message, context)


def stream_proposals(
    db: sqlite3.Connection,
    user_message: str,
    assistant_message: str,
    context: dict[str, Any],
    graph_intent: dict[str, Any],
) -> Iterator[dict[str, Any]]:
    if graph_intent.get("should_edit") is False:
        return

    settings = get_settings()
    emitted = False
    if settings.openai_api_key:
        try:
            for raw_spec in call_graph_writer_model_stream(settings, user_message, assistant_message, context, graph_intent):
                for spec in normalize_proposal_specs([raw_spec], context):
                    if not validate_proposal_spec(db, spec):
                        continue
                    emitted = True
                    yield create_proposal_from_spec(db, spec)
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError, ValueError):
            pass

    if emitted:
        return

    for proposal in graph_writer.propose_updates(db, user_message, assistant_message, context):
        if validate_proposal_spec(db, proposal):
            yield proposal


def call_graph_writer_model(settings, user_message: str, assistant_message: str, context: dict[str, Any], graph_intent: dict[str, Any]) -> dict:
    payload = graph_writer_payload(
        settings,
        GRAPH_WRITER_SYSTEM_PROMPT,
        user_message,
        assistant_message,
        context,
        graph_intent,
        stream=False,
    )
    request = urllib.request.Request(
        f"{settings.openai_base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        data = json.loads(response.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"].strip()
        return parse_json_object(content)


def call_graph_writer_model_stream(settings, user_message: str, assistant_message: str, context: dict[str, Any], graph_intent: dict[str, Any]) -> Iterator[dict[str, Any]]:
    payload = graph_writer_payload(
        settings,
        GRAPH_WRITER_STREAM_SYSTEM_PROMPT,
        user_message,
        assistant_message,
        context,
        graph_intent,
        stream=True,
    )
    request = urllib.request.Request(
        f"{settings.openai_base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    buffer = ""
    with urllib.request.urlopen(request, timeout=90) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8").strip()
            if not line or not line.startswith("data:"):
                continue
            data = line.removeprefix("data:").strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue
            delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content")
            if not delta:
                continue
            buffer += delta
            objects, buffer = pop_json_objects(buffer)
            for item in objects:
                if "proposals" in item and isinstance(item["proposals"], list):
                    yield from (proposal for proposal in item["proposals"] if isinstance(proposal, dict))
                else:
                    yield item
    objects, _ = pop_json_objects(buffer, flush=True)
    for item in objects:
        if "proposals" in item and isinstance(item["proposals"], list):
            yield from (proposal for proposal in item["proposals"] if isinstance(proposal, dict))
        else:
            yield item


def graph_writer_payload(
    settings,
    system_prompt: str,
    user_message: str,
    assistant_message: str,
    context: dict[str, Any],
    graph_intent: dict[str, Any],
    stream: bool,
) -> dict[str, Any]:
    compact_nodes = [
        {
            "id": node["id"],
            "title": node["title"],
            "summary": node.get("summary"),
            "include_level": node.get("include_level"),
            "activation_score": node.get("activation_score"),
        }
        for node in context.get("context_nodes", [])
    ]
    payload = {
        "model": settings.openai_base_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "user_message": user_message,
                        "assistant_message": assistant_message,
                        "graph_intent": graph_intent,
                        "anchor_nodes": context.get("anchor_nodes", []),
                        "context_nodes": compact_nodes,
                        "context_summary": context.get("context_summary", ""),
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "temperature": 0.1,
    }
    if stream:
        payload["stream"] = True
    return payload


def normalize_proposal_specs(specs: list[dict[str, Any]], context: dict[str, Any]) -> list[dict[str, Any]]:
    allowed = {"create_node", "edit_node", "create_edge", "split_node", "promote_to_workspace"}
    anchors = context.get("anchor_nodes", [])
    normalized: list[dict[str, Any]] = []
    for spec in specs:
        operation = spec.get("operation")
        if operation not in allowed:
            continue
        target_ids = spec.get("target_ids") or anchors
        payload = spec.get("payload") or {}
        if operation == "create_node" and not payload.get("title"):
            continue
        normalized.append(
            {
                "operation": operation,
                "target_ids": [target_id for target_id in target_ids if isinstance(target_id, str)],
                "payload": payload,
                "reason": str(spec.get("reason") or "Graph Writer Agent 建议更新图结构。"),
                "confidence": float(spec.get("confidence", 0.7)),
                "risk_level": spec.get("risk_level") if spec.get("risk_level") in {"low", "medium", "high"} else "medium",
            }
        )
    return normalized


def create_proposal_from_spec(db: sqlite3.Connection, spec: dict[str, Any]) -> dict[str, Any]:
    return graph_store.create_proposal(
        db,
        operation=spec["operation"],
        target_ids=spec["target_ids"],
        payload=spec["payload"],
        reason=spec["reason"],
        confidence=spec["confidence"],
        risk_level=spec["risk_level"],
    )


def validate_proposal_spec(db: sqlite3.Connection, spec: dict[str, Any]) -> bool:
    operation = spec.get("operation")
    target_ids = [target_id for target_id in spec.get("target_ids", []) if isinstance(target_id, str)]
    payload = spec.get("payload") or {}
    if operation == "create_node":
        if not payload.get("title"):
            return False
        return all(graph_store.get_node(db, target_id) for target_id in target_ids)
    if operation == "create_edge":
        node_a_id = payload.get("node_a_id") or (target_ids[0] if target_ids else None)
        node_b_id = payload.get("node_b_id") or (target_ids[1] if len(target_ids) > 1 else None)
        return bool(
            node_a_id
            and node_b_id
            and node_a_id != node_b_id
            and graph_store.get_node(db, node_a_id)
            and graph_store.get_node(db, node_b_id)
        )
    if operation == "promote_to_workspace":
        node_id = payload.get("node_id") or (target_ids[0] if target_ids else None)
        return bool(node_id and graph_store.get_node(db, node_id))
    if operation == "split_node":
        proposed_nodes = payload.get("proposed_nodes", [])
        return bool(proposed_nodes and all(graph_store.get_node(db, target_id) for target_id in target_ids))
    if operation == "edit_node":
        node_id = payload.get("node_id") or (target_ids[0] if target_ids else None)
        return bool(node_id and graph_store.get_node(db, node_id))
    return False


def pop_json_objects(buffer: str, flush: bool = False) -> tuple[list[dict[str, Any]], str]:
    objects: list[dict[str, Any]] = []
    start: int | None = None
    depth = 0
    in_string = False
    escaped = False
    index = 0
    while index < len(buffer):
        char = buffer[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and start is not None:
                candidate = buffer[start : index + 1]
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    objects.append(parsed)
                buffer = buffer[index + 1 :]
                index = -1
                start = None
        index += 1
    if flush and buffer.strip():
        parsed = parse_json_object(buffer)
        if isinstance(parsed, dict):
            objects.append(parsed)
        return objects, ""
    return objects, buffer[start:] if start is not None else ""
