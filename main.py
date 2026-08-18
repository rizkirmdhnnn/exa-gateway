# exa-gateway — multi-account Exa proxy with round-robin.
# Standalone FastAPI server (optional — most users prefer the in-process
# Hermes plugin). Shares the same SQLite storage (db.py) as the plugin.
#
# Endpoint: POST /search, POST /contents, GET /health, GET /accounts
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import json
import time

import httpx
from fastapi import FastAPI, Request, Response

from db import add_key, bump_error, bump_request, clear_error, get_stats, list_keys

app = FastAPI(title="Exa Gateway", version="2.0.0")

EXA_BASE = "https://api.exa.ai"
RR_INDEX = 0


def _next_key() -> tuple[str, str]:
    """Pick next healthy key round-robin; if all unhealthy, reset."""
    global RR_INDEX
    keys = list_keys()
    if not keys:
        raise RuntimeError("No EXA keys configured")
    n = len(keys)
    for _ in range(n):
        idx = RR_INDEX % n
        RR_INDEX += 1
        key = keys[idx]["key"]
        account_id = f"{idx}:{key[:12]}"
        s = get_stats().get(account_id, {})
        if s.get("errors", 0) >= 5:
            continue
        return key, account_id
    RR_INDEX = 0
    key = keys[0]["key"]
    return key, f"0:{key[:12]}"


async def proxy_to_exa(path: str, body: bytes, headers: dict) -> Response:
    """Forward request to Exa with a selected key, translate errors."""
    key, account_id = _next_key()
    bump_request(account_id)

    url = f"{EXA_BASE}{path}"
    fwd_headers = {"x-api-key": key, "Content-Type": "application/json"}

    try:
        payload = json.loads(body)
    except Exception:
        payload = body

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.request("POST", url, json=payload, headers=fwd_headers)
        except httpx.HTTPError as e:
            bump_error(account_id, str(e)[:200])
            return Response(json.dumps({"error": str(e)}), status_code=502, media_type="application/json")

    if resp.status_code in (402, 429, 500, 502, 503):
        bump_error(account_id, f"HTTP {resp.status_code}")
        # try next account (once)
        try:
            key2, account_id2 = _next_key()
            bump_request(account_id2)
            async with httpx.AsyncClient(timeout=60) as client2:
                resp = await client2.request("POST", url, json=payload, headers={"x-api-key": key2, "Content-Type": "application/json"})
        except Exception:
            pass
    else:
        clear_error(account_id)

    return Response(content=resp.content, status_code=resp.status_code, media_type=resp.headers.get("content-type", "application/json"))


@app.post("/search")
async def search(request: Request):
    body = await request.body()
    return await proxy_to_exa("/search", body, dict(request.headers))


@app.post("/contents")
async def contents(request: Request):
    body = await request.body()
    return await proxy_to_exa("/contents", body, dict(request.headers))


@app.get("/health")
async def health():
    keys = list_keys()
    return {"accounts": len(keys), "status": "ok" if keys else "no-keys", "accounts_detail": get_stats()}


@app.get("/accounts")
async def accounts():
    return {"accounts": get_stats()}
