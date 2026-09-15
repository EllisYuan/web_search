import asyncio
import errno
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from harness import connected
from pdf_fixture import scanned_pdf, text_pdf
from test_webpage_image_ocr import GrowingImageBrowser, allow_public_url

from web_search.image import ImageExtraction, OcrBlock
from web_search.limits import WORK_TEMPORARY_BYTES
from web_search.resources import AdmissionController
from web_search.web_read import WebReadService


@pytest.mark.parametrize("operation", ["text", "regions"])
@pytest.mark.parametrize("fault", ["resource_exhausted", "timeout"])
async def test_pdf_advance_worker_failure_keeps_its_category(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str, fault: str
) -> None:
    pdf = text_pdf("Retained page one.", "Native page two.")
    original = WebReadService._run_worker

    async def worker(module: str, arguments: list[str], deadline: float) -> bytes:
        if module == "web_search.pdf_target_worker" and arguments[1] == operation:
            if fault == "timeout":
                raise TimeoutError
            return json.dumps({"ok": False, "category": fault}).encode()
        return await original(module, arguments, deadline)

    monkeypatch.setattr(WebReadService, "_run_worker", staticmethod(worker))

    def source(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=pdf)

    async with connected(
        source, api_key=None, url_policy=allow_public_url, artifact_directory=tmp_path
    ) as session:
        opened = await session.call_tool(
            "web_read", {"url": "https://example.org/book.pdf", "max_pages": 1}
        )
        assert opened.structuredContent
        identity = {"read_id": opened.structuredContent["read_id"]}
        result = await session.call_tool(
            "web_read", {"action": "advance", **identity, "targets": [{"page": 2}]}
        )
        assert result.structuredContent
        body = result.structuredContent
        if operation == "regions" and fault == "resource_exhausted":
            assert not result.isError and body["status"] == "partial"
            assert "Native page two." in body["content_markdown"]
            assert any(item["kind"] == fault for item in body["failures"])
        else:
            assert result.isError and body["error"]["category"] == fault
        retained = await session.call_tool("web_read", {"action": "read", **identity, "page": 1})
        assert not retained.isError


async def test_pdf_advance_reuses_reclaimed_scratch_reservation(tmp_path: Path) -> None:
    pdf = text_pdf(*(f"Retained page {page}." for page in range(1, 12)))
    pdf += b" " * (1_800_000 - len(pdf))

    def source(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=pdf)

    async with connected(
        source, api_key=None, url_policy=allow_public_url, artifact_directory=tmp_path
    ) as session:
        opened = await session.call_tool(
            "web_read", {"url": "https://example.org/book.pdf", "max_pages": 1}
        )
        assert opened.structuredContent
        result = await session.call_tool(
            "web_read",
            {
                "action": "advance",
                "read_id": opened.structuredContent["read_id"],
                "targets": [{"page": page} for page in range(2, 12)],
            },
        )
        assert not result.isError and result.structuredContent
        assert len(result.structuredContent["processed_targets"]) == 10
        assert not result.structuredContent["failures"]


