"""Chat endpoint: streams Bedrock responses to the client as SSE."""
from __future__ import annotations

import json
from typing import Iterator, Literal, Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..bedrock import stream_chat

router = APIRouter()


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[Message] = Field(..., min_length=1)
    system: Optional[str] = None


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _event_stream(req: ChatRequest) -> Iterator[str]:
    messages = [m.model_dump() for m in req.messages]
    try:
        for delta in stream_chat(messages, req.system):
            yield _sse({"delta": delta})
    except RuntimeError as err:
        yield _sse({"error": str(err)})
    finally:
        yield "data: [DONE]\n\n"


@router.post("/chat")
def chat(req: ChatRequest) -> StreamingResponse:
    return StreamingResponse(
        _event_stream(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable proxy buffering (nginx)
        },
    )
