import asyncio
from pathlib import Path

import httpx
import pytest
from harness import connected
from pdf_fixture import (
    combine_pdfs,
    mixed_page_pdf,
    mixed_regions_pdf,
    scanned_pdf,
    text_pdf,
)

from web_search.image import ImageExtraction, OcrBlock


async def allow_public_url(url: str) -> bool:
    return True


async def test_open_scanned_pdf_ocr_preserves_page_region_and_lineage(tmp_path: Path) -> None:
    image = (Path(__file__).parent / "fixtures" / "image-zh.png").read_bytes()
    payload = scanned_pdf(image)
    processed_paths: list[Path] = []

    def source(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=payload)

    async def processor(
        artifact_path: Path,
        regions: list[dict[str, float]],
        deadline: float,
    ) -> ImageExtraction:
        processed_paths.append(artifact_path)
        assert artifact_path.suffix == ".png"
        assert regions == [{"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}]
        return ImageExtraction(
            width=1200,
            height=500,
            format="PNG",
            mime_type="image/png",
            blocks=[
                OcrBlock(
                    "京东20260917 兰花 12345.67",
                    0.97,
                    {"x": 0.08, "y": 0.2, "width": 0.7, "height": 0.2},
                )
            ],
            failures=[],
            warnings=[],
            runtime={"execution_providers": ["CPUExecutionProvider"]},
            processed_regions=regions,
        )

    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
        image_processor=processor,
    ) as session:
        opened = await session.call_tool(
            "web_read",
            {
                "url": "https://example.org/scanned-zh.pdf",
                "max_pages": 1,
                "max_regions": 1,
            },
        )

    assert not opened.isError, opened.model_dump_json()
    assert opened.structuredContent is not None
    body = opened.structuredContent
    assert "京东20260917 兰花 12345.67" in body["content_markdown"]
    assert body["locators"][0]["page"] == 1
    assert body["locators"][0]["source_region"] == {
        "x": 0.08,
        "y": 0.2,
        "width": 0.7,
        "height": 0.2,
    }
    assert body["locators"][0]["processing_lineage"] == {
        "source": "ocr",
        "path": ["captured_pdf", "pdf_rasterize", "cpu_ocr"],
    }
    assert body["processing"]["ocr_used"] is True
    assert body["processing"]["execution_providers"] == ["CPUExecutionProvider"]
    assert body["processed_targets"] == [
        {"page": 1, "region": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}}
    ]
    assert processed_paths and not processed_paths[0].exists()
    assert list(tmp_path.glob("*.png")) == []


async def test_same_page_mixed_pdf_reuses_native_text_and_deduplicates_ocr(
    tmp_path: Path,
) -> None:
    image = (Path(__file__).parent / "fixtures" / "image-en.png").read_bytes()
    payload = mixed_page_pdf(image, "Native heading ORCHID-4096")

    def source(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=payload)

    async def processor(
        artifact_path: Path,
        regions: list[dict[str, float]],
        deadline: float,
    ) -> ImageExtraction:
        return ImageExtraction(
            width=1200,
            height=500,
            format="PNG",
            mime_type="image/png",
            blocks=[
                OcrBlock(
                    ("Native headlng ORCHID-4096 Scanned table value AX-2026-0917"),
                    0.96,
                    {"x": 0.1, "y": 0.05, "width": 0.7, "height": 0.35},
                ),
            ],
            failures=[],
            warnings=[],
            runtime={"execution_providers": ["CPUExecutionProvider"]},
            processed_regions=regions,
        )

    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
        image_processor=processor,
    ) as session:
        opened = await session.call_tool(
            "web_read",
            {
                "url": "https://example.org/mixed-page.pdf",
                "max_pages": 1,
                "max_regions": 1,
            },
        )

    assert not opened.isError, opened.model_dump_json()
    assert opened.structuredContent is not None
    body = opened.structuredContent
    assert body["content_markdown"].count("Native heading ORCHID-4096") == 1
    assert "Native headlng ORCHID-4096" not in body["content_markdown"]
    assert "Scanned table value AX-2026-0917" in body["content_markdown"]
    assert {locator["processing_lineage"]["source"] for locator in body["locators"]} == {
        "native_text",
        "ocr",
    }
    assert body["processing"]["ocr_used"] is True
    assert body["failures"] == []


