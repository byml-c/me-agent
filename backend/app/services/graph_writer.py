from __future__ import annotations

import sqlite3
from typing import Any

from backend.app.services import graph_store


def propose_updates(
    db: sqlite3.Connection,
    user_message: str,
    assistant_message: str,
    context: dict[str, Any],
) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    anchors = context.get("anchor_nodes", [])
    context_nodes = context.get("context_nodes", [])
    message = user_message.lower()

    if any(keyword in message for keyword in ["新建", "创建", "记录", "整理", "想法", "todo", "任务"]):
        title = infer_title(user_message)
        proposals.append(
            graph_store.create_proposal(
                db,
                operation="create_node",
                target_ids=anchors,
                payload={
                    "title": title,
                    "body": f"由对话整理生成。\n\n用户：{user_message}\n\nAgent：{assistant_message[:800]}",
                },
                reason="用户消息包含可沉淀为节点的内容。",
                confidence=0.72,
                risk_level="medium",
            )
        )

    if len(context_nodes) >= 2:
        a = context_nodes[0]["id"]
        b = context_nodes[1]["id"]
        if a != b:
            proposals.append(
                graph_store.create_proposal(
                    db,
                    operation="create_edge",
                    target_ids=[a, b],
                    payload={"node_a_id": a, "node_b_id": b, "weight": 0.35, "is_candidate": True},
                    reason="本轮上下文中两个节点共同被激活，先作为候选关系等待确认。",
                    confidence=0.62,
                    risk_level="low",
                )
            )

    anchor_node = graph_store.get_node(db, anchors[0]) if anchors else None
    dense_signal = bool(anchor_node and len((anchor_node.get("body") or "")) > 1200)
    if "拆分" in message or dense_signal:
        target_id = anchors[0] if anchors else None
        proposals.append(
            graph_store.create_proposal(
                db,
                operation="split_node",
                target_ids=[target_id] if target_id else [],
                payload={
                    "proposed_nodes": [
                        {"title": f"{anchor_node['title'] if anchor_node else '主题'}：机制", "body": "围绕机制、规则和结构的子主题。"},
                        {"title": f"{anchor_node['title'] if anchor_node else '主题'}：行动项", "body": "围绕任务、下一步和开放问题的子主题。"},
                    ]
                },
                reason="当前节点或对话呈现多个可独立演化的主题。",
                confidence=0.66,
                risk_level="high",
            )
        )

    if any(keyword in message for keyword in ["工作区", "项目", "长期"]):
        target = anchors[0] if anchors else None
        proposals.append(
            graph_store.create_proposal(
                db,
                operation="promote_to_workspace",
                target_ids=[target] if target else [],
                payload={"node_id": target},
                reason="该主题具备长期组织上下文的特征，适合升级为工作区。",
                confidence=0.68,
                risk_level="high",
            )
        )

    return proposals


def apply_auto_updates(db: sqlite3.Connection, proposals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    auto_operations = {"create_node", "create_edge"}
    applied: list[dict[str, Any]] = []
    for proposal in proposals:
        if proposal["operation"] in auto_operations and proposal["risk_level"] in {"low", "medium"}:
            result = apply_proposal(db, proposal)
            resolved = graph_store.resolve_proposal(db, proposal["id"], "accepted")
            if resolved:
                proposal.update(resolved)
            applied.append({"proposal": resolved or proposal, "result": result})
    return applied


def infer_title(text: str) -> str:
    first_line = " ".join(text.strip().split())
    return first_line[:42] or "未命名节点"


def apply_proposal(db: sqlite3.Connection, proposal: dict[str, Any]) -> dict[str, Any]:
    payload = proposal["payload"]
    operation = proposal["operation"]
    if operation == "create_node":
        node = graph_store.create_node(
            db,
            title=payload.get("title") or "未命名节点",
            body=payload.get("body") or "",
            is_workspace=bool(payload.get("is_workspace", False)),
            actor="agent",
        )
        for target_id in proposal["target_ids"]:
            if target_id:
                graph_store.create_edge(db, node["id"], target_id, weight=0.5, is_candidate=False, created_by="agent")
        return {"node": node}
    if operation == "create_edge":
        edge = graph_store.create_edge(
            db,
            payload["node_a_id"],
            payload["node_b_id"],
            weight=float(payload.get("weight", 0.5)),
            is_candidate=bool(payload.get("is_candidate", True)),
            created_by="agent",
        )
        return {"edge": edge}
    if operation == "promote_to_workspace" and payload.get("node_id"):
        node = graph_store.update_node(db, payload["node_id"], {"is_workspace": True}, actor="agent")
        return {"node": node}
    if operation == "split_node":
        created = [
            graph_store.create_node(db, item.get("title") or "拆分节点", item.get("body") or "", actor="agent")
            for item in payload.get("proposed_nodes", [])
        ]
        for node in created:
            for target_id in proposal["target_ids"]:
                if target_id:
                    graph_store.create_edge(db, node["id"], target_id, weight=0.4, is_candidate=False, created_by="agent")
        return {"nodes": created}
    return {"ignored": True, "operation": operation}
