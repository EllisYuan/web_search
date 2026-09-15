import asyncio
import hashlib
from collections.abc import Awaitable, Callable
from pathlib import Path

import httpx
import pytest
from browser_fixture import javascript_site
from harness import connected
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import ImageContent

from web_search.browser import BrowserSession, InteractionTarget, RenderedPage
from web_search.image import ImageExtraction, OcrBlock
from web_search.server import create_server
from web_search.web_read import WebReadService

pytestmark = pytest.mark.asyncio

PNG_BYTES = (Path(__file__).parent / "fixtures" / "image-en.png").read_bytes()
ZH_PNG_BYTES = (Path(__file__).parent / "fixtures" / "image-zh.png").read_bytes()
FULL_REGION = {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}


class GrowingImageBrowser(BrowserSession):
    def __init__(self, _: Callable[[str], Awaitable[bool]], __: float) -> None:
        self.closed = False

    @staticmethod
    def page(url: str, *, expanded: bool) -> RenderedPage:
        extra = (
            '<p>New rendered evidence.</p><img src="/second.png" alt="Second image">'
            if expanded
            else ""
        )
        html = (
            "<html><body><main><p>Rendered baseline.</p>"
            '<img src="/first.png" alt="First image">'
            '<button aria-expanded="false">Expand</button>'
            f"{extra}</main></body></html>"
        )
        return RenderedPage(
            url=url,
            html=html,
            title="Growing images",
            language="en",
            digest=hashlib.sha256(html.encode()).hexdigest(),
            targets=(InteractionTarget("expand-target", "expand", "Expand", "#expand"),),
            blocked_requests=0,
        )

    async def open(self, url: str) -> RenderedPage:
        return self.page(url, expanded=False)

    async def interact(
        self, target_id: str, operation: str, operation_value: str | int | None
    ) -> RenderedPage:
        assert (target_id, operation, operation_value) == ("expand-target", "expand", None)
        return self.page("https://example.org/app", expanded=True)

    async def close(self) -> None:
        self.closed = True


class RacingImageBrowser(BrowserSession):
    def __init__(self, _: Callable[[str], Awaitable[bool]], __: float) -> None:
        self.started = asyncio.Event()
        self.resume = asyncio.Event()
        self.invalidated = False

    @staticmethod
    def page(*, expanded: bool) -> RenderedPage:
        extra = '<p>Interaction evidence.</p><img src="/third.png">' if expanded else ""
        html = (
            "<html><body><main><p>Baseline.</p>"
            '<img src="/first.png"><img src="/second.png">'
            f"<button>Expand</button>{extra}</main></body></html>"
        )
        return RenderedPage(
            url="https://example.org/race",
            html=html,
            title="Race",
            language="en",
            digest=hashlib.sha256(html.encode()).hexdigest(),
            targets=(InteractionTarget("race-target", "expand", "Expand", "#expand"),),
            blocked_requests=0,
        )

    async def open(self, url: str) -> RenderedPage:
        return self.page(expanded=False)

    async def interact(
        self, target_id: str, operation: str, operation_value: str | int | None
    ) -> RenderedPage:
        assert (target_id, operation, operation_value) == ("race-target", "expand", None)
        self.started.set()
        await self.resume.wait()
        return self.page(expanded=True)

    async def close(self) -> None:
        self.invalidated = True

    async def invalidate(self) -> None:
        self.invalidated = True


async def allow_public_url(url: str) -> bool:
    return url.startswith("https://example.org/")


def webpage_source(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/article":
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            text=(
                "<html><body><main><p>Native article text.</p>"
                '<figure><img src="/revenue.png" alt="Revenue chart">'
                "<figcaption>Quarterly revenue</figcaption></figure>"
                "</main></body></html>"
            ),
        )
    if request.url.path == "/revenue.png":
        return httpx.Response(200, headers={"content-type": "image/png"}, content=PNG_BYTES)
    return httpx.Response(404)