async def test_partial_pdf_ocr_region_keeps_text_but_remains_retryable(
    tmp_path: Path,
) -> None:
    image = (Path(__file__).parent / "fixtures" / "image-en.png").read_bytes()
    payload = scanned_pdf(image)
    calls = 0

    def source(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=payload)

    async def processor(
        artifact_path: Path,
        regions: list[dict[str, float]],
        deadline: float,
    ) -> ImageExtraction:
        nonlocal calls
        calls += 1
        failure = (
            []
            if calls == 2
            else [
                {
                    "kind": "region_ocr_failed",
                    "message": "One OCR subregion failed.",
                    "locator": {"region": regions[0]},
                    "next_action": "advance",
                }
            ]
        )
        text = "Recovered OCR tail." if calls == 2 else "Reliable OCR prefix."
        return ImageExtraction(
            width=1200,
            height=500,
            format="PNG",
            mime_type="image/png",
            blocks=[
                OcrBlock(
                    text,
                    0.97,
                    {"x": 0.1, "y": 0.2, "width": 0.7, "height": 0.2},
                )
            ],
            failures=failure,
            warnings=[],
            runtime={"execution_providers": ["CPUExecutionProvider"]},
            processed_regions=regions if not failure else [],
        )

    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
        image_processor=processor,
    ) as session:
        opened = await session.call_tool(
            "web_read",
            {
                "url": "https://example.org/partial-region.pdf",
                "max_pages": 1,
                "max_regions": 1,
            },
        )
        assert opened.structuredContent is not None
        initial = opened.structuredContent
        target = next(
            item["locator"]
            for item in initial["unprocessed_ranges"]
            if item["kind"] == "unprocessed_region"
        )
        retried = await session.call_tool(
            "web_read",
            {
                "action": "advance",
                "read_id": initial["read_id"],
                "version": initial["version"],
                "targets": [target],
                "max_regions": 1,
            },
        )

    assert calls == 2
    assert "Reliable OCR prefix." in initial["content_markdown"]
    assert initial["processed_targets"] == []
    assert retried.structuredContent is not None
    assert retried.structuredContent["version"] != initial["version"]
    assert "Recovered OCR tail." in retried.structuredContent["content_markdown"]
    assert not retried.structuredContent["failures"]
    assert not retried.structuredContent["unprocessed_ranges"]


async def test_mixed_pdf_deduplicates_short_chinese_native_text(tmp_path: Path) -> None:
    image = (Path(__file__).parent / "fixtures" / "image-zh.png").read_bytes()
    payload = mixed_page_pdf(image, "单位")

    def source(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=payload)

    async def processor(
        artifact_path: Path,
        regions: list[dict[str, float]],
        deadline: float,
    ) -> ImageExtraction:
        return ImageExtraction(
            width=1200,
            height=500,
            format="PNG",
            mime_type="image/png",
            blocks=[
                OcrBlock(
                    "单位 扫描值 42",
                    0.98,
                    {"x": 0.1, "y": 0.2, "width": 0.7, "height": 0.2},
                )
            ],
            failures=[],
            warnings=[],
            runtime={"execution_providers": ["CPUExecutionProvider"]},
            processed_regions=regions,
        )

    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
        image_processor=processor,
    ) as session:
        opened = await session.call_tool(
            "web_read",
            {
                "url": "https://example.org/mixed-short-zh.pdf",
                "max_pages": 1,
                "max_regions": 1,
            },
        )

    assert opened.structuredContent is not None
    assert opened.structuredContent["content_markdown"].count("单位") == 1
    assert "扫描值 42" in opened.structuredContent["content_markdown"]


