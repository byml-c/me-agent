from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import json

from backend.app.api.schemas import ChatRequest
from backend.app.db.session import get_db
from backend.app.services import agent_runtime, graph_store, llm

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("")
def chat(payload: ChatRequest):
    with get_db() as db:
        return agent_runtime.chat(
            db,
            message=payload.message,
            session_id=payload.session_id,
            anchor_node_ids=payload.anchor_node_ids,
            workspace_id=payload.workspace_id,
            allow_proposals=payload.options.allow_proposals,
            context_budget=payload.options.context_budget,
        )


@router.post("/stream")
def chat_stream(payload: ChatRequest):
    def event_stream():
        with get_db() as db:
            prepared = agent_runtime.prepare_chat(
                db,
                message=payload.message,
                session_id=payload.session_id,
                anchor_node_ids=payload.anchor_node_ids,
                workspace_id=payload.workspace_id,
                context_budget=payload.options.context_budget,
            )
            session = prepared["session"]
            context = prepared["context"]
            episode = prepared["episode"]
            yield sse(
                "meta",
                {
                    "session_id": session["id"],
                    "used_context": context,
                    "episode_node": episode,
                },
            )

            chunks: list[str] = []
            for chunk in llm.stream_chat(payload.message, context["context_summary"]):
                chunks.append(chunk)
                yield sse("delta", {"content": chunk})

            assistant_message = "".join(chunks)
            finished = agent_runtime.finish_chat(
                db,
                session["id"],
                assistant_message,
                context,
                payload.message,
                allow_proposals=payload.options.allow_proposals,
            )
            yield sse(
                "done",
                {
                    "session_id": session["id"],
                    "assistant_message": assistant_message,
                    "used_context": context,
                    "episode_node": episode,
                    "proposals": finished["proposals"],
                    "auto_applied": finished["auto_applied"],
                },
            )

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/sessions")
def list_sessions(limit: int = 50):
    with get_db() as db:
        return graph_store.list_sessions(db, limit=limit)


@router.get("/sessions/{session_id}")
def get_session(session_id: str):
    with get_db() as db:
        session = graph_store.get_session(db, session_id)
        if not session:
            raise HTTPException(status_code=404, detail="session not found")
        return session


@router.post("/sessions/{session_id}/messages")
def send_message(session_id: str, payload: ChatRequest):
    payload.session_id = session_id
    return chat(payload)
