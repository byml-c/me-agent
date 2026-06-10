from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.api.schemas import NodeCreate, NodeScriptTriggerRequest, NodeUpdate, ScriptRunRequest
from backend.app.db.session import get_db
from backend.app.services import file_library, graph_store, node_runtime

router = APIRouter(prefix="/nodes", tags=["nodes"])


@router.get("")
def list_nodes(include_archived: bool = False):
    with get_db() as db:
        return graph_store.list_nodes(db, include_archived=include_archived)


@router.post("")
def create_node(payload: NodeCreate):
    with get_db() as db:
        return graph_store.create_node(
            db,
            title=payload.title,
            body=payload.body,
            summary=payload.summary,
            is_workspace=payload.is_workspace,
        )


@router.get("/graph")
def get_full_graph():
    with get_db() as db:
        return graph_store.full_graph(db)


@router.get("/{node_id}")
def get_node(node_id: str):
    with get_db() as db:
        node = graph_store.get_node(db, node_id)
        if not node:
            raise HTTPException(status_code=404, detail="node not found")
        return node


@router.patch("/{node_id}")
def update_node(node_id: str, payload: NodeUpdate):
    with get_db() as db:
        values = payload.model_dump(exclude_unset=True)
        if "memory" in values:
            values["memory"] = sync_node_memory_attachments(db, node_id, values.get("memory"))
        node = graph_store.update_node(db, node_id, values)
        if not node:
            raise HTTPException(status_code=404, detail="node not found")
        return node


@router.post("/{node_id}/archive")
def archive_node(node_id: str):
    with get_db() as db:
        node = graph_store.update_node(db, node_id, {"status": "archived"})
        if not node:
            raise HTTPException(status_code=404, detail="node not found")
        return node


@router.get("/{node_id}/neighbors")
def get_neighbors(node_id: str):
    with get_db() as db:
        if not graph_store.get_node(db, node_id):
            raise HTTPException(status_code=404, detail="node not found")
        return graph_store.neighbors(db, node_id)


@router.get("/{node_id}/history")
def get_history(node_id: str):
    with get_db() as db:
        return graph_store.list_events(db, node_id=node_id)


@router.post("/{node_id}/scripts/{script_id}/run")
def run_node_script(node_id: str, script_id: str, payload: ScriptRunRequest):
    with get_db() as db:
        node = graph_store.get_node(db, node_id)
        if not node:
            raise HTTPException(status_code=404, detail="node not found")
        script = {"id": script_id, "name": "草稿脚本", "language": "python", "code": payload.code} if payload.code is not None else node_runtime.find_script(node, script_id)
        if not script:
            raise HTTPException(status_code=404, detail="script not found")
        result = node_runtime.run_python_script(node, script, args=payload.args, trigger=payload.trigger or "manual_run")
        graph_store.append_event(db, "NodeScriptExecuted", "system", result)
        return result


@router.post("/{node_id}/scripts/trigger")
def trigger_node_scripts(node_id: str, payload: NodeScriptTriggerRequest):
    with get_db() as db:
        node = graph_store.get_node(db, node_id)
        if not node:
            raise HTTPException(status_code=404, detail="node not found")
        results = node_runtime.run_triggered_scripts(node, payload.trigger, args=payload.args)
        for result in results:
            graph_store.append_event(db, "NodeScriptTriggered", "system", result)
        return {"node_id": node_id, "trigger": payload.trigger, "results": results}


@router.get("/{node_id}/ego-graph")
def get_ego_graph(node_id: str, depth: int = 2, limit: int = 50):
    with get_db() as db:
        return graph_store.ego_graph(db, node_id, depth=depth, limit=limit)


def sync_node_memory_attachments(db, node_id: str, memory):
    if not isinstance(memory, dict):
        return memory
    attachments = memory.get("attachments")
    if not isinstance(attachments, dict):
        return memory
    files = attachments.get("files") if isinstance(attachments.get("files"), list) else []
    databases = attachments.get("databases") if isinstance(attachments.get("databases"), list) else []
    return {
        **memory,
        "attachments": {
            **attachments,
            "databases": file_library.sync_node_database_attachments(db, databases),
            "files": file_library.sync_node_file_attachments(db, files, node_id=node_id),
        },
    }
