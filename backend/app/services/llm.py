from __future__ import annotations

import json
import os
from collections.abc import Iterator
from typing import Any

from openai import OpenAI
from pydantic import BaseModel

from backend.app.core.config import get_settings

CONTROL_START = "<ME_AGENT_CONTROL>"
CONTROL_END = "</ME_AGENT_CONTROL>"
REASONING_EFFORT = "none"

SYSTEM_PROMPT = """你是 Me.Agent，一个以个人认知图为核心的长期陪伴型 Agent。
你回答时必须基于提供的局部图上下文，明确承认上下文不足的地方。
你需要专注于和用户对话，不要把内部图操作参数暴露给用户。
你应优先快速判断并直接推进任务，不要反复权衡、铺垫或过度解释。
只有在上下文确实缺失、操作有风险、或用户明确要求深入分析时，才展开不确定性和取舍。
普通对话用简洁结论和必要步骤回答；图编辑请求优先调用工具，再用一句话说明结果。
当用户明确要求记录、整理、修改节点，或本轮出现值得长期保存的信息时，优先使用可用工具读写个人认知图。
当你判断对话应该聚焦到另一个已有节点时，必须调用 switch_node；不要只在文字中说明要切换。
当你需要引用后端统一维护的知识库资料时，优先用 search_library 搜索文本/文件条目，再用 read_library_entry 读取完整内容；只有明确需要按文件维度操作时再用 search_files / read_file。
如果工具返回 review_required=true，说明变更已进入用户审核；你只需自然说明已放入待确认，不要声称已经永久写入。
只有当工具结果实际返回 proposal 时，才能说“已放入待确认/审核”。只有当工具结果 review_required=false 且 ok=true 时，才能说“已经更新/生效”。
如果用户要求删除节点、断开关系或调整结构，必须先调用对应工具；没有工具成功返回时，明确说明尚未执行。
当用户说“创建成节点”“记录下来”“保存一下”等省略宾语的指令时，默认指代上一条 assistant 回复或最近正在讨论的内容；不要因为用户没有重复标题/正文而反问，应该自行提炼标题、摘要和正文并调用 create_node。
当用户说“在/到/给 X 下/下面/里新建 Y 节点”时，X 是父节点或挂载位置，create_node 的 title 只写 Y，不要把父节点名拼进标题；层级关系由 link_to_node_ids 或后续边表达。
不要输出结构化 proposal JSON。"""

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

    try:
        payload = {
            "model": settings.openai_base_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"局部图上下文：\n{context_summary or '暂无'}\n\n用户消息：{user_message}"},
            ],
            "temperature": 0.4,
        }
        extra_body = provider_extra_body(settings)
        if extra_body:
            payload["extra_body"] = extra_body
        response = openai_client(timeout=45).chat.completions.create(**payload)
        return (response.choices[0].message.content or "").strip()
    except Exception as exc:
        return fallback_response(user_message, context_summary, f"LLM 调用失败：{exc}")


def graph_edit_intent(user_message: str, context: dict | str, assistant_message: str) -> dict:
    settings = get_settings()
    fallback = fallback_graph_intent(user_message)
    context_summary, context_nodes = intent_context_parts(context)
    context_node_ids = {node["id"] for node in context_nodes}
    if not settings.openai_api_key:
        return fallback

    try:
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
        extra_body = provider_extra_body(settings)
        if extra_body:
            payload["extra_body"] = extra_body
        response = openai_client(timeout=45).chat.completions.create(**payload)
        content = (response.choices[0].message.content or "").strip()
        parsed = parse_json_object(content)
        return normalize_graph_intent(parsed, context_node_ids)
    except Exception:
        return fallback


def stream_chat(user_message: str, context_summary: str) -> Iterator[str]:
    settings = get_settings()
    if not settings.openai_api_key:
        yield from chunk_text(fallback_response(user_message, context_summary, "未配置 OPENAI_API_KEY"))
        return

    try:
        payload = {
            "model": settings.openai_base_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"局部图上下文：\n{context_summary or '暂无'}\n\n用户消息：{user_message}"},
            ],
            "temperature": 0.4,
            "stream": True,
        }
        extra_body = provider_extra_body(settings)
        if extra_body:
            payload["extra_body"] = extra_body
        stream = openai_client(timeout=90).chat.completions.create(**payload)
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
    except Exception as exc:
        yield from chunk_text(fallback_response(user_message, context_summary, f"LLM 调用失败：{exc}"))


def openai_client(timeout: float = 90) -> OpenAI:
    settings = get_settings()
    return OpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        timeout=timeout,
    )


