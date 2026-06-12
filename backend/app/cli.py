from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Sequence
from typing import Any

from backend.app.db.session import get_db, init_db
from backend.app.main import seed_if_empty
from backend.app.services import agent_runtime, graph_store, graph_writer


CommandHandler = Callable[[argparse.Namespace], Any]


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.api_url:
        init_db()
        if not args.no_seed:
            seed_if_empty()
    result = args.handler(args)
    if result is not None:
        emit(result, as_json=args.json)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="me-agent", description="Me.Agent backend CLI")
    parser.add_argument("--json", action="store_true", help="output machine-readable JSON")
    parser.add_argument("--no-seed", action="store_true", help="do not seed the database before running")
    parser.add_argument("--api-url", help="connect to a running Me.Agent HTTP backend instead of local SQLite")
    subparsers = parser.add_subparsers(dest="command", required=True)

    chat_parser = subparsers.add_parser("chat", help="send one message or start an interactive chat")
    chat_parser.add_argument("message", nargs="*", help="message text; omit to enter interactive mode")
    add_chat_options(chat_parser)
    chat_parser.set_defaults(handler=handle_chat)

    session_parser = subparsers.add_parser("sessions", help="manage chat sessions")
    session_sub = session_parser.add_subparsers(dest="action", required=True)
    session_list = session_sub.add_parser("list", help="list chat sessions")
    session_list.add_argument("--limit", type=int, default=50)
    session_list.set_defaults(handler=handle_sessions_list)
    session_show = session_sub.add_parser("show", help="show one chat session")
    session_show.add_argument("session_id")
    session_show.set_defaults(handler=handle_sessions_show)

    node_parser = subparsers.add_parser("nodes", help="manage graph nodes")
    node_sub = node_parser.add_subparsers(dest="action", required=True)
    node_list = node_sub.add_parser("list", help="list nodes")
    node_list.add_argument("--include-archived", action="store_true")
    node_list.set_defaults(handler=handle_nodes_list)
    node_create = node_sub.add_parser("create", help="create a node")
    add_node_create_options(node_create)
    node_create.set_defaults(handler=handle_nodes_create)
    node_show = node_sub.add_parser("show", help="show one node")
    node_show.add_argument("node_id")
    node_show.set_defaults(handler=handle_nodes_show)
    node_update = node_sub.add_parser("update", help="update a node")
    node_update.add_argument("node_id")
    node_update.add_argument("--title")
    node_update.add_argument("--body")
    node_update.add_argument("--summary")
    node_update.add_argument("--workspace", action="store_true")
    node_update.add_argument("--status")
    node_update.set_defaults(handler=handle_nodes_update)
    node_archive = node_sub.add_parser("archive", help="archive a node")
    node_archive.add_argument("node_id")
    node_archive.set_defaults(handler=handle_nodes_archive)
    node_neighbors = node_sub.add_parser("neighbors", help="list node neighbors")
    node_neighbors.add_argument("node_id")
    node_neighbors.set_defaults(handler=handle_nodes_neighbors)
    node_ego = node_sub.add_parser("ego-graph", help="show an ego graph")
    node_ego.add_argument("node_id")
    node_ego.add_argument("--depth", type=int, default=2)
    node_ego.add_argument("--limit", type=int, default=50)
    node_ego.set_defaults(handler=handle_nodes_ego_graph)

    workspace_parser = subparsers.add_parser("workspaces", help="manage workspaces")
    workspace_sub = workspace_parser.add_subparsers(dest="action", required=True)
    workspace_list = workspace_sub.add_parser("list", help="list workspaces")
    workspace_list.set_defaults(handler=handle_workspaces_list)
    workspace_create = workspace_sub.add_parser("create", help="create a workspace")
    add_node_create_options(workspace_create)
    workspace_create.set_defaults(handler=handle_workspaces_create)
    workspace_show = workspace_sub.add_parser("show", help="show one workspace")
    workspace_show.add_argument("node_id")
    workspace_show.set_defaults(handler=handle_workspaces_show)

    edge_parser = subparsers.add_parser("edges", help="manage graph edges")
    edge_sub = edge_parser.add_subparsers(dest="action", required=True)
    edge_list = edge_sub.add_parser("list", help="list edges")
    edge_list.set_defaults(handler=handle_edges_list)
    edge_create = edge_sub.add_parser("create", help="create or strengthen an edge")
    edge_create.add_argument("node_a_id")
    edge_create.add_argument("node_b_id")
    edge_create.add_argument("--weight", type=float, default=1.0)
    edge_create.add_argument("--candidate", action="store_true")
    edge_create.set_defaults(handler=handle_edges_create)
    edge_update = edge_sub.add_parser("update", help="update an edge")
    edge_update.add_argument("edge_id")
    edge_update.add_argument("--weight", type=float)
    edge_update.add_argument("--candidate", action="store_true")
    edge_update.set_defaults(handler=handle_edges_update)
    edge_delete = edge_sub.add_parser("delete", help="delete an edge")
    edge_delete.add_argument("edge_id")
    edge_delete.set_defaults(handler=handle_edges_delete)

    proposal_parser = subparsers.add_parser("proposals", help="manage graph update proposals")
    proposal_sub = proposal_parser.add_subparsers(dest="action", required=True)
    proposal_list = proposal_sub.add_parser("list", help="list proposals")
    proposal_list.add_argument("--status")
    proposal_list.set_defaults(handler=handle_proposals_list)
    proposal_show = proposal_sub.add_parser("show", help="show one proposal")
    proposal_show.add_argument("proposal_id")
    proposal_show.set_defaults(handler=handle_proposals_show)
    proposal_accept = proposal_sub.add_parser("accept", help="accept and apply a proposal")
    proposal_accept.add_argument("proposal_id")
    proposal_accept.set_defaults(handler=handle_proposals_accept)
    proposal_reject = proposal_sub.add_parser("reject", help="reject a proposal")
    proposal_reject.add_argument("proposal_id")
    proposal_reject.set_defaults(handler=handle_proposals_reject)

    events_parser = subparsers.add_parser("events", help="list events")
    events_parser.add_argument("--limit", type=int, default=100)
    events_parser.add_argument("--node-id")
    events_parser.set_defaults(handler=handle_events)

    script_parser = subparsers.add_parser("scripts", help="run script placeholders")
    script_sub = script_parser.add_subparsers(dest="action", required=True)
    script_run = script_sub.add_parser("run", help="run a script placeholder")
    script_run.add_argument("script_id")
    script_run.add_argument("--node-id")
    script_run.add_argument("--arg", action="append", default=[], help="key=value argument")
    script_run.set_defaults(handler=handle_scripts_run)

    return parser


