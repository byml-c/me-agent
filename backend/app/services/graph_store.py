from __future__ import annotations

import sqlite3
from collections import deque
from typing import Any
from uuid import uuid4

from backend.app.db.session import dict_from_row, dumps, loads, utc_now


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def normalize_edge_nodes(a: str, b: str) -> tuple[str, str]:
    if a == b:
        raise ValueError("edge endpoints must be different")
    return a, b


def row_to_node(row: sqlite3.Row) -> dict[str, Any]:
    item = dict_from_row(row)
    item["memory"] = loads(item.get("memory"), {})
    item["is_workspace"] = bool(item["is_workspace"])
    return item


def row_to_edge(row: sqlite3.Row) -> dict[str, Any]:
    item = dict_from_row(row)
    item["is_candidate"] = bool(item["is_candidate"])
    return item


def row_to_event(row: sqlite3.Row) -> dict[str, Any]:
    item = dict_from_row(row)
    item["payload"] = loads(item.get("payload"), {})
    return item


def row_to_proposal(row: sqlite3.Row) -> dict[str, Any]:
    item = dict_from_row(row)
    item["target_ids"] = loads(item.get("target_ids"), [])
    item["payload"] = loads(item.get("payload"), {})
    return item


def row_to_session(row: sqlite3.Row) -> dict[str, Any]:
    item = dict_from_row(row)
    item["current_anchor_node_ids"] = loads(item.get("current_anchor_node_ids"), [])
    return item


def row_to_message(row: sqlite3.Row) -> dict[str, Any]:
    item = dict_from_row(row)
    item["context_node_ids"] = loads(item.get("context_node_ids"), [])
    item["token_usage"] = loads(item.get("token_usage"), None)
    item.setdefault("parent_message_id", None)
    item.setdefault("source_message_id", None)
    item.setdefault("variant_index", 0)
    item.setdefault("status", "active")
    item.setdefault("updated_at", item.get("created_at"))
    item.setdefault("provider_response_id", None)
    return item


def append_event(db: sqlite3.Connection, event_type: str, actor: str, payload: dict[str, Any]) -> dict[str, Any]:
    event = {
        "id": new_id("evt"),
        "type": event_type,
        "actor": actor,
        "payload": payload,
        "created_at": utc_now(),
    }
    db.execute(
        "INSERT INTO events (id,type,actor,payload,created_at) VALUES (?,?,?,?,?)",
        (event["id"], event["type"], actor, dumps(payload), event["created_at"]),
    )
    return event


