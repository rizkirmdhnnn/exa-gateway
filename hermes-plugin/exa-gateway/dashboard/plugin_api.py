# ~/.hermes/plugins/exa-gateway/dashboard/plugin_api.py
"""Exa Gateway dashboard backend — key management + stats.

Keys and stats live in the shared SQLite db (exa_gateway.db, see db.py),
read/written by both this dashboard API and the web provider.

Routes:
    GET    /api/plugins/exa-gateway/health      — account count + status
    GET    /api/plugins/exa-gateway/accounts    — per-account usage
    POST   /api/plugins/exa-gateway/keys        — add an API key
    DELETE /api/plugins/exa-gateway/keys/{id}   — remove an API key
"""
from fastapi import APIRouter, HTTPException

from .. import db

router = APIRouter()


@router.get("/health")
async def health():
    keys = db.list_keys()
    return {"accounts": len(keys), "status": "ok" if keys else "no-keys"}


@router.get("/accounts")
async def accounts():
    keys = db.list_keys()
    stats = db.get_stats()
    out = {}
    for i, k in enumerate(keys):
        account_id = f"{i}:{k['key'][:12]}"
        s = stats.get(account_id, {})
        out[account_id] = {
            "id": k["key"][:12],
            "requests": s.get("requests", 0),
            "errors": s.get("errors", 0),
            "last_error": s.get("last_error", ""),
            "last_used": s.get("last_used", 0),
        }
    return {"accounts": out}


@router.post("/keys")
async def add_key(body: dict):
    key = (body.get("key") or "").strip()
    if not key or len(key) < 10:
        raise HTTPException(status_code=400, detail="Invalid API key")
    db.add_key(key)
    return {"ok": True, "accounts": len(db.list_keys())}


@router.delete("/keys/{account_id}")
async def remove_key(account_id: str):
    idx = int(account_id.split(":")[0])
    removed = db.remove_key(idx)
    if not removed:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"ok": True, "accounts": len(db.list_keys())}