async def test_failure_only_pdf_advance_discloses_ocr_execution(tmp_path: Path) -> None:
    image = (Path(__file__).parent / "fixtures" / "image-en.png").read_bytes()
    payload = scanned_pdf(image, image)
    calls = 0

    def source(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=payload)

    async def processor(
        artifact_path: Path,
        regions: list[dict[str, float]],
        deadline: float,
    ) -> ImageExtraction:
        nonlocal calls
        calls += 1
        if calls == 1:
            return ImageExtraction(
                width=1200,
                height=500,
                format="PNG",
                mime_type="image/png",
                blocks=[
                    OcrBlock(
                        "Initial scanned page.",
                        0.98,
                        {"x": 0.1, "y": 0.2, "width": 0.7, "height": 0.2},
                    )
                ],
                failures=[],
                warnings=[],
                runtime={"execution_providers": ["CPUExecutionProvider"]},
                processed_regions=regions,
            )
        raise RuntimeError("Injected OCR backend failure.")

    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
        image_processor=processor,
    ) as session:
        opened = await session.call_tool(
            "web_read",
            {
                "url": "https://example.org/failure-trace.pdf",
                "max_pages": 1,
                "max_regions": 1,
            },
        )
        assert opened.structuredContent is not None
        advanced = await session.call_tool(
            "web_read",
            {
                "action": "advance",
                "read_id": opened.structuredContent["read_id"],
                "version": opened.structuredContent["version"],
                "targets": [{"page": 2}],
                "max_regions": 1,
            },
        )

    assert calls == 2
    assert advanced.structuredContent is not None
    assert advanced.structuredContent["processing"]["ocr_used"] is True
    assert advanced.structuredContent["processing"]["path"] == [
        "captured_pdf",
        "pdf_rasterize",
        "cpu_ocr",
    ]
    assert advanced.structuredContent["failures"][-1]["kind"] == ("target_extraction_failed")


async def test_advance_scanned_pdf_page_is_nonsequential_atomic_and_keeps_old_cursor(
    tmp_path: Path,
) -> None:
    image = (Path(__file__).parent / "fixtures" / "image-en.png").read_bytes()
    payload = scanned_pdf(image, image, image)
    requests = 0
    ocr_calls = 0

    def source(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=payload)

    async def processor(
        artifact_path: Path,
        regions: list[dict[str, float]],
        deadline: float,
    ) -> ImageExtraction:
        nonlocal ocr_calls
        ocr_calls += 1
        text = "Scanned page one cursor evidence." if ocr_calls == 1 else "Page three OCR ORCHID-3"
        return ImageExtraction(
            width=1200,
            height=500,
            format="PNG",
            mime_type="image/png",
            blocks=[OcrBlock(text, 0.98, {"x": 0.1, "y": 0.2, "width": 0.7, "height": 0.2})],
            failures=[],
            warnings=[],
            runtime={"execution_providers": ["CPUExecutionProvider"]},
            processed_regions=regions,
        )

    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
        image_processor=processor,
    ) as session:
        opened = await session.call_tool(
            "web_read",
            {
                "url": "https://example.org/long-scan.pdf",
                "max_pages": 1,
                "max_regions": 1,
                "max_output_chars": 8,
            },
        )
        assert opened.structuredContent is not None
        initial = opened.structuredContent
        advanced = await session.call_tool(
            "web_read",
            {
                "action": "advance",
                "read_id": initial["read_id"],
                "version": initial["version"],
                "targets": [{"page": 3}],
                "max_pages": 1,
                "max_regions": 1,
            },
        )
        assert advanced.structuredContent is not None
        old_cursor = await session.call_tool(
            "web_read",
            {
                "action": "read",
                "read_id": initial["read_id"],
                "version": initial["version"],
                "cursor": initial["next_cursor"],
                "max_output_chars": 8,
            },
        )
        current_find = await session.call_tool(
            "web_read",
            {
                "action": "find",
                "read_id": initial["read_id"],
                "version": advanced.structuredContent["version"],
                "query": "ORCHID-3",
                "scope": "page",
                "page": 3,
            },
        )

    assert not advanced.isError, advanced.model_dump_json()
    body = advanced.structuredContent
    assert body["version"] != initial["version"]
    assert body["processed_targets"] == [{"page": 3}]
    assert "Page three OCR ORCHID-3" in body["content_markdown"]
    assert body["processing"]["source_acquisition"] is False
    assert body["processing"]["ocr_used"] is True
    assert old_cursor.structuredContent is not None
    assert old_cursor.structuredContent["version"] == initial["version"]
    assert current_find.structuredContent is not None
    assert current_find.structuredContent["matches"][0]["page"] == 3
    assert requests == 1
    assert ocr_calls == 2


