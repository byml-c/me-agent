from __future__ import annotations


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
    assert payload["status"] == "completed"
    assert payload["stdout"].strip() == "hello node"


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
