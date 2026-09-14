"""One Tavily Search attempt, preserving upstream candidate order."""

import asyncio
import math
import re
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
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


def failure(
    query: str,
    category: str,
    message: str,
    *,
    retry_after_seconds: float | None = None,
) -> dict[str, Any]:
    error: dict[str, Any] = {"category": category, "message": message}
    if retry_after_seconds is not None:
        error["retry_after_seconds"] = retry_after_seconds
    return {"query": query, "status": "error", "error": error}


_DAY = r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)"
_MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
_TIME = r"[0-9]{2}:[0-9]{2}:[0-9]{2}"
_HTTP_DATE = re.compile(
    rf"(?:{_DAY}, [0-9]{{2}} {_MONTH} [0-9]{{4}} {_TIME} GMT"
    rf"|(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday), "
    rf"[0-9]{{2}}-{_MONTH}-[0-9]{{2}} {_TIME} GMT"
    rf"|{_DAY} {_MONTH} (?: [0-9]|[0-9]{{2}}) {_TIME} [0-9]{{4}})"
)


def parse_retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.strip()
    if value.isascii() and value.isdigit():
        seconds = float(value)
        return seconds if math.isfinite(seconds) else None
    # The email parser also accepts non-HTTP dates, missing zones and trailing text.
    if not _HTTP_DATE.fullmatch(value):
        return None
    try:
        retry_at = parsedate_to_datetime(value)
        if retry_at.tzinfo is None:  # HTTP's obsolete asctime form is implicitly GMT.
            retry_at = retry_at.replace(tzinfo=UTC)
        now = datetime.fromtimestamp(time.time(), UTC)
        return max(0.0, (retry_at - now).total_seconds())
    except (ValueError, TypeError, OverflowError):
        return None


async def search(
    http: httpx.AsyncClient,
    *,
    api_key: str,
    body: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    """Never raise for an upstream problem: one query's failure stays that query's error."""
    query = body["query"]
    try:
        return await _attempt(http, api_key=api_key, body=body, timeout_seconds=timeout_seconds)
    except asyncio.CancelledError:
        raise
    except Exception:
        # Exception text can quote the request, so it is logged nowhere and returned nowhere.
        return failure(query, "upstream_error", "The Tavily Search attempt failed unexpectedly.")


async def _attempt(
    http: httpx.AsyncClient,
    *,
    api_key: str,
    body: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    query = body["query"]
    try:
        # HTTPX timeouts cover phases; this deadline bounds the whole wait for the response,
        # including a body that trickles in. Parsing below is CPU-bound, which no asyncio
        # deadline can interrupt, but its input is already bounded by this wait.
        async with asyncio.timeout(timeout_seconds):
            response = await http.post(
                "https://api.tavily.com/search",
                headers={"Authorization": f"Bearer {api_key}"},
                json=body,
                timeout=timeout_seconds,
                follow_redirects=False,
            )
    except (TimeoutError, httpx.TimeoutException):
        return failure(query, "timeout_error", "The Tavily Search attempt exceeded its deadline.")
    except httpx.RequestError:
        return failure(query, "network_error", "Could not complete the connection to Tavily.")
    retry_after_seconds = parse_retry_after(response.headers.get("Retry-After"))
    if response.status_code == 400:
        return failure(
            query,
            "invalid_request",
            "Tavily rejected this Search request as invalid. Check the parameter values and "
            "their combination, for example country with a non-general topic.",
            retry_after_seconds=retry_after_seconds,
        )
    if response.status_code == 401:
        return failure(
            query,
            "invalid_or_missing_key",
            "Tavily rejected the API key. Check TAVILY_API_KEY in the MCP client configuration.",
            retry_after_seconds=retry_after_seconds,
        )
    if response.status_code == 429:
        return failure(
            query,
            "rate_limited",
            "Tavily rate limited this Search request (HTTP 429).",
            retry_after_seconds=retry_after_seconds,
        )
    if response.status_code == 432:
        return failure(
            query,
            "quota_exhausted",
            "Tavily rejected this Search request: plan_limit_exceeded (HTTP 432). "
            "Check the Tavily account plan limit.",
            retry_after_seconds=retry_after_seconds,
        )
    if response.status_code == 433:
        return failure(
            query,
            "quota_exhausted",
            "Tavily rejected this Search request: payg_limit_exceeded (HTTP 433). "
            "Check the Tavily account PAYG limit.",
            retry_after_seconds=retry_after_seconds,
        )
    if response.status_code != 200:
        return failure(
            query,
            "upstream_error",
            f"Tavily returned HTTP {response.status_code}.",
            retry_after_seconds=retry_after_seconds,
        )
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
