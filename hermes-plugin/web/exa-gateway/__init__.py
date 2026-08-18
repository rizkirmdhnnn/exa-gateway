"""Exa multi-account gateway web search + extract plugin.

Routes Hermes web_search / web_extract through a local exa-gateway server
that round-robins across N Exa API keys, so one stable endpoint consumes
multiple free-tier accounts. Backed by plain HTTP (httpx) — no Exa SDK.
"""

from __future__ import annotations

from .provider import ExaGatewayWebSearchProvider


def register(ctx) -> None:
    """Register the exa-gateway provider with the plugin context."""
    ctx.register_web_search_provider(ExaGatewayWebSearchProvider())
