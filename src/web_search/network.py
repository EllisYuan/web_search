"""HTTP transport that binds public-address validation to the actual TCP connection."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
import ssl
from collections.abc import Awaitable, Callable, Iterable

import httpcore
import httpx

Resolver = Callable[[str, int], Awaitable[tuple[str, ...]]]


async def resolve_public_addresses(host: str, port: int) -> tuple[str, ...]:
    try:
        records = await asyncio.to_thread(socket.getaddrinfo, host, port, type=socket.SOCK_STREAM)
    except OSError as error:
        raise httpcore.ConnectError("Host resolution failed") from error
    addresses = tuple(dict.fromkeys(str(record[4][0]) for record in records))
    if not addresses or not all(ipaddress.ip_address(address).is_global for address in addresses):
        raise httpcore.ConnectError("Host did not resolve exclusively to public addresses")
    return addresses


class PinnedPublicNetworkBackend(httpcore.AsyncNetworkBackend):
    """Resolve once, validate every answer, then connect to one of those exact addresses."""

    def __init__(
        self,
        *,
        resolver: Resolver = resolve_public_addresses,
        backend: httpcore.AsyncNetworkBackend | None = None,
    ) -> None:
        self._resolver = resolver
        self._backend = backend or httpcore.AnyIOBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        addresses = await self._resolver(host, port)
        last_error: Exception | None = None
        for address in addresses:
            try:
                return await self._backend.connect_tcp(
                    address,
                    port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except httpcore.ConnectError as error:
                last_error = error
        raise httpcore.ConnectError(
            "Could not connect to a validated public address"
        ) from last_error

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        raise httpcore.ConnectError("Unix sockets are not available to Web Read")

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


class PinnedPublicTransport(httpx.AsyncHTTPTransport):
    """HTTPX transport with TLS SNI preserved while TCP connects to the validated IP."""

    def __init__(self) -> None:
        super().__init__(trust_env=False)
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=ssl.create_default_context(),
            network_backend=PinnedPublicNetworkBackend(),
            max_connections=100,
            max_keepalive_connections=20,
            keepalive_expiry=5.0,
        )
