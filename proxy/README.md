# paper-organizer proxy

A minimal FastAPI proxy that lets 3–5 lab members share one OpenRouter key behind individual virtual keys. Runs on Railway (free tier is sufficient for light academic use).

---

## Architecture

```
Lab member's CLI / browser
        │  Authorization: Bearer sk-po-alice-xxxx
        ▼
  Railway proxy (this folder)
        │  resolves alias: smart → anthropic/claude-sonnet-4-6
        │  swaps key:      sk-po-alice-xxxx → sk-or-<owner-key>
        ▼
  OpenRouter API
```

---

## Deploy to Railway (one-time setup)

1. Fork or push this repo to GitHub.
2. In Railway → **New Project → Deploy from GitHub repo** → select this repo.
3. Set **Root directory** to `proxy/`.
4. Railway auto-detects the Dockerfile.
5. Add environment variables (see below).
6. Set the **healthcheck path** to `/health` in Railway → Service → Settings → Deploy.
7. Generate a public domain in Railway → Service → Settings → Networking.

> **Port gotcha**: Railway injects `$PORT` at runtime. Do not set `PORT=8000` yourself — the Dockerfile already handles this. If the public domain returns 502, open the Networking settings and confirm the target port matches the port printed in the Uvicorn startup log.

---

## Environment variables

Set these in Railway → Service → Variables:

| Variable | Value | Notes |
|---|---|---|
| `OPENROUTER_API_KEY` | `sk-or-...` | Your OpenRouter key — never shared with users |
| `MASTER_KEY` | Any long random string | For admin use and testing |
| `VIRTUAL_KEYS` | `sk-po-alice-xxx,sk-po-bob-yyy` | Comma-separated, one per lab member |

---

## Generate a virtual key for a new user

```bash
cd proxy
./keygen.sh alice
# User: alice
# Key: sk-po-alice-<random>
```

1. Copy the printed key.
2. In Railway → Variables, append it to `VIRTUAL_KEYS` (comma-separated).
3. Redeploy (Railway auto-redeploys on variable changes).
4. Send the key to Alice. She enters it during `paper-organizer init`.

---

## Verify the proxy is up

```bash
curl https://your-proxy.up.railway.app/health
# {"status":"ok"}
```

```bash
curl https://your-proxy.up.railway.app/v1/chat/completions \
  -H "Authorization: Bearer sk-po-alice-xxx" \
  -H "Content-Type: application/json" \
  -d '{"model":"fast","messages":[{"role":"user","content":"pong"}],"max_tokens":5}'
```

---

## Model aliases

| Alias | Routes to |
|---|---|
| `fast` | `openai/gpt-4o-mini` (~$0.001/1k tokens) |
| `smart` | `anthropic/claude-sonnet-4-6` (~$0.015/1k tokens) |
| `gemini-fast` | `google/gemini-flash-2.0-exp` (free tier) |

Other model names are forwarded to OpenRouter unchanged.

---

## Cost management

A typical paper ingest (abstract-only) uses ~2 000 tokens on `smart` ≈ **$0.03**. With a daily cap of $3 and per-paper cap of $0.15, the proxy stays within the free OpenRouter tier for light lab use.

Budget limits are enforced client-side in `paper-organizer`'s `BudgetConfig`; the proxy itself does not enforce quotas.
