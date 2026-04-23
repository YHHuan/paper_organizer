# paper-organizer FastAPI Proxy

Small FastAPI proxy for sharing one OpenRouter API key behind local virtual keys.

It exposes OpenAI-compatible `/v1/*` routes and rewrites a few short model aliases before forwarding requests to OpenRouter.

## Railway deployment

The Railway service should use:

- Root directory: `proxy/`
- Builder: Dockerfile
- Healthcheck path: `/health`
- Public domain target port: the same port shown in the deploy log, e.g. `8080`

Do not set `PORT=8000` for this service. Railway injects `PORT`, and the container starts Uvicorn on `0.0.0.0:$PORT`.

If `/health` passes internally but the public domain returns `502 Application failed to respond`, check the public domain target port first. In Railway, open:

`Service -> Settings -> Networking -> Public Networking -> domain edit`

Then set the target port to the port in the Uvicorn log, for example:

```text
INFO: Uvicorn running on http://0.0.0.0:8080
```

## Environment variables

Set these in Railway:

| Variable | Value |
|---|---|
| `OPENROUTER_API_KEY` | Owner OpenRouter key, usually `sk-or-...` |
| `MASTER_KEY` | Admin/shared proxy key |
| `VIRTUAL_KEYS` | Optional comma-separated user keys |

`MASTER_KEY` and any key listed in `VIRTUAL_KEYS` can call `/v1/*`.

## Health check

```bash
curl https://your-proxy.up.railway.app/health
```

Expected response:

```json
{"status":"ok"}
```

## Usage

```python
from openai import OpenAI

client = OpenAI(
    api_key="sk-user-or-master-key",
    base_url="https://your-proxy.up.railway.app/v1",
)

resp = client.chat.completions.create(
    model="smart",
    messages=[{"role": "user", "content": "Summarize this paper."}],
)
```

## Model aliases

| Alias | Routes to |
|---|---|
| `fast` | `openai/gpt-4o-mini` |
| `smart` | `anthropic/claude-sonnet-4-6` |
| `gemini-fast` | `google/gemini-flash-2.0-exp` |

Requests with other model names are forwarded unchanged to OpenRouter.
