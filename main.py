# exa-gateway — multi-account Exa proxy with round-robin.
# Endpoint: POST /search, POST /contents, GET /health, GET /accounts
import os
import time
import json
import httpx
from typing import Optional
from fastapi import FastAPI, Request, Response
from pydantic import BaseModel

app = FastAPI(title="Exa Gateway", version="1.0.0")

EXA_BASE = "https://api.exa.ai"

def load_keys() -> list[str]:
    """Load EXA_API_KEYS (comma-separated) or EXA_KEY_1..N env vars."""
    keys = [k.strip() for k in os.environ.get("EXA_API_KEYS", "").split(",") if k.strip()]
    if not keys:
        i = 1
        while True:
            k = os.environ.get(f"EXA_KEY_{i}", "").strip()
            if not k:
                break
            keys.append(k)
            i += 1
    return keys

KEYS = load_keys()
RR_INDEX = 0  # round-robin cursor

# per-account health: {key_prefix: {status, error_count, last_error, last_used}}
ACCOUNTS = {k[:12]: {"status": "ok", "error_count": 0, "last_error": "", "last_used": 0, "requests": 0} for k in KEYS}


def next_key() -> str:
    """Pick next healthy key round-robin; if all unhealthy, reset."""
    global RR_INDEX
    n = len(KEYS)
    if n == 0:
        raise RuntimeError("No EXA keys configured")
    for _ in range(n):
        idx = RR_INDEX % n
        RR_INDEX += 1
        key = KEYS[idx]
        info = ACCOUNTS[key[:12]]
        # skip accounts with many consecutive errors
        if info["error_count"] >= 5:
            continue
        return key
    # all marked unhealthy — reset and return the next anyway
    RR_INDEX = 0
    return KEYS[0]


async def proxy_to_exa(path: str, body: bytes, headers: dict) -> Response:
    """Forward request to Exa with a selected key, translate errors."""
    key = next_key()
    prefix = key[:12]
    ACCOUNTS[prefix]["last_used"] = int(time.time())
    ACCOUNTS[prefix]["requests"] += 1

    url = f"{EXA_BASE}{path}"
    # only pass through safe headers; we manage auth and content-type ourselves
    fwd_headers = {"x-api-key": key, "Content-Type": "application/json"}

    # parse body so httpx sends a proper JSON object, not a raw string
    try:
        payload = json.loads(body)
    except Exception:
        payload = body  # pass raw if not JSON

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.request("POST", url, json=payload, headers=fwd_headers)
        except httpx.HTTPError as e:
            ACCOUNTS[prefix]["error_count"] += 1
            ACCOUNTS[prefix]["last_error"] = str(e)[:200]
            return Response(json.dumps({"error": str(e)}), status_code=502, media_type="application/json")

    # account-level error handling
    if resp.status_code in (402, 429):
        ACCOUNTS[prefix]["error_count"] += 1
        ACCOUNTS[prefix]["last_error"] = f"HTTP {resp.status_code}: {resp.text[:100]}"
        # try next account (once)
        try:
            return await proxy_to_exa(path, body, headers)
        except Exception:
            pass
    elif resp.status_code < 500:
        ACCOUNTS[prefix]["error_count"] = 0
        ACCOUNTS[prefix]["last_error"] = ""

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
    return {
        "accounts": len(KEYS),
        "status": "ok" if KEYS else "no-keys",
        "accounts_detail": ACCOUNTS,
    }


@app.get("/accounts")
async def accounts():
    return {"accounts": ACCOUNTS}
