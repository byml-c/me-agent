from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Iterator

from backend.app.core.config import get_settings

CONTROL_START = "<ME_AGENT_CONTROL>"
CONTROL_END = "</ME_AGENT_CONTROL>"

SYSTEM_PROMPT = """你是 Me.Agent，一个以个人认知图为核心的长期陪伴型 Agent。
你回答时必须基于提供的局部图上下文，明确承认上下文不足的地方。
你需要专注于和用户对话。不要直接输出结构化图更新 proposal。
在每次回复末尾追加一个控制块，用于判断是否需要 Graph Writer Agent 创建新节点；控制块不要解释给用户。
控制块格式必须严格为：
<ME_AGENT_CONTROL>{"should_create_nodes":true|false,"reason":"一句话原因"}</ME_AGENT_CONTROL>"""

GRAPH_INTENT_PROMPT = """你是 Me.Agent 的 Conversation Agent。
请基于同一轮对话上下文，判断是否需要编辑个人认知图，并给出简洁的编辑方向。
同时判断下一轮对话最应该聚焦到哪个已有节点。只能从 available_context_nodes 中选择 suggested_anchor_node_id；如果不需要跳转则填 null。
如果 Conversation Agent 回复为空，说明你正在用户回复前先做路由判断，请只根据用户消息和图上下文输出 intent。
只输出 JSON，不要输出 Markdown。
JSON schema:
{
  "should_edit": true | false,
  "direction": "一句话说明应该怎样编辑图",
  "operations": ["create_node" | "edit_node" | "create_edge" | "split_node" | "promote_to_workspace"],
  "suggested_anchor_node_id": "node_id or null",
  "suggested_anchor_reason": "一句话说明为什么应该聚焦到这个节点"
}"""


def complete_chat(user_message: str, context_summary: str) -> str:
    settings = get_settings()
    if not settings.openai_api_key:
        return fallback_response(user_message, context_summary, "未配置 OPENAI_API_KEY")

    payload = {
        "model": settings.openai_base_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"局部图上下文：\n{context_summary or '暂无'}\n\n用户消息：{user_message}"},
        ],
        "temperature": 0.4,
    }
    request = urllib.request.Request(
        f"{settings.openai_base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
    except (urllib.error.URLError, KeyError, TimeoutError, json.JSONDecodeError) as exc:
        return fallback_response(user_message, context_summary, f"LLM 调用失败：{exc}")


def graph_edit_intent(user_message: str, context: dict | str, assistant_message: str) -> dict:
    settings = get_settings()
    fallback = fallback_graph_intent(user_message)
    context_summary, context_nodes = intent_context_parts(context)
    context_node_ids = {node["id"] for node in context_nodes}
    if not settings.openai_api_key:
        return fallback

    payload = {
        "model": settings.openai_base_model,
        "messages": [
            {"role": "system", "content": GRAPH_INTENT_PROMPT},
            {
                "role": "user",
                "content": (
                    f"局部图上下文：\n{context_summary or '暂无'}\n\n"
                    f"available_context_nodes：\n{json.dumps(context_nodes, ensure_ascii=False)}\n\n"
                    f"用户消息：{user_message}\n\n"
                    f"Conversation Agent 回复：{assistant_message}"
                ),
            },
        ],
        "temperature": 0.1,
    }
    request = urllib.request.Request(
        f"{settings.openai_base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"].strip()
            parsed = parse_json_object(content)
            return normalize_graph_intent(parsed, context_node_ids)
    except (urllib.error.URLError, KeyError, TimeoutError, json.JSONDecodeError, ValueError):
        return fallback


def stream_chat(user_message: str, context_summary: str) -> Iterator[str]:
    settings = get_settings()
    if not settings.openai_api_key:
        yield from chunk_text(fallback_response(user_message, context_summary, "未配置 OPENAI_API_KEY"))
        return

    payload = {
        "model": settings.openai_base_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"局部图上下文：\n{context_summary or '暂无'}\n\n用户消息：{user_message}"},
        ],
        "temperature": 0.4,
        "stream": True,
    }
    request = urllib.request.Request(
        f"{settings.openai_base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8").strip()
                if not line or not line.startswith("data:"):
                    continue
                data = line.removeprefix("data:").strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content")
                if delta:
                    yield delta
    except (urllib.error.URLError, TimeoutError) as exc:
        yield from chunk_text(fallback_response(user_message, context_summary, f"LLM 调用失败：{exc}"))


