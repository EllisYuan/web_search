import asyncio
from pathlib import Path
from typing import Any

import httpx
from harness import connected
from pdf_fixture import encrypted_pdf, text_pdf


async def allow_public_url(url: str) -> bool:
    return True


async def test_open_text_pdf_returns_native_text_metadata_outline_and_page_locators() -> None:
    requests = 0
    pdf = text_pdf("Overview 中文正文 and English evidence.", title="双语 PDF", outline=True)

    def source(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=pdf)

    async with connected(source, api_key=None, url_policy=allow_public_url) as session:
        result = await session.call_tool(
            "web_read", {"url": "https://example.org/report.pdf", "max_output_chars": 10_000}
        )

    assert not result.isError
    assert result.structuredContent is not None
    body = result.structuredContent
    assert body["metadata"]["content_type"] == "application/pdf"
    assert body["metadata"]["title"] == "双语 PDF"
    assert body["metadata"]["author"] == "Contract fixture"
    assert body["metadata"]["page_count"] == 1
    assert "Overview 中文正文 and English evidence." in body["content_markdown"]
    assert body["outline"][0]["title"] == "Page 1"
    assert body["outline"][0]["page"] == 1
    assert body["locators"][0]["page"] == 1
    assert body["processing"] == {
        "path": ["http_fetch", "pdf_parse", "native_text_extract"],
        "browser_rendered": False,
        "ocr_used": False,
    }
    assert body["capture_status"] == "complete"
    assert body["extraction_status"] == "complete"
    assert body["unprocessed_ranges"] == []
    assert requests == 1


async def test_pdf_budgets_and_state_reads_keep_processing_and_output_separate() -> None:
    requests = 0
    pdf = text_pdf(
        "First page evidence with a stable locator.",
        "Second page evidence remains captured only.",
        "Third page evidence remains captured only.",
    )

    def source(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=pdf)

    async with connected(source, api_key=None, url_policy=allow_public_url) as session:
        opened = await session.call_tool(
            "web_read",
            {
                "url": "https://example.org/long.pdf",
                "max_pages": 1,
                "max_output_chars": 12,
            },
        )
        assert opened.structuredContent is not None
        body = opened.structuredContent
        chunks = [body["content_markdown"]]
        cursor = body["next_cursor"]
        while cursor:
            continued = await session.call_tool(
                "web_read",
                {
                    "action": "read",
                    "read_id": body["read_id"],
                    "version": body["version"],
                    "cursor": cursor,
                    "max_output_chars": 12,
                },
            )
            assert continued.structuredContent is not None
            chunks.append(continued.structuredContent["content_markdown"])
            cursor = continued.structuredContent["next_cursor"]
        page = await session.call_tool(
            "web_read", {"action": "read", "read_id": body["read_id"], "page": 1}
        )
        block = await session.call_tool(
            "web_read",
            {
                "action": "read",
                "read_id": body["read_id"],
                "block_id": body["locators"][0]["block_id"],
            },
        )
        found = await session.call_tool(
            "web_read",
            {
                "action": "find",
                "read_id": body["read_id"],
                "query": "EVIDENCE",
                "scope": "page",
                "page": 1,
            },
        )
        unread = await session.call_tool(
            "web_read", {"action": "read", "read_id": body["read_id"], "page": 2}
        )
        unsearched = await session.call_tool(
            "web_read",
            {
                "action": "find",
                "read_id": body["read_id"],
                "query": "Second",
                "scope": "page",
                "page": 2,
            },
        )

    assert body["capture_status"] == "complete"
    assert body["extraction_status"] == "partial"
    assert body["output_status"] == "truncated"
    assert body["unprocessed_ranges"] == [
        {
            "kind": "unprocessed_pages",
            "message": "PDF page text has not been processed.",
            "locator": {"start_page": 2, "end_page": 3},
            "next_action": "advance",
        }
    ]
    assert "".join(chunks) == "## Page 1\n\nFirst page evidence with a stable locator."
    assert page.structuredContent is not None
    assert block.structuredContent is not None
    assert page.structuredContent["content_markdown"] == "".join(chunks)
    assert block.structuredContent["content_markdown"] == "".join(chunks)
    assert found.structuredContent is not None
    assert found.structuredContent["matches"][0]["page"] == 1
    assert found.structuredContent["searched_scope"]["page"] == 1
    assert found.structuredContent["searched_scope"]["unprocessed_ranges"] == []
    assert unread.isError and unsearched.isError
    assert unread.structuredContent is not None
    assert unsearched.structuredContent is not None
    assert "has not been processed" in unread.structuredContent["error"]["message"]
    assert "has not been processed" in unsearched.structuredContent["error"]["message"]
    assert requests == 1


