"""Exa multi-account gateway web search provider.

Round-robins across N Exa API keys stored in SQLite (exa_gateway.db).
Both search and extract call Exa directly with the selected key — no
external server, no dashboard dependency.

Keys + stats live in the shared SQLite db (see db.py), managed from the
Exa Gateway dashboard tab.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from agent.web_search_provider import WebSearchProvider

from . import db

logger = logging.getLogger(__name__)

EXA_BASE = "https://api.exa.ai"
RR_INDEX = 0


def _next_key() -> tuple[str, str]:
    """Round-robin pick a healthy key; returns (key, account_id)."""
    global RR_INDEX
    keys = db.list_keys()
    if not keys:
        raise RuntimeError("No Exa API keys configured — add one in the Exa Gateway dashboard tab")
    n = len(keys)
    for _ in range(n):
        idx = RR_INDEX % n
        RR_INDEX += 1
        k = keys[idx]
        account_id = f"{idx}:{k['key'][:12]}"
        return k["key"], account_id
    RR_INDEX = 0
    return keys[0]["key"], f"0:{keys[0]['key'][:12]}"


class ExaGatewayWebSearchProvider(WebSearchProvider):
    """Search + extract via round-robin across multiple Exa keys."""

    @property
    def name(self) -> str:
        return "exa-gateway"

    @property
    def display_name(self) -> str:
        return "Exa Gateway (multi-account)"

    def is_available(self) -> bool:
        return bool(db.list_keys())

    def supports_search(self) -> bool:
        return True

    def supports_extract(self) -> bool:
        return True

    def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """Execute an Exa search with a round-robin key."""
        try:
            from tools.interrupt import is_interrupted

            if is_interrupted():
                return {"success": False, "error": "Interrupted"}
            import httpx

            key, account_id = _next_key()
            db.bump_request(account_id)

            with httpx.Client(timeout=60) as client:
                resp = client.post(
                    f"{EXA_BASE}/search",
                    json={"query": query, "numResults": limit, "contents": {"highlights": True}},
                    headers={"x-api-key": key, "Content-Type": "application/json"},
                )
                if resp.status_code in (402, 429, 500, 502, 503):
                    db.bump_error(account_id, f"HTTP {resp.status_code}")
                    key2, account_id2 = _next_key()
                    db.bump_request(account_id2)
                    resp = client.post(
                        f"{EXA_BASE}/search",
                        json={"query": query, "numResults": limit, "contents": {"highlights": True}},
                        headers={"x-api-key": key2, "Content-Type": "application/json"},
                    )
                else:
                    db.clear_error(account_id)
                resp.raise_for_status()
                data = resp.json()

            web_results = []
            for i, r in enumerate(data.get("results", [])):
                highlights = r.get("highlights") or []
                web_results.append({
                    "url": r.get("url", ""),
                    "title": r.get("title", ""),
                    "description": " ".join(highlights) if highlights else "",
                    "position": i + 1,
                })
            return {"success": True, "data": {"web": web_results}}
        except ImportError as exc:
            return {"success": False, "error": f"httpx not installed: {exc}"}
        except Exception as exc:  # noqa: BLE001 — surface as failure
            logger.warning("exa-gateway search error: %s", exc)
            return {"success": False, "error": f"exa-gateway search failed: {exc}"}

    def extract(self, urls: List[str], **kwargs: Any) -> List[Dict[str, Any]]:
        """Extract content from URLs with a round-robin key."""
        try:
            from tools.interrupt import is_interrupted

            if is_interrupted():
                return [{"url": u, "error": "Interrupted", "title": ""} for u in urls]
            import httpx

            key, account_id = _next_key()
            db.bump_request(account_id)

            with httpx.Client(timeout=90) as client:
                resp = client.post(
                    f"{EXA_BASE}/contents",
                    json={"urls": urls, "text": {"maxCharacters": kwargs.get("char_limit", 20000)}},
                    headers={"x-api-key": key, "Content-Type": "application/json"},
                )
                if resp.status_code in (402, 429, 500, 502, 503):
                    db.bump_error(account_id, f"HTTP {resp.status_code}")
                    key2, account_id2 = _next_key()
                    db.bump_request(account_id2)
                    resp = client.post(
                        f"{EXA_BASE}/contents",
                        json={"urls": urls, "text": {"maxCharacters": kwargs.get("char_limit", 20000)}},
                        headers={"x-api-key": key2, "Content-Type": "application/json"},
                    )
                else:
                    db.clear_error(account_id)
                resp.raise_for_status()
                data = resp.json()

            results = []
            for r in data.get("results", []):
                content = r.get("text") or ""
                u = r.get("url") or ""
                title = r.get("title") or ""
                results.append({
                    "url": u,
                    "title": title,
                    "content": content,
                    "raw_content": content,
                    "metadata": {"sourceURL": u, "title": title},
                })
            return results
        except ImportError as exc:
            return [{"url": u, "title": "", "content": "", "error": f"httpx not installed: {exc}"} for u in urls]
        except Exception as exc:  # noqa: BLE001
            logger.warning("exa-gateway extract error: %s", exc)
            return [{"url": u, "title": "", "content": "", "error": f"exa-gateway extract failed: {exc}"} for u in urls]

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "Exa Gateway",
            "badge": "self-hosted",
            "tag": "Multi-account Exa search + extract via round-robin (keys managed in dashboard tab).",
            "env_vars": [],
        }
