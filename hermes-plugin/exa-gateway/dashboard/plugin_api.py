# ~/.hermes/plugins/exa-gateway/dashboard/plugin_api.py
"""Exa Gateway dashboard backend — key management + stats.

Keys live in ~/.hermes/plugins/web/exa-gw/keys.json (same file the web
provider reads). This API only manages keys and reports usage; actual
search/extract round-robin happens inside the provider.

Routes:
    GET    /api/plugins/exa-gateway/health      — account count + status
    GET    /api/plugins/exa-gateway/accounts    — per-account usage
    POST   /api/plugins/exa-gateway/keys        — add an API key
    DELETE /api/plugins/exa-gateway/keys/{id}   — remove an API key
"""
import json
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter()

KEYS_FILE = Path(os.path.expanduser("~/.hermes/plugins/exa-gateway/keys.json"))
STATS_FILE = Path(os.path.expanduser("~/.hermes/plugins/exa-gateway/stats.json"))


def _load_keys() -> list[dict]:
    if not KEYS_FILE.exists():
        return []
    try:
        return json.loads(KEYS_FILE.read_text())
    except Exception:
        return []


def _load_stats() -> dict:
    if not STATS_FILE.exists():
        return {}
    try:
        return json.loads(STATS_FILE.read_text())
    except Exception:
        return {}


def _save_keys(keys: list[dict]) -> None:
    KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)
    KEYS_FILE.write_text(json.dumps(keys, indent=2))
    try:
        os.chmod(KEYS_FILE, 0o600)
    except Exception:
        pass


@router.get("/health")
async def health():
    keys = _load_keys()
    return {"accounts": len(keys), "status": "ok" if keys else "no-keys"}


@router.get("/accounts")
async def accounts():
    keys = _load_keys()
    stats = _load_stats()
    out = {}
    for i, k in enumerate(keys):
        account_id = f"{i}:{k['id'][:12]}"
        s = stats.get(account_id, {})
        out[account_id] = {
            "id": k["id"][:12],
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
    keys = _load_keys()
    keys.append({"id": key, "key": key})
    _save_keys(keys)
    return {"ok": True, "accounts": len(keys)}


@router.delete("/keys/{account_id}")
async def remove_key(account_id: str):
    keys = _load_keys()
    idx = int(account_id.split(":")[0])
    if 0 <= idx < len(keys):
        keys.pop(idx)
        _save_keys(keys)
        return {"ok": True, "accounts": len(keys)}
    raise HTTPException(status_code=404, detail="Account not found")