def add_chat_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--session-id")
    parser.add_argument("--anchor", dest="anchor_node_ids", action="append", default=[])
    parser.add_argument("--workspace-id")
    parser.add_argument("--context-budget", type=int, default=12000)
    parser.add_argument("--no-proposals", action="store_true")


def add_node_create_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--title", required=True)
    parser.add_argument("--body", default="")
    parser.add_argument("--summary")


def handle_chat(args: argparse.Namespace) -> Any:
    message = " ".join(args.message).strip()
    if message:
        return run_chat(args, message)
    return interactive_chat(args)


def interactive_chat(args: argparse.Namespace) -> None:
    session_id = args.session_id
    print("Me.Agent CLI. Type /exit to quit.", file=sys.stderr)
    while True:
        try:
            message = input("> ").strip()
        except EOFError:
            print(file=sys.stderr)
            return None
        if message in {"/exit", "/quit"}:
            return None
        if not message:
            continue
        args.session_id = session_id
        result = run_chat(args, message)
        session_id = result["session_id"]
        if args.json:
            emit(result, as_json=True)
        else:
            print(result["assistant_message"])


def run_chat(args: argparse.Namespace, message: str) -> dict[str, Any]:
    if args.api_url:
        return http_request(
            args,
            "POST",
            "/chat",
            {
                "session_id": args.session_id,
                "message": message,
                "anchor_node_ids": args.anchor_node_ids,
                "workspace_id": args.workspace_id,
                "options": {
                    "allow_proposals": not args.no_proposals,
                    "context_budget": args.context_budget,
                },
            },
        )
    with get_db() as db:
        return agent_runtime.chat(
            db,
            message=message,
            session_id=args.session_id,
            anchor_node_ids=args.anchor_node_ids,
            workspace_id=args.workspace_id,
            allow_proposals=not args.no_proposals,
            context_budget=args.context_budget,
        )


def handle_sessions_list(args: argparse.Namespace) -> Any:
    if args.api_url:
        return http_request(args, "GET", f"/chat/sessions?limit={args.limit}")
    with get_db() as db:
        return graph_store.list_sessions(db, limit=args.limit)


def handle_sessions_show(args: argparse.Namespace) -> Any:
    if args.api_url:
        return http_request(args, "GET", f"/chat/sessions/{quote_path(args.session_id)}")
    with get_db() as db:
        session = graph_store.get_session(db, args.session_id)
        if not session:
            raise SystemExit(f"session not found: {args.session_id}")
        return session