async def test_pdf_ocr_failure_keeps_success_and_retries_only_on_explicit_advance(
    tmp_path: Path,
) -> None:
    image = (Path(__file__).parent / "fixtures" / "image-en.png").read_bytes()
    payload = scanned_pdf(image, image)
    calls = 0

    def source(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=payload)

    async def processor(
        artifact_path: Path,
        regions: list[dict[str, float]],
        deadline: float,
    ) -> ImageExtraction:
        nonlocal calls
        calls += 1
        if calls == 2:
            return ImageExtraction(
                width=1200,
                height=500,
                format="PNG",
                mime_type="image/png",
                blocks=[],
                failures=[
                    {
                        "kind": "region_ocr_failed",
                        "message": "Injected middle-page OCR failure.",
                        "locator": {"region": regions[0]},
                        "next_action": "asset",
                    }
                ],
                warnings=[],
                runtime={"execution_providers": ["CPUExecutionProvider"]},
                processed_regions=[],
            )
        text = "Successful scanned page one." if calls == 1 else "Recovered page two OCR."
        return ImageExtraction(
            width=1200,
            height=500,
            format="PNG",
            mime_type="image/png",
            blocks=[OcrBlock(text, 0.98, {"x": 0.1, "y": 0.2, "width": 0.7, "height": 0.2})],
            failures=[],
            warnings=[],
            runtime={"execution_providers": ["CPUExecutionProvider"]},
            processed_regions=regions,
        )

    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
        image_processor=processor,
    ) as session:
        opened = await session.call_tool(
            "web_read",
            {
                "url": "https://example.org/partial-scan.pdf",
                "max_pages": 2,
                "max_regions": 2,
            },
        )
        assert opened.structuredContent is not None
        partial = opened.structuredContent
        read_success = await session.call_tool(
            "web_read", {"action": "read", "read_id": partial["read_id"], "page": 1}
        )
        assert calls == 2
        retried = await session.call_tool(
            "web_read",
            {
                "action": "advance",
                "read_id": partial["read_id"],
                "version": partial["version"],
                "targets": [{"page": 2}],
                "max_pages": 1,
                "max_regions": 1,
            },
        )

    assert not opened.isError
    assert partial["status"] == "partial"
    assert "Successful scanned page one." in partial["content_markdown"]
    assert partial["processed_targets"] == [
        {"page": 1, "region": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}}
    ]
    assert partial["failures"][-1]["locator"]["page"] == 2
    assert any(
        item["kind"] == "unprocessed_region" and item["locator"]["page"] == 2
        for item in partial["unprocessed_ranges"]
    )
    assert not read_success.isError
    assert calls == 3
    assert retried.structuredContent is not None
    assert retried.structuredContent["version"] != partial["version"]
    assert "Recovered page two OCR." in retried.structuredContent["content_markdown"]
    assert not any(
        failure.get("locator", {}).get("page") == 2
        for failure in retried.structuredContent["failures"]
    )


async def test_real_cpu_ocr_reads_controlled_english_and_chinese_scanned_pdfs(
    tmp_path: Path,
) -> None:
    cases = [
        ("image-en.png", ["AX-2026-0917", "12345.67", "ORCHID"]),
        ("image-zh.png", ["京东20260917", "12345.67", "兰花"]),
    ]
    for filename, references in cases:
        image = (Path(__file__).parent / "fixtures" / filename).read_bytes()
        payload = scanned_pdf(image)

        def source(request: httpx.Request, data: bytes = payload) -> httpx.Response:
            return httpx.Response(
                200,
                headers={"content-type": "application/pdf"},
                content=data,
            )

        async with connected(
            source,
            api_key=None,
            url_policy=allow_public_url,
            artifact_directory=tmp_path,
            timeout_seconds=30,
        ) as session:
            opened = await session.call_tool(
                "web_read",
                {
                    "url": f"https://example.org/{filename}.pdf",
                    "max_pages": 1,
                    "max_regions": 1,
                },
            )

        assert not opened.isError, opened.model_dump_json()
        assert opened.structuredContent is not None
        body = opened.structuredContent
        assert all(reference in body["content_markdown"] for reference in references)
        assert body["processing"]["execution_providers"] == ["CPUExecutionProvider"]
        assert body["processing"]["ocr_used"] is True
        assert all(locator["processing_lineage"]["source"] == "ocr" for locator in body["locators"])


