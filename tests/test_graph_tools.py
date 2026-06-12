from __future__ import annotations

from backend.app.db.session import get_db
from backend.app.services import graph_store, graph_tools


def test_ai_tools_directly_write_node_content_and_cold_storage(isolated_db):
    with get_db() as db:
        node = graph_store.create_node(db, "记忆节点", "old")

        result = graph_tools.execute_tool(
            db,
            "update_node",
            {"node_id": node["id"], "body": "长期记忆：喜欢命令行。", "summary": "命令行偏好", "reason": "记忆更新"},
            {},
        )
        entry_result = graph_tools.execute_tool(
            db,
            "write_library_entry",
            {"title": "冷存储事实", "content": "用户偏好本地文件系统。", "reason": "长期事实"},
            {},
        )

        updated = graph_store.get_node(db, node["id"])

    assert result["ok"] is True
    assert result["review_required"] is False
    assert updated["body"] == "长期记忆：喜欢命令行。"
    assert entry_result["ok"] is True
    assert entry_result["review_required"] is False
    assert entry_result["entry"]["title"] == "冷存储事实"


def test_ai_graph_structure_changes_still_create_proposals(isolated_db):
    with get_db() as db:
        first = graph_store.create_node(db, "A", "")
        second = graph_store.create_node(db, "B", "")
        result = graph_tools.execute_tool(
            db,
            "create_edge",
            {"node_a_id": first["id"], "node_b_id": second["id"], "reason": "相关"},
            {},
        )

    assert result["ok"] is True
    assert result["review_required"] is True
    assert result["proposal"]["operation"] == "create_edge"