def create_node(
    db: sqlite3.Connection,
    title: str,
    body: str = "",
    summary: str | None = None,
    is_workspace: bool = False,
    status: str = "active",
    actor: str = "user",
    node_id: str | None = None,
) -> dict[str, Any]:
    now = utc_now()
    node = {
        "id": node_id or new_id("node"),
        "title": title,
        "body": body,
        "summary": summary or summarize_text(body),
        "memory": {},
        "is_workspace": is_workspace,
        "status": status,
        "created_at": now,
        "updated_at": now,
        "last_accessed_at": None,
        "access_count": 0,
    }
    db.execute(
        """
        INSERT INTO nodes
        (id,title,body,summary,memory,is_workspace,status,created_at,updated_at,last_accessed_at,access_count)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            node["id"],
            title,
            body,
            node["summary"],
            dumps(node["memory"]),
            int(is_workspace),
            status,
            now,
            now,
            None,
            0,
        ),
    )
    append_event(db, "WorkspaceCreated" if is_workspace else "NodeCreated", actor, {"node_id": node["id"]})
    return node


def summarize_text(text: str, limit: int = 180) -> str | None:
    clean = " ".join(text.split())
    if not clean:
        return None
    return clean[:limit] + ("..." if len(clean) > limit else "")


def list_nodes(db: sqlite3.Connection, include_archived: bool = False) -> list[dict[str, Any]]:
    sql = "SELECT * FROM nodes"
    params: tuple[Any, ...] = ()
    if not include_archived:
        sql += " WHERE status != ? AND title NOT LIKE ?"
        params = ("archived", "Episode:%")
    sql += " ORDER BY COALESCE(last_accessed_at, updated_at) DESC, created_at DESC"
    return [row_to_node(row) for row in db.execute(sql, params).fetchall()]


def get_node(db: sqlite3.Connection, node_id: str) -> dict[str, Any] | None:
    row = db.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
    return row_to_node(row) if row else None


def update_node(db: sqlite3.Connection, node_id: str, changes: dict[str, Any], actor: str = "user") -> dict[str, Any] | None:
    allowed = {"title", "body", "summary", "memory", "is_workspace", "status"}
    values = {key: value for key, value in changes.items() if key in allowed and value is not None}
    if "body" in values and "summary" not in values:
        values["summary"] = summarize_text(values["body"])
    if not values:
        return get_node(db, node_id)
    values["updated_at"] = utc_now()
    assignments = ",".join(f"{key} = ?" for key in values)
    params = [serialize_node_update_value(key, value) for key, value in values.items()]
    params.append(node_id)
    db.execute(f"UPDATE nodes SET {assignments} WHERE id = ?", params)
    append_event(db, "NodeEdited", actor, {"node_id": node_id, "changes": list(values)})
    if values.get("status") == "archived":
        append_event(db, "NodeArchived", actor, {"node_id": node_id})
    if values.get("is_workspace") is True:
        append_event(db, "NodePromotedToWorkspace", actor, {"node_id": node_id})
    return get_node(db, node_id)


def serialize_node_update_value(key: str, value: Any) -> Any:
    if key == "is_workspace":
        return int(value)
    if key == "memory":
        return dumps(value)
    return value


def touch_nodes(db: sqlite3.Connection, node_ids: list[str]) -> None:
    now = utc_now()
    for node_id in set(node_ids):
        db.execute(
            "UPDATE nodes SET access_count = access_count + 1, last_accessed_at = ?, updated_at = ? WHERE id = ?",
            (now, now, node_id),
        )


def create_edge(
    db: sqlite3.Connection,
    node_a_id: str,
    node_b_id: str,
    weight: float = 1.0,
    is_candidate: bool = False,
    created_by: str = "user",
) -> dict[str, Any]:
    a, b = normalize_edge_nodes(node_a_id, node_b_id)
    now = utc_now()
    edge_id = new_id("edge")
    try:
        db.execute(
            """
            INSERT INTO edges
            (id,node_a_id,node_b_id,weight,access_count,coactivation_count,is_candidate,created_by,created_at,updated_at,last_accessed_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (edge_id, a, b, weight, 0, 0, int(is_candidate), created_by, now, now, None),
        )
        append_event(db, "EdgeCreated", created_by, {"edge_id": edge_id, "node_a_id": a, "node_b_id": b})
    except sqlite3.IntegrityError:
        db.execute(
            """
            UPDATE edges
            SET weight = MAX(weight, ?), is_candidate = MIN(is_candidate, ?), updated_at = ?
            WHERE node_a_id = ? AND node_b_id = ?
            """,
            (weight, int(is_candidate), now, a, b),
        )
    row = db.execute("SELECT * FROM edges WHERE node_a_id = ? AND node_b_id = ?", (a, b)).fetchone()
    return row_to_edge(row)


def list_edges(db: sqlite3.Connection) -> list[dict[str, Any]]:
    return [row_to_edge(row) for row in db.execute("SELECT * FROM edges ORDER BY updated_at DESC").fetchall()]


def get_edge(db: sqlite3.Connection, edge_id: str) -> dict[str, Any] | None:
    row = db.execute("SELECT * FROM edges WHERE id = ?", (edge_id,)).fetchone()
    return row_to_edge(row) if row else None


def get_edge_between(db: sqlite3.Connection, node_a_id: str, node_b_id: str) -> dict[str, Any] | None:
    a, b = normalize_edge_nodes(node_a_id, node_b_id)
    row = db.execute("SELECT * FROM edges WHERE node_a_id = ? AND node_b_id = ?", (a, b)).fetchone()
    return row_to_edge(row) if row else None


def get_edges_between_any_direction(db: sqlite3.Connection, node_a_id: str, node_b_id: str) -> list[dict[str, Any]]:
    return [
        row_to_edge(row)
        for row in db.execute(
            """
            SELECT *
            FROM edges
            WHERE (node_a_id = ? AND node_b_id = ?)
               OR (node_a_id = ? AND node_b_id = ?)
            ORDER BY updated_at DESC
            """,
            (node_a_id, node_b_id, node_b_id, node_a_id),
        ).fetchall()
    ]


def update_edge(db: sqlite3.Connection, edge_id: str, changes: dict[str, Any]) -> dict[str, Any] | None:
    edge = get_edge(db, edge_id)
    if not edge:
        return None
    allowed = {"node_a_id", "node_b_id", "weight", "is_candidate"}
    values = {key: value for key, value in changes.items() if key in allowed and value is not None}
    if not values:
        return edge
    next_a = values.get("node_a_id", edge["node_a_id"])
    next_b = values.get("node_b_id", edge["node_b_id"])
    if next_a == next_b:
        raise ValueError("edge endpoints must be different")
    if ("node_a_id" in values or "node_b_id" in values) and (not get_node(db, next_a) or not get_node(db, next_b)):
        raise ValueError("edge endpoint node not found")
    values["updated_at"] = utc_now()
    assignments = ",".join(f"{key} = ?" for key in values)
    params = [int(v) if key == "is_candidate" else v for key, v in values.items()]
    params.append(edge_id)
    try:
        db.execute(f"UPDATE edges SET {assignments} WHERE id = ?", params)
    except sqlite3.IntegrityError as exc:
        raise ValueError("edge with same direction already exists") from exc
    return get_edge(db, edge_id)


def delete_edge(db: sqlite3.Connection, edge_id: str, actor: str = "user") -> None:
    edge = get_edge(db, edge_id)
    db.execute("DELETE FROM edges WHERE id = ?", (edge_id,))
    append_event(db, "EdgeRemoved", actor, {"edge_id": edge_id, "edge": edge})


def archive_node(db: sqlite3.Connection, node_id: str, actor: str = "agent") -> dict[str, Any] | None:
    return update_node(db, node_id, {"status": "archived"}, actor=actor)


def archive_nodes(db: sqlite3.Connection, node_ids: list[str], actor: str = "user") -> list[dict[str, Any]]:
    archived = []
    for node_id in dict.fromkeys(node_ids):
        node = update_node(db, node_id, {"status": "archived"}, actor=actor)
        if node:
            archived.append(node)
    return archived


def insert_node_between(
    db: sqlite3.Connection,
    first_node_id: str,
    second_node_id: str,
    title: str = "中间节点",
    body: str = "",
    actor: str = "user",
) -> dict[str, Any]:
    if first_node_id == second_node_id:
        raise ValueError("two different nodes are required")
    if not get_node(db, first_node_id) or not get_node(db, second_node_id):
        raise ValueError("selected node not found")
    edges = [
        edge
        for edge in get_edges_between_any_direction(db, first_node_id, second_node_id)
        if not edge["is_candidate"]
    ]
    if len(edges) != 1:
        raise ValueError("selected nodes must have exactly one real edge between them")
    edge = edges[0]
    node = create_node(db, title=title, body=body, actor=actor)
    delete_edge(db, edge["id"], actor=actor)
    first = create_edge(db, edge["node_a_id"], node["id"], weight=edge["weight"], is_candidate=False, created_by=actor)
    second = create_edge(db, node["id"], edge["node_b_id"], weight=edge["weight"], is_candidate=False, created_by=actor)
    append_event(
        db,
        "NodeInsertedBetween",
        actor,
        {"node_id": node["id"], "source_edge": edge, "edge_ids": [first["id"], second["id"]]},
    )
    return {"node": node, "edges": [first, second], "removed_edge": edge}


def add_cutpoint_for_nodes(
    db: sqlite3.Connection,
    node_ids: list[str],
    title: str = "割点",
    body: str = "",
    actor: str = "user",
) -> dict[str, Any]:
    selected_ids = [node_id for node_id in dict.fromkeys(node_ids) if get_node(db, node_id)]
    if not selected_ids:
        raise ValueError("at least one existing node is required")
    selected = set(selected_ids)
    incoming_edges = [
        edge
        for edge in list_edges(db)
        if not edge["is_candidate"] and edge["node_b_id"] in selected and edge["node_a_id"] not in selected
    ]
    cutpoint = create_node(db, title=title, body=body, actor=actor)
    removed_edges = []
    created_edges: dict[tuple[str, str], dict[str, Any]] = {}
    for edge in incoming_edges:
        removed_edges.append(edge)
        delete_edge(db, edge["id"], actor=actor)
        for source_id, target_id in ((edge["node_a_id"], cutpoint["id"]), (cutpoint["id"], edge["node_b_id"])):
            created_edges[(source_id, target_id)] = create_edge(
                db,
                source_id,
                target_id,
                weight=edge["weight"],
                is_candidate=False,
                created_by=actor,
            )
    append_event(
        db,
        "CutpointAdded",
        actor,
        {
            "cutpoint_node_id": cutpoint["id"],
            "target_node_ids": selected_ids,
            "removed_edge_ids": [edge["id"] for edge in removed_edges],
            "created_edge_ids": [edge["id"] for edge in created_edges.values()],
        },
    )
    return {"node": cutpoint, "removed_edges": removed_edges, "edges": list(created_edges.values())}


def neighbors(db: sqlite3.Connection, node_id: str) -> list[dict[str, Any]]:
    edges = [
        row_to_edge(row)
        for row in db.execute(
            """
            SELECT *
            FROM edges
            WHERE node_a_id = ? OR node_b_id = ?
            ORDER BY weight DESC, updated_at DESC
            """,
            (node_id, node_id),
        ).fetchall()
    ]
    result = []
    for edge in edges:
        other_id = edge["node_b_id"] if edge["node_a_id"] == node_id else edge["node_a_id"]
        node = get_node(db, other_id)
        if node:
            result.append({"edge": edge, "node": node})
    return result


def ego_graph(db: sqlite3.Connection, anchor_id: str | None, depth: int = 2, limit: int = 50) -> dict[str, Any]:
    all_nodes = {
        node["id"]: node
        for node in list_nodes(db, include_archived=False)
        if not node["title"].startswith("Episode:")
    }
    all_edges = list_edges(db)
    if not all_nodes:
        return {"nodes": [], "edges": []}
    start = anchor_id if anchor_id in all_nodes else next(iter(all_nodes))
    adjacency: dict[str, list[str]] = {}
    for edge in all_edges:
        if edge["node_a_id"] not in all_nodes or edge["node_b_id"] not in all_nodes:
            continue
        adjacency.setdefault(edge["node_a_id"], []).append(edge["node_b_id"])
        adjacency.setdefault(edge["node_b_id"], []).append(edge["node_a_id"])
    distances = {start: 0}
    queue: deque[str] = deque([start])
    while queue and len(distances) < limit:
        current = queue.popleft()
        if distances[current] >= depth:
            continue
        for nxt in adjacency.get(current, []):
            if nxt in all_nodes and nxt not in distances and len(distances) < limit:
                distances[nxt] = distances[current] + 1
                queue.append(nxt)
    node_ids = set(distances)
    nodes = [{**all_nodes[node_id], "distance": distances[node_id]} for node_id in node_ids if node_id in all_nodes]
    edges = [edge for edge in all_edges if edge["node_a_id"] in node_ids and edge["node_b_id"] in node_ids]
    return {"nodes": nodes, "edges": edges}


def full_graph(db: sqlite3.Connection) -> dict[str, Any]:
    nodes = [
        {**node, "distance": 0}
        for node in list_nodes(db, include_archived=False)
        if not node["title"].startswith("Episode:")
    ]
    node_ids = {node["id"] for node in nodes}
    edges = [edge for edge in list_edges(db) if edge["node_a_id"] in node_ids and edge["node_b_id"] in node_ids]
    return {"nodes": nodes, "edges": edges}


def create_proposal(
    db: sqlite3.Connection,
    operation: str,
    target_ids: list[str],
    payload: dict[str, Any],
    reason: str,
    confidence: float = 0.7,
    risk_level: str = "medium",
) -> dict[str, Any]:
    now = utc_now()
    proposal = {
        "id": new_id("prop"),
        "operation": operation,
        "target_ids": target_ids,
        "payload": payload,
        "reason": reason,
        "confidence": confidence,
        "risk_level": risk_level,
        "status": "pending",
        "created_at": now,
        "resolved_at": None,
    }
    db.execute(
        """
        INSERT INTO proposals
        (id,operation,target_ids,payload,reason,confidence,risk_level,status,created_at,resolved_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        """,
        (
            proposal["id"],
            operation,
            dumps(target_ids),
            dumps(payload),
            reason,
            confidence,
            risk_level,
            "pending",
            now,
            None,
        ),
    )
    append_event(db, "ProposalCreated", "agent", {"proposal_id": proposal["id"], "operation": operation})
    return proposal


def list_proposals(db: sqlite3.Connection, status: str | None = None) -> list[dict[str, Any]]:
    if status:
        rows = db.execute("SELECT * FROM proposals WHERE status = ? ORDER BY created_at DESC", (status,)).fetchall()
    else:
        rows = db.execute("SELECT * FROM proposals ORDER BY created_at DESC").fetchall()
    return [row_to_proposal(row) for row in rows]


def get_proposal(db: sqlite3.Connection, proposal_id: str) -> dict[str, Any] | None:
    row = db.execute("SELECT * FROM proposals WHERE id = ?", (proposal_id,)).fetchone()
    return row_to_proposal(row) if row else None


def resolve_proposal(db: sqlite3.Connection, proposal_id: str, status: str) -> dict[str, Any] | None:
    proposal = get_proposal(db, proposal_id)
    if not proposal:
        return None
    db.execute(
        "UPDATE proposals SET status = ?, resolved_at = ? WHERE id = ?",
        (status, utc_now(), proposal_id),
    )
    append_event(db, "ProposalAccepted" if status == "accepted" else "ProposalRejected", "user", {"proposal_id": proposal_id})
    return get_proposal(db, proposal_id)


def list_events(db: sqlite3.Connection, limit: int = 100, node_id: str | None = None) -> list[dict[str, Any]]:
    if node_id:
        pattern = f"%{node_id}%"
        rows = db.execute(
            "SELECT * FROM events WHERE payload LIKE ? ORDER BY created_at DESC LIMIT ?",
            (pattern, limit),
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM events ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [row_to_event(row) for row in rows]


def ensure_session(
    db: sqlite3.Connection,
    session_id: str | None,
    title: str,
    anchor_ids: list[str],
    workspace_id: str | None,
) -> dict[str, Any]:
    now = utc_now()
    if session_id:
        row = db.execute("SELECT * FROM chat_sessions WHERE id = ?", (session_id,)).fetchone()
        if row:
            db.execute(
                """
                UPDATE chat_sessions
                SET current_anchor_node_ids = ?, current_workspace_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (dumps(anchor_ids), workspace_id, now, session_id),
            )
            return row_to_session(db.execute("SELECT * FROM chat_sessions WHERE id = ?", (session_id,)).fetchone())
    session = {
        "id": session_id or new_id("chat"),
        "title": title,
        "current_anchor_node_ids": anchor_ids,
        "current_workspace_id": workspace_id,
        "created_at": now,
        "updated_at": now,
    }
    db.execute(
        """
        INSERT INTO chat_sessions
        (id,title,current_anchor_node_ids,current_workspace_id,created_at,updated_at)
        VALUES (?,?,?,?,?,?)
        """,
        (session["id"], title, dumps(anchor_ids), workspace_id, now, now),
    )
    return session


def add_message(
    db: sqlite3.Connection,
    session_id: str,
    role: str,
    content: str,
    context_node_ids: list[str] | None = None,
    parent_message_id: str | None = None,
    source_message_id: str | None = None,
    variant_index: int = 0,
    provider_response_id: str | None = None,
    token_usage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = utc_now()
    message = {
        "id": new_id("msg"),
        "session_id": session_id,
        "role": role,
        "content": content,
        "context_node_ids": context_node_ids or [],
        "parent_message_id": parent_message_id,
        "source_message_id": source_message_id,
        "variant_index": variant_index,
        "provider_response_id": provider_response_id,
        "token_usage": token_usage,
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }
    db.execute(
        """
        INSERT INTO chat_messages
        (id,session_id,role,content,context_node_ids,parent_message_id,source_message_id,variant_index,status,created_at,updated_at,provider_response_id,token_usage)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            message["id"],
            session_id,
            role,
            content,
            dumps(message["context_node_ids"]),
            parent_message_id,
            source_message_id,
            variant_index,
            "active",
            now,
            now,
            provider_response_id,
            dumps(token_usage) if token_usage is not None else None,
        ),
    )
    db.execute("UPDATE chat_sessions SET updated_at = ? WHERE id = ?", (now, session_id))
    return message


def get_message(db: sqlite3.Connection, message_id: str) -> dict[str, Any] | None:
    row = db.execute("SELECT * FROM chat_messages WHERE id = ?", (message_id,)).fetchone()
    return row_to_message(row) if row else None


def update_message_content(db: sqlite3.Connection, message_id: str, content: str) -> dict[str, Any] | None:
    message = get_message(db, message_id)
    if not message:
        return None
    now = utc_now()
    db.execute(
        "UPDATE chat_messages SET content = ?, updated_at = ?, status = 'active' WHERE id = ?",
        (content, now, message_id),
    )
    db.execute("UPDATE chat_sessions SET updated_at = ? WHERE id = ?", (now, message["session_id"]))
    append_event(db, "ChatMessageEdited", "user", {"message_id": message_id, "session_id": message["session_id"]})
    return get_message(db, message_id)


def active_messages(db: sqlite3.Connection, session_id: str) -> list[dict[str, Any]]:
    rows = db.execute(
        "SELECT * FROM chat_messages WHERE session_id = ? AND status = 'active' ORDER BY created_at ASC",
        (session_id,),
    ).fetchall()
    return [row_to_message(row) for row in rows]


def active_message_before(db: sqlite3.Connection, session_id: str, message_id: str, role: str | None = None) -> dict[str, Any] | None:
    message = get_message(db, message_id)
    if not message:
        return None
    sql = """
        SELECT *
        FROM chat_messages
        WHERE session_id = ? AND status = 'active' AND created_at < ?
    """
    params: list[Any] = [session_id, message["created_at"]]
    if role:
        sql += " AND role = ?"
        params.append(role)
    sql += " ORDER BY created_at DESC LIMIT 1"
    row = db.execute(sql, params).fetchone()
    return row_to_message(row) if row else None


def archive_messages_after(db: sqlite3.Connection, session_id: str, message_id: str, include_self: bool = False) -> list[dict[str, Any]]:
    message = get_message(db, message_id)
    if not message:
        return []
    op = ">=" if include_self else ">"
    rows = db.execute(
        f"""
        SELECT *
        FROM chat_messages
        WHERE session_id = ? AND status = 'active' AND created_at {op} ?
        ORDER BY created_at ASC
        """,
        (session_id, message["created_at"]),
    ).fetchall()
    archived = [row_to_message(row) for row in rows]
    if archived:
        now = utc_now()
        db.execute(
            f"""
            UPDATE chat_messages
            SET status = 'superseded', updated_at = ?
            WHERE session_id = ? AND status = 'active' AND created_at {op} ?
            """,
            (now, session_id, message["created_at"]),
        )
        db.execute("UPDATE chat_sessions SET updated_at = ? WHERE id = ?", (now, session_id))
        append_event(
            db,
            "ChatBranchSuperseded",
            "user",
            {"session_id": session_id, "from_message_id": message_id, "include_self": include_self, "count": len(archived)},
        )
    return archived


def next_variant_index(db: sqlite3.Connection, source_message_id: str) -> int:
    row = db.execute(
        """
        SELECT COALESCE(MAX(variant_index), 0) AS max_variant
        FROM chat_messages
        WHERE source_message_id = ? OR id = ?
        """,
        (source_message_id, source_message_id),
    ).fetchone()
    return int(row["max_variant"] or 0) + 1


def get_session(db: sqlite3.Connection, session_id: str) -> dict[str, Any] | None:
    row = db.execute("SELECT * FROM chat_sessions WHERE id = ?", (session_id,)).fetchone()
    if not row:
        return None
    session = row_to_session(row)
    messages = db.execute(
        "SELECT * FROM chat_messages WHERE session_id = ? AND status = 'active' ORDER BY created_at ASC",
        (session_id,),
    ).fetchall()
    session["messages"] = [row_to_message(message) for message in messages]
    return session


def list_sessions(db: sqlite3.Connection, limit: int = 50) -> list[dict[str, Any]]:
    rows = db.execute(
        "SELECT * FROM chat_sessions ORDER BY updated_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    sessions = [row_to_session(row) for row in rows]
    for session in sessions:
        message = db.execute(
            """
            SELECT content
            FROM chat_messages
            WHERE session_id = ? AND role = 'user' AND status = 'active'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (session["id"],),
        ).fetchone()
        session["last_message"] = message["content"] if message else ""
    return sessions
