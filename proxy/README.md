# paper-organizer LiteLLM Proxy

Shared LLM proxy for 3–5 lab members. Routes through OpenRouter (owner's key), enforces per-user monthly budget caps, logs to Postgres.

---

## 1. Deploy to Railway

**Option A — One-click (coming soon)**
[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new)

**Option B — Manual**

1. Push this repo to GitHub (or fork it).
2. In Railway: **New Project → Deploy from GitHub repo** → select your repo.
3. Railway auto-detects `proxy/railway.toml` and builds `proxy/Dockerfile`.
4. Add a **Postgres** add-on: Railway Dashboard → your project → **+ New** → **Database → PostgreSQL**. Railway injects `DATABASE_URL` automatically.

---

## 2. Set environment variables

In Railway Dashboard → your service → **Variables**, add:

| Variable | Value |
|---|---|
| `LITELLM_MASTER_KEY` | Generate with `openssl rand -hex 32` — keep this secret |
| `OPENROUTER_API_KEY` | Your OpenRouter key (starts with `sk-or-`) |
| `DATABASE_URL` | Auto-injected by Railway Postgres add-on |
| `PORT` | `8000` (already in `railway.toml`) |

The proxy is live once the healthcheck at `/health` returns 200.

---

## 3. Generate virtual keys for users

```bash
export LITELLM_MASTER_KEY="your-master-key"
export PROXY_URL="https://your-proxy.up.railway.app"

chmod +x proxy/keygen.sh
./proxy/keygen.sh alice 2.0    # $2/month cap for alice
./proxy/keygen.sh bob   3.0    # $3/month cap for bob
```

The script prints a JSON response containing the virtual key (`sk-...`). Copy the `key` field.

To revoke a key:
```bash
curl -X POST "$PROXY_URL/key/delete" \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"keys": ["sk-..."]}'
```

---

## 4. Share with users

Give each user:
- Their virtual key (`sk-...`)
- The proxy URL: `https://your-proxy.up.railway.app`

**Example usage (OpenAI-compatible):**
```python
from openai import OpenAI

client = OpenAI(
    api_key="sk-...",                              # their virtual key
    base_url="https://your-proxy.up.railway.app",
)

# Use shared aliases (billed to owner's OpenRouter key)
resp = client.chat.completions.create(
    model="smart",   # or "fast", "gemini-fast"
    messages=[{"role": "user", "content": "Summarize this paper..."}],
)

# Or pass-through with their own key (set via header)
resp = client.chat.completions.create(
    model="openai/gpt-4o",
    messages=[...],
    extra_headers={"x-openai-api-key": "sk-their-own-key"},
)
```

---

## Model aliases

| Alias | Routes to |
|---|---|
| `fast` | `openrouter/openai/gpt-4o-mini` |
| `smart` | `openrouter/anthropic/claude-sonnet-4-6` |
| `gemini-fast` | `openrouter/google/gemini-flash-2.0-exp` |
| `openai/*` | Direct OpenAI (user's own key) |
| `anthropic/*` | Direct Anthropic (user's own key) |
| `google/*` | Direct Google AI (user's own key) |
