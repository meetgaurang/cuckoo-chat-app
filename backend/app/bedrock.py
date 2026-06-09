"""Thin wrapper around the Bedrock Runtime Converse API.

Maps our simple ``[{role, content}]`` history onto the Bedrock Converse shape
and yields text deltas. Prefers streaming (``converse_stream``); if the model
does not support streaming it transparently falls back to a single
``converse`` call and yields the full text in one chunk.
"""
from __future__ import annotations

from typing import Iterator

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from .config import get_settings

# Roles Bedrock Converse accepts in the messages array.
_VALID_ROLES = {"user", "assistant"}


def _client():
    settings = get_settings()
    return boto3.client(
        "bedrock-runtime",
        region_name=settings.aws_region,
        # Adaptive retries add client-side backoff + rate-limiting, which
        # smooths over Bedrock ThrottlingException bursts (common on a freshly
        # enabled model with low default TPS).
        config=Config(retries={"max_attempts": 5, "mode": "adaptive"}),
    )


def _build_request(messages: list[dict], system: str | None) -> dict:
    """Translate our payload into Converse API kwargs."""
    settings = get_settings()

    converse_messages = [
        {"role": m["role"], "content": [{"text": m["content"]}]}
        for m in messages
        if m.get("role") in _VALID_ROLES and m.get("content")
    ]

    request: dict = {
        "modelId": settings.bedrock_model_id,
        "messages": converse_messages,
        "inferenceConfig": {
            "maxTokens": settings.max_tokens,
            "temperature": settings.temperature,
        },
    }

    system_text = (system or settings.system_prompt).strip()
    if system_text:
        request["system"] = [{"text": system_text}]

    return request


def stream_chat(messages: list[dict], system: str | None = None) -> Iterator[str]:
    """Yield assistant text deltas for the given conversation.

    Raises ``RuntimeError`` with a user-safe message on Bedrock failure.
    """
    client = _client()
    request = _build_request(messages, system)

    try:
        response = client.converse_stream(**request)
        for event in response["stream"]:
            delta = event.get("contentBlockDelta", {}).get("delta", {})
            text = delta.get("text")
            if text:
                yield text
        return
    except ClientError as err:
        code = err.response.get("Error", {}).get("Code", "")
        # Some models expose Converse but not ConverseStream — fall back to a
        # single non-streaming call rather than failing the request.
        if code in {"ValidationException", "UnsupportedOperationException"}:
            yield from _converse_once(client, request)
            return
        raise RuntimeError(_friendly_error(err)) from err
    except Exception as err:  # noqa: BLE001 - surface a safe message to the UI
        raise RuntimeError(f"Bedrock request failed: {err}") from err


def _converse_once(client, request: dict) -> Iterator[str]:
    try:
        response = client.converse(**request)
        for block in response["output"]["message"]["content"]:
            if "text" in block:
                yield block["text"]
    except ClientError as err:
        raise RuntimeError(_friendly_error(err)) from err


def _friendly_error(err: ClientError) -> str:
    code = err.response.get("Error", {}).get("Code", "UnknownError")
    msg = err.response.get("Error", {}).get("Message", str(err))
    if code == "AccessDeniedException":
        return (
            "Access denied to the Bedrock model. Enable model access for "
            "the configured model id/region and check IAM permissions."
        )
    if code == "ResourceNotFoundException":
        return "Model not found. Check BEDROCK_MODEL_ID and AWS_REGION."
    if code == "ThrottlingException":
        # Surface the real reason — could be rate-per-minute OR a daily token
        # cap ("Too many tokens per day"), which retries won't fix.
        return f"Bedrock throttled the request: {msg}"
    return f"Bedrock error ({code}): {msg}"