def multi_image_source(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/gallery":
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text=(
                "<html><body><main><p>Gallery body.</p>"
                '<figure><img src="/first.png"><figcaption>First</figcaption></figure>'
                '<figure><img src="/second.png"><figcaption>Second</figcaption></figure>'
                "</main></body></html>"
            ),
        )
    if request.url.path == "/first.png":
        return httpx.Response(200, headers={"content-type": "image/png"}, content=PNG_BYTES)
    if request.url.path == "/second.png":
        return httpx.Response(200, headers={"content-type": "image/png"}, content=ZH_PNG_BYTES)
    return httpx.Response(404)


async def fake_ocr(path: Path, regions: list[dict[str, float]], deadline: float) -> ImageExtraction:
    assert path.read_bytes() == PNG_BYTES
    assert regions == [FULL_REGION]
    assert deadline > 0
    return ImageExtraction(
        width=800,
        height=400,
        format="PNG",
        mime_type="image/png",
        blocks=[OcrBlock("Revenue 2026: 12,345", 0.98, FULL_REGION)],
        failures=[],
        warnings=[],
        runtime={"execution_providers": ["CPUExecutionProvider"]},
        processed_regions=[FULL_REGION],
    )


async def fixture_ocr(
    path: Path, regions: list[dict[str, float]], deadline: float
) -> ImageExtraction:
    payload = path.read_bytes()
    text = "First image text" if payload == PNG_BYTES else "Second image text"
    return ImageExtraction(
        width=800,
        height=400,
        format="PNG",
        mime_type="image/png",
        blocks=[OcrBlock(text, 0.99, regions[0])],
        failures=[],
        warnings=[],
        runtime={"execution_providers": ["CPUExecutionProvider"]},
        processed_regions=regions,
    )


async def test_static_html_open_keeps_native_text_and_discloses_image_ocr_lineage(
    tmp_path: Path,
) -> None:
    async with connected(
        webpage_source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
        image_processor=fake_ocr,
    ) as session:
        opened = await session.call_tool(
            "web_read", {"url": "https://example.org/article", "max_regions": 1}
        )

    assert not opened.isError, opened.model_dump_json()
    assert opened.structuredContent is not None
    body = opened.structuredContent
    assert "Native article text." in body["content_markdown"]
    assert "Revenue 2026: 12,345" in body["content_markdown"]
    native = next(item for item in body["locators"] if item["lineage"] == "native_text")
    ocr = next(item for item in body["locators"] if item["lineage"] == "image_ocr")
    assert native["block_id"]
    assert ocr["asset_id"]
    assert ocr["caption"] == "Quarterly revenue"
    assert ocr["source_region"] == FULL_REGION
    assert body["processing"]["ocr_used"] is True
    assert body["capture_status"] == "complete"
    assert body["extraction_status"] == "complete"


async def test_static_html_with_only_a_text_image_uses_the_ocr_path(tmp_path: Path) -> None:
    def source(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/image-only":
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                text='<html><body><main><img src="/first.png"></main></body></html>',
            )
        return httpx.Response(200, headers={"content-type": "image/png"}, content=PNG_BYTES)

    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
        image_processor=fixture_ocr,
    ) as session:
        opened = await session.call_tool("web_read", {"url": "https://example.org/image-only"})

    assert not opened.isError, opened.model_dump_json()
    assert opened.structuredContent is not None
    assert opened.structuredContent["content_markdown"] == "First image text"
    assert opened.structuredContent["locators"][0]["lineage"] == "image_ocr"