async def test_pdf_partial_text_layer_and_structure_warning_are_located() -> None:
    pdf = text_pdf(
        "",
        [
            ("Column A", 72, 720),
            ("Column B", 300, 720),
            ("value 1", 72, 700),
            ("milliseconds", 300, 700),
        ],
        outline=True,
    )

    def source(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=pdf)

    async with connected(source, api_key=None, url_policy=allow_public_url) as session:
        opened = await session.call_tool(
            "web_read", {"url": "https://example.org/mixed.pdf", "max_pages": 2}
        )
        assert opened.structuredContent is not None
        body = opened.structuredContent
        blank_page = await session.call_tool(
            "web_read", {"action": "read", "read_id": body["read_id"], "page": 1}
        )

    assert not opened.isError
    assert body["extraction_status"] == "partial"
    assert body["failures"][0]["kind"] == "text_layer_unavailable"
    assert body["failures"][0]["locator"] == {"page": 1}
    assert body["warnings"][0]["kind"] == "structure_incomplete"
    assert body["warnings"][0]["locator"] == {"page": 2}
    assert "section_id" not in body["outline"][0]
    assert body["outline"][1]["section_id"] == "pdf-page-2"
    assert "Column A" in body["content_markdown"]
    assert blank_page.isError
    assert blank_page.structuredContent is not None
    assert "no readable native text layer" in blank_page.structuredContent["error"]["message"]


async def test_pdf_plain_multiline_text_does_not_claim_structure_failure() -> None:
    pdf = text_pdf("First paragraph.\nSecond paragraph.")

    def source(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=pdf)

    async with connected(source, api_key=None, url_policy=allow_public_url) as session:
        opened = await session.call_tool("web_read", {"url": "https://example.org/plain.pdf"})

    assert opened.structuredContent is not None
    assert opened.structuredContent["extraction_status"] == "complete"
    assert opened.structuredContent["warnings"] == []
    assert "Second paragraph." in opened.structuredContent["content_markdown"]


async def test_pdf_worker_obeys_shared_open_deadline_and_cleans_artifact(tmp_path: Path) -> None:
    pdf = text_pdf("The native text must not outlive a timed-out open.")

    def source(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=pdf)

    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        timeout_seconds=0.05,
        artifact_directory=tmp_path,
    ) as session:
        result = await session.call_tool("web_read", {"url": "https://example.org/slow.pdf"})

    assert result.isError
    assert result.structuredContent is not None
    assert result.structuredContent["error"]["category"] == "timeout"
    assert result.structuredContent["capture_status"] == "complete"
    assert list(tmp_path.glob("web-read-*.pdf")) == []


async def test_encrypted_pdf_is_explainable_and_artifacts_are_cleaned(tmp_path: Path) -> None:
    responses = [
        text_pdf("retained artifact"),
        text_pdf("shutdown cleanup"),
        text_pdf("expiry cleanup"),
        encrypted_pdf(),
    ]

    def source(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "application/pdf"},
            content=responses.pop(0),
        )

    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
    ) as session:
        first = await session.call_tool("web_read", {"url": "https://example.org/first.pdf"})
        assert first.structuredContent is not None
        assert len(list(tmp_path.glob("web-read-*.pdf"))) == 1
        await session.call_tool(
            "web_read", {"action": "release", "read_id": first.structuredContent["read_id"]}
        )
        assert list(tmp_path.glob("web-read-*.pdf")) == []
        await session.call_tool("web_read", {"url": "https://example.org/second.pdf"})
        assert len(list(tmp_path.glob("web-read-*.pdf"))) == 1
    assert list(tmp_path.glob("web-read-*.pdf")) == []

    now = [0.0]
    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
        clock=lambda: now[0],
        idle_ttl_seconds=5,
    ) as session:
        expiring = await session.call_tool("web_read", {"url": "https://example.org/expiring.pdf"})
        assert expiring.structuredContent is not None
        now[0] = 5.0
        expired = await session.call_tool(
            "web_read",
            {
                "action": "find",
                "read_id": expiring.structuredContent["read_id"],
                "query": "expiry",
            },
        )
        assert expired.isError
        assert list(tmp_path.glob("web-read-*.pdf")) == []

    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
    ) as session:
        encrypted = await session.call_tool(
            "web_read", {"url": "https://example.org/encrypted.pdf"}
        )

    assert encrypted.isError
    assert encrypted.structuredContent is not None
    assert encrypted.structuredContent["error"]["category"] == "access_blocked"
    assert encrypted.structuredContent["capture_status"] == "complete"
    assert encrypted.structuredContent["extraction_status"] == "unavailable"
    assert list(tmp_path.glob("web-read-*.pdf")) == []