async def fixture_ocr(
    path: Path, regions: list[dict[str, float]], deadline: float
) -> ImageExtraction:
    return ImageExtraction(
        width=1400,
        height=420,
        format="PNG",
        mime_type="image/png",
        blocks=[OcrBlock("Retained OCR evidence.", 0.99, regions[0])],
        failures=[],
        warnings=[],
        runtime={},
        processed_regions=regions,
    )


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Job Object enforcement")
@pytest.mark.parametrize("kind", ["image", "pdf", "webpage"])
async def test_real_worker_memory_refusal_preserves_resource_category(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    image = (Path(__file__).parent / "fixtures" / "image-en.png").read_bytes()
    original = WebReadService._run_worker

    async def worker(module: str, arguments: list[str], deadline: float) -> bytes:
        if module == "web_search.image_worker":
            module = "fixture_exhausted_worker"
        return await original(module, arguments, deadline)

    monkeypatch.setattr(WebReadService, "_run_worker", staticmethod(worker))

    def source(request: httpx.Request) -> httpx.Response:
        if kind == "image" or request.url.path.endswith(".png"):
            mime, data = "image/png", image
        elif kind == "pdf":
            mime, data = "application/pdf", scanned_pdf(image)
        else:
            mime, data = "text/html", b'<p>Retained DOM.</p><img src="/image.png">'
        return httpx.Response(200, headers={"content-type": mime}, content=data)

    async with connected(
        source, api_key=None, url_policy=allow_public_url, artifact_directory=tmp_path
    ) as session:
        result = await session.call_tool("web_read", {"url": "https://example.org/source"})
        assert result.structuredContent
        body = result.structuredContent
        if kind == "webpage":
            assert not result.isError and body["status"] == "partial"
            assert "Retained DOM." in body["content_markdown"]
            assert any(item["kind"] == "resource_exhausted" for item in body["failures"])
        else:
            assert result.isError
            assert body["error"]["category"] == "resource_exhausted"
            assert body["error"]["retryable"] is True


@pytest.mark.parametrize("cleanup", ["release", "expiry"])
async def test_active_state_survives_expiry_scan_and_release_waits_for_commit(
    tmp_path: Path, cleanup: str
) -> None:
    started, resume = asyncio.Event(), asyncio.Event()
    now = 0.0
    calls = 0
    image = (Path(__file__).parent / "fixtures" / "image-en.png").read_bytes()

    def source(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "image/png"}, content=image)

    async def processor(
        path: Path, regions: list[dict[str, float]], deadline: float
    ) -> ImageExtraction:
        nonlocal calls
        calls += 1
        if calls == 2:
            started.set()
            await resume.wait()
        return await fixture_ocr(path, regions, deadline)

    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
        image_processor=processor,
        clock=lambda: now,
        idle_ttl_seconds=10,
    ) as session:
        opened = await session.call_tool("web_read", {"url": "https://example.org/image.png"})
        assert opened.structuredContent
        body = opened.structuredContent
        pending = asyncio.create_task(
            session.call_tool(
                "web_read",
                {
                    "action": "advance",
                    "read_id": body["read_id"],
                    "targets": [{"region": {"x": 0, "y": 0, "width": 0.5, "height": 1}}],
                },
            )
        )
        releasing = None
        try:
            await asyncio.wait_for(started.wait(), 5)
            now = 11
            found = await session.call_tool(
                "web_read", {"action": "find", "read_id": body["read_id"], "query": "Retained"}
            )
            assert not found.isError
            if cleanup == "release":
                releasing = asyncio.create_task(
                    session.call_tool("web_read", {"action": "release", "read_id": body["read_id"]})
                )
                await asyncio.sleep(0.05)
                assert not releasing.done()
        finally:
            resume.set()
            completed = await pending
        assert not completed.isError
        if releasing is not None:
            assert not (await releasing).isError
        else:
            now = 22
        expired = await session.call_tool(
            "web_read", {"action": "find", "read_id": body["read_id"], "query": "Retained"}
        )
        assert expired.isError and expired.structuredContent
        assert expired.structuredContent["error"]["category"] == "state_expired"
        assert list(tmp_path.iterdir()) == []
        recovered = await session.call_tool("web_read", {"url": "https://example.org/new.png"})
        assert not recovered.isError


@pytest.mark.parametrize("fault", [MemoryError, OSError])
async def test_pdf_resource_failure_retains_completed_ocr_page(
    tmp_path: Path, fault: type[Exception]
) -> None:
    image = (Path(__file__).parent / "fixtures" / "image-en.png").read_bytes()
    pdf = scanned_pdf(image, image)
    calls = 0

    async def processor(
        path: Path, regions: list[dict[str, float]], deadline: float
    ) -> ImageExtraction:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise fault("injected allocation/storage failure")
        return await fixture_ocr(path, regions, deadline)

    def source(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=pdf)

    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
        image_processor=processor,
    ) as session:
        opened = await session.call_tool("web_read", {"url": "https://example.org/scan.pdf"})
        assert not opened.isError and opened.structuredContent
        body = opened.structuredContent
        assert "Retained OCR evidence." in body["content_markdown"]
        assert body["status"] == "partial"
        assert any(
            item["kind"] == "resource_exhausted" and item["locator"]["page"] == 2
            for item in body["failures"]
        )
        read = await session.call_tool(
            "web_read", {"action": "read", "read_id": body["read_id"], "page": 1}
        )
        assert not read.isError
    assert list(tmp_path.iterdir()) == []


