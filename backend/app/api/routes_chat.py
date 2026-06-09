from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import json

from backend.app.api.schemas import ChatRequest
from backend.app.db.session import get_db
from backend.app.services import agent_runtime, graph_store, graph_writer, llm

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

            raw_chunks: list[str] = []
            visible_chunks: list[str] = []
            pending_visible = ""
            control_started = False
            for chunk in llm.stream_chat(payload.message, context["context_summary"]):
                raw_chunks.append(chunk)
                if control_started:
                    continue
                pending_visible += chunk
                marker_index = pending_visible.find(llm.CONTROL_START)
                if marker_index >= 0:
                    visible = pending_visible[:marker_index]
                    if visible:
                        visible_chunks.append(visible)
                        yield sse("delta", {"content": visible})
                    pending_visible = ""
                    control_started = True
                    continue
                safe_length = max(0, len(pending_visible) - len(llm.CONTROL_START) + 1)
                if safe_length:
                    visible = pending_visible[:safe_length]
                    pending_visible = pending_visible[safe_length:]
                    visible_chunks.append(visible)
                    yield sse("delta", {"content": visible})

            if not control_started and pending_visible:
                visible_chunks.append(pending_visible)
                yield sse("delta", {"content": pending_visible})

            assistant_raw = "".join(raw_chunks)
            assistant_message, conversation_control = llm.parse_conversation_control(assistant_raw)
            agent_runtime.record_assistant_message(db, session["id"], assistant_message, context)
            graph_intent = (
                llm.graph_writer_summary_intent(payload.message, assistant_message, conversation_control)
                if payload.options.allow_proposals
                else llm.no_graph_intent()
            )
            proposals: list[dict] = []
            auto_applied: list[dict] = []
            if payload.options.allow_proposals and graph_intent.get("should_edit"):
                yield sse("graph_intent", {"graph_intent": graph_intent})
                yield sse(
                    "graph_building",
                    {
                        "graph_intent": graph_intent,
                        "message": "建图中",
                    },
                )
                for proposal in agent_runtime.stream_graph_proposals(
                    db,
                    payload.message,
                    assistant_message,
                    context,
                    graph_intent,
                    allow_proposals=True,
                ):
                    if agent_runtime.proposal_requires_review(proposal):
                        proposals.append(proposal)
                        yield sse("proposal", {"proposal": proposal})
                    else:
                        applied = graph_writer.apply_proposal(db, proposal)
                        resolved = graph_store.resolve_proposal(db, proposal["id"], "accepted")
                        auto_applied.append({"proposal": resolved or proposal, "applied": applied})
                        yield sse("graph_changed", {"proposal": resolved or proposal, "applied": applied})
            yield sse(
                "done",
                {
                    "session_id": session["id"],
                    "assistant_message": assistant_message,
                    "used_context": context,
                    "episode_node": episode,
                    "graph_intent": graph_intent,
                    "proposals": proposals,
                    "auto_applied": auto_applied,
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
