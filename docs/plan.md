# Plan: Cuckoo Chat — ChatGPT-style demo app

## Context

Build a ChatGPT-like **demo** chat application from scratch (the working directory is currently empty). Goal is a portable, containerised app that streams responses from an AWS Bedrock model.

Decisions confirmed with the user:
- **Frontend:** React + ShadCN UI on **Vite (SPA)** — TanStack Start was dropped after review since a single-page chat demo gains nothing from its SSR/routing/server-function features and only adds weight.
- **Backend:** Python + FastAPI
- **Model:** AWS Bedrock **native Google Gemma 3 4B IT** (`google.gemma-3-4b-it`) via the **Converse/ConverseStream API**. Confirmed available on Bedrock (Dec 2025 open-weight expansion): 128K context, 8K max output, in-region inference in us-east-1, us-west-2, eu-west-1, ap-south-1, and others. Model id is env-configurable so it can be swapped. *Streaming caveat: the model card lists `Converse` explicitly; if `ConverseStream` is unsupported for Gemma, fall back to the OpenAI-compatible Chat Completions endpoint (`stream=True`) and relay as SSE.*
- **Responses:** **Streaming via SSE** (token-by-token, like ChatGPT)
- **History:** **client-side only** — backend is stateless; the full message list is sent on each request
- **Scope:** **single chat** thread (no multi-conversation sidebar)
- **No database**
- **Docker** containerised for portability

## Architecture

Two containers orchestrated by `docker-compose`:

```
┌─────────────────────┐        POST /api/chat (SSE)      ┌──────────────────────┐      ConverseStream     ┌──────────────┐
│ frontend            │  ───────────────────────────────▶ │ backend              │ ──────────────────────▶ │ AWS Bedrock  │
│ TanStack Start +    │  ◀───────────────────────────────  │ FastAPI + uvicorn    │ ◀────────────────────── │ (Converse)   │
│ React + ShadCN      │        text/event-stream           │ boto3 bedrock-runtime│      stream chunks      └──────────────┘
└─────────────────────┘                                    └──────────────────────┘
```

- Backend is **stateless**: each request carries the full `messages` array (client-side history). No DB, no in-memory session store.
- Frontend calls the backend over SSE and renders streamed tokens incrementally.
- AWS credentials + region + model id supplied to the backend purely via environment variables.

## Backend (`/backend`)

**Stack:** FastAPI, uvicorn, boto3, pydantic, python-dotenv.

Files:
- `backend/app/main.py` — FastAPI app, CORS middleware (allow frontend origin), health check `GET /api/health`.
- `backend/app/bedrock.py` — thin wrapper around `boto3.client("bedrock-runtime").converse_stream(...)`. Maps our `[{role, content}]` history to the Bedrock Converse `messages` shape, pulls system prompt out separately, yields text deltas from the `contentBlockDelta` events.
- `backend/app/routes/chat.py` — `POST /api/chat`:
  - Request body (pydantic): `{ messages: [{role: "user"|"assistant", content: str}], system?: str }`.
  - Returns `StreamingResponse(media_type="text/event-stream")` that yields SSE frames (`data: {"delta": "..."}\n\n`) and a terminal `data: [DONE]\n\n`.
  - Wrap Bedrock errors and emit an SSE `data: {"error": "..."}` frame so the UI can show a friendly message.
