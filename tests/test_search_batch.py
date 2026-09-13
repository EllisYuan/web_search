"""Search Batch behaviour observed through the public MCP tool call."""

import asyncio
import json
import logging
from typing import Any

import httpx
import pytest
from harness import DUMMY_KEY, connected

from web_search.server import (
    MAX_CONCURRENT_ATTEMPTS,
    SEARCH_PARAMETERS,
    has_valid_dates,
)


def candidates_for(query: str) -> dict[str, Any]:
    return {
        "results": [
            {
                "title": f"title for {query}",
                "url": f"https://example.org/{len(query)}",
                "content": f"snippet for {query}",
                "score": 0.5,
            }
        ]
    }


async def test_batch_runs_one_attempt_per_query_and_returns_results_in_input_order() -> None:
    received: list[str] = []

    def tavily(request: httpx.Request) -> httpx.Response:
        query = json.loads(request.content)["query"]
        received.append(query)
        return httpx.Response(200, json=candidates_for(query))

    async with connected(tavily) as session:
        result = await session.call_tool(
            "web_search",
            {"queries": [{"query": "第一个 query"}, {"query": "second query"}]},
        )

    assert sorted(received) == sorted(["第一个 query", "second query"])
    assert len(received) == 2
    assert result.structuredContent is not None
    items = result.structuredContent["results"]
    assert [item["query"] for item in items] == ["第一个 query", "second query"]
    assert [item["status"] for item in items] == ["ok", "ok"]
    assert items[0]["candidates"][0]["content"] == "snippet for 第一个 query"
    assert items[1]["candidates"][0]["content"] == "snippet for second query"
    assert result.structuredContent["partial"] is False