async def test_pdf_without_text_layer_returns_failure_without_retaining_artifact(
    tmp_path: Path,
) -> None:
    pdf = text_pdf("")

    def source(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=pdf)

    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
    ) as session:
        opened = await session.call_tool("web_read", {"url": "https://example.org/blank.pdf"})

    assert opened.isError
    assert opened.structuredContent is not None
    assert opened.structuredContent["error"]["category"] == "extraction_failed"
    assert opened.structuredContent["capture_status"] == "complete"
    assert opened.structuredContent["extraction_status"] == "unavailable"
    assert opened.structuredContent["failures"][0]["locator"] == {"page": 1}
    assert list(tmp_path.glob("web-read-*.pdf")) == []


async def test_pdf_read_id_does_not_survive_new_server_session() -> None:
    requests = 0
    pdf = text_pdf("short-lived state")

    def source(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=pdf)

    async with connected(source, api_key=None, url_policy=allow_public_url) as session:
        opened = await session.call_tool("web_read", {"url": "https://example.org/state.pdf"})
        assert opened.structuredContent is not None
        read_id = opened.structuredContent["read_id"]

    async with connected(source, api_key=None, url_policy=allow_public_url) as session:
        stale = await session.call_tool(
            "web_read", {"action": "read", "read_id": read_id, "page": 1}
        )

    assert stale.isError
    assert stale.structuredContent is not None
    assert stale.structuredContent["error"]["category"] == "state_expired"
    assert requests == 1


async def test_discovery_without_tavily_key_only_exposes_web_read() -> None:
    def unused_http(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected HTTP request: {request.url}")

    async with connected(unused_http, api_key=None) as session:
        discovery = await session.list_tools()

    assert [tool.name for tool in discovery.tools] == ["web_read"]
    schema = discovery.tools[0].inputSchema
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]["action"]["enum"]) == {
        "open",
        "read",
        "find",
        "advance",
        "interact",
        "asset",
        "release",
    }


async def test_open_static_html_returns_original_markdown_and_locators() -> None:
    requests: list[httpx.Request] = []

    def source(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            text="""
                <!doctype html><html lang="zh-CN"><head>
                <title>双语报告</title><meta name="description" content="fixture article">
                </head><body><main><h1>概览</h1>
                <p>中文正文 and English evidence.</p>
                <h2>Measurements</h2>
                <table><caption>Latency</caption><tr><th>Region</th><th>ms</th></tr>
                <tr><td>Singapore</td><td>42</td></tr></table>
                <p>Claim<sup><a href="#fn-1">1</a></sup>.</p>
                <p id="fn-1">1. Controlled fixture.</p></main></body></html>
            """,
        )

    async with connected(source, api_key=None, url_policy=allow_public_url) as session:
        result = await session.call_tool(
            "web_read", {"url": "https://example.org/article", "max_output_chars": 10_000}
        )

    assert not result.isError
    body = result.structuredContent
    assert body is not None
    assert body["action"] == "open"
    assert body["status"] == "ok"
    assert body["read_id"] and body["version"]
    assert body["metadata"] == {
        "url": "https://example.org/article",
        "content_type": "text/html",
        "title": "双语报告",
        "language": "zh-CN",
        "description": "fixture article",
        "retrieved_at": body["metadata"]["retrieved_at"],
    }
    assert [item["title"] for item in body["outline"]] == ["概览", "Measurements"]
    assert "# 概览" in body["content_markdown"]
    assert "中文正文 and English evidence." in body["content_markdown"]
    assert "| Region | ms |" in body["content_markdown"]
    assert "Controlled fixture." in body["content_markdown"]
    assert body["capture_status"] == "complete"
    assert body["extraction_status"] == "complete"
    assert body["output_status"] == "complete"
    assert body["processing"] == {
        "path": ["http_fetch", "html_parse", "text_extract"],
        "browser_rendered": False,
        "ocr_used": False,
    }
    assert body["next_cursor"] is None
    assert body["available_actions"] == ["read", "find", "release"]
    assert body["returned_range"]["total_chars"] == len(body["content_markdown"])
    assert len(requests) == 1


