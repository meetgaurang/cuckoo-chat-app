"""Thin wrapper around the OpenRouter chat-completions API.

OpenRouter is OpenAI-compatible. We send the conversation to the
``/chat/completions`` endpoint with ``stream=True`` and yield text deltas
parsed from the returned SSE stream.
"""
from __future__ import annotations

import json
from typing import Iterator, Optional

import httpx

from .config import get_settings

# Roles we forward to OpenRouter.
_VALID_ROLES = {"user", "assistant"}


def _build_payload(messages: list[dict], system: Optional[str]) -> dict:
    settings = get_settings()

    chat_messages: list[dict] = []
    system_text = (system or settings.system_prompt).strip()
    if system_text:
        chat_messages.append({"role": "system", "content": system_text})

    chat_messages.extend(
        {"role": m["role"], "content": m["content"]}
        for m in messages
        if m.get("role") in _VALID_ROLES and m.get("content")
    )

    return {
        "model": settings.openrouter_model,
        "messages": chat_messages,
        "max_tokens": settings.max_tokens,
        "temperature": settings.temperature,
        "stream": True,
    }


def stream_chat(messages: list[dict], system: Optional[str] = None) -> Iterator[str]:
    """Yield assistant text deltas for the given conversation.

    Raises ``RuntimeError`` with a user-safe message on failure.
    """
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Add it to your environment / .env."
        )

    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        # Optional attribution headers (recommended by OpenRouter).
        "HTTP-Referer": settings.openrouter_referer,
        "X-Title": settings.openrouter_title,
    }
    url = f"{settings.openrouter_base_url.rstrip('/')}/chat/completions"
    payload = _build_payload(messages, system)

    try:
        with httpx.Client(timeout=httpx.Timeout(300.0, connect=10.0)) as client:
            with client.stream("POST", url, headers=headers, json=payload) as resp:
                if resp.status_code != 200:
                    body = resp.read().decode("utf-8", "replace")
                    raise RuntimeError(_friendly_error(resp.status_code, body))

                for line in resp.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[len("data:"):].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue  # OpenRouter sends ": OPENROUTER PROCESSING" keep-alives
                    delta = (
                        chunk.get("choices", [{}])[0].get("delta", {}).get("content")
                    )
                    if delta:
                        yield delta
    except httpx.HTTPError as err:
        raise RuntimeError(f"OpenRouter request failed: {err}") from err


def _friendly_error(status: int, body: str) -> str:
    message = body
    try:
        parsed = json.loads(body)
        message = parsed.get("error", {}).get("message") or body
    except json.JSONDecodeError:
        pass

    if status == 401:
        return "OpenRouter rejected the API key (401). Check OPENROUTER_API_KEY."
    if status == 402:
        return "OpenRouter: payment required / insufficient credits (402)."
    if status == 429:
        return f"OpenRouter rate limit hit (429): {message}"
    return f"OpenRouter error ({status}): {message}"