def provider_extra_body(settings=None) -> dict[str, Any]:
    settings = settings or get_settings()
    base_url = settings.openai_base_url.lower()
    model = settings.openai_base_model.lower()
    enable_thinking = os.getenv("ME_AGENT_ENABLE_THINKING")
    if enable_thinking is not None and ("dashscope" in base_url or model.startswith("qwen")):
        enabled = enable_thinking.strip().lower() in {"1", "true", "yes", "on"}
        return {"enable_thinking": enabled}
    return {}


def reasoning_config() -> dict[str, str]:
    return {"effort": REASONING_EFFORT}


def responses_create(payload: dict[str, Any], timeout: int = 90) -> dict[str, Any]:
    response = openai_client(timeout=timeout).responses.create(**payload)
    return sdk_to_dict(response)


def responses_create_streaming(
    payload: dict[str, Any],
    on_text_delta=None,
    on_reasoning_delta=None,
    on_stream_event=None,
) -> tuple[dict[str, Any], str]:
    response_payload: dict[str, Any] = {}
    output_items: list[dict[str, Any]] = []
    text_chunks: list[str] = []
    stream = openai_client().responses.create(**payload, stream=True)
    for event in stream:
        event_data = sdk_to_dict(event)
        if on_stream_event:
            on_stream_event(event_data)
        event_name = str(event_data.get("type") or "")
        if event_name == "response.output_text.delta":
            delta = str(event_data.get("delta") or "")
            if delta:
                text_chunks.append(delta)
                if on_text_delta:
                    on_text_delta(delta)
        elif event_name == "response.reasoning_summary_text.delta":
            delta = str(event_data.get("delta") or "")
            if delta and on_reasoning_delta:
                on_reasoning_delta(delta)
        elif event_name == "response.output_item.done":
            item = event_data.get("item")
            if item is not None:
                output_items.append(sdk_to_dict(item))
        elif event_name == "response.output_text.done":
            text = str(event_data.get("text") or "")
            if text and not text_chunks:
                text_chunks.append(text)
        elif event_name == "response.completed":
            response = event_data.get("response")
            if response is not None:
                response_payload = sdk_to_dict(response)

    if not response_payload and not output_items and not text_chunks:
        response_payload = responses_create(payload)
        text = extract_response_text(response_payload)
        if text and on_text_delta:
            on_text_delta(text)
        return response_payload, text
    if not response_payload:
        response_payload = {"output": output_items, "output_text": "".join(text_chunks)}
    elif not response_payload.get("output") and output_items:
        response_payload["output"] = output_items
    if text_chunks and not response_payload.get("output_text"):
        response_payload["output_text"] = "".join(text_chunks)
    text = "".join(text_chunks) or extract_response_text(response_payload)
    if text and not text_chunks and on_text_delta:
        on_text_delta(text)
    return response_payload, text


