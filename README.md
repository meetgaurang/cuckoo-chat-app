# Cuckoo Chat 🐦

A ChatGPT-style demo chat app that streams responses from **Google Gemma**
via **OpenRouter**.

- **Frontend:** Vite + React + TypeScript + Tailwind + ShadCN-style UI
- **Backend:** Python + FastAPI, streaming via SSE
- **Model:** OpenRouter `google/gemma-4-31b-it:free` (OpenAI-compatible chat completions)
- **No database** — conversation history lives client-side (localStorage)
- **Serverless** — Lambda + S3/CloudFront, scales to zero (pay per request)

```
browser ──/api──▶ Lambda Function URL (FastAPI via Web Adapter) ──stream──▶ OpenRouter
   └──────/*─────▶ CloudFront ──▶ S3 (static frontend)
```

The browser calls the Lambda Function URL directly (CORS-enabled) so SSE streaming
isn't buffered by CloudFront; CloudFront just serves the static frontend from S3.

## Prerequisites

- An OpenRouter account and API key — create one at <https://openrouter.ai/keys>.
  The default model is on OpenRouter's free tier.
- For local dev: Python 3.12 and Node.js. **No Docker needed.**

## Local development

No Docker, no nginx — just two processes.

### One-time setup

```bash
# backend
cd backend
cp .env.example .env                  # then set OPENROUTER_API_KEY
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# frontend
cd ../frontend
npm install
```

### Run it

**Backend** (terminal 1):

```bash
cd backend
./dev.sh                              # uvicorn with --reload on :8000
```

**Frontend** (terminal 2):

```bash
cd frontend
npm run dev                           # http://localhost:5173, proxies /api to :8000
```

Open <http://localhost:5173>. The Vite dev server proxies `/api` to the backend,
so the browser sees a single origin (no CORS) — the same backend runtime used in
production.

> **`dev.sh` vs `run.sh`:** both start the same FastAPI app with uvicorn.
> `dev.sh` is for local use (autoreload, port 8000). `run.sh` is the **production
> entrypoint** that AWS Lambda invokes via the Web Adapter (no reload, port 8080) —
> you never run it by hand; `deploy.sh` wires it up.

## Deploy to AWS

The whole stack is serverless and scales to zero (≈$0 when idle):

- **Backend** → Lambda. FastAPI runs unchanged under the
  [AWS Lambda Web Adapter](https://github.com/awslabs/aws-lambda-web-adapter),
  which runs your real `uvicorn` and preserves SSE streaming via a
  response-streaming Function URL. The frontend calls this URL directly
  (CORS is enabled on the Function URL).
- **Frontend** → S3, served through CloudFront. `deploy.sh` bakes the Function URL
  into the build via `VITE_API_BASE_URL`.

```bash
cd backend && cp .env.example .env   # set OPENROUTER_API_KEY (one-time)
cd .. && ./deploy.sh
```

`deploy.sh` builds the Lambda (`sam build`), deploys the stack
([infra/template.yaml](infra/template.yaml)), then builds the frontend, syncs it
to S3, and invalidates the CloudFront cache. It prints the public URL at the end.

> **No Docker.** The backend build ([backend/Makefile](backend/Makefile), wired in
> via `Metadata: BuildMethod: makefile`) installs prebuilt Linux/arm64 wheels with
> `pip`, so `sam build` needs no container. If you ever add a dependency without a
> prebuilt arm64 wheel, switch that build back to `sam build --use-container`.

**Requirements:** AWS CLI (configured), SAM CLI, Node, Python 3 + pip.

**Region:** the default LWA layer ARN in the template is for `us-east-1`. To deploy
elsewhere, pass a matching layer ARN, e.g.:

```bash
AWS_REGION=eu-west-1 \
LWA_LAYER_ARN=arn:aws:lambda:eu-west-1:753240598075:layer:LambdaAdapterLayerArm64:24 \
./deploy.sh
```

(Find current ARNs in the [LWA releases](https://github.com/awslabs/aws-lambda-web-adapter).)

## Configuration

Backend config is via environment variables (see [backend/.env.example](backend/.env.example)).
Locally these come from `backend/.env`; in AWS they're set on the Lambda by the template.

| Variable | Default | Notes |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | _(required)_ | From <https://openrouter.ai/keys> |
| `OPENROUTER_MODEL` | `google/gemma-4-31b-it:free` | Any OpenRouter model slug |
| `MAX_TOKENS` | `1024` | Max output tokens |
| `TEMPERATURE` | `0.7` | Sampling temperature |
| `ALLOWED_ORIGIN` | `http://localhost:5173` | App-level CORS origin. Unused in prod — the Lambda Function URL handles CORS (allows all origins by default; see [infra/template.yaml](infra/template.yaml)). |

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
  dev.sh             # local entrypoint (uvicorn --reload on :8000)
  run.sh             # Lambda entrypoint (starts uvicorn for the Web Adapter)
  requirements.txt
infra/
  template.yaml      # SAM: Lambda + Function URL + S3 + CloudFront
deploy.sh            # build + deploy backend & frontend
frontend/
  src/
    App.tsx
    components/      # ChatWindow, MessageInput, ui/{button,textarea}
    hooks/useChatStream.ts  # SSE reader + client-side history
docs/plan.md
```