async def test_twenty_queries_are_accepted_and_twenty_one_are_rejected_whole() -> None:
    attempts = 0

    def tavily(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(200, json={"results": []})

    twenty = [{"query": f"query {index}"} for index in range(20)]
    async with connected(tavily) as session:
        accepted = await session.call_tool("web_search", {"queries": twenty})
        assert attempts == 20
        attempts = 0
        too_many = await session.call_tool(
            "web_search",
            {"queries": twenty + [{"query": "query 20"}]},
        )
        empty = await session.call_tool("web_search", {"queries": []})

    assert not accepted.isError
    assert accepted.structuredContent is not None
    assert [item["query"] for item in accepted.structuredContent["results"]] == [
        f"query {index}" for index in range(20)
    ]
    # No truncation: an over-limit batch sends nothing at all, not the first 20.
    assert too_many.isError
    assert empty.isError
    assert attempts == 0


async def sent_bodies(session: Any, arguments: dict[str, Any]) -> Any:
    result = await session.call_tool("web_search", arguments)
    assert not result.isError, result.content
    return result


async def test_query_parameters_override_batch_field_by_field() -> None:
    bodies: dict[str, dict[str, Any]] = {}

    def tavily(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        bodies[body["query"]] = body
        return httpx.Response(200, json={"results": []})

    async with connected(tavily) as session:
        await sent_bodies(
            session,
            {
                "search_depth": "basic",
                "max_results": 5,
                "topic": "news",
                "include_domains": ["batch.example"],
                "exact_match": True,
                "queries": [
                    {"query": "inherits"},
                    {
                        "query": "overrides",
                        "search_depth": "advanced",
                        "max_results": 0,
                        "include_domains": [],
                        "exact_match": False,
                    },
                ],
            },
        )

    assert bodies["inherits"] == {
        "query": "inherits",
        "search_depth": "basic",
        "max_results": 5,
        "topic": "news",
        "include_domains": ["batch.example"],
        "exact_match": True,
    }
    # Explicit false, 0 and [] are values, not "unset"; arrays replace rather than merge.
    assert bodies["overrides"] == {
        "query": "overrides",
        "search_depth": "advanced",
        "max_results": 0,
        "topic": "news",
        "include_domains": [],
        "exact_match": False,
    }


async def test_parameters_absent_at_both_levels_are_not_sent() -> None:
    bodies: list[dict[str, Any]] = []

    def tavily(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"results": []})

    async with connected(tavily) as session:
        await sent_bodies(session, {"queries": [{"query": "bare"}], "topic": "finance"})

    assert bodies == [{"query": "bare", "topic": "finance"}]


@pytest.mark.parametrize(
    "arguments",
    [
        {"queries": [{"query": "q"}], "search_depth": "deep"},
        {"queries": [{"query": "q", "search_depth": "deep"}]},
        {"queries": [{"query": "q"}], "topic": "sports"},
        {"queries": [{"query": "q"}], "time_range": "decade"},
        {"queries": [{"query": "q"}], "max_results": 21},
        {"queries": [{"query": "q", "max_results": 21}]},
        {"queries": [{"query": "q"}], "max_results": -1},
        {"queries": [{"query": "q"}], "max_results": 2.5},
        {"queries": [{"query": "q"}], "max_results": True},
        {"queries": [{"query": "q"}], "max_results": "5"},
        {"queries": [{"query": "q"}], "include_domains": "example.org"},
        {"queries": [{"query": "q"}], "include_domains": [1]},
        {"queries": [{"query": "q"}], "exclude_domains": {"host": "example.org"}},
        {"queries": [{"query": "q"}], "exact_match": "true"},
        {"queries": [{"query": "q"}], "country": 86},
        {"queries": [{"query": "q"}], "language": ["zh"]},
        {"queries": [{"query": "q"}], "start_date": 20260913},
        {"queries": [{"query": "q"}], "end_date": None},
        {"queries": [{"query": "q"}], "route": "tavily"},
        {"queries": [{"query": "q"}], "include_answer": True},
        # One invalid item rejects the whole batch, before any upstream request.
        {"queries": [{"query": "valid"}, {"query": "q", "topic": "sports"}]},
        {"queries": [{"query": "valid"}, {"query": ""}]},
        {"queries": [{"query": "valid"}, {}]},
    ],
)
async def test_invalid_parameters_reject_the_whole_batch_before_any_request(
    arguments: dict[str, Any],
) -> None:
    attempts = 0

    def tavily(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(200, json={"results": []})

    async with connected(tavily) as session:
        result = await session.call_tool("web_search", arguments)

    assert result.isError
    assert attempts == 0


async def test_mixed_success_and_failure_reports_partial_and_keeps_every_item() -> None:
    def tavily(request: httpx.Request) -> httpx.Response:
        query = json.loads(request.content)["query"]
        if query == "denied":
            return httpx.Response(401, json={"error": "unauthorized"})
        return httpx.Response(200, json=candidates_for(query))

    async with connected(tavily) as session:
        result = await session.call_tool(
            "web_search",
            {"queries": [{"query": "ok one"}, {"query": "denied"}, {"query": "ok two"}]},
        )

    assert result.structuredContent is not None
    assert result.structuredContent["partial"] is True
    items = result.structuredContent["results"]
    assert [item["query"] for item in items] == ["ok one", "denied", "ok two"]
    assert [item["status"] for item in items] == ["ok", "error", "ok"]
    assert items[0]["candidates"] and items[2]["candidates"]
    assert items[1]["error"]["category"] == "invalid_or_missing_key"
    assert "candidates" not in items[1]
    assert "error" not in items[0]


async def test_all_failed_keeps_every_error_and_is_not_partial() -> None:
    def tavily(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    async with connected(tavily) as session:
        result = await session.call_tool(
            "web_search",
            {"queries": [{"query": "one"}, {"query": "two"}]},
        )

    assert not result.isError
    assert result.structuredContent is not None
    # partial=false here means "not a mix", not "the batch succeeded".
    assert set(result.structuredContent) == {"partial", "results"}
    assert result.structuredContent["partial"] is False
    items = result.structuredContent["results"]
    assert [item["query"] for item in items] == ["one", "two"]
    for item in items:
        assert item["status"] == "error"
        assert item["error"]["category"] == "invalid_or_missing_key"


async def test_empty_candidates_count_as_ok_so_batch_is_not_partial() -> None:
    def tavily(request: httpx.Request) -> httpx.Response:
        query = json.loads(request.content)["query"]
        if query == "nothing found":
            return httpx.Response(200, json={"results": []})
        return httpx.Response(200, json=candidates_for(query))

    async with connected(tavily) as session:
        result = await session.call_tool(
            "web_search",
            {"queries": [{"query": "nothing found"}, {"query": "found"}]},
        )

    assert result.structuredContent is not None
    assert result.structuredContent["partial"] is False
    items = result.structuredContent["results"]
    assert items[0] == {"query": "nothing found", "status": "ok", "candidates": []}
    assert items[1]["status"] == "ok"


async def test_reverse_completion_order_still_returns_results_in_input_order() -> None:
    first_in_flight = asyncio.Event()

    async def tavily(request: httpx.Request) -> httpx.Response:
        query = json.loads(request.content)["query"]
        if query == "slow":
            first_in_flight.set()
            await asyncio.sleep(0.05)
        else:
            await first_in_flight.wait()
        return httpx.Response(200, json=candidates_for(query))

    async with connected(tavily) as session:
        result = await session.call_tool(
            "web_search",
            {"queries": [{"query": "slow"}, {"query": "fast"}]},
        )

    assert result.structuredContent is not None
    assert [item["query"] for item in result.structuredContent["results"]] == ["slow", "fast"]
    assert result.structuredContent["results"][0]["candidates"][0]["content"] == "snippet for slow"


async def test_duplicate_queries_stay_separate_items() -> None:
    attempts = 0

    def tavily(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(200, json=candidates_for("same"))

    async with connected(tavily) as session:
        result = await session.call_tool(
            "web_search",
            {"queries": [{"query": "same"}, {"query": "same"}, {"query": "other"}]},
        )

    assert attempts == 3
    assert result.structuredContent is not None
    items = result.structuredContent["results"]
    assert [item["query"] for item in items] == ["same", "same", "other"]
    # No cross-query dedupe: identical candidates are kept in both items.
    assert items[0]["candidates"] == items[1]["candidates"]


async def test_one_query_timing_out_does_not_discard_the_others() -> None:
    released = asyncio.Event()

    async def tavily(request: httpx.Request) -> httpx.Response:
        query = json.loads(request.content)["query"]
        if query == "hangs":
            try:
                await asyncio.Event().wait()
            finally:
                released.set()
        return httpx.Response(200, json=candidates_for(query))

    async with connected(tavily, timeout_seconds=0.05) as session:
        async with asyncio.timeout(5):
            result = await session.call_tool(
                "web_search",
                {"queries": [{"query": "hangs"}, {"query": "completes"}]},
            )

    assert released.is_set()
    assert result.structuredContent is not None
    assert result.structuredContent["partial"] is True
    items = result.structuredContent["results"]
    assert items[0]["error"]["category"] == "timeout_error"
    assert items[1]["status"] == "ok"


async def test_http_400_marks_only_that_query_invalid_request() -> None:
    def tavily(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body.get("country") and body.get("topic") == "news":
            return httpx.Response(400, json={"detail": {"error": "country requires general"}})
        return httpx.Response(200, json=candidates_for(body["query"]))

    async with connected(tavily) as session:
        result = await session.call_tool(
            "web_search",
            {
                "topic": "news",
                "queries": [
                    {"query": "rejected combination", "country": "china"},
                    {"query": "accepted combination", "topic": "general"},
                ],
            },
        )

    assert result.structuredContent is not None
    assert result.structuredContent["partial"] is True
    items = result.structuredContent["results"]
    assert items[0]["status"] == "error"
    assert items[0]["error"]["category"] == "invalid_request"
    assert items[0]["error"]["message"]
    assert "country requires general" not in items[0]["error"]["message"]
    assert items[1]["status"] == "ok"


async def test_concurrency_is_bounded_and_still_completes_a_full_batch() -> None:
    in_flight = 0
    peak = 0
    gate = asyncio.Event()

    async def tavily(request: httpx.Request) -> httpx.Response:
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        try:
            # Every attempt that the server lets start stays open until the test releases it.
            await gate.wait()
            return httpx.Response(200, json={"results": []})
        finally:
            in_flight -= 1

    async with connected(tavily) as session:
        async with asyncio.timeout(5):
            call = asyncio.create_task(
                session.call_tool(
                    "web_search",
                    {"queries": [{"query": f"query {index}"} for index in range(20)]},
                )
            )
            while in_flight < MAX_CONCURRENT_ATTEMPTS:
                await asyncio.sleep(0)
            # Give an unbounded implementation every chance to exceed the limit.
            await asyncio.sleep(0.05)
            held = peak
            gate.set()
            result = await call

    assert held == MAX_CONCURRENT_ATTEMPTS
    assert result.structuredContent is not None
    assert len(result.structuredContent["results"]) == 20
    assert all(item["status"] == "ok" for item in result.structuredContent["results"])


async def test_parameters_and_errors_never_disclose_the_configured_key(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def tavily(request: httpx.Request) -> httpx.Response:
        # Reflect the Authorization header the way a careless upstream error body might.
        return httpx.Response(400, json={"error": request.headers["authorization"]})

    caplog.set_level(logging.DEBUG)
    async with connected(tavily) as session:
        result = await session.call_tool(
            "web_search",
            {
                "country": "china",
                "language": "zh",
                "include_domains": ["example.org"],
                "queries": [{"query": "参数不泄漏 key"}, {"query": "second", "max_results": 3}],
            },
        )

    assert result.structuredContent is not None
    assert result.structuredContent["partial"] is False
    assert DUMMY_KEY not in result.model_dump_json() + caplog.text


async def test_discovery_describes_batch_limits_and_rejection_message_stays_generic() -> None:
    def tavily(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": []})

    async with connected(tavily) as session:
        discovery = await session.list_tools()
        rejected = await session.call_tool(
            "web_search",
            {"queries": [{"query": "q", "topic": "sports"}]},
        )

    description = discovery.tools[0].description
    assert description is not None
    assert "1" in description and "20" in description
    assert "exactly one query" not in description
    assert "max_results" in description

    schema: dict[str, Any] = discovery.tools[0].inputSchema
    assert schema["properties"]["max_results"]["maximum"] == 20
    assert schema["properties"]["queries"]["maxItems"] == 20

    assert rejected.isError
    text = rejected.model_dump_json()
    # The message explains the contract without echoing the rejected input back.
    assert "sports" not in text
    assert "queries" in text


BATCH_VALUES: dict[str, Any] = {
    "search_depth": "basic",
    "max_results": 5,
    "topic": "news",
    "time_range": "week",
    "start_date": "2026-09-01",
    "end_date": "2026-09-13",
    "include_domains": ["batch.example"],
    "exclude_domains": ["blocked.example"],
    "country": "china",
    "language": "zh",
    "exact_match": True,
}
QUERY_VALUES: dict[str, Any] = {
    "search_depth": "advanced",
    "max_results": 0,
    "topic": "finance",
    "time_range": "day",
    "start_date": "2026-01-01",
    "end_date": "2026-01-31",
    "include_domains": [],
    "exclude_domains": ["other.example"],
    "country": "japan",
    "language": "en",
    "exact_match": False,
}


async def test_every_parameter_inherits_and_can_be_overridden() -> None:
    assert set(BATCH_VALUES) == set(QUERY_VALUES) == set(SEARCH_PARAMETERS)
    bodies: dict[str, dict[str, Any]] = {}

    def tavily(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        bodies[body["query"]] = body
        return httpx.Response(200, json={"results": []})

    async with connected(tavily) as session:
        await sent_bodies(
            session,
            {
                **BATCH_VALUES,
                "queries": [
                    {"query": "inherits every parameter"},
                    {"query": "overrides every parameter", **QUERY_VALUES},
                ],
            },
        )

    assert bodies["inherits every parameter"] == {
        "query": "inherits every parameter",
        **BATCH_VALUES,
    }
    assert bodies["overrides every parameter"] == {
        "query": "overrides every parameter",
        **QUERY_VALUES,
    }


@pytest.mark.parametrize("name", sorted(SEARCH_PARAMETERS))
async def test_each_parameter_alone_reaches_tavily_from_either_level(name: str) -> None:
    bodies: dict[str, dict[str, Any]] = {}

    def tavily(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        bodies[body["query"]] = body
        return httpx.Response(200, json={"results": []})

    async with connected(tavily) as session:
        await sent_bodies(
            session,
            {
                name: BATCH_VALUES[name],
                "queries": [
                    {"query": "from batch"},
                    {"query": "from query", name: QUERY_VALUES[name]},
                ],
            },
        )
        await sent_bodies(session, {"queries": [{"query": "neither level"}]})

    assert bodies["from batch"] == {"query": "from batch", name: BATCH_VALUES[name]}
    assert bodies["from query"] == {"query": "from query", name: QUERY_VALUES[name]}
    assert bodies["neither level"] == {"query": "neither level"}


async def test_unexpected_failure_in_one_query_stays_that_query_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """One query blowing up must not cancel siblings or replace the per-item results."""
    reached: list[str] = []

    async def tavily(request: httpx.Request) -> httpx.Response:
        query = json.loads(request.content)["query"]
        if query == "boom":
            raise RuntimeError(f"unexpected internal failure {DUMMY_KEY}")
        # Yield first so the failing attempt is already in flight when this one runs.
        await asyncio.sleep(0.01)
        reached.append(query)
        return httpx.Response(200, json=candidates_for(query))

    caplog.set_level(logging.DEBUG)
    async with connected(tavily) as session:
        result = await session.call_tool(
            "web_search",
            {"queries": [{"query": "boom"}, {"query": "fine"}]},
        )

    assert reached == ["fine"]
    assert not result.isError
    assert result.structuredContent is not None
    assert result.structuredContent["partial"] is True
    items = result.structuredContent["results"]
    assert [item["query"] for item in items] == ["boom", "fine"]
    assert items[0]["status"] == "error"
    assert items[0]["error"]["category"] == "upstream_error"
    assert items[1]["status"] == "ok"
    assert DUMMY_KEY not in result.model_dump_json() + caplog.text


@pytest.mark.parametrize("field", ["start_date", "end_date"])
@pytest.mark.parametrize(
    "value", ["", "2026-99-99", "2026-02-30", "13-09-2026", "2026/09/13", "yesterday", "2026-9-13"]
)
async def test_malformed_dates_are_rejected_at_both_levels(field: str, value: str) -> None:
    attempts = 0

    def tavily(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(200, json={"results": []})

    async with connected(tavily) as session:
        batch_level = await session.call_tool(
            "web_search",
            {field: value, "queries": [{"query": "q"}]},
        )
        query_level = await session.call_tool(
            "web_search",
            {"queries": [{"query": "q", field: value}]},
        )

    assert batch_level.isError
    assert query_level.isError
    assert attempts == 0


@pytest.mark.parametrize("value", ["2026-09-13", "2024-02-29", "1999-12-31"])
async def test_valid_dates_reach_tavily_unchanged(value: str) -> None:
    bodies: list[dict[str, Any]] = []

    def tavily(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"results": []})

    async with connected(tavily) as session:
        await sent_bodies(
            session,
            {"start_date": value, "queries": [{"query": "q", "end_date": value}]},
        )

    assert bodies == [{"query": "q", "start_date": value, "end_date": value}]


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"queries": "not a list"},
        {"queries": [1, 2]},
        {"queries": [{"query": "q", "start_date": 20260913}]},
        {"queries": None},
    ],
)
async def test_structurally_broken_input_is_rejected_not_crashed(
    arguments: dict[str, Any],
) -> None:
    """Validation order must not be load-bearing: no input shape may raise."""
    assert has_valid_dates(arguments) in (True, False)

    def tavily(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no upstream request expected")

    async with connected(tavily) as session:
        result = await session.call_tool("web_search", arguments)

    assert result.isError
