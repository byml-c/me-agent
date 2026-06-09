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
