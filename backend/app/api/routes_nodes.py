from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.api.schemas import NodeCreate, NodeUpdate
from backend.app.db.session import get_db
from backend.app.services import graph_store

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
        node = graph_store.update_node(db, node_id, payload.model_dump(exclude_unset=True))
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


@router.get("/{node_id}/ego-graph")
def get_ego_graph(node_id: str, depth: int = 2, limit: int = 50):
    with get_db() as db:
        return graph_store.ego_graph(db, node_id, depth=depth, limit=limit)
