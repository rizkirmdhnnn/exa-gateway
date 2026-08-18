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

# per-account health: keyed by "<index>:<key-prefix>" so identical keys
# (same account duplicated in tests) still get separate tracking slots.
ACCOUNTS = {f"{i}:{k[:12]}": {"status": "ok", "error_count": 0, "last_error": "", "last_used": 0, "requests": 0} for i, k in enumerate(KEYS)}


def next_key() -> tuple[str, str]:
    """Pick next healthy key round-robin; if all unhealthy, reset.
    Returns (key, account_id) where account_id = "<index>:<prefix>"."""
    global RR_INDEX
    n = len(KEYS)
    if n == 0:
        raise RuntimeError("No EXA keys configured")
    for _ in range(n):
        idx = RR_INDEX % n
        RR_INDEX += 1
        key = KEYS[idx]
        account_id = f"{idx}:{key[:12]}"
        info = ACCOUNTS[account_id]
        # skip accounts with many consecutive errors
        if info["error_count"] >= 5:
            continue
        return key, account_id
    # all marked unhealthy — reset and return the next anyway
    RR_INDEX = 0
    key = KEYS[0]
    return key, f"0:{key[:12]}"


async def proxy_to_exa(path: str, body: bytes, headers: dict) -> Response:
    """Forward request to Exa with a selected key, translate errors."""
    key, account_id = next_key()
    ACCOUNTS[account_id]["last_used"] = int(time.time())
    ACCOUNTS[account_id]["requests"] += 1

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
            ACCOUNTS[account_id]["error_count"] += 1
            ACCOUNTS[account_id]["last_error"] = str(e)[:200]
            return Response(json.dumps({"error": str(e)}), status_code=502, media_type="application/json")

    # account-level error handling
    if resp.status_code in (402, 429):
        ACCOUNTS[account_id]["error_count"] += 1
        ACCOUNTS[account_id]["last_error"] = f"HTTP {resp.status_code}: {resp.text[:100]}"
        # try next account (once)
        try:
            return await proxy_to_exa(path, body, headers)
        except Exception:
            pass
    elif resp.status_code < 500:
        ACCOUNTS[account_id]["error_count"] = 0
        ACCOUNTS[account_id]["last_error"] = ""

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