async def test_real_cpu_ocr_reads_same_page_and_cross_page_mixed_pdfs(tmp_path: Path) -> None:
    image = (Path(__file__).parent / "fixtures" / "image-en.png").read_bytes()
    cases = [
        (
            mixed_page_pdf(image, "Reliable native heading NATIVE-22"),
            ["Reliable native heading NATIVE-22", "AX-2026-0917", "ORCHID"],
        ),
        (
            combine_pdfs(text_pdf("Cross-page native evidence."), scanned_pdf(image)),
            ["Cross-page native evidence.", "AX-2026-0917", "ORCHID"],
        ),
    ]
    for index, (payload, references) in enumerate(cases):

        def source(request: httpx.Request, data: bytes = payload) -> httpx.Response:
            return httpx.Response(
                200,
                headers={"content-type": "application/pdf"},
                content=data,
            )

        async with connected(
            source,
            api_key=None,
            url_policy=allow_public_url,
            artifact_directory=tmp_path,
            timeout_seconds=30,
        ) as session:
            opened = await session.call_tool(
                "web_read",
                {
                    "url": f"https://example.org/mixed-{index}.pdf",
                    "max_pages": 2,
                    "max_regions": 1,
                },
            )

        assert not opened.isError, opened.model_dump_json()
        assert opened.structuredContent is not None
        body = opened.structuredContent
        assert all(reference in body["content_markdown"] for reference in references)
        assert body["content_markdown"].count(references[0]) == 1
        assert {locator["processing_lineage"]["source"] for locator in body["locators"]} == {
            "native_text",
            "ocr",
        }
        assert body["processing"]["ocr_used"] is True


async def test_open_scanned_pdf_enforces_region_hard_limit_and_locates_remaining_work(
    tmp_path: Path,
) -> None:
    image = (Path(__file__).parent / "fixtures" / "image-en.png").read_bytes()
    payload = scanned_pdf(image, image, image, image, image)
    calls = 0

    def source(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=payload)

    async def processor(
        artifact_path: Path,
        regions: list[dict[str, float]],
        deadline: float,
    ) -> ImageExtraction:
        nonlocal calls
        calls += 1
        return ImageExtraction(
            width=1200,
            height=500,
            format="PNG",
            mime_type="image/png",
            blocks=[
                OcrBlock(
                    f"Bounded OCR page {calls}",
                    0.99,
                    {"x": 0.1, "y": 0.2, "width": 0.7, "height": 0.2},
                )
            ],
            failures=[],
            warnings=[],
            runtime={"execution_providers": ["CPUExecutionProvider"]},
            processed_regions=regions,
        )

    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
        image_processor=processor,
    ) as session:
        opened = await session.call_tool(
            "web_read",
            {
                "url": "https://example.org/bounded-long-scan.pdf",
                "max_pages": 5,
                "max_regions": 4,
            },
        )

    assert not opened.isError
    assert opened.structuredContent is not None
    body = opened.structuredContent
    assert calls == 4
    assert len(body["processed_targets"]) == 4
    assert any(
        item["kind"] == "unprocessed_region" and item["locator"]["page"] == 5
        for item in body["unprocessed_ranges"]
    )
    assert body["capture_status"] == "complete"
    assert body["extraction_status"] == "partial"


