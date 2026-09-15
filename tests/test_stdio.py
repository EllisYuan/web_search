import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory, TemporaryFile
from typing import TextIO, cast

from browser_fixture import javascript_site
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import ImageContent, TextContent


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
                assert [tool.name for tool in tools.tools] == ["web_search", "web_read"]
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
                assert ok.structuredContent is not None
                candidate_url = ok.structuredContent["results"][0]["candidates"][0]["url"]
                opened = await session.call_tool(
                    "web_read", {"url": candidate_url, "max_output_chars": 20}
                )
                assert opened.structuredContent is not None
                continued = await session.call_tool(
                    "web_read",
                    {
                        "action": "read",
                        "read_id": opened.structuredContent["read_id"],
                        "cursor": opened.structuredContent["next_cursor"],
                        "max_output_chars": 20,
                    },
                )
                found = await session.call_tool(
                    "web_read",
                    {
                        "action": "find",
                        "read_id": opened.structuredContent["read_id"],
                        "query": "FINDING",
                    },
                )
                released = await session.call_tool(
                    "web_read",
                    {"action": "release", "read_id": opened.structuredContent["read_id"]},
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

    assert not opened.isError and not continued.isError and not found.isError
    assert opened.structuredContent is not None
    assert opened.structuredContent["output_status"] == "truncated"
    assert continued.structuredContent is not None
    assert continued.structuredContent["content_markdown"]
    assert found.structuredContent is not None
    assert found.structuredContent["matches"][0]["text"] == "finding"
    assert released.structuredContent is not None
    assert released.structuredContent["released"] is True

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


async def test_real_stdio_media_advance_assets_and_webpage_ocr_without_key() -> None:
    with TemporaryDirectory() as artifact_temp:
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(Path(__file__).with_name("fixture_stdio_server.py"))],
            env={
                "TAVILY_API_KEY": "",
                "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
                "TEMP": artifact_temp,
                "TMP": artifact_temp,
            },
        )
        errors = TemporaryFile(mode="w+", encoding="utf-8")
        try:
            async with stdio_client(params, errlog=cast(TextIO, errors)) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    assert [tool.name for tool in tools.tools] == ["web_read"]
                    html = await session.call_tool(
                        "web_read", {"url": "https://example.org/source"}
                    )
                    webpage = await session.call_tool(
                        "web_read", {"url": "https://example.org/source-page"}
                    )
                    assert webpage.structuredContent is not None
                    webpage_body = webpage.structuredContent
                    webpage_ocr = next(
                        locator
                        for locator in webpage_body["locators"]
                        if locator["lineage"] == "image_ocr"
                    )
                    webpage_found = await session.call_tool(
                        "web_read",
                        {
                            "action": "find",
                            "read_id": webpage_body["read_id"],
                            "version": webpage_body["version"],
                            "query": "AX-2026-0917",
                        },
                    )
                    webpage_asset = await session.call_tool(
                        "web_read",
                        {
                            "action": "asset",
                            "read_id": webpage_body["read_id"],
                            "version": webpage_body["version"],
                            "asset_type": "image",
                            "asset_id": webpage_ocr["asset_id"],
                        },
                    )
                    webpage_released = await session.call_tool(
                        "web_read",
                        {"action": "release", "read_id": webpage_body["read_id"]},
                    )
                    image = await session.call_tool(
                        "web_read", {"url": "https://example.org/source.png"}
                    )
                    assert image.structuredContent is not None
                    image_body = image.structuredContent
                    image_asset = await session.call_tool(
                        "web_read",
                        {
                            "action": "asset",
                            "read_id": image_body["read_id"],
                            "version": image_body["version"],
                            "asset_type": "image",
                            "asset_id": image_body["asset_id"],
                        },
                    )
                    image_released = await session.call_tool(
                        "web_read",
                        {"action": "release", "read_id": image_body["read_id"]},
                    )
                    scanned_pdf_result = await session.call_tool(
                        "web_read",
                        {
                            "url": "https://example.org/source-scan.pdf",
                            "max_pages": 1,
                            "max_regions": 1,
                        },
                    )
                    pdf = await session.call_tool(
                        "web_read",
                        {
                            "url": "https://example.org/source.pdf",
                            "max_pages": 1,
                            "max_output_chars": 10,
                        },
                    )
                    assert pdf.structuredContent is not None
                    body = pdf.structuredContent
                    stale_selection = await session.call_tool(
                        "web_read",
                        {
                            "action": "read",
                            "read_id": body["read_id"],
                            "version": body["version"],
                            "block_id": body["locators"][0]["block_id"],
                            "max_output_chars": 10,
                        },
                    )
                    assert stale_selection.structuredContent is not None
                    stale_cursor = stale_selection.structuredContent["next_cursor"]
                    chunks = [body["content_markdown"]]
                    cursor = body["next_cursor"]
                    while cursor is not None:
                        continued = await session.call_tool(
                            "web_read",
                            {
                                "action": "read",
                                "read_id": body["read_id"],
                                "version": body["version"],
                                "cursor": cursor,
                                "max_output_chars": 10,
                            },
                        )
                        assert continued.structuredContent is not None
                        chunks.append(continued.structuredContent["content_markdown"])
                        cursor = continued.structuredContent["next_cursor"]
                    found = await session.call_tool(
                        "web_read",
                        {
                            "action": "find",
                            "read_id": body["read_id"],
                            "scope": "page",
                            "page": 1,
                            "query": "FIRST PAGE",
                        },
                    )
                    unread = await session.call_tool(
                        "web_read", {"action": "read", "read_id": body["read_id"], "page": 2}
                    )
                    invalid = await session.call_tool(
                        "web_read",
                        {
                            "action": "advance",
                            "read_id": body["read_id"],
                            "targets": [
                                {
                                    "page": 2,
                                    "region": {"x": 0.8, "y": 0, "width": 0.3, "height": 1},
                                }
                            ],
                        },
                    )
                    advanced = await session.call_tool(
                        "web_read",
                        {
                            "action": "advance",
                            "read_id": body["read_id"],
                            "version": body["version"],
                            "targets": [{"page": 3}, {"page": 2}],
                        },
                    )
                    assert advanced.structuredContent is not None
                    stale = await session.call_tool(
                        "web_read",
                        {
                            "action": "read",
                            "read_id": body["read_id"],
                            "cursor": stale_cursor,
                            "max_output_chars": 10,
                        },
                    )
                    crop = await session.call_tool(
                        "web_read",
                        {
                            "action": "asset",
                            "read_id": body["read_id"],
                            "version": advanced.structuredContent["version"],
                            "asset_type": "pdf_page_crop",
                            "page": 3,
                        },
                    )
                    released = await session.call_tool(
                        "web_read", {"action": "release", "read_id": body["read_id"]}
                    )
            errors.seek(0)
            stderr = errors.read()
        finally:
            errors.close()
        assert list(Path(artifact_temp).glob("*.pdf")) == []
        assert list(Path(artifact_temp).glob("*.image")) == []

    assert not html.isError and html.structuredContent is not None
    assert "Search 后读取的原文" in html.structuredContent["content_markdown"]
    assert not webpage.isError
    assert "Webpage image fixture." in webpage_body["content_markdown"]
    assert "AX-2026-0917" in webpage_body["content_markdown"]
    assert webpage_ocr["caption"] == "Captured evidence"
    assert webpage_body["processing"]["image_ocr"][0]["execution_providers"] == [
        "CPUExecutionProvider"
    ]
    assert webpage_found.structuredContent is not None
    assert webpage_found.structuredContent["matches"][0]["asset_id"] == webpage_ocr["asset_id"]
    assert not webpage_asset.isError
    assert any(isinstance(part, ImageContent) for part in webpage_asset.content)
    assert webpage_released.structuredContent is not None
    assert webpage_released.structuredContent["released"] is True
    assert not pdf.isError
    assert not image.isError
    assert "AX-2026-0917" in image_body["content_markdown"]
    assert image_body["processing"]["execution_providers"] == ["CPUExecutionProvider"]
    assert not image_asset.isError
    assert any(isinstance(part, ImageContent) for part in image_asset.content)
    assert image_released.structuredContent is not None
    assert image_released.structuredContent["released"] is True
    assert not scanned_pdf_result.isError
    assert scanned_pdf_result.structuredContent is not None
    assert "京东20260917" in scanned_pdf_result.structuredContent["content_markdown"]
    assert scanned_pdf_result.structuredContent["processing"]["ocr_used"] is True
    assert body["metadata"]["page_count"] == 3
    assert body["capture_status"] == "complete"
    assert body["extraction_status"] == "partial"
    assert body["output_status"] == "truncated"
    assert "".join(chunks) == "## Page 1\n\nPDF fixture first page."
    assert found.structuredContent is not None
    assert found.structuredContent["matches"][0]["page"] == 1
    assert unread.isError and unread.structuredContent is not None
    assert "has not been processed" in unread.structuredContent["error"]["message"]
    assert invalid.isError and invalid.structuredContent is not None
    assert invalid.structuredContent["error"]["category"] == "invalid_request"
    assert not advanced.isError and advanced.structuredContent is not None
    assert advanced.structuredContent["status"] == "partial"
    assert advanced.structuredContent["failures"][-1]["locator"] == {"page": 2}
    assert advanced.structuredContent["version"] != body["version"]
    assert "third page advanced" in advanced.structuredContent["content_markdown"]
    assert advanced.structuredContent["processing"]["source_acquisition"] is False
    assert stale.isError and stale.structuredContent is not None
    assert stale.structuredContent["error"]["category"] == "version_mismatch"
    assert not crop.isError and crop.structuredContent is not None
    assert crop.structuredContent["page"] == 3
    assert any(isinstance(part, ImageContent) for part in crop.content)
    assert released.structuredContent is not None
    assert released.structuredContent["released"] is True
    assert isinstance(pdf.content[0], TextContent)
    assert json.loads(pdf.content[0].text) == body
    assert stderr == ""