def handle_nodes_list(args: argparse.Namespace) -> Any:
    if args.api_url:
        query = "?include_archived=true" if args.include_archived else ""
        return http_request(args, "GET", f"/nodes{query}")
    with get_db() as db:
        return graph_store.list_nodes(db, include_archived=args.include_archived)


def handle_nodes_create(args: argparse.Namespace) -> Any:
    if args.api_url:
        return http_request(
            args,
            "POST",
            "/nodes",
            {"title": args.title, "body": args.body, "summary": args.summary, "is_workspace": False},
        )
    with get_db() as db:
        return graph_store.create_node(db, args.title, args.body, args.summary)


def handle_nodes_show(args: argparse.Namespace) -> Any:
    if args.api_url:
        return http_request(args, "GET", f"/nodes/{quote_path(args.node_id)}")
    with get_db() as db:
        node = graph_store.get_node(db, args.node_id)
        if not node:
            raise SystemExit(f"node not found: {args.node_id}")
        return node


def handle_nodes_update(args: argparse.Namespace) -> Any:
    changes = optional_changes(args, ["title", "body", "summary", "status"])
    if args.workspace:
        changes["is_workspace"] = True
    if args.api_url:
        return http_request(args, "PATCH", f"/nodes/{quote_path(args.node_id)}", changes)
    with get_db() as db:
        node = graph_store.update_node(db, args.node_id, changes)
        if not node:
            raise SystemExit(f"node not found: {args.node_id}")
        return node


def handle_nodes_archive(args: argparse.Namespace) -> Any:
    if args.api_url:
        return http_request(args, "POST", f"/nodes/{quote_path(args.node_id)}/archive")
    with get_db() as db:
        node = graph_store.update_node(db, args.node_id, {"status": "archived"})
        if not node:
            raise SystemExit(f"node not found: {args.node_id}")
        return node


def handle_nodes_neighbors(args: argparse.Namespace) -> Any:
    if args.api_url:
        return http_request(args, "GET", f"/nodes/{quote_path(args.node_id)}/neighbors")
    with get_db() as db:
        require_node(db, args.node_id)
        return graph_store.neighbors(db, args.node_id)


def handle_nodes_ego_graph(args: argparse.Namespace) -> Any:
    if args.api_url:
        return http_request(args, "GET", f"/nodes/{quote_path(args.node_id)}/ego-graph?depth={args.depth}&limit={args.limit}")
    with get_db() as db:
        require_node(db, args.node_id)
        return graph_store.ego_graph(db, args.node_id, depth=args.depth, limit=args.limit)


def handle_workspaces_list(args: argparse.Namespace) -> Any:
    if args.api_url:
        return http_request(args, "GET", "/workspaces")
    with get_db() as db:
        return [node for node in graph_store.list_nodes(db) if node["is_workspace"]]


def handle_workspaces_create(args: argparse.Namespace) -> Any:
    if args.api_url:
        return http_request(
            args,
            "POST",
            "/nodes",
            {"title": args.title, "body": args.body, "summary": args.summary, "is_workspace": True},
        )
    with get_db() as db:
        return graph_store.create_node(db, args.title, args.body, args.summary, is_workspace=True)


def handle_workspaces_show(args: argparse.Namespace) -> Any:
    with get_db() as db:
        node = require_node(db, args.node_id)
        if not node["is_workspace"]:
            raise SystemExit(f"workspace not found: {args.node_id}")
        return {
            "workspace": node,
            "graph": graph_store.ego_graph(db, args.node_id, depth=2, limit=50),
            "recent_events": graph_store.list_events(db, limit=30, node_id=args.node_id),
            "related_nodes": graph_store.neighbors(db, args.node_id),
        }


def handle_edges_list(args: argparse.Namespace) -> Any:
    if args.api_url:
        return http_request(args, "GET", "/edges")
    with get_db() as db:
        return graph_store.list_edges(db)


def handle_edges_create(args: argparse.Namespace) -> Any:
    if args.api_url:
        return http_request(
            args,
            "POST",
            "/edges",
            {
                "node_a_id": args.node_a_id,
                "node_b_id": args.node_b_id,
                "weight": args.weight,
                "is_candidate": args.candidate,
            },
        )
    with get_db() as db:
        return graph_store.create_edge(
            db,
            args.node_a_id,
            args.node_b_id,
            weight=args.weight,
            is_candidate=args.candidate,
        )