async def test_image_only_page_can_defer_ocr_and_advance_the_captured_asset(
    tmp_path: Path,
) -> None:
    calls = 0

    def source(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/image-only-deferred":
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                text=(
                    '<html><body><main><img src="/empty.png">'
                    '<img src="/first.png"></main></body></html>'
                ),
            )
        return httpx.Response(200, headers={"content-type": "image/png"}, content=PNG_BYTES)

    async def counting_ocr(
        path: Path, regions: list[dict[str, float]], deadline: float
    ) -> ImageExtraction:
        nonlocal calls
        calls += 1
        if calls == 1:
            return ImageExtraction(
                width=800,
                height=400,
                format="PNG",
                mime_type="image/png",
                blocks=[],
                failures=[],
                warnings=[],
                runtime={"execution_providers": ["CPUExecutionProvider"]},
                processed_regions=regions,
            )
        return await fixture_ocr(path, regions, deadline)

    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
        image_processor=counting_ocr,
    ) as session:
        opened = await session.call_tool(
            "web_read",
            {"url": "https://example.org/image-only-deferred", "max_regions": 1},
        )
        assert opened.structuredContent is not None
        initial = opened.structuredContent
        target = initial["unprocessed_ranges"][0]["locator"]
        asset = await session.call_tool(
            "web_read",
            {
                "action": "asset",
                "read_id": initial["read_id"],
                "version": initial["version"],
                "asset_type": "image",
                "asset_id": target["asset_id"],
            },
        )
        advanced = await session.call_tool(
            "web_read",
            {
                "action": "advance",
                "read_id": initial["read_id"],
                "version": initial["version"],
                "asset_id": target["asset_id"],
                "targets": [{"region": target["region"]}],
            },
        )

    assert not opened.isError
    assert initial["output_status"] == "empty"
    assert initial["capture_status"] == "complete"
    assert initial["extraction_status"] == "partial"
    assert calls == 2
    assert not asset.isError
    assert not advanced.isError and advanced.structuredContent is not None
    assert advanced.structuredContent["content_markdown"] == "First image text"


async def test_output_truncation_is_independent_from_image_capture_and_extraction(
    tmp_path: Path,
) -> None:
    async with connected(
        webpage_source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
        image_processor=fake_ocr,
    ) as session:
        opened = await session.call_tool(
            "web_read",
            {
                "url": "https://example.org/article",
                "max_regions": 1,
                "max_output_chars": 5,
            },
        )

    assert not opened.isError
    assert opened.structuredContent is not None
    body = opened.structuredContent
    assert body["capture_status"] == "complete"
    assert body["extraction_status"] == "complete"
    assert body["output_status"] == "truncated"
    assert body["next_cursor"] is not None


async def test_webpage_advance_and_asset_require_an_exact_captured_image_target(
    tmp_path: Path,
) -> None:
    async with connected(
        multi_image_source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
        image_processor=fixture_ocr,
    ) as session:
        opened = await session.call_tool(
            "web_read", {"url": "https://example.org/gallery", "max_regions": 1}
        )
        assert opened.structuredContent is not None
        initial = opened.structuredContent
        pending = next(
            item
            for item in initial["unprocessed_ranges"]
            if item["kind"] == "unprocessed_image_region"
        )
        second_asset_id = pending["locator"]["asset_id"]
        ambiguous = await session.call_tool(
            "web_read",
            {
                "action": "advance",
                "read_id": initial["read_id"],
                "version": initial["version"],
                "targets": [{"region": FULL_REGION}],
            },
        )
        missing = await session.call_tool(
            "web_read",
            {
                "action": "advance",
                "read_id": initial["read_id"],
                "version": initial["version"],
                "asset_id": "not-a-captured-asset",
                "targets": [{"region": FULL_REGION}],
            },
        )
        advanced = await session.call_tool(
            "web_read",
            {
                "action": "advance",
                "read_id": initial["read_id"],
                "version": initial["version"],
                "asset_id": second_asset_id,
                "targets": [{"region": FULL_REGION}],
            },
        )
        assert advanced.structuredContent is not None
        current = advanced.structuredContent
        old = await session.call_tool(
            "web_read",
            {
                "action": "find",
                "read_id": initial["read_id"],
                "version": initial["version"],
                "query": "Second image text",
            },
        )
        asset = await session.call_tool(
            "web_read",
            {
                "action": "asset",
                "read_id": initial["read_id"],
                "version": current["version"],
                "asset_type": "image",
                "asset_id": second_asset_id,
            },
        )

    assert initial["extraction_status"] == "partial"
    assert "First image text" in initial["content_markdown"]
    assert "Second image text" not in initial["content_markdown"]
    assert ambiguous.isError and ambiguous.structuredContent is not None
    assert ambiguous.structuredContent["error"]["category"] == "invalid_request"
    assert missing.isError and missing.structuredContent is not None
    assert missing.structuredContent["error"]["category"] == "not_found"
    assert not advanced.isError
    assert current["version"] != initial["version"]
    assert current["content_markdown"] == "Second image text"
    assert old.structuredContent is not None and old.structuredContent["matches"] == []
    assert not asset.isError
    assert asset.structuredContent is not None
    assert asset.structuredContent["asset_id"] == second_asset_id
    assert any(isinstance(part, ImageContent) for part in asset.content)


