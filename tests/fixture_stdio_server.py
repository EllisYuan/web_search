"""Offline-only bootstrap for a real stdio MCP client; never contacts Tavily."""

import asyncio
import json

import httpx

from web_search.server import read_api_key, serve


def respond(request: httpx.Request) -> httpx.Response:
    assert request.method == "POST"
    assert str(request.url) == "https://api.tavily.com/search"
    body = json.loads(request.content)
    query = body["query"]
    if query == "fixture-401":
        # Deliberately reflect the credential to exercise safe error handling.
        return httpx.Response(401, json={"error": request.headers["authorization"]})
    if query == "fixture-400":
        return httpx.Response(400, json={"detail": {"error": request.headers["authorization"]}})
    return httpx.Response(
        200,
        json={
            "results": [
                {
                    "title": "受控 Search fixture",
                    # Echo the resolved parameters so a client can see what was actually sent.
                    "url": f"https://example.org/source?depth={body.get('search_depth', 'unset')}",
                    "content": f"Offline SERP metadata for {query}",
                    "score": 0.8,
                    "published_date": "2026-09-13",
                }
            ]
        },
    )


if __name__ == "__main__":
    asyncio.run(serve(read_api_key(), transport=httpx.MockTransport(respond)))
