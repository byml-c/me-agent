from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Iterator

from backend.app.core.config import get_settings


SYSTEM_PROMPT = """你是 Me.Agent，一个以个人认知图为核心的长期陪伴型 Agent。
你回答时必须基于提供的局部图上下文，明确承认上下文不足的地方。
你可以提出图更新建议，但不能声称已经执行需要用户确认的高风险操作。"""


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
