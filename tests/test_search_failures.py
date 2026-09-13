"""Failure and recovery contracts observed through the public MCP boundary."""

import asyncio
import json
import logging
import socket
import time
from collections import Counter
from datetime import UTC, datetime

import httpx
import pytest
from harness import DUMMY_KEY, connected
from http_fixture import LoopbackTransport, TavilyHTTPFixture
from mcp.types import TextContent


@pytest.mark.parametrize(
    "status,header,expected",
    [
        (429, "120", 120),
        (429, "0", 0),
        (429, " 007 \t", 7),
        (432, "37", 37),
        (433, "41", 41),
        (503, "60", 60),
        (429, None, None),
        (429, "", None),
        (429, "-1", None),
        (429, "+5", None),
        (429, "1.5", None),
        (429, "1e3", None),
        (429, "NaN", None),
        (429, "inf", None),
        (429, "1, 2", None),
        pytest.param(429, "9" * 400, None, id="non-finite-delay"),
        (429, DUMMY_KEY, None),
    ],
)
async def test_retry_after_seconds_are_optional_advice_not_automatic_retry(
    status: int,
    header: str | None,
    expected: int | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    requests: list[httpx.Request] = []

    def tavily(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            status,
            headers={} if header is None else {"Retry-After": header},
            json={"error": request.headers["authorization"]},
        )

    caplog.set_level(logging.DEBUG)
    async with connected(tavily) as session:
        async with asyncio.timeout(2):
            first = await session.call_tool("web_search", {"queries": [{"query": "limited"}]})
            assert len(requests) == 1
            second = await session.call_tool("web_search", {"queries": [{"query": "limited"}]})

    assert len(requests) == 2
    assert all(str(request.url) == "https://api.tavily.com/search" for request in requests)
    assert all(request.method == "POST" for request in requests)
    assert first.structuredContent == second.structuredContent
    for result in (first, second):
        assert not result.isError
        assert result.structuredContent is not None
        assert set(result.structuredContent) == {"partial", "results"}
        assert result.structuredContent["partial"] is False
        item = result.structuredContent["results"][0]
        assert set(item) == {"query", "status", "error"}
        assert item["status"] == "error"
        error = item["error"]
        assert (
            error["category"]
            == {
                429: "rate_limited",
                432: "quota_exhausted",
                433: "quota_exhausted",
                503: "upstream_error",
            }[status]
        )
        if expected is None:
            assert set(error) == {"category", "message"}
        else:
            assert set(error) == {"category", "message", "retry_after_seconds"}
            assert type(error["retry_after_seconds"]) in (int, float)
            assert error["retry_after_seconds"] == expected
        assert DUMMY_KEY not in result.model_dump_json() + caplog.text


@pytest.mark.parametrize(
    "header,expected",
    [
        ("Sun, 13 Sep 2026 12:01:30 GMT", 89.75),
        ("Sunday, 13-Sep-26 12:01:30 GMT", 89.75),
        ("Sun Sep 13 12:01:30 2026", 89.75),
        (" \tSun, 13 Sep 2026 12:01:30 GMT\t", 89.75),
        ("Sun, 13 Sep 2026 12:00:00 GMT", 0),
        ("Sat, 12 Sep 2026 12:00:00 GMT", 0),
        ("Sun, 13 Sep 2026 12:01:30", None),
        ("Sun, 13 Sep 2026 12:01:30 XYZ", None),
        ("Sun, 13 Sep 2026 12:01:30 +0000", None),
        ("Sun, 13 Sep 2026 12:01 GMT", None),
        ("Sun, 30 Feb 2026 12:01:30 GMT", None),
        ("Sun, 13 Sep 10000 12:01:30 GMT", None),
        ("Sun, 13 Sep 2026 12:01:30 GMT, 120", None),
        ("tomorrow", None),
    ],
)
async def test_retry_after_http_date_uses_a_controlled_clock(
    header: str,
    expected: float | None,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    now = datetime(2026, 9, 13, 12, 0, 0, 250000, tzinfo=UTC).timestamp()
    monkeypatch.setattr(time, "time", lambda: now)
    attempts = 0

    def tavily(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(
            429,
            headers={"Retry-After": header},
            json={"error": DUMMY_KEY},
        )

    caplog.set_level(logging.DEBUG)
    async with connected(tavily) as session:
        async with asyncio.timeout(2):
            result = await session.call_tool("web_search", {"queries": [{"query": "date"}]})

    assert attempts == 1
    assert not result.isError
    assert result.structuredContent is not None
    error = result.structuredContent["results"][0]["error"]
    assert error["category"] == "rate_limited"
    if expected is None:
        assert set(error) == {"category", "message"}
    else:
        assert type(error["retry_after_seconds"]) in (int, float)
        assert error["retry_after_seconds"] == expected
    assert DUMMY_KEY not in result.model_dump_json() + caplog.text


async def test_mixed_failures_keep_every_result_in_input_order(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fast_finished = asyncio.Event()
    released = asyncio.Event()
    received: list[str] = []
    finished: list[str] = []
    queries = ["slow ok", "fast ok", "dns", "connect", "429", "432", "433", "malformed", "hang"]

    async def tavily(request: httpx.Request) -> httpx.Response:
        query = json.loads(request.content)["query"]
        received.append(query)
        assert request.method == "POST"
        assert str(request.url) == "https://api.tavily.com/search"
        try:
            if query == "slow ok":
                await fast_finished.wait()
            if query == "fast ok":
                fast_finished.set()
            if query == "dns":
                raise httpx.ConnectError(DUMMY_KEY, request=request) from socket.gaierror(
                    socket.EAI_NONAME, DUMMY_KEY
                )
            if query == "connect":
                raise httpx.ConnectError(DUMMY_KEY, request=request) from ConnectionRefusedError(
                    DUMMY_KEY
                )
            if query in {"429", "432", "433"}:
                return httpx.Response(
                    int(query), headers={"Retry-After": "120"}, json={"error": DUMMY_KEY}
                )
            if query == "malformed":
                return httpx.Response(200, content=f"invalid JSON {DUMMY_KEY}".encode())
            if query == "hang":
                try:
                    await asyncio.Event().wait()
                finally:
                    released.set()
            return httpx.Response(
                200,
                json={"results": [{"title": query, "url": "u", "content": query, "score": 0.7}]},
            )
        finally:
            finished.append(query)

    caplog.set_level(logging.DEBUG)
    async with connected(tavily, timeout_seconds=0.1) as session:
        async with asyncio.timeout(3):
            result = await session.call_tool(
                "web_search", {"queries": [{"query": q} for q in queries]}
            )

    assert released.is_set()
    assert Counter(received) == Counter(queries)
    assert finished.index("fast ok") < finished.index("slow ok")
    assert not result.isError
    assert isinstance(result.content[0], TextContent)
    assert json.loads(result.content[0].text) == result.structuredContent
    assert result.structuredContent is not None
    assert set(result.structuredContent) == {"partial", "results"}
    assert result.structuredContent["partial"] is True
    items = result.structuredContent["results"]
    assert [item["query"] for item in items] == queries
    assert [item["status"] for item in items] == ["ok", "ok"] + ["error"] * 7
    assert [item["candidates"][0]["content"] for item in items[:2]] == ["slow ok", "fast ok"]
    assert [item["error"]["category"] for item in items[2:]] == [
        "network_error",
        "network_error",
        "rate_limited",
        "quota_exhausted",
        "quota_exhausted",
        "upstream_error",
        "timeout_error",
    ]
    assert "plan_limit_exceeded" in items[5]["error"]["message"]
    assert "payg_limit_exceeded" in items[6]["error"]["message"]
    for item in items[2:]:
        expected_keys = {"category", "message"}
        if item["query"] in {"429", "432", "433"}:
            expected_keys.add("retry_after_seconds")
            assert item["error"]["retry_after_seconds"] == 120
        assert set(item) == {"query", "status", "error"}
        assert set(item["error"]) == expected_keys
    assert DUMMY_KEY not in result.model_dump_json() + caplog.text


async def test_repeated_timeouts_release_http_connections_and_next_batch_still_completes(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    expected_requests: list[str] = []
    async with TavilyHTTPFixture() as upstream:
        async with connected(LoopbackTransport(upstream.port), timeout_seconds=0.3) as session:
            async with asyncio.timeout(8):
                for _ in range(3):
                    stalled = ["fixture-trickle", "fixture-timeout"]
                    expected_requests.extend(stalled)
                    result = await session.call_tool(
                        "web_search", {"queries": [{"query": q} for q in stalled]}
                    )
                    assert not result.isError
                    assert result.structuredContent is not None
                    assert result.structuredContent["partial"] is False
                    items = result.structuredContent["results"]
                    assert [item["query"] for item in items] == stalled
                    assert [item["error"]["category"] for item in items] == [
                        "timeout_error",
                        "timeout_error",
                    ]
                    assert all(set(item["error"]) == {"category", "message"} for item in items)
                    # Observe client disconnects before closing the MCP session or HTTP client.
                    closed = [await upstream.disconnected.get(), await upstream.disconnected.get()]
                    assert sorted(closed) == sorted(stalled)
                    assert DUMMY_KEY not in result.model_dump_json() + caplog.text

                    mixed = [
                        "fixture-reset",
                        "fixture-429",
                        "fixture-432",
                        "fixture-433",
                        "recovered",
                    ]
                    expected_requests.extend(mixed)
                    recovered = await session.call_tool(
                        "web_search", {"queries": [{"query": q} for q in mixed]}
                    )
                    assert not recovered.isError
                    assert recovered.structuredContent is not None
                    assert recovered.structuredContent["partial"] is True
                    items = recovered.structuredContent["results"]
                    assert [item["query"] for item in items] == mixed
                    assert [item["error"]["category"] for item in items[:-1]] == [
                        "network_error",
                        "rate_limited",
                        "quota_exhausted",
                        "quota_exhausted",
                    ]
                    assert items[-1]["status"] == "ok"
                    assert (
                        items[-1]["candidates"][0]["content"]
                        == "Offline SERP metadata for recovered"
                    )
                    assert DUMMY_KEY not in recovered.model_dump_json() + caplog.text

                final_queries = [f"normal {index}" for index in range(20)]
                expected_requests.extend(final_queries)
                final = await session.call_tool(
                    "web_search", {"queries": [{"query": q} for q in final_queries]}
                )
                assert not final.isError
                assert final.structuredContent is not None
                assert final.structuredContent["partial"] is False
                assert [
                    item["query"] for item in final.structuredContent["results"]
                ] == final_queries
                assert all(item["status"] == "ok" for item in final.structuredContent["results"])
                assert DUMMY_KEY not in final.model_dump_json() + caplog.text

        assert upstream.trickle_chunks >= 3
        assert Counter(item["body"]["query"] for item in upstream.requests) == Counter(
            expected_requests
        )
        assert all(item["request_line"] == "POST /search HTTP/1.1" for item in upstream.requests)


async def test_real_http_mixed_batch_preserves_slow_success_and_all_failure_categories(
    caplog: pytest.LogCaptureFixture,
) -> None:
    queries = [
        "slow success",
        "fixture-trickle",
        "fixture-429",
        "fixture-432",
        "fast success",
        "fixture-433",
        "fixture-reset",
        "fixture-400",
        "fixture-401",
        "fixture-500",
        "fixture-418",
        "fixture-malformed",
    ]
    caplog.set_level(logging.DEBUG)
    async with TavilyHTTPFixture() as upstream:
        gate = upstream.gates["slow success"] = asyncio.Event()
        async with connected(
            LoopbackTransport(upstream.port, max_connections=20), timeout_seconds=0.3
        ) as session:
            async with asyncio.timeout(5):
                call = asyncio.create_task(
                    session.call_tool("web_search", {"queries": [{"query": q} for q in queries]})
                )
                while "fast success" not in upstream.completed:
                    await asyncio.sleep(0.001)
                gate.set()
                result = await call
                assert await upstream.disconnected.get() == "fixture-trickle"

        assert upstream.completed.index("fast success") < upstream.completed.index("slow success")
        assert Counter(item["body"]["query"] for item in upstream.requests) == Counter(queries)
        assert not result.isError
        assert isinstance(result.content[0], TextContent)
        assert json.loads(result.content[0].text) == result.structuredContent
        assert result.structuredContent is not None
        assert set(result.structuredContent) == {"partial", "results"}
        assert result.structuredContent["partial"] is True
        items = result.structuredContent["results"]
        assert [item["query"] for item in items] == queries
        assert [item.get("error", {}).get("category") for item in items] == [
            None,
            "timeout_error",
            "rate_limited",
            "quota_exhausted",
            None,
            "quota_exhausted",
            "network_error",
            "invalid_request",
            "invalid_or_missing_key",
            "upstream_error",
            "upstream_error",
            "upstream_error",
        ]
        assert [items[index]["candidates"][0]["content"] for index in (0, 4)] == [
            "Offline SERP metadata for slow success",
            "Offline SERP metadata for fast success",
        ]
        assert DUMMY_KEY not in result.model_dump_json() + caplog.text


async def test_queued_queries_get_their_own_deadline_not_a_batch_deadline() -> None:
    async with TavilyHTTPFixture() as upstream:
        async with connected(
            LoopbackTransport(upstream.port, max_connections=20), timeout_seconds=0.1
        ) as session:
            async with asyncio.timeout(5):
                result = await session.call_tool(
                    "web_search", {"queries": [{"query": "fixture-timeout"} for _ in range(20)]}
                )
                assert not result.isError
                assert result.structuredContent is not None
                assert result.structuredContent["partial"] is False
                items = result.structuredContent["results"]
                assert len(items) == 20
                assert all(item["error"]["category"] == "timeout_error" for item in items)
                assert len(upstream.requests) == 20
                assert all(
                    item["body"] == {"query": "fixture-timeout"} for item in upstream.requests
                )
                for _ in range(20):
                    assert await upstream.disconnected.get() == "fixture-timeout"
                recovered = await session.call_tool("web_search", {"queries": [{"query": "next"}]})
                assert recovered.structuredContent is not None
                assert recovered.structuredContent["results"][0]["status"] == "ok"