async def test_cursor_and_selection_read_from_state_without_refetch() -> None:
    requests = 0

    def source(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text=("<main><h1>First</h1><p>abcdefghij</p><h2>Second</h2><p>klmnopqrstuv</p></main>"),
        )

    async with connected(source, api_key=None, url_policy=allow_public_url) as session:
        opened = await session.call_tool(
            "web_read", {"url": "https://example.org/long", "max_output_chars": 9}
        )
        assert opened.structuredContent is not None
        body = opened.structuredContent
        chunks = [body["content_markdown"]]
        ranges = [body["returned_range"]]
        warnings = list(body["warnings"])
        cursor = body["next_cursor"]
        while cursor:
            continued = await session.call_tool(
                "web_read",
                {
                    "action": "read",
                    "read_id": body["read_id"],
                    "version": body["version"],
                    "cursor": cursor,
                    "max_output_chars": 9,
                },
            )
            assert not continued.isError
            assert continued.structuredContent is not None
            chunks.append(continued.structuredContent["content_markdown"])
            ranges.append(continued.structuredContent["returned_range"])
            warnings.extend(continued.structuredContent["warnings"])
            cursor = continued.structuredContent["next_cursor"]

        section = await session.call_tool(
            "web_read",
            {
                "action": "read",
                "read_id": body["read_id"],
                "section_id": body["outline"][1]["section_id"],
                "max_output_chars": 100,
            },
        )
        block = await session.call_tool(
            "web_read",
            {
                "action": "read",
                "read_id": body["read_id"],
                "block_id": body["locators"][-1]["block_id"],
                "max_output_chars": 100,
            },
        )

    assert "".join(chunks) == "# First\n\nabcdefghij\n\n## Second\n\nklmnopqrstuv"
    assert ranges[0]["start_char"] == 0
    assert all(left["end_char"] == right["start_char"] for left, right in zip(ranges, ranges[1:]))
    assert ranges[-1]["end_char"] == ranges[-1]["total_chars"]
    assert any(warning["kind"] == "block_split" for warning in warnings)
    assert section.structuredContent is not None
    assert section.structuredContent["content_markdown"] == "## Second\n\nklmnopqrstuv"
    assert block.structuredContent is not None
    assert block.structuredContent["content_markdown"] == "## Second\n\nklmnopqrstuv"
    assert requests == 1


async def test_find_is_deterministic_and_discloses_the_searched_scope() -> None:
    requests = 0

    def source(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text=(
                "<main><h1>Deutsch</h1><p>Die Straße ist offen.</p>"
                "<h1>中文</h1><p>目标事实位于这里。Cafe\u0301.</p></main>"
            ),
        )

    async with connected(source, api_key=None, url_policy=allow_public_url) as session:
        opened = await session.call_tool("web_read", {"url": "https://example.org/find"})
        assert opened.structuredContent is not None
        state = opened.structuredContent
        found = await session.call_tool(
            "web_read",
            {
                "action": "find",
                "read_id": state["read_id"],
                "version": state["version"],
                "query": "STRASSE",
                "scope": "document",
            },
        )
        missing = await session.call_tool(
            "web_read",
            {
                "action": "find",
                "read_id": state["read_id"],
                "query": "不存在",
                "scope": "section",
                "section_id": state["outline"][1]["section_id"],
            },
        )
        composed = await session.call_tool(
            "web_read",
            {
                "action": "find",
                "read_id": state["read_id"],
                "query": "CAFÉ",
            },
        )

    assert not found.isError
    assert found.structuredContent is not None
    assert found.structuredContent["matches"][0]["text"] == "Straße"
    assert found.structuredContent["matches"][0]["block_id"]
    assert found.structuredContent["searched_scope"] == {
        "scope": "document",
        "processed_blocks": 4,
        "unprocessed_ranges": [],
    }
    assert missing.structuredContent is not None
    assert missing.structuredContent["status"] == "ok"
    assert missing.structuredContent["matches"] == []
    assert missing.structuredContent["searched_scope"]["scope"] == "section"
    assert "searched scope" in missing.structuredContent["message"]
    assert composed.structuredContent is not None
    assert composed.structuredContent["matches"][0]["text"] == "Cafe\u0301"
    assert requests == 1