async def test_pdf_ocr_advance_timeout_commits_completed_targets_and_reports_gap(
    tmp_path: Path,
) -> None:
    image = (Path(__file__).parent / "fixtures" / "image-en.png").read_bytes()
    payload = scanned_pdf(image, image, image)
    calls = 0

    def source(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=payload)

    async def processor(
        artifact_path: Path,
        regions: list[dict[str, float]],
        deadline: float,
    ) -> ImageExtraction:
        nonlocal calls
        calls += 1
        if calls == 3:
            await asyncio.Event().wait()
            raise AssertionError("unreachable")
        return ImageExtraction(
            width=1200,
            height=500,
            format="PNG",
            mime_type="image/png",
            blocks=[
                OcrBlock(
                    f"OCR call {calls}",
                    0.99,
                    {"x": 0.1, "y": 0.2, "width": 0.7, "height": 0.2},
                )
            ],
            failures=[],
            warnings=[],
            runtime={"execution_providers": ["CPUExecutionProvider"]},
            processed_regions=regions,
        )

    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
        image_processor=processor,
        timeout_seconds=2,
    ) as session:
        opened = await session.call_tool(
            "web_read",
            {
                "url": "https://example.org/atomic-scan.pdf",
                "max_pages": 1,
                "max_regions": 1,
            },
        )
        assert opened.structuredContent is not None
        initial = opened.structuredContent
        timed_out = await session.call_tool(
            "web_read",
            {
                "action": "advance",
                "read_id": initial["read_id"],
                "version": initial["version"],
                "targets": [{"page": 2}, {"page": 3}],
                "max_pages": 2,
                "max_regions": 2,
            },
        )
        current_page_two = await session.call_tool(
            "web_read",
            {
                "action": "read",
                "read_id": initial["read_id"],
                "page": 2,
            },
        )

    assert not timed_out.isError
    assert timed_out.structuredContent is not None
    assert timed_out.structuredContent["status"] == "partial"
    assert any(item["kind"] == "timeout" for item in timed_out.structuredContent["failures"])
    assert timed_out.structuredContent["version"] != initial["version"]
    assert not current_page_two.isError
    assert current_page_two.structuredContent is not None
    assert "OCR call 2" in current_page_two.structuredContent["content_markdown"]
    assert current_page_two.structuredContent["version"] == timed_out.structuredContent["version"]
    assert list(tmp_path.glob("*.png")) == []


async def test_cancelled_scanned_pdf_open_cleans_uncommitted_pdf_and_raster(
    tmp_path: Path,
) -> None:
    image = (Path(__file__).parent / "fixtures" / "image-en.png").read_bytes()
    payload = scanned_pdf(image)
    started = asyncio.Event()

    def source(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=payload)

    async def processor(
        artifact_path: Path,
        regions: list[dict[str, float]],
        deadline: float,
    ) -> ImageExtraction:
        started.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
        image_processor=processor,
    ) as session:
        call = asyncio.create_task(
            session.call_tool(
                "web_read",
                {
                    "url": "https://example.org/cancelled-scan.pdf",
                    "max_pages": 1,
                    "max_regions": 1,
                },
            )
        )
        await asyncio.wait_for(started.wait(), 2)
        call.cancel()
        with pytest.raises(asyncio.CancelledError):
            await call
        await asyncio.sleep(0)

    assert list(tmp_path.iterdir()) == []


async def test_real_pdf_ocr_preserves_rotation_and_columns_with_structure_warning(
    tmp_path: Path,
) -> None:
    cases = [
        ("columns-en.png", ["Left A: 101", "Right B: 202"]),
        ("rotated-zh.png", ["京东20260917", "兰花"]),
    ]
    for filename, references in cases:
        image = (Path(__file__).parent / "fixtures" / filename).read_bytes()
        payload = scanned_pdf(image)

        def source(request: httpx.Request, data: bytes = payload) -> httpx.Response:
            return httpx.Response(
                200,
                headers={"content-type": "application/pdf"},
                content=data,
            )

        async with connected(
            source,
            api_key=None,
            url_policy=allow_public_url,
            artifact_directory=tmp_path,
            timeout_seconds=30,
        ) as session:
            opened = await session.call_tool(
                "web_read",
                {
                    "url": f"https://example.org/{filename}.pdf",
                    "max_pages": 1,
                    "max_regions": 1,
                },
            )

        assert not opened.isError, opened.model_dump_json()
        assert opened.structuredContent is not None
        body = opened.structuredContent
        assert all(reference in body["content_markdown"] for reference in references)
        assert body["status"] == "partial"
        assert body["extraction_status"] == "partial"
        assert any(warning["kind"] == "structure_incomplete" for warning in body["warnings"])
        assert "|" not in body["content_markdown"]


