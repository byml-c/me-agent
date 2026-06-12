from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from backend.app import cli
from backend.app.db.session import get_db
from backend.app.services import graph_store


@pytest.fixture(autouse=True)
def clear_cli_server_env(monkeypatch):
    monkeypatch.delenv("ME_AGENT_API_URL", raising=False)
    monkeypatch.delenv("SERVER_URL", raising=False)


def run_cli(args, capsys):
    exit_code = cli.main(["--no-seed", *args])
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


def test_cli_agent_can_attach_database_and_search_nodes(isolated_db, capsys):
    node = run_cli(["nodes", "create", "--title", "研究节点", "--body", "视觉触觉"], capsys)

    updated = run_cli(
        [
            "nodes",
            "databases",
            "add",
            node["id"],
            "--name",
            "实验数据库",
            "--description",
            "包含 GelSight 采集数据",
            "--content",
            "GelSight tactile samples",
        ],
        capsys,
    )
    databases = updated["memory"]["attachments"]["databases"]
    results = run_cli(["nodes", "search", "GelSight", "--with-database", "GelSight"], capsys)

    assert databases[0]["name"] == "实验数据库"
    assert databases[0]["entry_id"].startswith("entry_")
    assert [item["id"] for item in results] == [node["id"]]


def test_cli_agent_can_add_update_and_list_node_scripts(isolated_db, capsys):
    node = run_cli(["nodes", "create", "--title", "脚本节点"], capsys)

    updated = run_cli(
        [
            "nodes",
            "scripts",
            "add",
            node["id"],
            "--name",
            "打开项目",
            "--description",
            "启动编辑器",
            "--code",
            "log({'ok': True})",
            "--trigger-on-enter",
        ],
        capsys,
    )
    script = updated["memory"]["attachments"]["scripts"][0]

    run_cli(
        [
            "nodes",
            "scripts",
            "update",
            node["id"],
            script["id"],
            "--description",
            "进入节点时启动编辑器",
            "--no-trigger-on-enter",
        ],
        capsys,
    )
    scripts = run_cli(["nodes", "scripts", "list", node["id"]], capsys)

    assert scripts[0]["description"] == "进入节点时启动编辑器"
    assert scripts[0]["trigger_on_enter"] is False


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

    exit_code = cli.main(["--api-url", "http://localhost:8000", "chat", "hello", "--anchor", "node_1"])
    result = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert captured["url"] == "http://localhost:8000/chat"
    assert captured["method"] == "POST"
    assert captured["payload"]["message"] == "hello"
    assert captured["payload"]["anchor_node_ids"] == ["node_1"]
    assert result["assistant_message"] == "ok"


def test_cli_reads_server_url_env_for_http_mode(monkeypatch, capsys):
    captured = {}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps([]).encode()

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setenv("SERVER_URL", "http://localhost:11001")
    monkeypatch.setattr(cli.urllib.request, "urlopen", fake_urlopen)

    exit_code = cli.main(["nodes", "list"])
    result = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert captured["url"] == "http://localhost:11001/nodes"
    assert result == []


def test_cli_file_can_run_by_absolute_path_from_other_cwd(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    cli_path = project_root / "backend" / "app" / "cli.py"
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("ME_AGENT_API_URL", None)
    env.pop("SERVER_URL", None)
    env["ME_AGENT_DB"] = str(tmp_path / "me_agent.sqlite3")

    result = subprocess.run(
        [sys.executable, str(cli_path), "--no-seed", "nodes", "list"],
        cwd=tmp_path,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == []
