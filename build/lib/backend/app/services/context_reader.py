from __future__ import annotations

import math
import sqlite3
from typing import Any

from backend.app.services import graph_store


def lexical_relevance(query: str, text: str) -> float:
    query_terms = {term for term in query.lower().split() if len(term) > 1}
    if not query_terms:
        return 0.0
    haystack = text.lower()
    hits = sum(1 for term in query_terms if term in haystack)
    return min(1.0, hits / max(1, len(query_terms)))


def resolve_anchors(
    db: sqlite3.Connection,
    message: str,
    explicit_anchor_ids: list[str] | None,
    workspace_id: str | None,
) -> list[str]:
    anchors = [node_id for node_id in (explicit_anchor_ids or []) if graph_store.get_node(db, node_id)]
    if workspace_id and graph_store.get_node(db, workspace_id) and workspace_id not in anchors:
        anchors.append(workspace_id)
    if anchors:
        return anchors

    nodes = graph_store.list_nodes(db)
    if nodes:
        scored = sorted(
            nodes,
            key=lambda node: (
                lexical_relevance(message, f"{node['title']} {node.get('body') or ''}"),
                node["access_count"],
                node["updated_at"],
            ),
            reverse=True,
        )
        if lexical_relevance(message, f"{scored[0]['title']} {scored[0].get('body') or ''}") > 0:
            return [scored[0]["id"]]

    title = message.strip().splitlines()[0][:40] or "临时对话"
    node = graph_store.create_node(
        db,
        title=f"对话主题：{title}",
        body=f"由对话自动创建的锚点。\n\n首条消息：{message}",
        summary=title,
        actor="agent",
    )
    return [node["id"]]


def read_context(
    db: sqlite3.Connection,
    message: str,
    anchor_ids: list[str],
    depth: int = 2,
    limit: int = 24,
) -> dict[str, Any]:
    candidates: dict[str, dict[str, Any]] = {}
    for anchor_id in anchor_ids:
        graph = graph_store.ego_graph(db, anchor_id, depth=depth, limit=limit)
        for node in graph["nodes"]:
            existing = candidates.get(node["id"])
            if existing is None or node["distance"] < existing["distance"]:
                candidates[node["id"]] = node

    scored = []
    for node in candidates.values():
        distance = node.get("distance", 0)
        text = f"{node['title']} {node.get('summary') or ''} {node.get('body') or ''}"
        score = (
            0.45 * lexical_relevance(message, text)
            + 0.25 * math.exp(-0.8 * distance)
            + 0.12 * min(1.0, node["access_count"] / 10)
            + 0.12 * (1.0 if node["is_workspace"] else 0.0)
            - 0.25 * (1.0 if node["status"] == "archived" else 0.0)
        )
        include_level = 0 if node["id"] in anchor_ids else min(3, distance)
        scored.append(
            {
                **node,
                "activation_score": round(score, 4),
                "include_level": include_level,
                "reason": "当前锚点" if include_level == 0 else f"距离锚点 {distance} 跳",
            }
        )
    scored.sort(key=lambda node: (node["include_level"], -node["activation_score"]))
    context_node_ids = [node["id"] for node in scored[:limit]]
    graph_store.touch_nodes(db, context_node_ids)
    strengthen_coactivated_edges(db, context_node_ids)
    return {
        "anchor_nodes": anchor_ids,
        "context_nodes": scored[:limit],
        "context_edges": [
            edge
            for edge in graph_store.list_edges(db)
            if edge["node_a_id"] in context_node_ids and edge["node_b_id"] in context_node_ids
        ],
        "context_summary": assemble_summary(scored[:limit]),
    }


def search_nodes(db: sqlite3.Connection, query: str, limit: int = 8) -> list[dict[str, Any]]:
    nodes = graph_store.list_nodes(db)
    scored = [
        (
            lexical_relevance(query, f"{node['title']} {node.get('summary') or ''} {node.get('body') or ''}"),
            node,
        )
        for node in nodes
    ]
    scored.sort(key=lambda item: (item[0], item[1]["access_count"], item[1]["updated_at"]), reverse=True)
    return [node for score, node in scored if score > 0][:limit]


def strengthen_coactivated_edges(db: sqlite3.Connection, node_ids: list[str]) -> None:
    node_set = set(node_ids)
    now = graph_store.utc_now() if hasattr(graph_store, "utc_now") else None
    for edge in graph_store.list_edges(db):
        if edge["node_a_id"] in node_set and edge["node_b_id"] in node_set:
            db.execute(
                """
                UPDATE edges
                SET coactivation_count = coactivation_count + 1,
                    access_count = access_count + 1,
                    weight = MIN(weight + 0.08, 10),
                    last_accessed_at = COALESCE(?, last_accessed_at),
                    updated_at = COALESCE(?, updated_at)
                WHERE id = ?
                """,
                (now, now, edge["id"]),
            )


def assemble_summary(nodes: list[dict[str, Any]]) -> str:
    lines = []
    for node in nodes:
        if node["include_level"] == 0:
            body = node.get("body") or node.get("summary") or ""
            lines.append(f"[锚点] {node['title']}: {body[:900]}")
        elif node["include_level"] == 1:
            lines.append(f"[一跳] {node['title']}: {(node.get('summary') or node.get('body') or '')[:260]}")
        elif node["include_level"] == 2:
            lines.append(f"[二跳] {node['title']}: {(node.get('summary') or '')[:140]}")
        else:
            lines.append(f"[候选] {node['title']}")
    return "\n".join(lines)
