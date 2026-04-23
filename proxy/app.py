import json
import os

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response

app = FastAPI(title="paper-organizer-proxy")

_OR_KEY = os.environ["OPENROUTER_API_KEY"]
_MASTER_KEY = os.environ["MASTER_KEY"]

# VIRTUAL_KEYS env var: comma-separated keys, e.g. "sk-alice-xxx,sk-bob-yyy"
_virtual = {k.strip() for k in os.environ.get("VIRTUAL_KEYS", "").split(",") if k.strip()}
_valid = _virtual | {_MASTER_KEY}

_OR_BASE = "https://openrouter.ai/api/v1"
_OR_HEADERS = {
    "HTTP-Referer": "https://github.com/YHHuan/paper_organizer",
    "X-Title": "paper-organizer",
}

_ALIASES = {
    "fast": "openai/gpt-4o-mini",
    "smart": "anthropic/claude-sonnet-4-6",
    "gemini-fast": "google/gemini-flash-2.0-exp",
}


def _auth(request: Request) -> None:
    token = request.headers.get("Authorization", "")[7:].strip()
    if token not in _valid:
        raise HTTPException(status_code=401, detail="Invalid key")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/v1/models")
async def models(request: Request):
    _auth(request)
    return {
        "object": "list",
        "data": [{"id": k, "object": "model"} for k in _ALIASES],
    }


@app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(path: str, request: Request):
    _auth(request)

    body = await request.body()

    # Resolve model alias (fast / smart / gemini-fast)
    if body:
        try:
            data = json.loads(body)
            if data.get("model") in _ALIASES:
                data["model"] = _ALIASES[data["model"]]
                body = json.dumps(data).encode()
        except (json.JSONDecodeError, KeyError):
            pass

    headers = {"Authorization": f"Bearer {_OR_KEY}", **_OR_HEADERS}
    if ct := request.headers.get("content-type"):
        headers["content-type"] = ct

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.request(
            method=request.method,
            url=f"{_OR_BASE}/{path}",
            content=body,
            headers=headers,
        )

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type", "application/json"),
    )
