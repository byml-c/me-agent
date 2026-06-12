from __future__ import annotations

import json
import time
from pathlib import Path

from backend.app.services import llm


def test_default_seed_nodes_are_user_facing_workspaces(client):
    nodes = client.get("/nodes").json()
    titles = {node["title"] for node in nodes}

    assert {
        "Me.Agent",
        "Me.Agent - 工作",
        "Me.Agent - 生活",
        "Me.Agent - Me.Agent 设计",
    } <= titles
    assert all(node["is_workspace"] for node in nodes if node["title"].startswith("Me.Agent - "))
    assert next(node for node in nodes if node["title"] == "Me.Agent")["is_workspace"] is True


def test_chat_api_creates_session_and_keeps_response_shape(client):
    response = client.post(
        "/chat",
        json={
            "message": "记录一个 todo：完善 CLI",
            "options": {"allow_proposals": False, "context_budget": 4000},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "session_id",
        "assistant_message",
        "used_context",
        "episode_node",
        "graph_intent",
        "proposals",
        "auto_applied",
    }
    assert payload["assistant_message"].startswith("测试回复：记录一个 todo")
    assert payload["proposals"] == []

    session_response = client.get(f"/chat/sessions/{payload['session_id']}")
    assert session_response.status_code == 200
    messages = session_response.json()["messages"]
    assert [message["role"] for message in messages] == ["user", "assistant"]


def test_session_message_endpoint_reuses_path_session_id(client):
    first = client.post("/chat", json={"message": "第一轮", "options": {"allow_proposals": False}})
    session_id = first.json()["session_id"]

    second = client.post(
        f"/chat/sessions/{session_id}/messages",
        json={"message": "第二轮", "session_id": "ignored", "options": {"allow_proposals": False}},
    )

    assert second.status_code == 200
    assert second.json()["session_id"] == session_id
    session = client.get(f"/chat/sessions/{session_id}").json()
    assert [message["content"] for message in session["messages"] if message["role"] == "user"] == ["第一轮", "第二轮"]


def test_node_edge_and_workspace_routes_keep_existing_contract(client):
    node_a = client.post("/nodes", json={"title": "A", "body": "alpha"}).json()
    node_b = client.post("/nodes", json={"title": "B", "body": "beta"}).json()
    edge = client.post(
        "/edges",
        json={"node_a_id": node_a["id"], "node_b_id": node_b["id"], "weight": 0.8},
    )

    assert edge.status_code == 200
    edge_payload = edge.json()
    assert edge_payload["weight"] == 0.8
    assert edge_payload["is_candidate"] is False

    workspace = client.post("/workspaces", json={"title": "工作区", "body": "workspace"}).json()
    workspace_detail = client.get(f"/workspaces/{workspace['id']}")
    assert workspace_detail.status_code == 200
    assert set(workspace_detail.json()) == {"workspace", "graph", "recent_events", "related_nodes"}


def test_directed_edges_preserve_order_and_allow_reverse(client):
    node_a = client.post("/nodes", json={"title": "Directed A"}).json()
    node_b = client.post("/nodes", json={"title": "Directed B"}).json()

    forward = client.post("/edges", json={"node_a_id": node_a["id"], "node_b_id": node_b["id"], "weight": 0.8}).json()
    reverse = client.post("/edges", json={"node_a_id": node_b["id"], "node_b_id": node_a["id"], "weight": 0.4}).json()

    assert forward["node_a_id"] == node_a["id"]
    assert forward["node_b_id"] == node_b["id"]
    assert reverse["node_a_id"] == node_b["id"]
    assert reverse["node_b_id"] == node_a["id"]
    assert forward["id"] != reverse["id"]

    extra = client.post("/nodes", json={"title": "Directed C"}).json()
    turned = client.patch(f"/edges/{forward['id']}", json={"node_a_id": node_b["id"], "node_b_id": extra["id"]})
    assert turned.status_code == 200
    assert turned.json()["node_a_id"] == node_b["id"]
    assert turned.json()["node_b_id"] == extra["id"]


def test_batch_graph_actions_ignore_candidate_edges(client):
    parent = client.post("/nodes", json={"title": "Parent"}).json()
    child = client.post("/nodes", json={"title": "Child"}).json()
    reference = client.post("/nodes", json={"title": "Reference"}).json()
    real_edge = client.post("/edges", json={"node_a_id": parent["id"], "node_b_id": child["id"], "weight": 0.9}).json()
    candidate_edge = client.post(
        "/edges",
        json={"node_a_id": reference["id"], "node_b_id": child["id"], "weight": 0.35, "is_candidate": True},
    ).json()

    inserted = client.post("/nodes/graph-actions/insert-between", json={"node_ids": [parent["id"], child["id"]], "title": "Middle"})
    assert inserted.status_code == 200
    middle = inserted.json()["node"]
    graph = client.get("/nodes/graph").json()
    edges = graph["edges"]
    assert not any(edge["id"] == real_edge["id"] for edge in edges)
    assert any(edge["node_a_id"] == parent["id"] and edge["node_b_id"] == middle["id"] and not edge["is_candidate"] for edge in edges)
    assert any(edge["node_a_id"] == middle["id"] and edge["node_b_id"] == child["id"] and not edge["is_candidate"] for edge in edges)
    assert any(edge["id"] == candidate_edge["id"] and edge["is_candidate"] for edge in edges)

    cut = client.post("/nodes/graph-actions/add-cutpoint", json={"node_ids": [child["id"]], "title": "Cut"})
    assert cut.status_code == 200
    cutpoint = cut.json()["node"]
    graph = client.get("/nodes/graph").json()
    edges = graph["edges"]
    assert any(edge["node_a_id"] == middle["id"] and edge["node_b_id"] == cutpoint["id"] and not edge["is_candidate"] for edge in edges)
    assert any(edge["node_a_id"] == cutpoint["id"] and edge["node_b_id"] == child["id"] and not edge["is_candidate"] for edge in edges)
    assert any(edge["id"] == candidate_edge["id"] and edge["node_a_id"] == reference["id"] and edge["node_b_id"] == child["id"] and edge["is_candidate"] for edge in edges)


def test_node_attachments_are_stored_and_scripts_run(client):
    node = client.post("/nodes", json={"title": "附带资源", "body": "node"}).json()
    updated = client.patch(
        f"/nodes/{node['id']}",
        json={
            "memory": {
                "attachments": {
                    "databases": [{"id": "db_1", "name": "local", "path": "/tmp/example.sqlite"}],
                    "files": [{"id": "file_1", "name": "notes", "path": "/tmp/notes.md"}],
                    "scripts": [{"id": "script_1", "name": "hello", "language": "python", "code": "print('hello node')"}],
                }
            }
        },
    ).json()

    assert updated["memory"]["attachments"]["databases"][0]["name"] == "local"
    run = client.post(f"/nodes/{node['id']}/scripts/script_1/run", json={"args": {"x": 1}})

    assert run.status_code == 200
    payload = run.json()
    assert payload["status"] == "started"
    assert payload["log_path"]
    assert Path(payload["script_path"]).name == f"{node['id']}-script_1.py"
    log_payload = wait_for_script_log(Path(payload["log_path"]))
    assert log_payload["status"] == "completed"
    assert log_payload["stdout"].strip() == "hello node"
    assert log_payload["code"] == "print('hello node')"


def wait_for_script_log(path: Path) -> dict:
    deadline = time.time() + 3
    while time.time() < deadline:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        time.sleep(0.05)
    raise AssertionError(f"script log was not written: {path}")


def test_stream_chat_emits_meta_delta_and_done(client):
    with client.stream(
        "POST",
        "/chat/stream",
        json={"message": "流式测试", "options": {"allow_proposals": False}},
    ) as response:
        assert response.status_code == 200
        body = response.read().decode("utf-8")

    assert "event: meta" in body
    assert "event: delta" in body
    assert "event: done" in body
    assert "测试流式流式测试" in body


def test_stream_chat_emits_provider_error_event(client, monkeypatch):
    def responses_chat_with_tools(*args, **kwargs):
        raise RuntimeError("Error code: 400 - DataInspectionFailed: Input text data may contain inappropriate content.")

    monkeypatch.setattr(llm, "responses_chat_with_tools", responses_chat_with_tools)

    with client.stream(
        "POST",
        "/chat/stream",
        json={"message": "触发供应商错误", "options": {"allow_proposals": True}},
    ) as response:
        assert response.status_code == 200
        body = response.read().decode("utf-8")

    assert "event: meta" in body
    assert "event: error" in body
    assert "DataInspectionFailed" in body
    assert "inappropriate content" in body
    assert "event: done" not in body


def test_edit_message_stream_emits_delta_and_done(client):
    first = client.post("/chat", json={"message": "原始消息", "options": {"allow_proposals": False}})
    session_id = first.json()["session_id"]
    session = client.get(f"/chat/sessions/{session_id}").json()
    user_message_id = next(message["id"] for message in session["messages"] if message["role"] == "user")

    with client.stream(
        "POST",
        f"/chat/messages/{user_message_id}/edit/stream",
        json={"content": "编辑后的消息", "context_budget": 4000},
    ) as response:
        assert response.status_code == 200
        body = response.read().decode("utf-8")

    assert "event: delta" in body
    assert "event: done" in body
    assert "测试流式编辑后的消息" in body
