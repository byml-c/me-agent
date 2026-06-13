from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api import (
    routes_config,
    routes_chat,
    routes_edges,
    routes_events,
    routes_files,
    routes_library,
    routes_nodes,
    routes_proposals,
    routes_scripts,
    routes_workspaces,
)
from backend.app.db.session import get_db, init_db
from backend.app.services import graph_store


app = FastAPI(title="Me.Agent API", version="0.1.0")

DEFAULT_CORS_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]


def get_cors_origins() -> list[str]:
    raw_origins = os.getenv("ME_AGENT_CORS_ORIGINS")
    if not raw_origins:
        return DEFAULT_CORS_ORIGINS
    origins = [origin.strip().rstrip("/") for origin in raw_origins.split(",")]
    return [origin for origin in origins if origin]


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
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
            body="个人认知图的总入口，用于连接工作、生活和 Me.Agent 自身设计三个长期上下文。",
            is_workspace=True,
            actor="system",
        )
        work = graph_store.create_node(
            db,
            title="Me.Agent - 工作",
            body=(
                "工作相关的长期上下文入口，用于沉淀项目、任务、会议、代码、研究和职业规划。"
            ),
            is_workspace=True,
            actor="system",
        )
        life = graph_store.create_node(
            db,
            title="Me.Agent - 生活",
            body="生活相关的长期上下文入口，用于记录日常事件、关系、习惯、兴趣、灵感和个人安排。",
            is_workspace=True,
            actor="system",
        )
        design = graph_store.create_node(
            db,
            title="Me.Agent - Me.Agent 设计",
            body="Me.Agent 自身的产品、架构、交互、图模型、上下文机制和迭代计划。",
            is_workspace=True,
            actor="system",
        )
        graph_store.create_edge(db, root["id"], work["id"], weight=1.0, created_by="system")
        graph_store.create_edge(db, root["id"], life["id"], weight=1.0, created_by="system")
        graph_store.create_edge(db, root["id"], design["id"], weight=1.0, created_by="system")
        graph_store.append_event(
            db,
            "Seeded",
            "system",
            {"root_node_id": root["id"], "node_ids": [root["id"], work["id"], life["id"], design["id"]]},
        )


app.include_router(routes_nodes.router)
app.include_router(routes_edges.router)
app.include_router(routes_config.router)
app.include_router(routes_chat.router)
app.include_router(routes_files.router)
app.include_router(routes_library.router)
app.include_router(routes_workspaces.router)
app.include_router(routes_proposals.router)
app.include_router(routes_events.router)
app.include_router(routes_scripts.router)
