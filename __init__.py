"""Exa Gateway — all-in-one plugin.

Registers a web search/extract provider (round-robin across multiple Exa
API keys) and ships a dashboard tab for key management + usage stats.
"""

from __future__ import annotations

from .provider import ExaGatewayWebSearchProvider


def register(ctx) -> None:
    """Register the exa-gateway provider with the plugin context."""
    ctx.register_web_search_provider(ExaGatewayWebSearchProvider())