async def test_image_capture_failure_preserves_dom_and_committed_ocr_without_hidden_work(
    tmp_path: Path,
) -> None:
    requests: list[str] = []
    ocr_calls = 0

    def source(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        if request.url.path == "/partial":
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                text=(
                    "<html><body><main><p>Reliable DOM text.</p>"
                    '<img src="/available.png"><img src="/forbidden.png">'
                    "</main></body></html>"
                ),
            )
        if request.url.path == "/available.png":
            return httpx.Response(200, headers={"content-type": "image/png"}, content=PNG_BYTES)
        return httpx.Response(403)

    async def counting_ocr(
        path: Path, regions: list[dict[str, float]], deadline: float
    ) -> ImageExtraction:
        nonlocal ocr_calls
        ocr_calls += 1
        return await fixture_ocr(path, regions, deadline)

    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
        image_processor=counting_ocr,
    ) as session:
        opened = await session.call_tool("web_read", {"url": "https://example.org/partial"})
        assert opened.structuredContent is not None
        body = opened.structuredContent
        ocr_locator = next(item for item in body["locators"] if item["lineage"] == "image_ocr")
        baseline = (list(requests), ocr_calls)
        found = await session.call_tool(
            "web_read",
            {
                "action": "find",
                "read_id": body["read_id"],
                "version": body["version"],
                "query": "First image text",
            },
        )
        read = await session.call_tool(
            "web_read",
            {
                "action": "read",
                "read_id": body["read_id"],
                "version": body["version"],
                "block_id": ocr_locator["block_id"],
            },
        )
        asset = await session.call_tool(
            "web_read",
            {
                "action": "asset",
                "read_id": body["read_id"],
                "version": body["version"],
                "asset_type": "image",
                "asset_id": ocr_locator["asset_id"],
            },
        )
        released = await session.call_tool(
            "web_read", {"action": "release", "read_id": body["read_id"]}
        )

    assert not opened.isError
    assert "Reliable DOM text." in body["content_markdown"]
    assert "First image text" in body["content_markdown"]
    assert body["capture_status"] == "partial"
    assert body["extraction_status"] == "partial"
    assert body["failures"][0]["kind"] == "image_capture_failed"
    assert found.structuredContent is not None
    assert found.structuredContent["matches"][0]["asset_id"] == ocr_locator["asset_id"]
    assert read.structuredContent is not None
    assert read.structuredContent["locators"][0]["lineage"] == "image_ocr"
    assert not asset.isError
    assert released.structuredContent is not None and released.structuredContent["released"]
    assert (requests, ocr_calls) == baseline
    assert list(tmp_path.glob("*.image")) == []


async def test_failed_image_capture_does_not_consume_the_ocr_region_budget(
    tmp_path: Path,
) -> None:
    def source(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/capture-budget":
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                text=(
                    "<html><body><main><p>Reliable DOM.</p>"
                    '<img src="/missing.png"><img src="/available.png">'
                    "</main></body></html>"
                ),
            )
        if request.url.path == "/available.png":
            return httpx.Response(200, headers={"content-type": "image/png"}, content=PNG_BYTES)
        return httpx.Response(404)

    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
        image_processor=fixture_ocr,
    ) as session:
        opened = await session.call_tool(
            "web_read",
            {"url": "https://example.org/capture-budget", "max_regions": 1},
        )

    assert not opened.isError
    assert opened.structuredContent is not None
    body = opened.structuredContent
    assert "First image text" in body["content_markdown"]
    assert body["capture_status"] == "partial"
    assert body["failures"][0]["kind"] == "image_capture_failed"
    assert not any(
        item["kind"] == "unprocessed_image_region" for item in body["unprocessed_ranges"]
    )


