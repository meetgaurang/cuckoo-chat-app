# Cuckoo Chat 🐦

A ChatGPT-style demo chat app that streams responses from **Google Gemma 3 4B**
running natively on **AWS Bedrock**.

- **Frontend:** Vite + React + TypeScript + Tailwind + ShadCN-style UI
- **Backend:** Python + FastAPI, streaming via SSE
- **Model:** AWS Bedrock `google.gemma-3-4b-it` (Converse / ConverseStream API)
- **No database** — conversation history lives client-side (localStorage)
- **Containerised** with Docker Compose

```
browser ──SSE──▶ nginx (frontend) ──/api──▶ FastAPI (backend) ──ConverseStream──▶ AWS Bedrock
```

## Prerequisites

1. An AWS account with **Bedrock model access enabled** for `google.gemma-3-4b-it`
   in your chosen region (e.g. `us-east-1`). Enable it in the Bedrock console under
   **Model access**.
2. AWS credentials for a principal with these permissions:
   - `bedrock:InvokeModelWithResponseStream`
   - `bedrock:Converse`
   - `bedrock:InvokeModel`
3. Docker + Docker Compose.

> Gemma 3 supports **in-region inference** in us-east-1, us-east-2, us-west-2,
> eu-west-1/2, eu-central-1, ap-south-1, and more. Pick a region where you've
> enabled access.

## Run with Docker (recommended)

```bash
cp .env.example .env
# edit .env: set AWS creds + region
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
export AWS_REGION=us-east-1 BEDROCK_MODEL_ID=google.gemma-3-4b-it
export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=...
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
| `AWS_REGION` | `us-east-1` | Region where Gemma access is enabled |
| `BEDROCK_MODEL_ID` | `google.gemma-3-4b-it` | Any native Bedrock model id |
| `MAX_TOKENS` | `1024` | Max output tokens (Gemma 3 4B supports up to 8K) |
| `TEMPERATURE` | `0.7` | Sampling temperature |
| `ALLOWED_ORIGIN` | `http://localhost:5173` | CORS origin (dev only; nginx proxies in Docker) |

**Swap the model** by changing `BEDROCK_MODEL_ID` — no code change needed thanks
to the Converse API. The backend automatically falls back to a single
(non-streaming) Converse call if a model doesn't support streaming.

## API

`POST /api/chat` — streams `text/event-stream`:

```bash
curl -N -X POST http://localhost:8000/api/chat \
  -H 'content-type: application/json' \
  -d '{"messages":[{"role":"user","content":"Say hi in 3 words"}]}'
```

Frames: `data: {"delta":"..."}` … terminated by `data: [DONE]`.
Errors arrive as `data: {"error":"..."}`.

`GET /api/health` — `{"status":"ok","model":...,"region":...}`

## Project layout

```
backend/
  app/
    main.py        # FastAPI app + CORS + /api/health
    config.py      # env-driven settings
    bedrock.py     # Converse/ConverseStream wrapper (+ non-stream fallback)
    routes/chat.py # POST /api/chat → SSE
  Dockerfile
frontend/
  src/
    App.tsx
    components/    # ChatWindow, MessageInput, ui/{button,textarea}
    hooks/useChatStream.ts  # SSE reader + client-side history
  Dockerfile       # multi-stage: build → nginx
  nginx.conf       # serves SPA + proxies /api (SSE-friendly)
docker-compose.yml
docs/plan.md
```
