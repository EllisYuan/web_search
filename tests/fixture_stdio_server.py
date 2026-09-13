"""Offline-only bootstrap for a real stdio MCP client; never contacts Tavily."""

import asyncio
import json

import httpx

from web_search.server import read_api_key, serve


def respond(request: httpx.Request) -> httpx.Response:
    assert request.method == "POST"
    assert str(request.url) == "https://api.tavily.com/search"
    query = json.loads(request.content)["query"]
    if query == "fixture-401":
        # Deliberately reflect the credential to exercise safe error handling.
        return httpx.Response(401, json={"error": request.headers["authorization"]})
    return httpx.Response(
        200,
        json={
            "results": [
                {
                    "title": "受控 Search fixture",
                    "url": "https://example.org/source",
                    "content": "Offline SERP metadata",
                    "score": 0.8,
                    "published_date": "2026-09-13",
                }
            ]
        },
    )


if __name__ == "__main__":
    asyncio.run(serve(read_api_key(), transport=httpx.MockTransport(respond)))