async def test_captured_image_ocr_failure_requires_explicit_advance_to_retry(
    tmp_path: Path,
) -> None:
    calls = 0

    async def fail_then_succeed(
        path: Path, regions: list[dict[str, float]], deadline: float
    ) -> ImageExtraction:
        nonlocal calls
        calls += 1
        if calls == 1:
            return ImageExtraction(
                width=800,
                height=400,
                format="PNG",
                mime_type="image/png",
                blocks=[],
                failures=[
                    {
                        "kind": "region_ocr_failed",
                        "message": "Injected OCR failure.",
                        "locator": {"region": regions[0]},
                        "next_action": "asset",
                    }
                ],
                warnings=[],
                runtime={"execution_providers": ["CPUExecutionProvider"]},
                processed_regions=[],
            )
        return await fake_ocr(path, regions, deadline)

    async with connected(
        webpage_source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
        image_processor=fail_then_succeed,
    ) as session:
        opened = await session.call_tool("web_read", {"url": "https://example.org/article"})
        assert opened.structuredContent is not None
        initial = opened.structuredContent
        pending = initial["unprocessed_ranges"][0]["locator"]
        asset = await session.call_tool(
            "web_read",
            {
                "action": "asset",
                "read_id": initial["read_id"],
                "version": initial["version"],
                "asset_type": "image",
                "asset_id": pending["asset_id"],
            },
        )
        advanced = await session.call_tool(
            "web_read",
            {
                "action": "advance",
                "read_id": initial["read_id"],
                "version": initial["version"],
                "asset_id": pending["asset_id"],
                "targets": [{"region": pending["region"]}],
            },
        )

    assert not opened.isError
    assert initial["capture_status"] == "complete"
    assert initial["extraction_status"] == "partial"
    assert initial["failures"][0]["kind"] == "region_ocr_failed"
    assert not asset.isError
    assert not advanced.isError and advanced.structuredContent is not None
    assert advanced.structuredContent["version"] != initial["version"]
    assert advanced.structuredContent["content_markdown"] == "Revenue 2026: 12,345"
    assert advanced.structuredContent["unprocessed_ranges"] == []
    assert advanced.structuredContent["failures"] == []
    assert calls == 2


async def test_webpage_advance_discloses_ocr_failure_without_committing_a_version(
    tmp_path: Path,
) -> None:
    calls = 0

    async def no_text(
        path: Path, regions: list[dict[str, float]], deadline: float
    ) -> ImageExtraction:
        nonlocal calls
        calls += 1
        if calls == 1:
            return await fixture_ocr(path, regions, deadline)
        return ImageExtraction(
            width=800,
            height=400,
            format="PNG",
            mime_type="image/png",
            blocks=[],
            failures=[
                {
                    "kind": "region_ocr_failed",
                    "message": "No reliable text.",
                    "locator": {"region": regions[0]},
                    "next_action": "asset",
                }
            ],
            warnings=[],
            runtime={"execution_providers": ["CPUExecutionProvider"]},
            processed_regions=[],
        )

    async with connected(
        multi_image_source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
        image_processor=no_text,
    ) as session:
        opened = await session.call_tool(
            "web_read", {"url": "https://example.org/gallery", "max_regions": 1}
        )
        assert opened.structuredContent is not None
        initial = opened.structuredContent
        target = initial["unprocessed_ranges"][0]["locator"]
        advanced = await session.call_tool(
            "web_read",
            {
                "action": "advance",
                "read_id": initial["read_id"],
                "version": initial["version"],
                "asset_id": target["asset_id"],
                "targets": [{"region": target["region"]}],
            },
        )

    assert not advanced.isError
    assert advanced.structuredContent is not None
    body = advanced.structuredContent
    assert body["version"] == initial["version"]
    assert body["status"] == "partial"
    assert body["extraction_status"] == "partial"
    assert body["failures"][-1]["kind"] == "region_ocr_failed"
    assert body["unprocessed_ranges"][-1]["locator"]["asset_id"] == target["asset_id"]
    assert calls == 2


