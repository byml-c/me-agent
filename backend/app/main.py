from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api import (
    routes_chat,
    routes_edges,
    routes_events,
    routes_nodes,
    routes_proposals,
    routes_scripts,
    routes_workspaces,
)
from backend.app.db.session import get_db, init_db
from backend.app.services import graph_store


app = FastAPI(title="Me.Agent API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    seed_if_empty()


@app.get("/health")
def health():
    return {"ok": True}


def seed_if_empty() -> None:
    with get_db() as db:
        if graph_store.list_nodes(db, include_archived=True):
            return
        root = graph_store.create_node(
            db,
            title="Me.Agent",
            body=(
                "以个人认知图为核心的长期陪伴型 Agent。MVP 支持节点、边、局部图、对话、"
                "episode、proposal、工作区和事件日志。"
            ),
            is_workspace=True,
            actor="system",
        )
        context = graph_store.create_node(
            db,
            title="差序格局上下文",
            body="以当前锚点为中心，结合图距离、边权、访问频次、时间和语义相关性组织局部视野。",
            actor="system",
        )
        writer = graph_store.create_node(
            db,
            title="Graph Writer 提案机制",
            body="Agent 不直接执行高风险图更新，而是生成 create_node、create_edge、split_node 等 proposal。",
            actor="system",
        )
        graph_store.create_edge(db, root["id"], context["id"], weight=1.0, created_by="system")
        graph_store.create_edge(db, root["id"], writer["id"], weight=0.9, created_by="system")
        graph_store.append_event(db, "Seeded", "system", {"root_node_id": root["id"]})


app.include_router(routes_nodes.router)
app.include_router(routes_edges.router)
app.include_router(routes_chat.router)
app.include_router(routes_workspaces.router)
app.include_router(routes_proposals.router)
app.include_router(routes_events.router)
app.include_router(routes_scripts.router)
