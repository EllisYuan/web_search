"""Offline stdio bootstrap with real loopback HTTP and a shortened attempt deadline."""

import asyncio

from http_fixture import LoopbackTransport, TavilyHTTPFixture

from web_search.server import read_api_key, serve


async def main() -> None:
    api_key = read_api_key()
    async with TavilyHTTPFixture() as upstream:
        await serve(
            api_key,
            transport=LoopbackTransport(upstream.port, max_connections=20),
            timeout_seconds=0.3,
        )


if __name__ == "__main__":
    asyncio.run(main())
