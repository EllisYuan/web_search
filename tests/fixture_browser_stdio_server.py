"""Offline stdio server whose Web Read browser may access only the loopback fixture."""

import asyncio

import httpx
from resource_fixture import contract_capacity

from web_search.resources import AdmissionController
from web_search.server import serve


async def allow_loopback_fixture(_: str) -> bool:
    return True


if __name__ == "__main__":
    asyncio.run(
        serve(
            None,
            transport=httpx.AsyncHTTPTransport(retries=0),
            url_policy=allow_loopback_fixture,
            admission=AdmissionController(capacity=contract_capacity),
        )
    )
