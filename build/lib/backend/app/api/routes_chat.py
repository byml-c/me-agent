from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import json
from queue import Queue
from threading import Thread

from backend.app.api.schemas import ChatMessageEditRequest, ChatRegenerateRequest, ChatRequest
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
        events: Queue[tuple[str, dict | None]] = Queue()

        def push(event: str, data: dict) -> None:
            events.put((event, data))

        def run_agent() -> None:
            try:
                deferred_events: list[tuple[str, dict]] = []
                with get_db() as db:
                    prepared = agent_runtime.prepare_chat(
                        db,
                        message=payload.message,
                        session_id=payload.session_id,
                        anchor_node_ids=payload.anchor_node_ids,
                        workspace_id=payload.workspace_id,
                        context_budget=payload.options.context_budget,
                        parent_message_id=payload.parent_message_id,
                    )
                    session = prepared["session"]
                    context = prepared["context"]
                    episode = prepared["episode"]
                    push(
                        "meta",
                        {
                            "session_id": session["id"],
                            "used_context": context,
                            "episode_node": episode,
                        },
                    )
                    if payload.options.allow_proposals:
                        push(
                            "graph_building",
                            {
                                "graph_intent": {
                                    "should_edit": True,
                                    "direction": "Conversation Agent 正在按需调用图工具。",
                                    "operations": [],
                                    "suggested_anchor_node_id": None,
                                    "suggested_anchor_reason": "",
                                    "source": "responses_tools",
                                },
                                "message": "工具调用中",
                            },
                        )
                    result = agent_runtime.run_responses_agent(
                        db,
                        session,
                        context,
                        episode,
                        prepared["user_message"],
                        allow_proposals=payload.options.allow_proposals,
                        variant_temperature=payload.options.variant_temperature,
                        on_tool_call=lambda event: push("tool_call", event),
                        on_text_delta=lambda delta: push("delta", {"content": delta}),
                        on_reasoning_delta=lambda delta: push("reasoning_delta", {"content": delta}),
                    )
                    if result["graph_intent"].get("should_edit"):
                        deferred_events.append(("graph_intent", {"graph_intent": result["graph_intent"]}))
                        for proposal in result["proposals"]:
                            deferred_events.append(("proposal", {"proposal": proposal}))
                        for applied in result["auto_applied"]:
                            deferred_events.append(("graph_changed", applied))
                    deferred_events.append(
                        (
                            "done",
                            agent_runtime.response_payload(session, context, episode, result),
                        )
                    )
                for event, data in deferred_events:
                    push(event, data)
            except Exception as exc:
                push("error", {"message": str(exc)})
            finally:
                events.put(("", None))

        Thread(target=run_agent, daemon=True).start()
        while True:
            event, data = events.get()
            if not event:
                break
            yield sse(event, data or {})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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


@router.post("/messages/{message_id}/edit")
def edit_message(message_id: str, payload: ChatMessageEditRequest):
    with get_db() as db:
        result = agent_runtime.edit_user_message_and_regenerate(
            db,
            message_id,
            payload.content,
            context_budget=payload.context_budget,
        )
        if not result:
            raise HTTPException(status_code=404, detail="editable user message not found")
        return result


@router.post("/messages/{message_id}/edit/stream")
def edit_message_stream(message_id: str, payload: ChatMessageEditRequest):
    def run(push):
        with get_db() as db:
            push("graph_building", {"graph_intent": streaming_graph_intent(), "message": "工具调用中"})
            result = agent_runtime.edit_user_message_and_regenerate(
                db,
                message_id,
                payload.content,
                context_budget=payload.context_budget,
                on_tool_call=lambda event: push("tool_call", event),
                on_text_delta=lambda delta: push("delta", {"content": delta}),
                on_reasoning_delta=lambda delta: push("reasoning_delta", {"content": delta}),
            )
            if not result:
                raise HTTPException(status_code=404, detail="editable user message not found")
            return stream_tail_events(result)

    return sse_response(run)


@router.post("/messages/{message_id}/regenerate")
def regenerate_message(message_id: str, payload: ChatRegenerateRequest):
    with get_db() as db:
        result = agent_runtime.regenerate_assistant(
            db,
            message_id,
            variant_temperature=payload.variant_temperature,
            context_budget=payload.context_budget,
        )
        if not result:
            raise HTTPException(status_code=404, detail="assistant message not found")
        return result


@router.post("/messages/{message_id}/regenerate/stream")
def regenerate_message_stream(message_id: str, payload: ChatRegenerateRequest):
    def run(push):
        with get_db() as db:
            push("graph_building", {"graph_intent": streaming_graph_intent(), "message": "工具调用中"})
            result = agent_runtime.regenerate_assistant(
                db,
                message_id,
                variant_temperature=payload.variant_temperature,
                context_budget=payload.context_budget,
                on_tool_call=lambda event: push("tool_call", event),
                on_text_delta=lambda delta: push("delta", {"content": delta}),
                on_reasoning_delta=lambda delta: push("reasoning_delta", {"content": delta}),
            )
            if not result:
                raise HTTPException(status_code=404, detail="assistant message not found")
            return stream_tail_events(result)

    return sse_response(run)


@router.post("/sessions/{session_id}/messages")
def send_message(session_id: str, payload: ChatRequest):
    payload.session_id = session_id
    return chat(payload)


def streaming_graph_intent() -> dict:
    return {
        "should_edit": True,
        "direction": "Conversation Agent 正在按需调用图工具。",
        "operations": [],
        "suggested_anchor_node_id": None,
        "suggested_anchor_reason": "",
        "source": "responses_tools",
    }


def stream_tail_events(result: dict) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    graph_intent = result.get("graph_intent") or {}
    if graph_intent.get("should_edit"):
        events.append(("graph_intent", {"graph_intent": graph_intent}))
        for proposal in result.get("proposals") or []:
            events.append(("proposal", {"proposal": proposal}))
        for applied in result.get("auto_applied") or []:
            events.append(("graph_changed", applied))
    events.append(("done", result))
    return events


def sse_response(run_agent):
    def event_stream():
        events: Queue[tuple[str, dict | None]] = Queue()

        def push(event: str, data: dict) -> None:
            events.put((event, data))

        def run() -> None:
            try:
                deferred_events = run_agent(push)
                for event, data in deferred_events:
                    push(event, data)
            except Exception as exc:
                push("error", {"message": str(exc)})
            finally:
                events.put(("", None))

        Thread(target=run, daemon=True).start()
        while True:
            event, data = events.get()
            if not event:
                break
            yield sse(event, data or {})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
