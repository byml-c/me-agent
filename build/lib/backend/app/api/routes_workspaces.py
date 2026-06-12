from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.api.schemas import NodeCreate
from backend.app.db.session import get_db
from backend.app.services import graph_store

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("")
def list_workspaces():
    with get_db() as db:
        return [node for node in graph_store.list_nodes(db) if node["is_workspace"]]


@router.post("")
def create_workspace(payload: NodeCreate):
    with get_db() as db:
        return graph_store.create_node(
            db,
            title=payload.title,
            body=payload.body,
            summary=payload.summary,
            is_workspace=True,
        )


@router.get("/{node_id}")
def get_workspace(node_id: str):
    with get_db() as db:
        node = graph_store.get_node(db, node_id)
        if not node or not node["is_workspace"]:
            raise HTTPException(status_code=404, detail="workspace not found")
        return {
            "workspace": node,
            "graph": graph_store.ego_graph(db, node_id, depth=2, limit=50),
            "recent_events": graph_store.list_events(db, limit=30, node_id=node_id),
            "related_nodes": graph_store.neighbors(db, node_id),
        }
