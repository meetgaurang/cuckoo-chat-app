# Cuckoo Chat 🐦

A ChatGPT-style demo chat app that streams responses from **Google Gemma**
via **OpenRouter**.

- **Frontend:** Vite + React + TypeScript + Tailwind + ShadCN-style UI
- **Backend:** Python + FastAPI, streaming via SSE
- **Model:** OpenRouter `google/gemma-4-31b-it:free` (OpenAI-compatible chat completions)
- **No database** — conversation history lives client-side (localStorage)
- **Containerised** with Docker Compose

```
browser ──SSE──▶ nginx (frontend) ──/api──▶ FastAPI (backend) ──stream──▶ OpenRouter
```

## Prerequisites

1. An OpenRouter account and API key — create one at <https://openrouter.ai/keys>.
   The default model is on OpenRouter's free tier.
2. Docker + Docker Compose.

## Run with Docker (recommended)

```bash
cp .env.example .env
# edit .env: set OPENROUTER_API_KEY
docker compose up --build
```

- Frontend: <http://localhost:3000>
- Backend:  <http://localhost:8000> (proxied at `/api` by the frontend's nginx)

## Run locally without Docker

Backend:

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export OPENROUTER_API_KEY=sk-or-...
export OPENROUTER_MODEL=google/gemma-4-31b-it:free
uvicorn app.main:app --reload --port 8000
```

Frontend (in another terminal):

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173, proxies /api to localhost:8000
```

## Configuration

All backend config is via environment variables (see `.env.example`):

| Variable | Default | Notes |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | _(required)_ | From <https://openrouter.ai/keys> |
| `OPENROUTER_MODEL` | `google/gemma-4-31b-it:free` | Any OpenRouter model slug |
| `MAX_TOKENS` | `1024` | Max output tokens |
| `TEMPERATURE` | `0.7` | Sampling temperature |
| `ALLOWED_ORIGIN` | `http://localhost:5173` | CORS origin (dev only; nginx proxies in Docker) |

**Swap the model** by changing `OPENROUTER_MODEL` — no code change needed, since
OpenRouter is OpenAI-compatible (e.g. `google/gemma-4-26b-a4b-it:free`).

## API

`POST /api/chat` — streams `text/event-stream`:

```bash
curl -N -X POST http://localhost:8000/api/chat \
  -H 'content-type: application/json' \
  -d '{"messages":[{"role":"user","content":"Say hi in 3 words"}]}'
```

Frames: `data: {"delta":"..."}` … terminated by `data: [DONE]`.
Errors arrive as `data: {"error":"..."}`.

`GET /api/health` — `{"status":"ok","provider":"openrouter","model":...}`

## Project layout

```
backend/
  app/
    main.py          # FastAPI app + CORS + /api/health
    config.py        # env-driven settings
    openrouter.py    # OpenRouter streaming chat-completions wrapper
    routes/chat.py   # POST /api/chat → SSE
  Dockerfile
frontend/
  src/
    App.tsx
    components/      # ChatWindow, MessageInput, ui/{button,textarea}
    hooks/useChatStream.ts  # SSE reader + client-side history
  Dockerfile         # multi-stage: build → nginx
  nginx.conf         # serves SPA + proxies /api (SSE-friendly)
docker-compose.yml
docs/plan.md
```