async def test_release_is_idempotent_and_expiry_never_refetches() -> None:
    now = [10.0]
    requests = 0

    def clock() -> float:
        return now[0]

    def source(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(
            200, headers={"content-type": "text/html"}, text="<main><p>stateful</p></main>"
        )

    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        clock=clock,
        idle_ttl_seconds=5,
    ) as session:
        first = await session.call_tool("web_read", {"url": "https://example.org/one"})
        assert first.structuredContent is not None
        first_id = first.structuredContent["read_id"]
        released = await session.call_tool("web_read", {"action": "release", "read_id": first_id})
        released_again = await session.call_tool(
            "web_read", {"action": "release", "read_id": first_id}
        )
        after_release = await session.call_tool(
            "web_read",
            {"action": "find", "read_id": first_id, "query": "stateful"},
        )

        second = await session.call_tool("web_read", {"url": "https://example.org/two"})
        assert second.structuredContent is not None
        now[0] = 15.0
        expired = await session.call_tool(
            "web_read",
            {
                "action": "read",
                "read_id": second.structuredContent["read_id"],
                "block_id": second.structuredContent["locators"][0]["block_id"],
            },
        )

    assert not released.isError and not released_again.isError
    assert released.structuredContent == released_again.structuredContent
    assert released.structuredContent is not None
    assert released.structuredContent["released"] is True
    assert after_release.isError and expired.isError
    assert after_release.structuredContent is not None
    assert expired.structuredContent is not None
    assert after_release.structuredContent["error"]["category"] == "state_expired"
    assert expired.structuredContent["error"]["category"] == "state_expired"
    assert requests == 2


async def test_cursor_rejects_version_change_budget_change_and_reuse() -> None:
    def source(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="<main><p>abcdefghijklmnop</p></main>",
        )

    async with connected(source, api_key=None, url_policy=allow_public_url) as session:
        opened = await session.call_tool(
            "web_read", {"url": "https://example.org/cursor", "max_output_chars": 5}
        )
        assert opened.structuredContent is not None
        body = opened.structuredContent
        wrong_version = await session.call_tool(
            "web_read",
            {
                "action": "read",
                "read_id": body["read_id"],
                "version": "wrong-version",
                "cursor": body["next_cursor"],
                "max_output_chars": 5,
            },
        )
        changed_budget = await session.call_tool(
            "web_read",
            {
                "action": "read",
                "read_id": body["read_id"],
                "cursor": body["next_cursor"],
                "max_output_chars": 6,
            },
        )
        reused = await session.call_tool(
            "web_read",
            {
                "action": "read",
                "read_id": body["read_id"],
                "cursor": body["next_cursor"],
                "max_output_chars": 5,
            },
        )

    assert wrong_version.structuredContent is not None
    assert changed_budget.structuredContent is not None
    assert reused.structuredContent is not None
    assert wrong_version.structuredContent["error"]["category"] == "version_mismatch"
    assert changed_budget.structuredContent["error"]["category"] == "cursor_invalid"
    assert reused.structuredContent["error"]["category"] == "cursor_invalid"