def fallback_response(user_message: str, context_summary: str, reason: str) -> str:
    if context_summary:
        return (
            f"{reason}。我先基于当前局部图做一个离线整理：\n\n"
            f"{context_summary[:1400]}\n\n"
            f"针对你的问题“{user_message}”，建议先确认锚点是否正确，再接受或拒绝下面的图更新提案。"
        )
    return f"{reason}。当前图里还没有足够上下文，我已保留这轮对话并生成可确认的整理提案。"


def chunk_text(text: str, size: int = 12) -> Iterator[str]:
    for index in range(0, len(text), size):
        yield text[index : index + size]


def fallback_graph_intent(user_message: str) -> dict:
    message = user_message.lower()
    operations: list[str] = []
    if any(keyword in message for keyword in ["新建", "创建", "记录", "整理", "想法", "todo", "任务"]):
        operations.append("create_node")
    if any(keyword in message for keyword in ["关联", "连接", "关系"]):
        operations.append("create_edge")
    if "拆分" in message:
        operations.append("split_node")
    if any(keyword in message for keyword in ["工作区", "项目", "长期"]):
        operations.append("promote_to_workspace")
    return {
        "should_edit": bool(operations),
        "direction": "根据用户本轮消息沉淀或调整图结构。" if operations else "无需编辑图。",
        "operations": operations,
        "suggested_anchor_node_id": None,
        "suggested_anchor_reason": "离线规则未判断跳转节点。",
    }


def graph_writer_summary_intent(user_message: str, assistant_message: str, control: dict | None = None) -> dict:
    should_create = bool((control or {}).get("should_create_nodes", True))
    return {
        "should_edit": should_create,
        "direction": str((control or {}).get("reason") or "由 Graph Writer Agent 基于本轮对话回复总结可沉淀的图更新。"),
        "operations": ["create_node", "edit_node", "create_edge", "split_node", "promote_to_workspace"] if should_create else [],
        "suggested_anchor_node_id": None,
        "suggested_anchor_reason": "",
        "source": "graph_writer_summary",
        "user_message": user_message[:240],
        "assistant_message": assistant_message[:480],
    }


def no_graph_intent() -> dict:
    return {
        "should_edit": False,
        "direction": "本轮未启用图更新。",
        "operations": [],
        "suggested_anchor_node_id": None,
        "suggested_anchor_reason": "",
    }


def parse_conversation_control(content: str) -> tuple[str, dict]:
    start = content.find(CONTROL_START)
    end = content.find(CONTROL_END, start + len(CONTROL_START)) if start >= 0 else -1
    if start < 0 or end < 0:
        return content.strip(), {"should_create_nodes": False, "reason": "Conversation Agent 未请求创建节点。"}
    visible = (content[:start] + content[end + len(CONTROL_END) :]).strip()
    raw = content[start + len(CONTROL_START) : end].strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {}
    return visible, {
        "should_create_nodes": bool(parsed.get("should_create_nodes")),
        "reason": str(parsed.get("reason") or "Conversation Agent 未提供原因。"),
    }


def parse_json_object(content: str) -> dict:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start < 0 or end < start:
        raise ValueError("JSON object not found")
    return json.loads(stripped[start : end + 1])


def intent_context_parts(context: dict | str) -> tuple[str, list[dict]]:
    if not isinstance(context, dict):
        return str(context or ""), []
    nodes = []
    for node in context.get("context_nodes", []):
        node_id = node.get("id")
        if not node_id:
            continue
        nodes.append(
            {
                "id": node_id,
                "title": node.get("title", ""),
                "summary": node.get("summary") or node.get("body", "")[:180],
                "reason": node.get("reason", ""),
            }
        )
    return str(context.get("context_summary") or ""), nodes


def normalize_graph_intent(value: dict, context_node_ids: set[str] | None = None) -> dict:
    allowed = {"create_node", "edit_node", "create_edge", "split_node", "promote_to_workspace"}
    operations = [operation for operation in value.get("operations", []) if operation in allowed]
    suggested_anchor = value.get("suggested_anchor_node_id")
    if not isinstance(suggested_anchor, str) or not suggested_anchor.strip():
        suggested_anchor = None
    if context_node_ids is not None and suggested_anchor not in context_node_ids:
        suggested_anchor = None
    return {
        "should_edit": bool(value.get("should_edit", bool(operations))),
        "direction": str(value.get("direction") or "根据对话更新图结构。"),
        "operations": operations,
        "suggested_anchor_node_id": suggested_anchor,
        "suggested_anchor_reason": str(value.get("suggested_anchor_reason") or ""),
    }