def handle_edges_update(args: argparse.Namespace) -> Any:
    changes: dict[str, Any] = {}
    if args.weight is not None:
        changes["weight"] = args.weight
    if args.candidate:
        changes["is_candidate"] = True
    if args.api_url:
        return http_request(args, "PATCH", f"/edges/{quote_path(args.edge_id)}", changes)
    with get_db() as db:
        edge = graph_store.update_edge(db, args.edge_id, changes)
        if not edge:
            raise SystemExit(f"edge not found: {args.edge_id}")
        return edge


def handle_edges_delete(args: argparse.Namespace) -> Any:
    if args.api_url:
        return http_request(args, "DELETE", f"/edges/{quote_path(args.edge_id)}")
    with get_db() as db:
        if not graph_store.get_edge(db, args.edge_id):
            raise SystemExit(f"edge not found: {args.edge_id}")
        graph_store.delete_edge(db, args.edge_id)
        return {"deleted": True, "edge_id": args.edge_id}


def handle_proposals_list(args: argparse.Namespace) -> Any:
    if args.api_url:
        query = f"?status={urllib.parse.quote(args.status)}" if args.status else ""
        return http_request(args, "GET", f"/proposals{query}")
    with get_db() as db:
        return graph_store.list_proposals(db, status=args.status)


def handle_proposals_show(args: argparse.Namespace) -> Any:
    with get_db() as db:
        proposal = graph_store.get_proposal(db, args.proposal_id)
        if not proposal:
            raise SystemExit(f"proposal not found: {args.proposal_id}")
        return proposal


def handle_proposals_accept(args: argparse.Namespace) -> Any:
    if args.api_url:
        return http_request(args, "POST", f"/proposals/{quote_path(args.proposal_id)}/accept")
    with get_db() as db:
        proposal = graph_store.get_proposal(db, args.proposal_id)
        if not proposal:
            raise SystemExit(f"proposal not found: {args.proposal_id}")
        applied = graph_writer.apply_proposal(db, proposal)
        resolved = graph_store.resolve_proposal(db, args.proposal_id, "accepted")
        return {"proposal": resolved, "applied": applied}


def handle_proposals_reject(args: argparse.Namespace) -> Any:
    if args.api_url:
        return http_request(args, "POST", f"/proposals/{quote_path(args.proposal_id)}/reject")
    with get_db() as db:
        proposal = graph_store.resolve_proposal(db, args.proposal_id, "rejected")
        if not proposal:
            raise SystemExit(f"proposal not found: {args.proposal_id}")
        return proposal


def handle_events(args: argparse.Namespace) -> Any:
    if args.api_url:
        params = {"limit": str(args.limit)}
        if args.node_id:
            params["node_id"] = args.node_id
        return http_request(args, "GET", f"/events?{urllib.parse.urlencode(params)}")
    with get_db() as db:
        return graph_store.list_events(db, limit=args.limit, node_id=args.node_id)


def handle_scripts_run(args: argparse.Namespace) -> Any:
    result = {
        "script_id": args.script_id,
        "node_id": args.node_id,
        "args": parse_key_values(args.arg),
        "status": "blocked",
        "stdout": "",
        "stderr": "MVP 默认禁用脚本执行。请在后续版本接入沙盒 runtime 后再启用。",
    }
    with get_db() as db:
        graph_store.append_event(db, "ScriptExecuted", "system", result)
    return result


def require_node(db: Any, node_id: str) -> dict[str, Any]:
    node = graph_store.get_node(db, node_id)
    if not node:
        raise SystemExit(f"node not found: {node_id}")
    return node


def optional_changes(args: argparse.Namespace, names: list[str]) -> dict[str, Any]:
    return {name: getattr(args, name) for name in names if getattr(args, name) is not None}


def parse_key_values(values: list[str]) -> dict[str, str]:
    parsed = {}
    for value in values:
        if "=" not in value:
            raise SystemExit(f"invalid --arg value, expected key=value: {value}")
        key, item = value.split("=", 1)
        parsed[key] = item
    return parsed


def http_request(args: argparse.Namespace, method: str, path: str, payload: Any | None = None) -> Any:
    base_url = str(args.api_url or "").rstrip("/")
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(f"{base_url}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            if response.status == 204:
                return None
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"failed to connect to backend: {exc.reason}") from exc
    if not raw:
        return None
    return json.loads(raw)


def quote_path(value: str) -> str:
    return urllib.parse.quote(str(value), safe="")


def emit(result: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return
    if isinstance(result, dict) and "assistant_message" in result:
        print(result["assistant_message"])
        return
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