async def test_real_stdio_renders_and_interacts_with_javascript_page() -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).with_name("fixture_browser_stdio_server.py"))],
        env={"TAVILY_API_KEY": ""},
    )
    async with javascript_site() as base_url:
        with TemporaryFile(mode="w+", encoding="utf-8") as errors:
            async with stdio_client(params, errlog=cast(TextIO, errors)) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    opened = await session.call_tool(
                        "web_read", {"url": f"{base_url}/interactions"}
                    )
                    assert opened.structuredContent is not None
                    body = opened.structuredContent
                    expand = next(
                        target
                        for target in body["interaction_targets"]
                        if target["operation"] == "expand"
                    )
                    interacted = await session.call_tool(
                        "web_read",
                        {
                            "action": "interact",
                            "read_id": body["read_id"],
                            "version": body["version"],
                            "target_id": expand["target_id"],
                            "operation": "expand",
                        },
                    )
                    failed = await session.call_tool("web_read", {"url": f"{base_url}/empty-js"})
            errors.seek(0)
            stderr = errors.read()

    assert not opened.isError
    assert body["processing"]["browser_rendered"] is True
    assert "Original version text" in body["content_markdown"]
    assert not interacted.isError and interacted.structuredContent is not None
    assert interacted.structuredContent["content_markdown"] == "Expanded evidence"
    assert interacted.structuredContent["previous_version"] == body["version"]
    assert interacted.structuredContent["version"] != body["version"]
    assert failed.isError and failed.structuredContent is not None
    assert failed.structuredContent["error"]["category"] == "extraction_failed"
    assert stderr == ""
