from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

from backend.app.api.schemas import EdgeCreate, EdgeUpdate
from backend.app.db.session import get_db
from backend.app.services import graph_store

router = APIRouter(prefix="/edges", tags=["edges"])


@router.get("")
def list_edges():
    with get_db() as db:
        return graph_store.list_edges(db)


@router.post("")
def create_edge(payload: EdgeCreate):
    with get_db() as db:
        try:
            return graph_store.create_edge(
                db,
                payload.node_a_id,
                payload.node_b_id,
                payload.weight,
                payload.is_candidate,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{edge_id}")
def update_edge(edge_id: str, payload: EdgeUpdate):
    with get_db() as db:
        try:
            edge = graph_store.update_edge(db, edge_id, payload.model_dump(exclude_unset=True))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not edge:
            raise HTTPException(status_code=404, detail="edge not found")
        return edge


@router.delete("/{edge_id}", status_code=204)
def delete_edge(edge_id: str):
    with get_db() as db:
        if not graph_store.get_edge(db, edge_id):
            raise HTTPException(status_code=404, detail="edge not found")
        graph_store.delete_edge(db, edge_id)
    return Response(status_code=204)
