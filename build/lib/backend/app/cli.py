from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.db.session import get_db, init_db
from backend.app.main import seed_if_empty
from backend.app.services import agent_runtime, file_library, graph_store, graph_writer, node_runtime


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
        emit(result)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="me-agent", description="Me.Agent backend CLI")
    parser.add_argument("--no-seed", action="store_true", help="do not seed the database before running")
    parser.add_argument(
        "--api-url",
        default=default_api_url(),
        help=(
            "connect to a running Me.Agent HTTP backend instead of local SQLite "
            "(default: ME_AGENT_API_URL or SERVER_URL)"
        ),
    )
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
    node_search = node_sub.add_parser("search", help="search nodes by text and attachments")
    node_search.add_argument("query")
    node_search.add_argument("--workspace-id")
    node_search.add_argument("--anchor")
    node_search.add_argument("--depth", type=int, default=2)
    node_search.add_argument("--limit", type=int, default=20)
    node_search.add_argument("--include-archived", action="store_true")
    node_search.add_argument("--with-database", help="only include nodes with a matching database attachment")
    node_search.set_defaults(handler=handle_nodes_search)
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

    node_memory = node_sub.add_parser("memory", help="inspect or replace node memory")
    node_memory_sub = node_memory.add_subparsers(dest="memory_action", required=True)
    node_memory_show = node_memory_sub.add_parser("show", help="show node memory")
    node_memory_show.add_argument("node_id")
    node_memory_show.set_defaults(handler=handle_nodes_memory_show)
    node_memory_update = node_memory_sub.add_parser("update", help="replace node memory from JSON")
    node_memory_update.add_argument("node_id")
    add_json_input_options(node_memory_update)
    node_memory_update.set_defaults(handler=handle_nodes_memory_update)

    node_databases = node_sub.add_parser("databases", help="manage node database attachments")
    node_databases_sub = node_databases.add_subparsers(dest="database_action", required=True)
    node_databases_list = node_databases_sub.add_parser("list", help="list node database attachments")
    node_databases_list.add_argument("node_id")
    node_databases_list.set_defaults(handler=handle_nodes_databases_list)
    node_databases_add = node_databases_sub.add_parser("add", help="add a database attachment to a node")
    node_databases_add.add_argument("node_id")
    node_databases_add.add_argument("--name", required=True)
    node_databases_add.add_argument("--description")
    node_databases_add.add_argument("--content")
    node_databases_add.add_argument("--content-file")
    node_databases_add.add_argument("--path")
    node_databases_add.add_argument("--media-type")
    node_databases_add.add_argument("--kind", choices=["text", "file"], default="text")
    node_databases_add.add_argument("--entry-id")
    node_databases_add.add_argument("--file-id")
    node_databases_add.set_defaults(handler=handle_nodes_databases_add)
    node_databases_update = node_databases_sub.add_parser("update", help="update a node database attachment")
    node_databases_update.add_argument("node_id")
    node_databases_update.add_argument("database_id")
    node_databases_update.add_argument("--name")
    node_databases_update.add_argument("--description")
    node_databases_update.add_argument("--content")
    node_databases_update.add_argument("--content-file")
    node_databases_update.add_argument("--path")
    node_databases_update.add_argument("--media-type")
    node_databases_update.set_defaults(handler=handle_nodes_databases_update)
    node_databases_delete = node_databases_sub.add_parser("delete", help="remove a node database attachment")
    node_databases_delete.add_argument("node_id")
    node_databases_delete.add_argument("database_id")
    node_databases_delete.set_defaults(handler=handle_nodes_databases_delete)

    node_files = node_sub.add_parser("files", help="manage node file attachments")
    node_files_sub = node_files.add_subparsers(dest="file_action", required=True)
    node_files_list = node_files_sub.add_parser("list", help="list node file attachments")
    node_files_list.add_argument("node_id")
    node_files_list.set_defaults(handler=handle_nodes_files_list)
    node_files_add = node_files_sub.add_parser("add", help="add a file attachment to a node")
    node_files_add.add_argument("node_id")
    node_files_add.add_argument("--name", required=True)
    node_files_add.add_argument("--description")
    node_files_add.add_argument("--content")
    node_files_add.add_argument("--content-file")
    node_files_add.add_argument("--path")
    node_files_add.add_argument("--media-type")
    node_files_add.add_argument("--file-id")
    node_files_add.set_defaults(handler=handle_nodes_files_add)
    node_files_delete = node_files_sub.add_parser("delete", help="remove a node file attachment")
    node_files_delete.add_argument("node_id")
    node_files_delete.add_argument("file_attachment_id")
    node_files_delete.set_defaults(handler=handle_nodes_files_delete)

    node_scripts = node_sub.add_parser("scripts", help="manage node script attachments")
    node_scripts_sub = node_scripts.add_subparsers(dest="script_action", required=True)
    node_scripts_list = node_scripts_sub.add_parser("list", help="list node scripts")
    node_scripts_list.add_argument("node_id")
    node_scripts_list.set_defaults(handler=handle_nodes_scripts_list)
    node_scripts_add = node_scripts_sub.add_parser("add", help="add a Python script to a node")
    node_scripts_add.add_argument("node_id")
    add_script_mutation_options(node_scripts_add, require_code=True)
    node_scripts_add.set_defaults(handler=handle_nodes_scripts_add)
    node_scripts_update = node_scripts_sub.add_parser("update", help="update a node script")
    node_scripts_update.add_argument("node_id")
    node_scripts_update.add_argument("script_id")
    add_script_mutation_options(node_scripts_update, require_code=False)
    node_scripts_update.set_defaults(handler=handle_nodes_scripts_update)
    node_scripts_delete = node_scripts_sub.add_parser("delete", help="remove a node script")
    node_scripts_delete.add_argument("node_id")
    node_scripts_delete.add_argument("script_id")
    node_scripts_delete.set_defaults(handler=handle_nodes_scripts_delete)
    node_scripts_run = node_scripts_sub.add_parser("run", help="run a node script")
    node_scripts_run.add_argument("node_id")
    node_scripts_run.add_argument("script_id")
    node_scripts_run.add_argument("--arg", action="append", default=[], help="key=value argument")
    node_scripts_run.add_argument("--trigger", default="manual_run")
    node_scripts_run.set_defaults(handler=handle_nodes_scripts_run)

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


