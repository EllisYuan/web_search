"""Shared MCP session harness: real client/server session, fixtures only at the HTTP edge."""

from collections.abc import AsyncIterator, Callable, Coroutine
from contextlib import asynccontextmanager
from typing import Any

import httpx
from mcp import ClientSession
from mcp.shared.memory import create_connected_server_and_client_session

from web_search.server import create_server

DUMMY_KEY = "dummy-secret-for-contract-tests"

Handler = (
    Callable[[httpx.Request], httpx.Response]
    | Callable[[httpx.Request], Coroutine[None, None, httpx.Response]]
)


@asynccontextmanager
async def connected(
    handler: Handler | httpx.AsyncBaseTransport,
    *,
    api_key: str | None = DUMMY_KEY,
    timeout_seconds: float | None = None,
    **server_options: Any,
) -> AsyncIterator[ClientSession]:
    transport = (
        handler if isinstance(handler, httpx.AsyncBaseTransport) else httpx.MockTransport(handler)
    )
    async with httpx.AsyncClient(transport=transport, trust_env=False) as http:
        options: dict[str, Any] = {}
        if timeout_seconds is not None:
            options["timeout_seconds"] = timeout_seconds
        server = create_server(api_key=api_key, http=http, **options, **server_options)
        async with create_connected_server_and_client_session(server) as session:
            yield session
