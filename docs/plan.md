# Plan: Cuckoo Chat — ChatGPT-style demo app

## Context

A ChatGPT-like **demo** chat app that streams responses from an LLM. Built to be
simple to run locally and cheap to host — it deploys serverless and scales to zero.

Decisions confirmed with the user:
- **Frontend:** React + ShadCN-style UI on **Vite (SPA)** — a single-page chat demo
  gains nothing from SSR/routing, so the lighter SPA was chosen.
- **Backend:** Python + FastAPI.
- **Model:** **OpenRouter** (`google/gemma-4-31b-it:free` by default). OpenRouter is
  OpenAI-compatible, so the model is a one-line env change with no code rewrite.
  *(Originally targeted AWS Bedrock; moved to OpenRouter for a simpler, free-tier-friendly path.)*
- **Responses:** **Streaming via SSE** (token-by-token, like ChatGPT).
- **History:** **client-side only** — backend is stateless; the full message list is
  sent on each request and stored in `localStorage`.
- **Scope:** **single chat** thread (no multi-conversation sidebar).
- **No database.**
- **Serverless deploy** — Lambda + S3/CloudFront, no servers to keep running.

## Architecture

Local dev and production share the same backend runtime (uvicorn); only the
front door differs.

```
                    POST /api/chat (SSE)                         OpenAI-compatible
  ┌──────────────┐  ──────────────────────▶ ┌────────────────────┐  /chat/completions  ┌────────────┐
  │ frontend     │                           │ backend            │ ───(stream=True)──▶ │ OpenRouter │
  │ Vite + React │  ◀──────────────────────  │ FastAPI + uvicorn  │ ◀───────────────── │            │
  └──────────────┘   text/event-stream       │ + httpx            │    stream chunks    └────────────┘
                                              └────────────────────┘
```

- Backend is **stateless**: each request carries the full `messages` array. No DB,
  no session store.
- Frontend reads the SSE stream via `fetch` + `ReadableStream` and renders tokens
  incrementally.
- Config (API key, model, inference params) is supplied via environment variables.

## Backend (`/backend`)

**Stack:** FastAPI, uvicorn, httpx, pydantic, pydantic-settings, python-dotenv.

Files:
- `app/main.py` — FastAPI app, CORS middleware, health check `GET /api/health`.
- `app/openrouter.py` — thin wrapper around OpenRouter's OpenAI-compatible
  `/chat/completions` endpoint with `stream=True`; yields text deltas parsed from
  the returned SSE stream.
- `app/routes/chat.py` — `POST /api/chat`:
  - Request body (pydantic): `{ messages: [{role: "user"|"assistant", content: str}], system?: str }`.
  - Returns `StreamingResponse(media_type="text/event-stream")` yielding SSE frames
    (`data: {"delta": "..."}\n\n`) terminated by `data: [DONE]\n\n`.
  - Errors are emitted as an SSE `data: {"error": "..."}` frame so the UI can show
    a friendly message.
- `app/config.py` — env-driven settings: `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`,
  `MAX_TOKENS`, `TEMPERATURE`, `ALLOWED_ORIGIN`.
- `requirements.txt`
- `run.sh` — Lambda entrypoint; starts the same `uvicorn` command used locally so
  the AWS Lambda Web Adapter can proxy invocations to it (preserving SSE streaming).

## Frontend (`/frontend`)

**Stack:** Vite + React + TypeScript, Tailwind CSS + ShadCN-style components.

- `src/App.tsx` — the single chat page (no router needed).
- `src/components/ChatWindow.tsx` — message list (user vs assistant bubbles,
  markdown rendering for assistant via `react-markdown`), auto-scroll.
- `src/components/MessageInput.tsx` — Textarea + send; Enter to send, Shift+Enter
  for newline; disabled while streaming.
- `src/hooks/useChatStream.ts` — holds `messages` in React state (client-side
  history + `localStorage`), POSTs to the backend, reads the SSE stream via
  `fetch` + `ReadableStream`/`TextDecoder`, appends deltas to the in-progress
  assistant message.
- Backend base URL via `VITE_API_BASE_URL` — empty in dev (Vite proxy), set to the
  Lambda Function URL at build time in production.

## Local development (no Docker)

Two processes:
- Backend: `cd backend && uvicorn app.main:app --reload --port 8000` (reads `backend/.env`).
- Frontend: `cd frontend && npm run dev` (`:5173`, proxies `/api` → `:8000`).

The Vite dev proxy means the browser sees a single origin, so no CORS is needed locally.

## Deployment (serverless)

Defined in `infra/template.yaml` (AWS SAM), deployed by `deploy.sh`:

- **Backend → Lambda.** FastAPI runs unchanged under the **AWS Lambda Web Adapter**
  (a layer), which runs `run.sh`'s uvicorn and proxies invocations to it. Exposed via
  a **Function URL** in `RESPONSE_STREAM` mode so SSE streaming is preserved.
- **Frontend → S3 + CloudFront.** Static build is synced to a private S3 bucket served
  through CloudFront (Origin Access Control).
- **API routing:** the browser calls the **Function URL directly** (CORS enabled on the
  URL) rather than via CloudFront — this avoids CloudFront buffering the token stream.
  `deploy.sh` bakes the Function URL into the build via `VITE_API_BASE_URL`.

`deploy.sh`: `sam build --use-container` → `sam deploy` → `npm run build` →
`aws s3 sync` → CloudFront invalidation. Docker is needed *only* by
`sam build --use-container` (to compile native deps for Lambda's arm64 Linux), not
for local dev.

## Key risks / notes

- **SSE through the browser:** uses `fetch` + streaming reader (not `EventSource`,
  since we need POST with a body).
- **Streaming on Lambda:** requires the Web Adapter + `AWS_LWA_INVOKE_MODE=response_stream`
  on a Function URL. Mangum would *not* work here — it buffers responses.
- **CORS:** handled at the Lambda Function URL (allows all origins by default in the
  template; tighten to the CloudFront URL to lock down). The app's `CORSMiddleware`
  covers local/direct use.
- **LWA layer ARN** is region- and version-specific; the template defaults to
  `us-east-1` and is overridable via the `LwaLayerArn` parameter / `LWA_LAYER_ARN` env.
- Model id is fully env-driven — switching OpenRouter models needs no code change.

## Verification

Local:
1. `cd backend && cp .env.example .env` and set `OPENROUTER_API_KEY`.
2. Start backend + frontend (see above).
3. `curl http://localhost:8000/api/health` → `{"status":"ok",...}`.
4. `curl -N -X POST http://localhost:5173/api/chat -H 'content-type: application/json' \
   -d '{"messages":[{"role":"user","content":"Say hi in 3 words"}]}'` → streamed
   `data:` SSE frames ending in `[DONE]` (also exercises the Vite proxy path).
5. Browser at http://localhost:5173: tokens stream live; multi-turn context works;
   "New chat" clears the thread; refresh restores history from localStorage.

Deployed:
6. `./deploy.sh` → open the printed CloudFront URL → chat streams end-to-end.