async def test_advance_whole_mixed_page_reuses_native_and_ocr_image_regions(
    tmp_path: Path,
) -> None:
    image = (Path(__file__).parent / "fixtures" / "image-en.png").read_bytes()
    payload = combine_pdfs(
        text_pdf("Initial native page."),
        mixed_page_pdf(image, "Mixed page native NATIVE-ADVANCE"),
    )
    calls = 0

    def source(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=payload)

    async def processor(
        artifact_path: Path,
        regions: list[dict[str, float]],
        deadline: float,
    ) -> ImageExtraction:
        nonlocal calls
        calls += 1
        return ImageExtraction(
            width=1200,
            height=500,
            format="PNG",
            mime_type="image/png",
            blocks=[
                OcrBlock(
                    "Mixed page native NATIVE-ADVANCE",
                    0.99,
                    {"x": 0.1, "y": 0.05, "width": 0.7, "height": 0.1},
                ),
                OcrBlock(
                    "Mixed page scanned SCAN-ADVANCE-22",
                    0.98,
                    {"x": 0.1, "y": 0.3, "width": 0.7, "height": 0.1},
                ),
            ],
            failures=[],
            warnings=[],
            runtime={"execution_providers": ["CPUExecutionProvider"]},
            processed_regions=regions,
        )

    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
        image_processor=processor,
    ) as session:
        opened = await session.call_tool(
            "web_read",
            {"url": "https://example.org/advance-mixed.pdf", "max_pages": 1},
        )
        assert opened.structuredContent is not None
        initial = opened.structuredContent
        advanced = await session.call_tool(
            "web_read",
            {
                "action": "advance",
                "read_id": initial["read_id"],
                "version": initial["version"],
                "targets": [{"page": 2}],
                "max_pages": 1,
                "max_regions": 1,
            },
        )

    assert not advanced.isError
    assert advanced.structuredContent is not None
    body = advanced.structuredContent
    assert calls == 1
    assert body["content_markdown"].count("Mixed page native NATIVE-ADVANCE") == 1
    assert "Mixed page scanned SCAN-ADVANCE-22" in body["content_markdown"]
    assert {locator["processing_lineage"]["source"] for locator in body["locators"]} == {
        "native_text",
        "ocr",
    }
    assert body["processing"]["ocr_used"] is True


async def test_mixed_page_pending_region_advances_once_and_stays_processed(
    tmp_path: Path,
) -> None:
    image = (Path(__file__).parent / "fixtures" / "image-en.png").read_bytes()
    payload = mixed_regions_pdf(image, "Mixed region native NATIVE-PENDING")
    calls = 0

    def source(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=payload)

    async def processor(
        artifact_path: Path,
        regions: list[dict[str, float]],
        deadline: float,
    ) -> ImageExtraction:
        nonlocal calls
        calls += 1
        text = "Top image alpha evidence." if calls == 1 else "Bottom image beta result."
        return ImageExtraction(
            width=600,
            height=300,
            format="PNG",
            mime_type="image/png",
            blocks=[
                OcrBlock(
                    text,
                    0.99,
                    {"x": 0.1, "y": 0.1, "width": 0.7, "height": 0.2},
                )
            ],
            failures=[],
            warnings=[],
            runtime={"execution_providers": ["CPUExecutionProvider"]},
            processed_regions=regions,
        )

    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
        image_processor=processor,
    ) as session:
        opened = await session.call_tool(
            "web_read",
            {
                "url": "https://example.org/mixed-pending.pdf",
                "max_pages": 1,
                "max_regions": 1,
            },
        )
        assert opened.structuredContent is not None
        initial = opened.structuredContent
        pending = [
            item for item in initial["unprocessed_ranges"] if item["kind"] == "unprocessed_region"
        ]
        assert len(pending) == 1

        target = pending[0]["locator"]
        advanced = await session.call_tool(
            "web_read",
            {
                "action": "advance",
                "read_id": initial["read_id"],
                "version": initial["version"],
                "targets": [target],
                "max_regions": 1,
            },
        )
        assert advanced.structuredContent is not None
        updated = advanced.structuredContent

        repeated = await session.call_tool(
            "web_read",
            {
                "action": "advance",
                "read_id": initial["read_id"],
                "version": updated["version"],
                "targets": [target],
                "max_regions": 1,
            },
        )

    assert calls == 2
    assert "Top image alpha evidence." in initial["content_markdown"]
    assert "Bottom image beta result." in updated["content_markdown"]
    assert not any(item["locator"] == target for item in updated["unprocessed_ranges"])
    assert not repeated.isError
    assert repeated.structuredContent is not None
    assert repeated.structuredContent["version"] == updated["version"]
    assert any(
        warning["kind"] == "already_processed" for warning in repeated.structuredContent["warnings"]
    )