async def test_invalid_requests_are_rejected_before_policy_or_network() -> None:
    policy_calls: list[str] = []
    requests: list[httpx.Request] = []

    async def policy(url: str) -> bool:
        policy_calls.append(url)
        return True

    def source(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, headers={"content-type": "text/html"}, text="<p>x</p>")

    invalid: list[dict[str, Any]] = [
        {"url": "file:///etc/passwd"},
        {"url": "https://user:secret@example.org/"},
        {"url": "https://example.org", "read_id": "mixed"},
        {"url": "https://example.org", "unknown": True},
        {"url": "https://example.org", "max_output_chars": 100_001},
        {"url": "https://example.org", "max_pages": 101},
        {"action": "read", "read_id": "x", "cursor": "a", "block_id": "b"},
        {"action": "find", "read_id": "x", "query": "q", "cursor": "a"},
        {"action": "find", "read_id": "x", "query": "q", "scope": "section"},
        {"action": "find", "read_id": "x", "query": "q", "scope": "page"},
        {"action": "find", "read_id": "x", "query": "q", "scope": "document", "page": 1},
        {"action": "advance", "read_id": "x", "targets": []},
        {"action": "advance", "read_id": "x", "targets": [{"page": 1, "extra": 2}]},
        {"action": "interact", "read_id": "x", "operation": "expand"},
        {"action": "asset", "read_id": "x", "asset_type": "image"},
        {"action": "release", "read_id": "x", "query": "inapplicable"},
    ]
    async with connected(source, api_key=None, url_policy=policy) as session:
        results = [await session.call_tool("web_read", arguments) for arguments in invalid]

    assert all(result.isError for result in results)
    assert all(
        result.structuredContent is not None
        and result.structuredContent["error"]["category"] == "invalid_request"
        for result in results
    )
    assert policy_calls == []
    assert requests == []


async def test_default_public_policy_blocks_non_public_ip_literals() -> None:
    requests: list[httpx.Request] = []

    def source(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, headers={"content-type": "text/html"}, text="<p>x</p>")

    async with connected(source, api_key=None) as session:
        results = [
            await session.call_tool("web_read", {"url": url})
            for url in (
                "http://127.0.0.1/private",
                "http://[::1]/private",
                "http://169.254.169.254/latest/meta-data",
            )
        ]

    assert all(result.isError for result in results)
    assert all(
        result.structuredContent is not None
        and result.structuredContent["error"]["category"] == "access_blocked"
        for result in results
    )
    assert requests == []


async def test_redirect_public_boundary_and_resource_gate_precede_acquisition() -> None:
    allowed_urls: list[str] = []
    requests: list[httpx.Request] = []

    async def policy(url: str) -> bool:
        allowed_urls.append(url)
        return url != "http://127.0.0.1/private"

    def source(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})

    async with connected(source, api_key=None, url_policy=policy) as session:
        redirected = await session.call_tool("web_read", {"url": "https://example.org/start"})

    gate_requests: list[httpx.Request] = []

    def gated_source(request: httpx.Request) -> httpx.Response:
        gate_requests.append(request)
        raise AssertionError("resource gate must run before acquisition")

    async with connected(
        gated_source,
        api_key=None,
        url_policy=allow_public_url,
        resource_gate=lambda: False,
    ) as session:
        gated = await session.call_tool("web_read", {"url": "https://example.org/"})

    assert redirected.isError and gated.isError
    assert redirected.structuredContent is not None
    assert gated.structuredContent is not None
    assert redirected.structuredContent["error"]["category"] == "access_blocked"
    assert gated.structuredContent["error"]["category"] == "resource_exhausted"
    assert allowed_urls == ["https://example.org/start", "http://127.0.0.1/private"]
    assert len(requests) == 1
    assert gate_requests == []

    scheme_requests: list[httpx.Request] = []

    def unsafe_redirect(request: httpx.Request) -> httpx.Response:
        scheme_requests.append(request)
        return httpx.Response(302, headers={"location": "file:///etc/passwd"})

    async with connected(unsafe_redirect, api_key=None, url_policy=allow_public_url) as session:
        unsafe_scheme = await session.call_tool("web_read", {"url": "https://example.org/start"})

    assert unsafe_scheme.isError
    assert unsafe_scheme.structuredContent is not None
    assert unsafe_scheme.structuredContent["error"]["category"] == "access_blocked"
    assert len(scheme_requests) == 1


