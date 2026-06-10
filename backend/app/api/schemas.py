from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class NodeCreate(BaseModel):
    title: str
    body: str = ""
    summary: str | None = None
    is_workspace: bool = False


class NodeUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    summary: str | None = None
    memory: dict[str, Any] | None = None
    is_workspace: bool | None = None
    status: str | None = None


class EdgeCreate(BaseModel):
    node_a_id: str
    node_b_id: str
    weight: float = 1.0
    is_candidate: bool = False


class EdgeUpdate(BaseModel):
    weight: float | None = None
    is_candidate: bool | None = None


class ChatOptions(BaseModel):
    allow_proposals: bool = True
    context_budget: int = 12000
    variant_temperature: float = 0.4


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str
    anchor_node_ids: list[str] = Field(default_factory=list)
    workspace_id: str | None = None
    parent_message_id: str | None = None
    options: ChatOptions = Field(default_factory=ChatOptions)


class ChatMessageEditRequest(BaseModel):
    content: str
    context_budget: int = 12000


class ChatRegenerateRequest(BaseModel):
    variant_temperature: float = 0.75
    context_budget: int = 12000


class ScriptRunRequest(BaseModel):
    node_id: str | None = None
    code: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    trigger: str | None = None


class LibraryFileCreate(BaseModel):
    name: str
    description: str | None = None
    media_type: str | None = None
    source_path: str | None = None
    content: str | None = None


class LibraryEntryCreate(BaseModel):
    title: str
    description: str | None = None
    content: str = ""


class NodeScriptTriggerRequest(BaseModel):
    trigger: str
    args: dict[str, Any] = Field(default_factory=dict)
