"""Exa gateway web provider registration."""

from agent.web_search_provider import WebSearchProvider


def register(ctx) -> None:
    from .provider import ExaGatewayWebSearchProvider

    ctx.register_web_search_provider(ExaGatewayWebSearchProvider())