async def test_source_failures_are_safe_and_timeout_does_not_commit_partial_state() -> None:
    requests: list[str] = []

    async def source(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        if request.url.path == "/slow":
            await asyncio.Event().wait()
        if request.url.path == "/denied":
            return httpx.Response(403, text="credential=do-not-disclose")
        if request.url.path == "/pdf":
            return httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF")
        if request.url.path == "/empty":
            return httpx.Response(
                200, headers={"content-type": "text/html"}, text="<html><body></body></html>"
            )
        return httpx.Response(
            200, headers={"content-type": "text/html"}, text="<main><p>recovered</p></main>"
        )

    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        timeout_seconds=0.01,
    ) as session:
        timed_out = await session.call_tool("web_read", {"url": "https://example.org/slow"})
        denied = await session.call_tool("web_read", {"url": "https://example.org/denied"})
        empty = await session.call_tool("web_read", {"url": "https://example.org/empty"})
        recovered = await session.call_tool("web_read", {"url": "https://example.org/recovered"})
        reserved = await session.call_tool(
            "web_read", {"action": "advance", "read_id": "missing", "targets": [{"page": 1}]}
        )
    async with connected(source, api_key=None, url_policy=allow_public_url) as session:
        damaged_pdf = await session.call_tool("web_read", {"url": "https://example.org/pdf"})

    assert timed_out.structuredContent is not None
    assert denied.structuredContent is not None
    assert damaged_pdf.structuredContent is not None
    assert empty.structuredContent is not None
    assert recovered.structuredContent is not None
    assert reserved.structuredContent is not None
    assert timed_out.structuredContent["error"]["category"] == "timeout"
    assert denied.structuredContent["error"]["category"] == "access_blocked"
    assert "do-not-disclose" not in denied.model_dump_json()
    assert damaged_pdf.structuredContent["error"]["category"] == "extraction_failed"
    assert damaged_pdf.structuredContent["capture_status"] == "complete"
    assert damaged_pdf.structuredContent["extraction_status"] == "failed"
    assert empty.structuredContent["error"]["category"] == "extraction_failed"
    assert empty.structuredContent["capture_status"] == "complete"
    assert empty.structuredContent["extraction_status"] == "failed"
    assert recovered.structuredContent["content_markdown"] == "recovered"
    assert reserved.structuredContent["error"]["category"] == "unsupported_format"
    assert requests == ["/slow", "/denied", "/empty", "/recovered", "/pdf"]


async def test_linked_footnote_is_kept_with_section_and_unreliable_table_is_disclosed() -> None:
    def source(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text=(
                "<main><h1>Claim</h1><p>Result.</p>"
                "<table><tr><td>A<a href='#note-1'>[1]</a></td><td>B</td></tr>"
                "<tr><td>only one</td></tr></table>"
                "<h2>Notes</h2><p id='note-1'>[1] Unit: milliseconds.</p></main>"
            ),
        )

    async with connected(source, api_key=None, url_policy=allow_public_url) as session:
        opened = await session.call_tool("web_read", {"url": "https://example.org/structure"})
        assert opened.structuredContent is not None
        body = opened.structuredContent
        section = await session.call_tool(
            "web_read",
            {
                "action": "read",
                "read_id": body["read_id"],
                "section_id": body["outline"][0]["section_id"],
            },
        )

    assert body["status"] == "partial"
    assert body["capture_status"] == "complete"
    assert body["extraction_status"] == "partial"
    assert body["warnings"][0]["kind"] == "structure_incomplete"
    assert "| A | B |" not in body["content_markdown"]
    assert body["content_markdown"].count("Unit: milliseconds.") == 1
    assert section.structuredContent is not None
    assert "Unit: milliseconds." in section.structuredContent["content_markdown"]


async def test_acquisition_size_limit_and_gate_do_not_evict_existing_state() -> None:
    gate_open = [True]

    def source(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/large":
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                content=b"x" * 2_000_001,
            )
        return httpx.Response(
            200, headers={"content-type": "text/html"}, text="<main><p>kept</p></main>"
        )

    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        resource_gate=lambda: gate_open[0],
    ) as session:
        opened = await session.call_tool("web_read", {"url": "https://example.org/kept"})
        assert opened.structuredContent is not None
        gate_open[0] = False
        gated = await session.call_tool("web_read", {"url": "https://example.org/new"})
        read_kept = await session.call_tool(
            "web_read",
            {
                "action": "read",
                "read_id": opened.structuredContent["read_id"],
                "block_id": opened.structuredContent["locators"][0]["block_id"],
            },
        )
        gate_open[0] = True
        too_large = await session.call_tool("web_read", {"url": "https://example.org/large"})

    assert gated.structuredContent is not None
    assert read_kept.structuredContent is not None
    assert too_large.structuredContent is not None
    assert gated.structuredContent["error"]["category"] == "resource_exhausted"
    assert read_kept.structuredContent["content_markdown"] == "kept"
    assert too_large.structuredContent["error"]["category"] == "resource_exhausted"
