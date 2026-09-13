import json
import sys
from pathlib import Path
from tempfile import TemporaryFile
from typing import TextIO, cast

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent


async def test_real_stdio_discovery_success_and_401() -> None:
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
                        "url": "https://example.org/source",
                        "content": "Offline SERP metadata",
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
    for result in (ok, denied):
        assert not result.isError
        assert isinstance(result.content[0], TextContent)
        assert json.loads(result.content[0].text) == result.structuredContent
        assert key not in result.model_dump_json() + stderr