def responses_chat_with_tools(
    input_items: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    execute_tool,
    temperature: float = 0.4,
    max_tool_rounds: int = 4,
    on_tool_call=None,
    on_text_delta=None,
    on_reasoning_delta=None,
    on_stream_event=None,
    previous_response_id: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.openai_api_key:
        last_user = next((item for item in reversed(input_items) if item.get("role") == "user"), {})
        content = str(last_user.get("content") or "")
        return {"text": fallback_response(content, "", "未配置 OPENAI_API_KEY"), "tool_results": []}

    working_input = list(input_items)
    working_previous_response_id = previous_response_id
    tool_results: list[dict[str, Any]] = []
    last_response: dict[str, Any] | None = None
    usage_totals: dict[str, int] = empty_usage_totals()
    for round_index in range(max_tool_rounds + 1):
        payload = {
            "model": settings.openai_base_model,
            "instructions": response_instructions(context),
            "input": working_input,
            "tools": tools,
            "store": True
        }
        if 'dashscope' in settings.openai_base_url.lower():
            payload["reasoning"] = reasoning_config()
        if 'volcano' in settings.openai_base_url.lower():
            payload['caching'] = {'type': 'enabled'}
            payload['reasoning'] = {'type': 'disabled'}
            payload['reasoning_effort'] = 'minimal'

        extra_body = provider_extra_body(settings)
        if extra_body:
            payload["extra_body"] = extra_body
        if working_previous_response_id:
            payload["previous_response_id"] = working_previous_response_id
        last_response, streamed_text = responses_create_streaming(
            payload,
            on_text_delta=on_text_delta,
            on_reasoning_delta=on_reasoning_delta,
            on_stream_event=on_stream_event,
        )
        add_response_usage(usage_totals, last_response)
        output = last_response.get("output", [])
        calls = [item for item in output if item.get("type") == "function_call"]
        if not calls:
            return {
                "text": streamed_text or extract_response_text(last_response),
                "tool_results": tool_results,
                "response": last_response,
                "response_id": last_response.get("id"),
                "usage": usage_totals,
            }
        working_previous_response_id = str(last_response.get("id") or "") or working_previous_response_id
        function_outputs: list[dict[str, Any]] = []
        for call in calls:
            try:
                arguments = json.loads(call.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {}
            result = execute_tool(call.get("name") or "", arguments)
            if on_tool_call:
                on_tool_call(
                    {
                        "name": call.get("name") or "",
                        "arguments": arguments,
                        "call_id": call.get("call_id"),
                        "result": result,
                    }
                )
            tool_results.append({"call": call, "result": result})
            function_outputs.append(
                {
                    "type": "function_call_output",
                    "call_id": call.get("call_id"),
                    "output": json.dumps(result, ensure_ascii=False),
                }
            )
        working_input = function_outputs
    return {
        "text": extract_response_text(last_response or {}),
        "tool_results": tool_results,
        "response": last_response,
        "response_id": (last_response or {}).get("id"),
        "usage": usage_totals,
    }


def response_instructions(context: dict[str, Any] | None = None) -> str:
    if not context:
        return SYSTEM_PROMPT
    return (
        f"{SYSTEM_PROMPT}\n\n"
        "本轮局部图上下文：\n"
        f"{context.get('context_summary') or '暂无'}\n\n"
        "本轮可用上下文节点：\n"
        f"{compact_context_nodes(context)}"
    )


def compact_context_nodes(context: dict[str, Any]) -> str:
    nodes = [
        {
            "id": node.get("id"),
            "title": node.get("title"),
            "summary": node.get("summary"),
            "include_level": node.get("include_level"),
            "activation_score": node.get("activation_score"),
        }
        for node in context.get("context_nodes", [])
    ]
    return json.dumps(nodes, ensure_ascii=False)


def sdk_to_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return {}


def empty_usage_totals() -> dict[str, int]:
    return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cached_tokens": 0}


def add_response_usage(target: dict[str, int], response: dict[str, Any]) -> None:
    usage = response.get("usage")
    if not isinstance(usage, dict):
        return
    input_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or input_tokens + output_tokens)
    cached_tokens = int(
        usage.get("cached_tokens")
        or nested_int(usage, "input_tokens_details", "cached_tokens")
        or nested_int(usage, "prompt_tokens_details", "cached_tokens")
        or 0
    )
    target["input_tokens"] += input_tokens
    target["output_tokens"] += output_tokens
    target["total_tokens"] += total_tokens
    target["cached_tokens"] += cached_tokens


def nested_int(value: dict[str, Any], key: str, nested_key: str) -> int:
    nested = value.get(key)
    if not isinstance(nested, dict):
        return 0
    return int(nested.get(nested_key) or 0)


def extract_response_text(response: dict[str, Any]) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    chunks: list[str] = []
    for item in response.get("output", []):
        content = item.get("content") if isinstance(item, dict) else None
        if not isinstance(content, list):
            continue
        for part in content:
            if part.get("type") in {"output_text", "text"} and isinstance(part.get("text"), str):
                chunks.append(part["text"])
    return "".join(chunks).strip()


def fallback_response(user_message: str, context_summary: str, reason: str) -> str:
    if context_summary:
        return (
            f"{reason}。我先基于当前局部图做一个离线整理：\n\n"
            f"{context_summary[:1400]}\n\n"
            f"针对你的问题“{user_message}”，建议先确认锚点是否正确，再接受或拒绝下面的图更新提案。"
        )
    return f"{reason}。当前图里还没有足够上下文，我已保留这轮对话并生成可确认的整理提案。"


def summarize_library_item(title: str, description: str, content: str, limit: int = 240) -> str:
    source = "\n".join(part for part in [title.strip(), description.strip(), content.strip()] if part).strip()
    if not source:
        return ""
    settings = get_settings()
    if not settings.openai_api_key:
        compact = " ".join(source.split())
        return compact[:limit] + ("..." if len(compact) > limit else "")
    try:
        payload = {
            "model": settings.openai_base_model,
            "messages": [
                {"role": "system", "content": "请把给定资料压缩成 2 句中文摘要，保留主题、用途和关键约束。不要使用项目符号。"},
                {"role": "user", "content": source[:12000]},
            ],
            "temperature": 0.1,
        }
        extra_body = provider_extra_body(settings)
        if extra_body:
            payload["extra_body"] = extra_body
        response = openai_client(timeout=45).chat.completions.create(**payload)
        summary = (response.choices[0].message.content or "").strip()
        if summary:
            return summary[:limit]
    except Exception:
        pass
    compact = " ".join(source.split())
    return compact[:limit] + ("..." if len(compact) > limit else "")


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
