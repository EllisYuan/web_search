"""One Tavily Search attempt, preserving upstream candidate order."""

import asyncio
import math
from typing import Any

import httpx
from jsonschema import Draft202012Validator, ValidationError

_RESPONSE = Draft202012Validator(
    {
        "type": "object",
        "required": ["results"],
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["title", "url", "content", "score"],
                    "properties": {
                        "title": {"type": "string"},
                        "url": {"type": "string"},
                        "content": {"type": "string"},
                        "score": {"type": "number"},
                        "published_date": {"type": ["string", "null"]},
                    },
                },
            }
        },
    }
)


def failure(query: str, category: str, message: str) -> dict[str, Any]:
    return {
        "query": query,
        "status": "error",
        "error": {
            "category": category,
            "message": message,
        },
    }


async def search(
    http: httpx.AsyncClient,
    *,
    api_key: str,
    query: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    try:
        # HTTPX timeouts cover phases; this deadline also bounds the entire attempt.
        async with asyncio.timeout(timeout_seconds):
            response = await http.post(
                "https://api.tavily.com/search",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"query": query},
                timeout=timeout_seconds,
                follow_redirects=False,
            )
    except (TimeoutError, httpx.TimeoutException):
        return failure(query, "timeout_error", "The Tavily Search attempt exceeded its deadline.")
    except httpx.RequestError:
        return failure(query, "network_error", "Could not complete the connection to Tavily.")
    if response.status_code == 401:
        return failure(
            query,
            "invalid_or_missing_key",
            "Tavily rejected the API key. Check TAVILY_API_KEY in the MCP client configuration.",
        )
    if response.status_code != 200:
        return failure(query, "upstream_error", f"Tavily returned HTTP {response.status_code}.")
    try:
        payload = response.json()
        _RESPONSE.validate(payload)
        candidates = []
        for rank, item in enumerate(payload["results"], start=1):
            if not math.isfinite(item["score"]):
                raise ValueError("Non-finite score")
            candidate = {key: item[key] for key in ("title", "url", "content", "score")}
            candidate["rank"] = rank
            if item.get("published_date"):
                candidate["published_date"] = item["published_date"]
            if any(api_key in value for value in candidate.values() if isinstance(value, str)):
                raise ValueError("Credential reflected in upstream metadata")
            candidates.append(candidate)
    except (ValueError, ValidationError, OverflowError):
        return failure(query, "upstream_error", "Tavily returned an invalid Search response.")
    return {"query": query, "status": "ok", "candidates": candidates}
