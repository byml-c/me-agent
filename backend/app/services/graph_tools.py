from __future__ import annotations

import sqlite3
from typing import Any

from backend.app.services import context_reader, file_library, graph_store, graph_writer


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "read_node",
        "description": "读取一个个人认知图节点的完整内容。",
        "parameters": {
            "type": "object",
            "properties": {"node_id": {"type": "string"}},
            "required": ["node_id"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "search_nodes",
        "description": "按关键词搜索个人认知图节点，用于找可编辑或可连接的节点。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 12},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "switch_node",
        "description": "将对话焦点切换到一个已有节点。该工具不修改图结构，只用于让 UI 聚焦到更相关的节点。",
        "parameters": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["node_id", "reason"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "search_library",
        "description": "搜索后端统一维护的知识库。知识库同时包含文本条目和文件条目。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "kind": {"type": "string", "enum": ["text", "file"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": 12},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "read_library_entry",
        "description": "读取知识库中的一个条目，返回标题、摘要、完整内容以及关联文件。",
        "parameters": {
            "type": "object",
            "properties": {"entry_id": {"type": "string"}},
            "required": ["entry_id"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "search_files",
        "description": "按文件名或简介搜索统一文件库，先定位可用文件，再决定是否读取。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 12},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "read_file",
        "description": "读取统一文件库中的文本文件内容与元数据。",
        "parameters": {
            "type": "object",
            "properties": {"file_id": {"type": "string"}},
            "required": ["file_id"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "create_node",
        "description": "把本轮对话中明确值得长期保存的信息沉淀为新节点。默认创建孤立节点；只有当新节点确实应直接连接到已有节点时，才填写 link_to_node_ids。若用户说“在/到/给 X 下/下面/里新建 Y 节点”，title 只写 Y，不要包含父节点名 X。",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "body": {"type": "string"},
                "summary": {"type": "string"},
                "is_workspace": {"type": "boolean"},
                "link_to_node_ids": {"type": "array", "items": {"type": "string"}},
                "reason": {"type": "string"},
            },
            "required": ["title", "body", "reason"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "update_node",
        "description": "直接修改已有节点的标题、正文、摘要或状态。正文里可以沉淀对用户的长短期记忆；图结构变化仍必须使用单独工具生成审核提案。",
        "parameters": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string"},
                "title": {"type": "string"},
                "body": {"type": "string"},
                "summary": {"type": "string"},
                "is_workspace": {"type": "boolean"},
                "status": {"type": "string", "enum": ["active", "dense", "archived"]},
                "reason": {"type": "string"},
            },
            "required": ["node_id", "reason"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "write_library_entry",
        "description": "直接写入冷存储知识库条目，用于保存不适合放进节点正文的结构化背景、事实、摘录或长期记忆。不会改变图结构。",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
                "description": {"type": "string"},
                "kind": {"type": "string", "enum": ["text"]},
                "reason": {"type": "string"},
            },
            "required": ["title", "content", "reason"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "create_edge",
        "description": "在两个已有节点之间建立或加强关系。该操作只会创建待审核提案，用户接受后才会写入。",
        "parameters": {
            "type": "object",
            "properties": {
                "node_a_id": {"type": "string"},
                "node_b_id": {"type": "string"},
                "weight": {"type": "number", "minimum": 0, "maximum": 1},
                "is_candidate": {"type": "boolean"},
                "reason": {"type": "string"},
            },
            "required": ["node_a_id", "node_b_id", "reason"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "promote_to_workspace",
        "description": "把一个节点升级为工作区节点。",
        "parameters": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["node_id", "reason"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "delete_node",
        "description": "删除/移除一个已有节点。该操作只会创建待审核提案，用户接受后才会归档节点。",
        "parameters": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["node_id", "reason"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "remove_edge",
        "description": "断开两个已有节点之间的关系。该操作只会创建待审核提案，用户接受后才会删除边。",
        "parameters": {
            "type": "object",
            "properties": {
                "node_a_id": {"type": "string"},
                "node_b_id": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["node_a_id", "node_b_id", "reason"],
            "additionalProperties": False,
        },
    },
]


def execute_tool(db: sqlite3.Connection, name: str, arguments: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    if name == "read_node":
        node = graph_store.get_node(db, str(arguments.get("node_id") or ""))
        return {"ok": bool(node), "node": node}
    if name == "search_nodes":
        query = str(arguments.get("query") or "")
        limit = int(arguments.get("limit") or 8)
        nodes = context_reader.search_nodes(db, query, limit=max(1, min(limit, 12)))
        return {"ok": True, "nodes": compact_nodes(nodes)}
    if name == "switch_node":
        return switch_node(db, arguments)
    if name == "search_library":
        query = str(arguments.get("query") or "")
        kind = str(arguments.get("kind") or "") or None
        limit = int(arguments.get("limit") or 8)
        entries = file_library.list_entries(db, query=query, kind=kind, limit=max(1, min(limit, 12)))
        return {
            "ok": True,
            "entries": [
                {
                    "id": item["id"],
                    "title": item["title"],
                    "kind": item["kind"],
                    "description": item.get("description"),
                    "summary": item.get("summary"),
                    "source_file_id": item.get("source_file_id"),
                }
                for item in entries
            ],
        }
    if name == "read_library_entry":
        item = file_library.get_entry(db, str(arguments.get("entry_id") or ""))
        file_item = file_library.get_file(db, item.get("source_file_id")) if item and item.get("source_file_id") else None
        return {"ok": bool(item), "entry": item, "file": file_item}
    if name == "search_files":
        query = str(arguments.get("query") or "")
        limit = int(arguments.get("limit") or 8)
        files = file_library.list_files(db, query=query, limit=max(1, min(limit, 12)))
        return {
            "ok": True,
            "files": [
                {
                    "id": item["id"],
                    "name": item["name"],
                    "description": item.get("description"),
                    "media_type": item.get("media_type"),
                    "source_path": item.get("source_path"),
                }
                for item in files
            ],
        }
    if name == "read_file":
        item = file_library.get_file(db, str(arguments.get("file_id") or ""))
        return {"ok": bool(item), "file": item}
    if name == "create_node":
        return create_node(db, arguments, context)
    if name == "update_node":
        return update_node(db, arguments)
    if name == "write_library_entry":
        return write_library_entry(db, arguments)
    if name == "create_edge":
        return create_edge(db, arguments)
    if name == "promote_to_workspace":
        return promote_to_workspace(db, arguments)
    if name == "delete_node":
        return delete_node(db, arguments)
    if name == "remove_edge":
        return remove_edge(db, arguments)
    return {"ok": False, "error": f"unknown tool: {name}"}


def create_node(db: sqlite3.Connection, arguments: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    target_ids = safe_node_ids(db, arguments.get("link_to_node_ids"))
    proposal = graph_store.create_proposal(
        db,
        operation="create_node",
        target_ids=target_ids,
        payload={
            "title": str(arguments.get("title") or "未命名节点")[:120],
            "body": str(arguments.get("body") or ""),
            "summary": arguments.get("summary"),
            "is_workspace": bool(arguments.get("is_workspace", False)),
        },
        reason=str(arguments.get("reason") or "模型建议沉淀为新节点。"),
        confidence=0.82,
        risk_level="medium",
    )
    return {"ok": True, "review_required": True, "proposal": proposal}


def switch_node(db: sqlite3.Connection, arguments: dict[str, Any]) -> dict[str, Any]:
    node_id = str(arguments.get("node_id") or "")
    node = graph_store.get_node(db, node_id)
    if not node:
        return {"ok": False, "error": "node not found"}
    return {
        "ok": True,
        "review_required": False,
        "node_id": node["id"],
        "node": compact_nodes([node])[0],
        "reason": str(arguments.get("reason") or "模型切换对话焦点。"),
    }


def update_node(db: sqlite3.Connection, arguments: dict[str, Any]) -> dict[str, Any]:
    node_id = str(arguments.get("node_id") or "")
    if not graph_store.get_node(db, node_id):
        return {"ok": False, "error": "node not found"}
    changes = {key: arguments.get(key) for key in ["title", "body", "summary", "is_workspace", "status"] if key in arguments}
    if "is_workspace" in changes or changes.get("status") == "archived":
        proposal = graph_store.create_proposal(
            db,
            operation="edit_node",
            target_ids=[node_id],
            payload={"node_id": node_id, **changes},
            reason=str(arguments.get("reason") or "模型建议修改节点。"),
            confidence=0.76,
            risk_level="high",
        )
        return {"ok": True, "review_required": True, "proposal": proposal}
    node = graph_store.update_node(db, node_id, changes, actor="agent")
    return {
        "ok": bool(node),
        "review_required": False,
        "node": node,
        "reason": str(arguments.get("reason") or "模型直接更新节点正文或摘要。"),
    }


def write_library_entry(db: sqlite3.Connection, arguments: dict[str, Any]) -> dict[str, Any]:
    entry = file_library.create_or_update_entry(
        db,
        title=str(arguments.get("title") or "未命名冷存储条目"),
        description=str(arguments.get("description") or arguments.get("reason") or "") or None,
        content=str(arguments.get("content") or ""),
        kind="text",
        actor="agent",
    )
    return {
        "ok": True,
        "review_required": False,
        "entry": {
            "id": entry["id"],
            "title": entry["title"],
            "description": entry.get("description"),
            "summary": entry.get("summary"),
            "kind": entry.get("kind"),
        },
        "reason": str(arguments.get("reason") or "模型写入冷存储知识库。"),
    }


def create_edge(db: sqlite3.Connection, arguments: dict[str, Any]) -> dict[str, Any]:
    node_a_id = str(arguments.get("node_a_id") or "")
    node_b_id = str(arguments.get("node_b_id") or "")
    if not graph_store.get_node(db, node_a_id) or not graph_store.get_node(db, node_b_id) or node_a_id == node_b_id:
        return {"ok": False, "error": "invalid edge endpoints"}
    proposal = graph_store.create_proposal(
        db,
        operation="create_edge",
        target_ids=[node_a_id, node_b_id],
        payload={
            "node_a_id": node_a_id,
            "node_b_id": node_b_id,
            "weight": float(arguments.get("weight", 0.45)),
            "is_candidate": bool(arguments.get("is_candidate", True)),
        },
        reason=str(arguments.get("reason") or "模型建议建立节点关系。"),
        confidence=0.72,
        risk_level="low",
    )
    return {"ok": True, "review_required": True, "proposal": proposal}


def promote_to_workspace(db: sqlite3.Connection, arguments: dict[str, Any]) -> dict[str, Any]:
    node_id = str(arguments.get("node_id") or "")
    if not graph_store.get_node(db, node_id):
        return {"ok": False, "error": "node not found"}
    proposal = graph_store.create_proposal(
        db,
        operation="promote_to_workspace",
        target_ids=[node_id],
        payload={"node_id": node_id},
        reason=str(arguments.get("reason") or "模型建议升级为工作区。"),
        confidence=0.72,
        risk_level="high",
    )
    return {"ok": True, "review_required": True, "proposal": proposal}


def delete_node(db: sqlite3.Connection, arguments: dict[str, Any]) -> dict[str, Any]:
    node_id = str(arguments.get("node_id") or "")
    if not graph_store.get_node(db, node_id):
        return {"ok": False, "error": "node not found"}
    proposal = graph_store.create_proposal(
        db,
        operation="delete_node",
        target_ids=[node_id],
        payload={"node_id": node_id},
        reason=str(arguments.get("reason") or "模型建议移除该节点。"),
        confidence=0.72,
        risk_level="high",
    )
    return {"ok": True, "review_required": True, "proposal": proposal}


def remove_edge(db: sqlite3.Connection, arguments: dict[str, Any]) -> dict[str, Any]:
    node_a_id = str(arguments.get("node_a_id") or "")
    node_b_id = str(arguments.get("node_b_id") or "")
    try:
        node_a_id, node_b_id = graph_store.normalize_edge_nodes(node_a_id, node_b_id)
    except ValueError:
        return {"ok": False, "error": "invalid edge endpoints"}
    edge = graph_store.get_edge_between(db, node_a_id, node_b_id)
    if not edge:
        return {"ok": False, "error": "edge not found"}
    proposal = graph_store.create_proposal(
        db,
        operation="remove_edge",
        target_ids=[node_a_id, node_b_id],
        payload={"edge_id": edge["id"], "node_a_id": node_a_id, "node_b_id": node_b_id},
        reason=str(arguments.get("reason") or "模型建议断开这两个节点的关系。"),
        confidence=0.74,
        risk_level="high",
    )
    return {"ok": True, "review_required": True, "proposal": proposal}


def safe_node_ids(db: sqlite3.Connection, value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [node_id for node_id in value if isinstance(node_id, str) and graph_store.get_node(db, node_id)]


def compact_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": node["id"],
            "title": node["title"],
            "summary": node.get("summary"),
            "is_workspace": node.get("is_workspace", False),
        }
        for node in nodes
    ]