- `backend/app/config.py` — settings via env: `AWS_REGION`, `BEDROCK_MODEL_ID`, `MAX_TOKENS`, `TEMPERATURE`, `ALLOWED_ORIGIN`. AWS creds come from the standard chain (`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/`AWS_SESSION_TOKEN` or a mounted profile).
- `backend/requirements.txt`
- `backend/Dockerfile` — `python:3.12-slim`, install deps, run `uvicorn app.main:app --host 0.0.0.0 --port 8000`.

Why Converse API: it normalises message format and streaming across Bedrock model families, so swapping the model is a one-line env change with no code rewrite.

## Frontend (`/frontend`)

**Stack:** Vite + React + TypeScript, Tailwind CSS + ShadCN UI.

Setup:
- Scaffold `npm create vite@latest` (react-ts), add Tailwind, init ShadCN, add components: `button`, `textarea`, `scroll-area`, `card`, `avatar` (and `skeleton` for loading).
- `frontend/src/App.tsx` — the single chat page (no router needed).
- `frontend/src/components/ChatWindow.tsx` — message list (user vs assistant bubbles, markdown rendering for assistant via `react-markdown`), auto-scroll to bottom.
- `frontend/src/components/MessageInput.tsx` — ShadCN `Textarea` + send button; Enter to send, Shift+Enter for newline; disabled while streaming.
- `frontend/src/hooks/useChatStream.ts` — holds `messages` in React state (client-side history), POSTs to the backend, reads the SSE stream via `fetch` + `ReadableStream`/`TextDecoder`, appends deltas to the in-progress assistant message. Optional `localStorage` persistence so a refresh keeps the chat.
- Backend base URL via `VITE_API_BASE_URL`, defaulting to the docker-compose service URL.
- `frontend/Dockerfile` — multi-stage: build static assets with Node, then serve them with **nginx** on port 80 (lightweight; nginx also proxies `/api` to the backend to sidestep CORS in the container setup).

UI: clean ChatGPT-style layout — centered conversation column, sticky input at bottom, header with app name, "Stop" button while streaming, and a "New chat" button that clears state.

## Containerisation (root)

- `docker-compose.yml` — two services:
  - `backend` (port 8000) — env passes `AWS_REGION`, `BEDROCK_MODEL_ID`, AWS creds, `ALLOWED_ORIGIN`.
  - `frontend` (port 3000 → nginx :80) — nginx serves the static SPA and reverse-proxies `/api/*` to the `backend` service, so the browser only ever talks to one origin (no CORS issues).
- `.env.example` — documents all required env vars (AWS creds, region, model id).
- `.dockerignore` files for each service.
- `README.md` — prerequisites (AWS account with Bedrock model access **enabled in the chosen region**), how to set env, `docker compose up --build`, and how to swap the model.

## Key risks / notes

- **Bedrock model access** must be explicitly enabled in the AWS console for the chosen region, and the IAM principal needs `bedrock:InvokeModelWithResponseStream` (Converse stream). README will call this out.
- **SSE through the browser:** using `fetch` + streaming reader (not `EventSource`, since we need POST with a body).
- **CORS:** backend allows the frontend origin explicitly.
- Model id is fully env-driven, so switching to Nova, Llama, or a Custom Model Import (if Gemma is later imported) needs no code change.

## Verification

1. `cp .env.example .env` and fill AWS creds + region + model id.
2. `docker compose up --build` → frontend on http://localhost:3000, backend on http://localhost:8000.
3. `curl http://localhost:8000/api/health` → `{"status":"ok"}`.
4. `curl -N -X POST http://localhost:8000/api/chat -H 'content-type: application/json' -d '{"messages":[{"role":"user","content":"Say hi in 3 words"}]}'` → observe streamed `data:` SSE frames ending in `[DONE]`.
5. In the browser: type a message → tokens stream in live; multi-turn context works (history sent each request); "New chat" clears the thread; refresh behaviour matches the chosen localStorage option.
6. Error path: set a bad `BEDROCK_MODEL_ID` → UI shows a friendly error rather than hanging.

## Suggested build order

1. Backend: config + Bedrock Converse wrapper + `/api/chat` SSE + health. Verify with curl.
2. Dockerise backend.
3. Frontend: scaffold Vite + React + Tailwind + ShadCN, build chat UI + SSE hook against the running backend.
4. Dockerise frontend + `docker-compose.yml` + `.env.example` + README.
5. End-to-end verification.