async def test_gate_rejects_all_new_work_but_preserves_read_find_and_release(
    tmp_path: Path,
) -> None:
    admitted = True

    def source(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="<html><body><div id='app'></div><script src='/app.js'></script></body></html>",
        )

    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
        resource_gate=lambda: admitted,
        browser_factory=GrowingImageBrowser,
    ) as session:
        opened = await session.call_tool(
            "web_read", {"url": "https://example.org/app", "max_output_chars": 8}
        )
        assert not opened.isError
        body = opened.structuredContent
        assert body is not None
        identity = {"read_id": body["read_id"], "version": body["version"]}
        admitted = False
        requests: list[dict[str, Any]] = [
            {"url": "https://example.org/new"},
            {"action": "advance", **identity, "targets": [{"page": 1}]},
            {"action": "interact", **identity, "target_id": "expand-target", "operation": "expand"},
        ]
        for arguments in requests:
            refused = await session.call_tool("web_read", arguments)
            assert refused.isError
            assert refused.structuredContent is not None
            assert refused.structuredContent["error"]["category"] == "resource_exhausted"
            assert refused.structuredContent["error"]["retryable"] is True
        read = await session.call_tool(
            "web_read", {"action": "read", **identity, "cursor": body["next_cursor"]}
        )
        found = await session.call_tool(
            "web_read", {"action": "find", **identity, "query": "baseline"}
        )
        released = await session.call_tool("web_read", {"action": "release", **identity})
        assert not read.isError and not found.isError and not released.isError
        assert found.structuredContent and found.structuredContent["matches"]
        admitted = True
        recovered = await session.call_tool("web_read", {"url": "https://example.org/app"})
        assert not recovered.isError


async def test_budget_above_actual_region_limit_is_rejected_before_acquisition() -> None:
    requests = 0

    def source(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, headers={"content-type": "text/html"}, text="<p>Evidence.</p>")

    async with connected(source, api_key=None, url_policy=allow_public_url) as session:
        refused = await session.call_tool(
            "web_read", {"url": "https://example.org/article", "max_regions": 5}
        )
        assert refused.isError
        assert refused.structuredContent
        assert refused.structuredContent["error"]["category"] == "invalid_request"
        assert requests == 0


@pytest.mark.parametrize("suffix", ["pdf", "png"])
async def test_storage_failure_is_resource_exhausted_and_keeps_old_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, suffix: str
) -> None:
    payload = (
        text_pdf("PDF evidence")
        if suffix == "pdf"
        else (Path(__file__).parent / "fixtures" / "image-en.png").read_bytes()
    )

    def source(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/old":
            return httpx.Response(
                200, headers={"content-type": "text/html"}, text="<p>Saved evidence.</p>"
            )
        return httpx.Response(
            200,
            headers={"content-type": "application/pdf" if suffix == "pdf" else "image/png"},
            content=payload,
        )

    async with connected(
        source, api_key=None, url_policy=allow_public_url, artifact_directory=tmp_path
    ) as session:
        old = await session.call_tool("web_read", {"url": "https://example.org/old"})
        assert old.structuredContent
        with monkeypatch.context() as patch:

            def full_disk(*args: Any, **kwargs: Any) -> Any:
                raise OSError(errno.ENOSPC, "injected disk full")

            patch.setattr("tempfile.NamedTemporaryFile", full_disk)
            failed = await session.call_tool("web_read", {"url": f"https://example.org/a.{suffix}"})
        assert failed.isError
        assert failed.structuredContent
        assert failed.structuredContent["error"]["category"] == "resource_exhausted"
        assert failed.structuredContent["error"]["retryable"] is True
        found = await session.call_tool(
            "web_read",
            {"action": "find", "read_id": old.structuredContent["read_id"], "query": "Saved"},
        )
        assert not found.isError and found.structuredContent and found.structuredContent["matches"]
        assert list(tmp_path.iterdir()) == []


async def test_storage_reservation_is_reclaimed_by_release_and_expiry(tmp_path: Path) -> None:
    now = 0.0
    payload = (Path(__file__).parent / "fixtures" / "image-en.png").read_bytes()
    admission = AdmissionController(max_temporary_bytes=WORK_TEMPORARY_BYTES + len(payload))

    def source(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "image/png"}, content=payload)

    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
        image_processor=fixture_ocr,
        admission=admission,
        clock=lambda: now,
        idle_ttl_seconds=10,
    ) as session:
        for cleanup in ("release", "expiry"):
            first = await session.call_tool("web_read", {"url": "https://example.org/image.png"})
            second = await session.call_tool("web_read", {"url": "https://example.org/image.png"})
            assert not first.isError and not second.isError
            assert first.structuredContent and second.structuredContent
            refused = await session.call_tool("web_read", {"url": "https://example.org/image.png"})
            assert refused.isError and refused.structuredContent
            assert refused.structuredContent["error"]["category"] == "resource_exhausted"
            if cleanup == "release":
                released = await session.call_tool(
                    "web_read", {"action": "release", "read_id": first.structuredContent["read_id"]}
                )
                assert not released.isError
            else:
                now += 11
            recovered = await session.call_tool(
                "web_read", {"url": "https://example.org/image.png"}
            )
            assert not recovered.isError and recovered.structuredContent
            for body in (second.structuredContent, recovered.structuredContent):
                await session.call_tool(
                    "web_read", {"action": "release", "read_id": body["read_id"]}
                )
    assert list(tmp_path.iterdir()) == []


