"""Observe lost MCP responses, including the SDK's post-handler delivery window.

The low-level SDK exposes no public response-delivery hook. Keep this small adapter
at the server boundary and exercise it through real ClientSession requests.
"""

import asyncio
from typing import Any, cast

import anyio
from mcp import types
from mcp.server import Server

from web_search.web_read import WebReadService


class _DeliveryObserver:
    def __init__(self, responder: Any, service: WebReadService, arguments: dict[str, Any]) -> None:
        self.responder = responder
        self.service = service
        self.arguments = arguments
        self.lost = False

    def __getattr__(self, name: str) -> Any:
        return getattr(self.responder, name)

    async def respond(self, response: Any) -> None:
        body = getattr(getattr(response, "root", None), "structuredContent", None)
        if isinstance(body, dict) and "read_id" in body:
            self.arguments = {**self.arguments, "read_id": body["read_id"]}
        try:
            await self.responder.respond(response)
        except (asyncio.CancelledError, anyio.BrokenResourceError, anyio.ClosedResourceError):
            self.lost = True
            await self.service.interrupted(self.arguments, phase="delivery")
            raise


class ReadServer(Server[Any]):
    def __init__(self, service: WebReadService, **kwargs: Any) -> None:
        super().__init__("tavily-web-search", **kwargs)
        self.read_service = service

    async def _handle_request(
        self, message: Any, req: Any, session: Any, lifespan_context: Any, raise_exceptions: bool
    ) -> None:
        if not isinstance(req, types.CallToolRequest) or req.params.name != "web_read":
            await super()._handle_request(message, req, session, lifespan_context, raise_exceptions)
            return
        arguments = req.params.arguments or {}
        observer = _DeliveryObserver(message, self.read_service, arguments)
        try:
            await super()._handle_request(
                cast(Any, observer),
                req,
                session,
                lifespan_context,
                raise_exceptions,
            )
        except asyncio.CancelledError:
            # SDK handles notification cancellation during the handler, but its
            # response send is outside that try block. Do not cancel sibling requests.
            if not message.cancelled:
                raise
        finally:
            # The SDK consumes explicit notification cancellation inside its handler.
            if message.cancelled and not observer.lost:
                await self.read_service.interrupted(arguments, phase="request")