def default_api_url() -> str | None:
    for name in ("ME_AGENT_API_URL", "SERVER_URL"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return None


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


def add_json_input_options(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--memory", dest="json_text", help="memory JSON object text")
    group.add_argument("--file", dest="json_file", help="path to a JSON file")


def add_script_mutation_options(parser: argparse.ArgumentParser, *, require_code: bool) -> None:
    parser.add_argument("--name", required=require_code)
    parser.add_argument("--description")
    code_group = parser.add_mutually_exclusive_group(required=require_code)
    code_group.add_argument("--code")
    code_group.add_argument("--code-file")
    parser.add_argument("--trigger-on-enter", action="store_true")
    parser.add_argument("--no-trigger-on-enter", action="store_true")
    parser.add_argument("--trigger-on-ai-switch", action="store_true")
    parser.add_argument("--no-trigger-on-ai-switch", action="store_true")


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


def handle_nodes_search(args: argparse.Namespace) -> Any:
    if args.api_url:
        nodes = http_request(args, "GET", nodes_list_path(include_archived=args.include_archived))
        edges = http_request(args, "GET", "/edges")
    else:
        with get_db() as db:
            nodes = graph_store.list_nodes(db, include_archived=args.include_archived)
            edges = graph_store.list_edges(db)
    return search_nodes(
        nodes,
        edges,
        query=args.query,
        workspace_id=args.workspace_id,
        anchor_id=args.anchor,
        depth=args.depth,
        limit=args.limit,
        database_query=args.with_database,
    )


def handle_nodes_memory_show(args: argparse.Namespace) -> Any:
    node = load_node(args, args.node_id)
    return node.get("memory") or {}


def handle_nodes_memory_update(args: argparse.Namespace) -> Any:
    memory = parse_json_object(read_json_input(args))
    return save_node_memory(args, args.node_id, memory, event_type="NodeMemoryUpdated")


def handle_nodes_databases_list(args: argparse.Namespace) -> Any:
    return node_attachments(load_node(args, args.node_id)).get("databases", [])


def handle_nodes_databases_add(args: argparse.Namespace) -> Any:
    attachment = {
        "id": graph_store.new_id("dbatt"),
        "entry_id": args.entry_id,
        "file_id": args.file_id,
        "kind": args.kind,
        "name": args.name,
        "description": args.description,
        "content": read_optional_text(args.content, args.content_file),
        "path": args.path,
        "media_type": args.media_type,
    }
    return mutate_attachment_list(args, args.node_id, "databases", lambda items: [*items, compact_dict(attachment)])


def handle_nodes_databases_update(args: argparse.Namespace) -> Any:
    changes = compact_dict(
        {
            "name": args.name,
            "description": args.description,
            "content": read_optional_text(args.content, args.content_file),
            "path": args.path,
            "media_type": args.media_type,
        }
    )
    return mutate_attachment_list(
        args,
        args.node_id,
        "databases",
        lambda items: update_attachment(items, args.database_id, changes, "database attachment"),
    )


def handle_nodes_databases_delete(args: argparse.Namespace) -> Any:
    return mutate_attachment_list(
        args,
        args.node_id,
        "databases",
        lambda items: delete_attachment(items, args.database_id, "database attachment"),
    )


def handle_nodes_files_list(args: argparse.Namespace) -> Any:
    return node_attachments(load_node(args, args.node_id)).get("files", [])


def handle_nodes_files_add(args: argparse.Namespace) -> Any:
    attachment = {
        "id": graph_store.new_id("fileatt"),
        "file_id": args.file_id,
        "name": args.name,
        "description": args.description,
        "content": read_optional_text(args.content, args.content_file),
        "path": args.path,
        "media_type": args.media_type,
    }
    return mutate_attachment_list(args, args.node_id, "files", lambda items: [*items, compact_dict(attachment)])


def handle_nodes_files_delete(args: argparse.Namespace) -> Any:
    return mutate_attachment_list(
        args,
        args.node_id,
        "files",
        lambda items: delete_attachment(items, args.file_attachment_id, "file attachment"),
    )


def handle_nodes_scripts_list(args: argparse.Namespace) -> Any:
    return node_attachments(load_node(args, args.node_id)).get("scripts", [])


def handle_nodes_scripts_add(args: argparse.Namespace) -> Any:
    script = compact_dict(
        {
            "id": graph_store.new_id("script"),
            "name": args.name,
            "language": "python",
            "code": read_optional_text(args.code, args.code_file) or "",
            "description": args.description,
            "trigger_on_enter": bool(args.trigger_on_enter),
            "trigger_on_ai_switch": bool(args.trigger_on_ai_switch),
            "schedule_rules": [],
        }
    )
    return mutate_attachment_list(args, args.node_id, "scripts", lambda items: [*items, script])


def handle_nodes_scripts_update(args: argparse.Namespace) -> Any:
    changes = compact_dict(
        {
            "name": args.name,
            "description": args.description,
            "code": read_optional_text(args.code, args.code_file),
        }
    )
    if args.trigger_on_enter or args.no_trigger_on_enter:
        changes["trigger_on_enter"] = bool(args.trigger_on_enter)
    if args.trigger_on_ai_switch or args.no_trigger_on_ai_switch:
        changes["trigger_on_ai_switch"] = bool(args.trigger_on_ai_switch)
    return mutate_attachment_list(
        args,
        args.node_id,
        "scripts",
        lambda items: update_attachment(items, args.script_id, changes, "script"),
    )


def handle_nodes_scripts_delete(args: argparse.Namespace) -> Any:
    return mutate_attachment_list(
        args,
        args.node_id,
        "scripts",
        lambda items: delete_attachment(items, args.script_id, "script"),
    )


def handle_nodes_scripts_run(args: argparse.Namespace) -> Any:
    payload = {"args": parse_key_values(args.arg), "trigger": args.trigger}
    if args.api_url:
        return http_request(args, "POST", f"/nodes/{quote_path(args.node_id)}/scripts/{quote_path(args.script_id)}/run", payload)
    with get_db() as db:
        node = require_node(db, args.node_id)
        script = node_runtime.find_script(node, args.script_id)
        if not script:
            raise SystemExit(f"script not found: {args.script_id}")
        result = node_runtime.run_python_script(node, script, args=payload["args"], trigger=args.trigger)
        graph_store.append_event(db, "NodeScriptExecuted", "agent", result)
        return result


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
    if args.api_url:
        return http_request(args, "GET", f"/workspaces/{quote_path(args.node_id)}")
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
    if args.api_url:
        return http_request(args, "GET", f"/proposals/{quote_path(args.proposal_id)}")
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


def load_node(args: argparse.Namespace, node_id: str) -> dict[str, Any]:
    if args.api_url:
        return http_request(args, "GET", f"/nodes/{quote_path(node_id)}")
    with get_db() as db:
        return require_node(db, node_id)


def save_node_memory(
    args: argparse.Namespace,
    node_id: str,
    memory: dict[str, Any],
    *,
    event_type: str = "NodeMemoryEditedByAgent",
) -> dict[str, Any]:
    if args.api_url:
        return http_request(args, "PATCH", f"/nodes/{quote_path(node_id)}", {"memory": memory})
    with get_db() as db:
        require_node(db, node_id)
        synced = sync_memory_attachments(db, node_id, memory)
        node = graph_store.update_node(db, node_id, {"memory": synced}, actor="agent")
        graph_store.append_event(db, event_type, "agent", {"node_id": node_id})
        return node


def sync_memory_attachments(db: Any, node_id: str, memory: dict[str, Any]) -> dict[str, Any]:
    attachments = ensure_attachments(memory)
    return {
        **memory,
        "attachments": {
            **attachments,
            "databases": file_library.sync_node_database_attachments(db, attachments["databases"]),
            "files": file_library.sync_node_file_attachments(db, attachments["files"], node_id=node_id),
            "scripts": attachments["scripts"],
        },
    }


def mutate_attachment_list(
    args: argparse.Namespace,
    node_id: str,
    kind: str,
    mutate: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
) -> dict[str, Any]:
    node = load_node(args, node_id)
    memory = node.get("memory") if isinstance(node.get("memory"), dict) else {}
    attachments = ensure_attachments(memory)
    attachments[kind] = mutate(attachments[kind])
    memory = {**memory, "attachments": attachments}
    return save_node_memory(args, node_id, memory, event_type=f"Node{kind.title()}EditedByAgent")


def ensure_attachments(memory: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    raw = memory.get("attachments") if isinstance(memory.get("attachments"), dict) else {}
    return {
        "databases": attachment_items(raw.get("databases")),
        "files": attachment_items(raw.get("files")),
        "scripts": attachment_items(raw.get("scripts")),
    }


def node_attachments(node: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    memory = node.get("memory") if isinstance(node.get("memory"), dict) else {}
    return ensure_attachments(memory)


def attachment_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def update_attachment(
    items: list[dict[str, Any]],
    attachment_id: str,
    changes: dict[str, Any],
    label: str,
) -> list[dict[str, Any]]:
    updated = []
    found = False
    for item in items:
        if str(item.get("id") or item.get("entry_id") or item.get("file_id") or "") == attachment_id:
            updated.append({**item, **changes})
            found = True
        else:
            updated.append(item)
    if not found:
        raise SystemExit(f"{label} not found: {attachment_id}")
    return updated


def delete_attachment(items: list[dict[str, Any]], attachment_id: str, label: str) -> list[dict[str, Any]]:
    filtered = [
        item
        for item in items
        if str(item.get("id") or item.get("entry_id") or item.get("file_id") or "") != attachment_id
    ]
    if len(filtered) == len(items):
        raise SystemExit(f"{label} not found: {attachment_id}")
    return filtered


def search_nodes(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    *,
    query: str,
    workspace_id: str | None,
    anchor_id: str | None,
    depth: int,
    limit: int,
    database_query: str | None = None,
) -> list[dict[str, Any]]:
    allowed = reachable_node_ids(nodes, edges, workspace_id or anchor_id, depth) if (workspace_id or anchor_id) else None
    terms = tokenize(query)
    database_terms = tokenize(database_query or "")
    scored: list[tuple[int, dict[str, Any]]] = []
    for node in nodes:
        if allowed is not None and node.get("id") not in allowed:
            continue
        if database_terms and not database_matches(node, database_terms):
            continue
        score = score_node(node, terms)
        if database_terms:
            score += 10
        if score > 0:
            scored.append((score, {**node, "match_score": score}))
    scored.sort(key=lambda item: (-item[0], str(item[1].get("updated_at") or "")), reverse=False)
    return [node for _, node in scored[: max(1, min(limit, 100))]]


def reachable_node_ids(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    start_id: str,
    depth: int,
) -> set[str]:
    node_ids = {str(node.get("id")) for node in nodes}
    if start_id not in node_ids:
        return set()
    adjacency: dict[str, set[str]] = {}
    for edge in edges:
        a = str(edge.get("node_a_id") or "")
        b = str(edge.get("node_b_id") or "")
        if a in node_ids and b in node_ids:
            adjacency.setdefault(a, set()).add(b)
            adjacency.setdefault(b, set()).add(a)
    seen = {start_id}
    frontier = {start_id}
    for _ in range(max(0, depth)):
        nxt = {neighbor for node_id in frontier for neighbor in adjacency.get(node_id, set()) if neighbor not in seen}
        seen.update(nxt)
        frontier = nxt
        if not frontier:
            break
    return seen


def score_node(node: dict[str, Any], terms: list[str]) -> int:
    if not terms:
        return 1
    title = str(node.get("title") or "").lower()
    summary = str(node.get("summary") or "").lower()
    body = str(node.get("body") or "").lower()
    attachment_text = json.dumps(node_attachments(node), ensure_ascii=False).lower()
    score = 0
    for term in terms:
        if term in title:
            score += 8
        if term in summary:
            score += 4
        if term in body:
            score += 3
        if term in attachment_text:
            score += 2
    return score


def database_matches(node: dict[str, Any], terms: list[str]) -> bool:
    text = json.dumps(node_attachments(node).get("databases", []), ensure_ascii=False).lower()
    return all(term in text for term in terms)


def tokenize(value: str) -> list[str]:
    return [part.lower() for part in str(value or "").split() if part.strip()]


def nodes_list_path(*, include_archived: bool) -> str:
    return "/nodes?include_archived=true" if include_archived else "/nodes"


def read_json_input(args: argparse.Namespace) -> str:
    if getattr(args, "json_text", None) is not None:
        return args.json_text
    path = Path(args.json_file).expanduser()
    return path.read_text(encoding="utf-8")


def parse_json_object(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise SystemExit("expected a JSON object")
    return parsed


def read_optional_text(value: str | None, path: str | None) -> str | None:
    if path:
        return Path(path).expanduser().read_text(encoding="utf-8")
    return value


def compact_dict(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item is not None}


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


def emit(result: Any) -> None:
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
