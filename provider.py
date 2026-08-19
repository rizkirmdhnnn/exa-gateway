"""Exa multi-account gateway web search provider."""
from __future__ import annotations
import logging
import time
from typing import Any, Dict, List
from agent.web_search_provider import WebSearchProvider
from . import db
logger = logging.getLogger(__name__)
EXA_BASE = "https://api.exa.ai"
RR_INDEX = 0
RETRY_STATUSES = (402, 429, 500, 502, 503)

def _next_key() -> tuple[str, str]:
    global RR_INDEX
    keys = [k for k in db.list_keys() if k.get("enabled", 1)]
    if not keys:
        raise RuntimeError("No Exa API keys configured — add one in the Exa Gateway dashboard tab")
    k = keys[RR_INDEX % len(keys)]; RR_INDEX += 1
    return k["key"], f"key:{k['id']}"

def _request(operation: str, path: str, payload: dict, timeout: int):
    import httpx
    key, account = _next_key(); started = time.monotonic()
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(f"{EXA_BASE}/{path}", json=payload, headers={"x-api-key": key, "Content-Type": "application/json"})
        elapsed = int((time.monotonic() - started) * 1000)
        if resp.status_code in RETRY_STATUSES:
            db.bump_error(account, f"HTTP {resp.status_code}")
            db.record_event(operation, "rate_limited" if resp.status_code == 429 else "error", int(account.split(":")[1]), resp.status_code, elapsed, f"http_{resp.status_code}")
            key, account = _next_key(); started = time.monotonic()
            resp = client.post(f"{EXA_BASE}/{path}", json=payload, headers={"x-api-key": key, "Content-Type": "application/json"})
            elapsed = int((time.monotonic() - started) * 1000)
        if resp.is_error:
            db.bump_error(account, f"HTTP {resp.status_code}")
            db.record_event(operation, "rate_limited" if resp.status_code == 429 else "error", int(account.split(":")[1]), resp.status_code, elapsed, f"http_{resp.status_code}")
        else:
            db.bump_request(account); db.clear_error(account)
            db.record_event(operation, "success", int(account.split(":")[1]), resp.status_code, elapsed)
        resp.raise_for_status()
        return resp.json()

class ExaGatewayWebSearchProvider(WebSearchProvider):
    @property
    def name(self) -> str: return "exa-gateway"
    @property
    def display_name(self) -> str: return "Exa Gateway (multi-account)"
    def is_available(self) -> bool: return any(k.get("enabled",1) for k in db.list_keys())
    def supports_search(self) -> bool: return True
    def supports_extract(self) -> bool: return True
    def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        try:
            from tools.interrupt import is_interrupted
            if is_interrupted(): return {"success": False, "error": "Interrupted"}
            data = _request("search", "search", {"query": query, "numResults": limit, "contents": {"highlights": True}}, 60)
            return {"success": True, "data": {"web": [{"url":r.get("url",""),"title":r.get("title",""),"description":" ".join(r.get("highlights") or []),"position":i+1} for i,r in enumerate(data.get("results",[]))]}}
        except ImportError as exc: return {"success":False,"error":f"httpx not installed: {exc}"}
        except Exception as exc: logger.warning("exa-gateway search error: %s", exc); return {"success":False,"error":"exa-gateway search failed"}
    def extract(self, urls: List[str], **kwargs: Any) -> List[Dict[str, Any]]:
        try:
            data = _request("extract", "contents", {"urls":urls,"text":{"maxCharacters":kwargs.get("char_limit",20000)}}, 90)
            return [{"url":r.get("url", ""),"title":r.get("title", ""),"content":r.get("text") or "","raw_content":r.get("text") or "","metadata":{"sourceURL":r.get("url", ""),"title":r.get("title", "")}} for r in data.get("results",[])]
        except Exception as exc: logger.warning("exa-gateway extract error: %s", exc); return [{"url":u,"title":"","content":"","error":"exa-gateway extract failed"} for u in urls]
    def get_setup_schema(self) -> Dict[str, Any]: return {"name":"Exa Gateway","badge":"self-hosted","tag":"Multi-account Exa search + extract via round-robin.","env_vars":[]}

# Keep testable helper compatibility.
def _record_request(*args, **kwargs): return db.record_event(*args, **kwargs)