async def test_interaction_does_not_refetch_a_previously_failed_image_reference() -> None:
    image_requests = 0

    def source(request: httpx.Request) -> httpx.Response:
        nonlocal image_requests
        if request.url.path == "/broken-app":
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                text="<html><body><main></main><script></script></body></html>",
            )
        image_requests += 1
        return httpx.Response(404)

    class BrokenImageBrowser(GrowingImageBrowser):
        @staticmethod
        def page(url: str, *, expanded: bool) -> RenderedPage:
            extra = "<p>Expanded.</p>" if expanded else ""
            html = (
                "<html><body><main><p>Rendered.</p>"
                f'<img src="/broken.png"><button>Expand</button>{extra}</main></body></html>'
            )
            return RenderedPage(
                url=url,
                html=html,
                title="Broken image",
                language="en",
                digest=hashlib.sha256(html.encode()).hexdigest(),
                targets=(InteractionTarget("expand-target", "expand", "Expand", "#expand"),),
                blocked_requests=0,
            )

    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        browser_factory=BrokenImageBrowser,
    ) as session:
        opened = await session.call_tool("web_read", {"url": "https://example.org/broken-app"})
        assert opened.structuredContent is not None
        initial = opened.structuredContent
        interacted = await session.call_tool(
            "web_read",
            {
                "action": "interact",
                "read_id": initial["read_id"],
                "version": initial["version"],
                "target_id": "expand-target",
                "operation": "expand",
            },
        )

    assert not opened.isError and not interacted.isError
    assert image_requests == 1
    assert interacted.structuredContent is not None
    assert interacted.structuredContent["capture_status"] == "partial"
    assert interacted.structuredContent["failures"][0]["kind"] == "image_capture_failed"


async def test_interaction_cannot_overwrite_a_concurrent_webpage_image_advance(
    tmp_path: Path,
) -> None:
    browsers: list[RacingImageBrowser] = []

    def factory(policy: Callable[[str], Awaitable[bool]], timeout: float) -> BrowserSession:
        browser = RacingImageBrowser(policy, timeout)
        browsers.append(browser)
        return browser

    def source(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/race":
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                text="<html><body><main></main><script></script></body></html>",
            )
        payload = PNG_BYTES if request.url.path != "/second.png" else ZH_PNG_BYTES
        return httpx.Response(200, headers={"content-type": "image/png"}, content=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(source)) as http:
        service = WebReadService(
            http,
            url_policy=allow_public_url,
            artifact_directory=tmp_path,
            image_processor=fixture_ocr,
            browser_factory=factory,
        )
        async with service.lifecycle():
            opened, opened_error = await service.dispatch(
                {"url": "https://example.org/race", "max_regions": 1}
            )
            pending_target = opened["unprocessed_ranges"][0]["locator"]
            interaction = asyncio.create_task(
                service.dispatch(
                    {
                        "action": "interact",
                        "read_id": opened["read_id"],
                        "version": opened["version"],
                        "target_id": "race-target",
                        "operation": "expand",
                    }
                )
            )
            await asyncio.wait_for(browsers[0].started.wait(), timeout=1)
            advanced, advanced_error = await service.dispatch(
                {
                    "action": "advance",
                    "read_id": opened["read_id"],
                    "version": opened["version"],
                    "asset_id": pending_target["asset_id"],
                    "targets": [{"region": pending_target["region"]}],
                }
            )
            browsers[0].resume.set()
            interacted, interacted_error = await interaction

    assert not opened_error and not advanced_error
    assert advanced["version"] != opened["version"]
    assert interacted_error
    assert interacted["error"]["category"] == "version_mismatch"
    assert interacted["version"] == advanced["version"]
    assert browsers[0].invalidated is True


