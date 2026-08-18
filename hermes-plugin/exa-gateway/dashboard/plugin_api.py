# ~/.hermes/plugins/exa-gateway/dashboard/plugin_api.py
"""Exa Gateway dashboard backend — key management + stats.

Keys and stats live in the shared SQLite db (exa_gateway.db, see db.py),
read/written by both this dashboard API and the web provider.

NOTE: the dashboard loads plugin_api.py as a standalone module via
importlib.spec_from_file_location — relative imports don't work here.
db.py is loaded directly by path.

Routes:
    GET    /api/plugins/exa-gateway/health      — account count + status
    GET    /api/plugins/exa-gateway/accounts    — per-account usage
    POST   /api/plugins/exa-gateway/keys        — add an API key
    DELETE /api/plugins/exa-gateway/keys/{id}   — remove an API key
"""
import importlib.util
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter()

# load db.py directly (standalone module, no package context)
_db_path = Path(__file__).resolve().parent.parent / "db.py"
_spec = importlib.util.spec_from_file_location("exa_gateway_db", _db_path)
_db = importlib.util.module_from_spec(_spec)
sys.modules["exa_gateway_db"] = _db
_spec.loader.exec_module(_db)


@router.get("/health")
async def health():
    keys = _db.list_keys()
    return {"accounts": len(keys), "status": "ok" if keys else "no-keys"}


@router.get("/accounts")
async def accounts():
    keys = _db.list_keys()
    stats = _db.get_stats()
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
    _db.add_key(key)
    return {"ok": True, "accounts": len(_db.list_keys())}


@router.delete("/keys/{account_id}")
async def remove_key(account_id: str):
    idx = int(account_id.split(":")[0])
    removed = _db.remove_key(idx)
    if not removed:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"ok": True, "accounts": len(_db.list_keys())}
