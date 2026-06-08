from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.db.session import get_db
from backend.app.services import graph_store, graph_writer

router = APIRouter(prefix="/proposals", tags=["proposals"])


@router.get("")
def list_proposals(status: str | None = None):
    with get_db() as db:
        return graph_store.list_proposals(db, status=status)


@router.get("/{proposal_id}")
def get_proposal(proposal_id: str):
    with get_db() as db:
        proposal = graph_store.get_proposal(db, proposal_id)
        if not proposal:
            raise HTTPException(status_code=404, detail="proposal not found")
        return proposal


@router.post("/{proposal_id}/accept")
def accept_proposal(proposal_id: str):
    with get_db() as db:
        proposal = graph_store.get_proposal(db, proposal_id)
        if not proposal:
            raise HTTPException(status_code=404, detail="proposal not found")
        applied = graph_writer.apply_proposal(db, proposal)
        resolved = graph_store.resolve_proposal(db, proposal_id, "accepted")
        return {"proposal": resolved, "applied": applied}


@router.post("/{proposal_id}/reject")
def reject_proposal(proposal_id: str):
    with get_db() as db:
        proposal = graph_store.resolve_proposal(db, proposal_id, "rejected")
        if not proposal:
            raise HTTPException(status_code=404, detail="proposal not found")
        return proposal
