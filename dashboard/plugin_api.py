"""Authenticated dashboard API for Exa Gateway management."""
import importlib.util, re, sys, time
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
router = APIRouter()
_db_path = Path(__file__).resolve().parent.parent / "db.py"
_spec = importlib.util.spec_from_file_location("exa_gateway_db", _db_path)
_db = importlib.util.module_from_spec(_spec); sys.modules["exa_gateway_db"] = _db; _spec.loader.exec_module(_db)
_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")

def _key_id(value):
    try: value=int(value)
    except (TypeError, ValueError): raise HTTPException(400, "Invalid key ID")
    if value <= 0: raise HTTPException(400, "Invalid key ID")
    return value

@router.get("/health")
async def health():
    keys=_db.list_key_summaries(); return {"accounts":len(keys),"enabled_accounts":sum(k["enabled"] for k in keys),"status":"ok" if keys else "no-keys"}

@router.get("/summary")
async def summary(days: int = Query(30, ge=1, le=365)):
    now=int(time.time()); s=_db.event_summary(now-days*86400,now); keys=_db.list_key_summaries(); s.update({"total_accounts":len(keys),"healthy_accounts":sum(k["last_status"]=="healthy" for k in keys),"disabled_accounts":sum(not k["enabled"] for k in keys)}); return s

@router.get("/accounts")
async def accounts():
    return {"accounts": {f"key:{k['id']}": k for k in _db.list_key_summaries()}}

@router.get("/events")
async def events(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), operation: str|None=None, status: str|None=None):
    return {"events":_db.recent_events(limit, offset, operation, status),"limit":limit,"offset":offset}

@router.get("/activity")
async def activity(days: int = Query(1, ge=1, le=365)):
    now=int(time.time()); return {"activity":_db.hourly_activity(now-days*86400,now)}

@router.get("/settings")
async def settings(): return {"retention_days":int(_db.get_setting("retention_days","30")),"max_events":int(_db.get_setting("max_events","10000"))}

@router.post("/keys")
async def add_key(body: dict):
    key=(body.get("key") or "").strip()
    if not _UUID.fullmatch(key): raise HTTPException(400,"Invalid API key")
    _db.add_key(key); return {"ok":True,"accounts":len(_db.list_keys())}

@router.post("/keys/{key_id}/enable")
async def enable(key_id: int):
    if not _db.set_key_enabled(_key_id(key_id),True): raise HTTPException(404,"Account not found")
    return {"ok":True}

@router.post("/keys/{key_id}/disable")
async def disable(key_id: int):
    if not _db.set_key_enabled(_key_id(key_id),False): raise HTTPException(404,"Account not found")
    return {"ok":True}

@router.delete("/keys/{account_id}")
async def remove_key(account_id: str):
    if not account_id.startswith("key:"): raise HTTPException(400,"Invalid account ID")
    if not _db.remove_key_id(_key_id(account_id[4:])): raise HTTPException(404,"Account not found")
    return {"ok":True,"accounts":len(_db.list_keys())}

@router.post("/events/prune")
async def prune():
    n=_db.prune_events(int(_db.get_setting("retention_days","30")),int(_db.get_setting("max_events","10000"))); return {"ok":True,"removed":n}

@router.get("/export")
async def export(days: int = Query(30, ge=1, le=365)):
    return {"days":days,"accounts":_db.account_export(int(time.time())-days*86400)}

@router.post("/settings")
async def update_settings(body: dict):
    for name, lo, hi in (("retention_days",1,365),("max_events",100,100000)):
        if name in body:
            try: value=int(body[name])
            except (TypeError,ValueError): raise HTTPException(400,f"Invalid {name}")
            if not lo<=value<=hi: raise HTTPException(400,f"Invalid {name}")
            _db.set_setting(name,str(value))
    return await settings()

@router.post("/test-key/{key_id}")
async def test_key(key_id: int):
    key_id=_key_id(key_id); key=_db.key_by_id(key_id)
    if not key: raise HTTPException(404,"Account not found")
    started=time.monotonic()
    try:
        import httpx
        with httpx.Client(timeout=30) as client: response=client.post("https://api.exa.ai/search",json={"query":"test","numResults":1},headers={"x-api-key":key["key"]})
        latency=int((time.monotonic()-started)*1000); status="healthy" if response.is_success else ("rate_limited" if response.status_code==429 else "upstream_error")
        _db.update_key_check(key_id,status,latency,"" if response.is_success else status); _db.record_event("key_test","success" if response.is_success else "error",key_id,response.status_code,latency,status if not response.is_success else "")
        return {"ok":response.is_success,"status":status,"latency_ms":latency,"checked_at":int(time.time())}
    except Exception:
        latency=int((time.monotonic()-started)*1000); _db.update_key_check(key_id,"upstream_error",latency,"upstream_error"); _db.record_event("key_test","error",key_id,0,latency,"upstream_error"); return {"ok":False,"status":"upstream_error","latency_ms":latency,"checked_at":int(time.time())}
