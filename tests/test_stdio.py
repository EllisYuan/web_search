import json
import sys
from pathlib import Path
from tempfile import TemporaryFile
from typing import TextIO, cast

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent


async def test_real_stdio_discovery_and_mixed_batch() -> None:
    key = "dummy-key-for-stdio"
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).with_name("fixture_stdio_server.py"))],
        env={"TAVILY_API_KEY": key},
    )
    with TemporaryFile(mode="w+", encoding="utf-8") as errors:
        async with stdio_client(params, errlog=cast(TextIO, errors)) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert [tool.name for tool in tools.tools] == ["web_search"]
                ok = await session.call_tool("web_search", {"queries": [{"query": "中文 MCP"}]})
                denied = await session.call_tool(
                    "web_search",
                    {"queries": [{"query": "fixture-401"}]},
                )
                mixed = await session.call_tool(
                    "web_search",
                    {
                        "search_depth": "basic",
                        "queries": [
                            {"query": "batch ok"},
                            {"query": "fixture-401"},
                            {"query": "batch advanced", "search_depth": "advanced"},
                        ],
                    },
                )
        errors.seek(0)
        stderr = errors.read()

    assert ok.structuredContent == {
        "partial": False,
        "results": [
            {
                "query": "中文 MCP",
                "status": "ok",
                "candidates": [
                    {
                        "title": "受控 Search fixture",
                        "url": "https://example.org/source?depth=unset",
                        "content": "Offline SERP metadata for 中文 MCP",
                        "score": 0.8,
                        "rank": 1,
                        "published_date": "2026-09-13",
                    }
                ],
            }
        ],
    }
    assert denied.structuredContent is not None
    assert denied.structuredContent["results"][0]["error"]["category"] == "invalid_or_missing_key"

    assert mixed.structuredContent is not None
    assert mixed.structuredContent["partial"] is True
    items = mixed.structuredContent["results"]
    assert [item["query"] for item in items] == ["batch ok", "fixture-401", "batch advanced"]
    assert [item["status"] for item in items] == ["ok", "error", "ok"]
    assert items[0]["candidates"][0]["url"].endswith("depth=basic")
    assert items[2]["candidates"][0]["url"].endswith("depth=advanced")

    for result in (ok, denied, mixed):
        assert not result.isError
        assert isinstance(result.content[0], TextContent)
        assert json.loads(result.content[0].text) == result.structuredContent
        assert key not in result.model_dump_json() + stderr


async def test_real_stdio_rate_quota_timeout_and_subsequent_search() -> None:
    key = "dummy-key-for-http-stdio"
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).with_name("fixture_http_stdio_server.py"))],
        env={"TAVILY_API_KEY": key},
    )
    with TemporaryFile(mode="w+", encoding="utf-8") as errors:
        async with stdio_client(params, errlog=cast(TextIO, errors)) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                description = tools.tools[0].description or ""
                assert "retry_after_seconds" in description
                assert "30" in description and "deadline" in description
                limited = await session.call_tool(
                    "web_search",
                    {
                        "queries": [
                            {"query": q} for q in ["fixture-429", "fixture-432", "fixture-433"]
                        ]
                    },
                )
                partial = await session.call_tool(
                    "web_search",
                    {"queries": [{"query": "fixture-trickle"}, {"query": "preserved"}]},
                )
                recovered = await session.call_tool("web_search", {"queries": [{"query": "next"}]})
        errors.seek(0)
        stderr = errors.read()

    assert limited.structuredContent is not None
    assert limited.structuredContent["partial"] is False
    items = limited.structuredContent["results"]
    assert [item["error"]["category"] for item in items] == [
        "rate_limited",
        "quota_exhausted",
        "quota_exhausted",
    ]
    assert "plan_limit_exceeded" in items[1]["error"]["message"]
    assert "payg_limit_exceeded" in items[2]["error"]["message"]
    assert all(item["error"]["retry_after_seconds"] == 120 for item in items)
    assert partial.structuredContent is not None
    assert partial.structuredContent["partial"] is True
    assert partial.structuredContent["results"][0]["error"]["category"] == "timeout_error"
    assert partial.structuredContent["results"][1]["status"] == "ok"
    assert recovered.structuredContent is not None
    assert recovered.structuredContent["results"][0]["status"] == "ok"
    for result in (limited, partial, recovered):
        assert not result.isError
        assert isinstance(result.content[0], TextContent)
        assert json.loads(result.content[0].text) == result.structuredContent
        assert key not in result.model_dump_json() + stderr
