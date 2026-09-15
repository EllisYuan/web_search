"""Production server over real stdio, with explicitly controlled resource probes for smoke."""

import asyncio
import os
from pathlib import Path

import httpx
from mcp.server.stdio import stdio_server

from web_search.resources import AdmissionController, system_capacity
from web_search.server import create_server


async def main() -> None:
    control = Path(os.environ["WEB_READ_SMOKE_CONTROL"])
    artifacts = Path(os.environ["WEB_READ_SMOKE_ARTIFACTS"])
    sources = os.environ["WEB_READ_SMOKE_SOURCES"].split(",")

    async def policy(url: str) -> bool:
        return any(url.startswith(source + "/") for source in sources)

    def capacity(directory: Path) -> tuple[int, int, int]:
        available, rss, disk = system_capacity(directory)
        mode = control.read_text(encoding="utf-8")
        return (0 if mode == "ram" else available, rss, 0 if mode == "disk" else disk)

    async with httpx.AsyncClient(trust_env=False) as http:
        server = create_server(
            api_key=None,
            http=http,
            url_policy=policy,
            artifact_directory=artifacts,
            resource_gate=lambda: control.read_text(encoding="utf-8") != "gate",
            admission=AdmissionController(capacity=capacity),
        )
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