async def test_mid_capture_storage_failure_retains_completed_image_and_dom(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    image = (Path(__file__).parent / "fixtures" / "image-en.png").read_bytes()

    def source(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith(".png"):
            return httpx.Response(200, headers={"content-type": "image/png"}, content=image)
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text='<p>Retained native evidence.</p><img src="/first.png"><img src="/second.png">',
        )

    original = tempfile.NamedTemporaryFile
    writes = 0

    def fail_second_write(*args: Any, **kwargs: Any) -> Any:
        nonlocal writes
        writes += 1
        if writes == 2:
            raise OSError(errno.ENOSPC, "injected storage exhaustion")
        return original(*args, **kwargs)

    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
        image_processor=fixture_ocr,
    ) as session:
        with monkeypatch.context() as patch:
            patch.setattr(tempfile, "NamedTemporaryFile", fail_second_write)
            opened = await session.call_tool("web_read", {"url": "https://example.org/article"})
        assert not opened.isError and opened.structuredContent
        body = opened.structuredContent
        assert body["status"] == "partial" and body["capture_status"] == "partial"
        assert "Retained native evidence." in body["content_markdown"]
        assert "Retained OCR evidence." in body["content_markdown"]
        assert any(item["kind"] == "resource_exhausted" for item in body["failures"])
        locator = next(item for item in body["locators"] if item.get("asset_id"))
        asset = await session.call_tool(
            "web_read",
            {
                "action": "asset",
                "read_id": body["read_id"],
                "asset_type": "image",
                "asset_id": locator["asset_id"],
            },
        )
        assert not asset.isError
    assert list(tmp_path.iterdir()) == []


async def test_process_wide_admission_is_shared_by_independent_mcp_servers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "web_search.resources.psutil.virtual_memory",
        lambda: SimpleNamespace(available=8_000_000_000),
    )
    started = 0
    occupied = asyncio.Event()
    resume = asyncio.Event()

    async def source(request: httpx.Request) -> httpx.Response:
        nonlocal started
        if request.url.path == "/slow":
            started += 1
            if started == 2:
                occupied.set()
            await resume.wait()
        return httpx.Response(
            200, headers={"content-type": "text/html"}, text="<p>Retained evidence.</p>"
        )

    async with (
        connected(source, api_key=None, url_policy=allow_public_url) as first,
        connected(source, api_key=None, url_policy=allow_public_url) as second,
    ):
        retained = await first.call_tool("web_read", {"url": "https://example.org/retained"})
        assert retained.structuredContent
        identity = {"read_id": retained.structuredContent["read_id"]}
        pending = [
            asyncio.create_task(client.call_tool("web_read", {"url": "https://example.org/slow"}))
            for client in (first, second)
        ]
        try:
            await asyncio.wait_for(occupied.wait(), 5)
            refused = await second.call_tool("web_read", {"url": "https://example.org/third"})
            assert refused.isError
            assert refused.structuredContent
            assert refused.structuredContent["error"]["category"] == "resource_exhausted"
            found = await first.call_tool(
                "web_read", {"action": "find", **identity, "query": "Retained"}
            )
            released = await first.call_tool("web_read", {"action": "release", **identity})
            assert not found.isError and not released.isError
        finally:
            resume.set()
            completed = await asyncio.gather(*pending)
        assert all(not result.isError for result in completed)
        recovered = await second.call_tool("web_read", {"url": "https://example.org/recovered"})
        assert not recovered.isError
