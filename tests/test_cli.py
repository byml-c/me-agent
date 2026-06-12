from __future__ import annotations

import json

from backend.app import cli
from backend.app.db.session import get_db
from backend.app.services import graph_store


def run_cli(args, capsys):
    exit_code = cli.main(["--json", "--no-seed", *args])
    captured = capsys.readouterr()
    assert exit_code == 0
    return json.loads(captured.out)


def test_cli_can_create_list_and_show_nodes(isolated_db, capsys):
    created = run_cli(["nodes", "create", "--title", "CLI 节点", "--body", "body"], capsys)
    listed = run_cli(["nodes", "list"], capsys)
    shown = run_cli(["nodes", "show", created["id"]], capsys)

    assert created["title"] == "CLI 节点"
    assert any(node["id"] == created["id"] for node in listed)
    assert shown["body"] == "body"


def test_cli_chat_uses_backend_runtime(isolated_db, deterministic_llm, capsys):
    result = run_cli(["chat", "记录", "一个", "todo", "--no-proposals"], capsys)

    assert result["assistant_message"].startswith("测试回复：记录 一个 todo")
    with get_db() as db:
        session = graph_store.get_session(db, result["session_id"])
    assert session is not None
    assert [message["role"] for message in session["messages"]] == ["user", "assistant"]


def test_cli_accepts_create_node_proposal(isolated_db, capsys):
    with get_db() as db:
        proposal = graph_store.create_proposal(
            db,
            operation="create_node",
            target_ids=[],
            payload={"title": "提案节点", "body": "from proposal"},
            reason="test",
        )

    result = run_cli(["proposals", "accept", proposal["id"]], capsys)

    assert result["proposal"]["status"] == "accepted"
    assert result["applied"]["node"]["title"] == "提案节点"


def test_cli_create_node_proposal_links_parent_to_child(isolated_db, capsys):
    with get_db() as db:
        parent = graph_store.create_node(db, title="父节点", body="parent")
        proposal = graph_store.create_proposal(
            db,
            operation="create_node",
            target_ids=[parent["id"]],
            payload={"title": "子节点", "body": "child"},
            reason="test",
        )

    result = run_cli(["proposals", "accept", proposal["id"]], capsys)
    child_id = result["applied"]["node"]["id"]

    with get_db() as db:
        edge = graph_store.get_edge_between(db, parent["id"], child_id)
        reverse_edge = graph_store.get_edge_between(db, child_id, parent["id"])

    assert edge is not None
    assert reverse_edge is None


def test_cli_http_chat_posts_to_backend(monkeypatch, capsys):
    captured = {}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"session_id": "sess_1", "assistant_message": "ok", "proposals": []}).encode()

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["payload"] = json.loads(request.data.decode())
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(cli.urllib.request, "urlopen", fake_urlopen)

    exit_code = cli.main(["--json", "--api-url", "http://localhost:8000", "chat", "hello", "--anchor", "node_1"])
    result = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert captured["url"] == "http://localhost:8000/chat"
    assert captured["method"] == "POST"
    assert captured["payload"]["message"] == "hello"
    assert captured["payload"]["anchor_node_ids"] == ["node_1"]
    assert result["assistant_message"] == "ok"
