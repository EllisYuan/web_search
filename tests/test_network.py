from collections.abc import Iterable

import httpcore
import pytest

from web_search.network import PinnedPublicNetworkBackend


class RecordingBackend(httpcore.AsyncNetworkBackend):
    def __init__(self) -> None:
        self.hosts: list[str] = []

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        self.hosts.append(host)
        return httpcore.AsyncMockStream([])

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        raise AssertionError("unexpected Unix socket")

    async def sleep(self, seconds: float) -> None:
        return None


async def test_network_backend_connects_to_the_exact_validated_address() -> None:
    resolutions: list[tuple[str, int]] = []
    backend = RecordingBackend()

    async def resolver(host: str, port: int) -> tuple[str, ...]:
        resolutions.append((host, port))
        return ("93.184.216.34",)

    pinned = PinnedPublicNetworkBackend(resolver=resolver, backend=backend)
    await pinned.connect_tcp("example.org", 443)

    assert resolutions == [("example.org", 443)]
    assert backend.hosts == ["93.184.216.34"]


async def test_network_backend_never_connects_when_validation_fails() -> None:
    backend = RecordingBackend()

    async def rejected(host: str, port: int) -> tuple[str, ...]:
        raise httpcore.ConnectError("private address")

    pinned = PinnedPublicNetworkBackend(resolver=rejected, backend=backend)
    with pytest.raises(httpcore.ConnectError):
        await pinned.connect_tcp("rebind.example", 80)

    assert backend.hosts == []
