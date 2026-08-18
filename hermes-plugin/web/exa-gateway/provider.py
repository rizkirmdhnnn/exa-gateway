"""Exa multi-account gateway web search provider.

Calls a local gateway (exa-gateway) that round-robins across N Exa API keys.
Same response shape as the built-in exa provider so Hermes handles results
identically.

Config:
    web:
      backend: exa-gateway
      extract_backend: exa-gateway
Env:
    EXA_GATEWAY_URL=http://<host>:8123
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

from agent.web_search_provider import WebSearchProvider

logger = logging.getLogger(__name__)


def _gateway_url() -> str:
    try:
        from hermes_cli.config import get_env_value

        val = get_env_value("EXA_GATEWAY_URL")
    except Exception:
        val = None
    if val is None:
        val = os.getenv("EXA_GATEWAY_URL", "")
    return (val or "").strip().rstrip("/")


class ExaGatewayWebSearchProvider(WebSearchProvider):
    """Search + extract via the local multi-account Exa gateway."""

    @property
    def name(self) -> str:
        return "exa-gateway"

    @property
    def display_name(self) -> str:
        return "Exa Gateway (multi-account)"

    def is_available(self) -> bool:
        return bool(_gateway_url())

    def supports_search(self) -> bool:
        return True

    def supports_extract(self) -> bool:
        return True

    def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        import httpx

        url = _gateway_url()
        if not url:
            return {"success": False, "error": "EXA_GATEWAY_URL not set"}
        try:
            with httpx.Client(timeout=60) as client:
                resp = client.post(
                    f"{url}/search",
                    json={"query": query, "numResults": limit, "contents": {"highlights": True}},
                )
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
        except Exception as exc:  # noqa: BLE001
            logger.warning("exa-gateway search error: %s", exc)
            return {"success": False, "error": f"exa-gateway search failed: {exc}"}

    def extract(self, urls: List[str], **kwargs: Any) -> List[Dict[str, Any]]:
        import httpx

        url = _gateway_url()
        if not url:
            return [{"url": u, "title": "", "content": "", "error": "EXA_GATEWAY_URL not set"} for u in urls]
        try:
            with httpx.Client(timeout=90) as client:
                resp = client.post(
                    f"{url}/contents",
                    json={"urls": urls, "text": {"maxCharacters": kwargs.get("char_limit", 20000)}},
                )
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
        except Exception as exc:  # noqa: BLE001
            logger.warning("exa-gateway extract error: %s", exc)
            return [{"url": u, "title": "", "content": "", "error": f"exa-gateway extract failed: {exc}"} for u in urls]

    def get_setup_schema(self) -> Dict[str, Any]:
        return {}