async def test_interaction_atomically_adds_new_rendered_image_to_only_the_new_version(
    tmp_path: Path,
) -> None:
    image_requests: list[str] = []

    def source(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/app":
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                text="<html><body><main></main><script src='/app.js'></script></body></html>",
            )
        image_requests.append(request.url.path)
        payload = PNG_BYTES if request.url.path == "/first.png" else ZH_PNG_BYTES
        return httpx.Response(200, headers={"content-type": "image/png"}, content=payload)

    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
        image_processor=fixture_ocr,
        browser_factory=GrowingImageBrowser,
    ) as session:
        opened = await session.call_tool("web_read", {"url": "https://example.org/app"})
        assert opened.structuredContent is not None
        initial = opened.structuredContent
        interacted = await session.call_tool(
            "web_read",
            {
                "action": "interact",
                "read_id": initial["read_id"],
                "version": initial["version"],
                "target_id": "expand-target",
                "operation": "expand",
            },
        )
        assert interacted.structuredContent is not None
        current = interacted.structuredContent
        second_locator = current["locators"][-1]
        assert second_locator["lineage"] == "image_ocr"
        old_asset = await session.call_tool(
            "web_read",
            {
                "action": "asset",
                "read_id": initial["read_id"],
                "version": initial["version"],
                "asset_type": "image",
                "asset_id": second_locator["asset_id"],
            },
        )
        new_asset = await session.call_tool(
            "web_read",
            {
                "action": "asset",
                "read_id": initial["read_id"],
                "version": current["version"],
                "asset_type": "image",
                "asset_id": second_locator["asset_id"],
            },
        )

    assert not opened.isError and not interacted.isError
    assert "First image text" in initial["content_markdown"]
    assert "Second image text" in current["content_markdown"]
    assert "New rendered evidence." in current["content_markdown"]
    assert current["version"] != initial["version"]
    assert image_requests == ["/first.png", "/second.png"]
    assert old_asset.isError and old_asset.structuredContent is not None
    assert old_asset.structuredContent["error"]["category"] == "not_found"
    assert not new_asset.isError


async def test_real_cpu_ocr_reads_text_image_embedded_in_static_html(tmp_path: Path) -> None:
    async with connected(
        webpage_source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
        timeout_seconds=30,
    ) as session:
        opened = await session.call_tool("web_read", {"url": "https://example.org/article"})

    assert not opened.isError, opened.model_dump_json()
    assert opened.structuredContent is not None
    body = opened.structuredContent
    assert "AX-2026-0917" in body["content_markdown"]
    assert "12345.67" in body["content_markdown"]
    assert body["processing"]["ocr_used"] is True
    runtime = body["processing"]["image_ocr"][0]
    assert runtime["execution_providers"] == ["CPUExecutionProvider"]
    assert any(warning["kind"] == "structure_incomplete" for warning in body["warnings"])


async def test_real_browser_and_cpu_ocr_commit_new_image_after_interaction(
    tmp_path: Path,
) -> None:
    async with javascript_site() as base_url:
        async with httpx.AsyncClient(trust_env=False) as http:
            server = create_server(
                api_key=None,
                http=http,
                url_policy=lambda _: _allow_all(),
                artifact_directory=tmp_path,
                timeout_seconds=30,
            )
            async with create_connected_server_and_client_session(server) as session:
                opened = await session.call_tool(
                    "web_read", {"url": f"{base_url}/image-app", "max_regions": 1}
                )
                assert opened.structuredContent is not None
                initial = opened.structuredContent
                target = next(
                    item
                    for item in initial["interaction_targets"]
                    if item["operation"] == "load_more"
                )
                interacted = await session.call_tool(
                    "web_read",
                    {
                        "action": "interact",
                        "read_id": initial["read_id"],
                        "version": initial["version"],
                        "target_id": target["target_id"],
                        "operation": "load_more",
                    },
                )

    assert not opened.isError, opened.model_dump_json()
    assert "京东20260917" in initial["content_markdown"]
    assert initial["processing"]["browser_rendered"] is True
    assert initial["processing"]["image_ocr"][0]["execution_providers"] == ["CPUExecutionProvider"]
    assert not interacted.isError, interacted.model_dump_json()
    assert interacted.structuredContent is not None
    current = interacted.structuredContent
    assert current["version"] != initial["version"]
    assert "New rendered image" in current["content_markdown"]
    assert "AX-2026-0917" in current["content_markdown"]
    assert current["processing"]["browser_rendered"] is True
    assert current["processing"]["ocr_used"] is True


async def _allow_all() -> bool:
    return True
