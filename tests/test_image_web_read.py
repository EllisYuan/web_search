import asyncio
import base64
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
from harness import connected
from PIL import Image

from web_search.image import ImageExtraction, OcrBlock

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
FULL_REGION = {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}


async def allow_public_url(url: str) -> bool:
    return True


def extraction(
    *blocks: OcrBlock,
    failures: list[dict[str, Any]] | None = None,
    warnings: list[dict[str, Any]] | None = None,
) -> ImageExtraction:
    return ImageExtraction(
        width=640,
        height=360,
        format="PNG",
        mime_type="image/png",
        blocks=list(blocks),
        failures=failures or [],
        warnings=warnings or [],
        runtime={
            "engine": "RapidOCR",
            "engine_version": "3.9.2",
            "runtime": "ONNX Runtime",
            "runtime_version": "1.29.0",
            "execution_providers": ["CPUExecutionProvider"],
            "intra_op_num_threads": 2,
            "inter_op_num_threads": 1,
            "models": [],
        },
        processed_regions=[FULL_REGION],
    )


async def test_image_open_read_find_asset_and_cleanup_use_captured_bytes(tmp_path: Path) -> None:
    requests = 0
    processor_calls: list[list[dict[str, float]]] = []

    def source(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, headers={"content-type": "image/png"}, content=PNG_BYTES)

    async def processor(
        artifact_path: Path,
        regions: list[dict[str, float]],
        deadline: float,
    ) -> ImageExtraction:
        assert artifact_path.read_bytes() == PNG_BYTES
        assert deadline > 0
        processor_calls.append(regions)
        return extraction(
            OcrBlock(
                text="Invoice ORCHID-2048",
                confidence=0.98,
                source_region={"x": 0.10, "y": 0.20, "width": 0.50, "height": 0.10},
            ),
            OcrBlock(
                text="中文金额 128.50 元",
                confidence=0.96,
                source_region={"x": 0.10, "y": 0.40, "width": 0.55, "height": 0.10},
            ),
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
                "url": "https://example.org/invoice.png",
                "max_regions": 1,
                "max_output_chars": 12,
            },
        )
        assert not opened.isError, opened.model_dump_json()
        assert opened.structuredContent is not None
        body = opened.structuredContent
        block_id = body["locators"][0]["block_id"]
        found = await session.call_tool(
            "web_read",
            {
                "action": "find",
                "read_id": body["read_id"],
                "version": body["version"],
                "query": "orchid-2048",
            },
        )
        read = await session.call_tool(
            "web_read",
            {
                "action": "read",
                "read_id": body["read_id"],
                "version": body["version"],
                "block_id": block_id,
            },
        )
        asset = await session.call_tool(
            "web_read",
            {
                "action": "asset",
                "read_id": body["read_id"],
                "version": body["version"],
                "asset_type": "image",
                "asset_id": body["asset_id"],
            },
        )

        assert body["metadata"] == {
            "url": "https://example.org/invoice.png",
            "content_type": "image/png",
            "format": "PNG",
            "width": 640,
            "height": 360,
            "retrieved_at": body["metadata"]["retrieved_at"],
        }
        assert body["outline"] == []
        assert body["processing"]["path"] == ["http_fetch", "image_decode", "cpu_ocr"]
        assert body["processing"]["ocr_used"] is True
        assert body["processing"]["execution_providers"] == ["CPUExecutionProvider"]
        assert body["locators"][0]["source_region"] == {
            "x": 0.10,
            "y": 0.20,
            "width": 0.50,
            "height": 0.10,
        }
        assert body["output_status"] == "truncated"
        assert body["extraction_status"] == "complete"
        assert body["unprocessed_ranges"] == []
        assert body["available_actions"] == ["read", "find", "advance", "asset", "release"]
        assert found.structuredContent is not None
        assert found.structuredContent["matches"][0]["text"] == "ORCHID-2048"
        assert found.structuredContent["matches"][0]["source_region"] == {
            "x": 0.10,
            "y": 0.20,
            "width": 0.50,
            "height": 0.10,
        }
        assert found.structuredContent["matches"][0]["confidence"] == 0.98
        assert found.structuredContent["searched_scope"]["unprocessed_ranges"] == []
        assert read.structuredContent is not None
        assert read.structuredContent["content_markdown"] == "Invoice ORCHID-2048"
        assert asset.structuredContent is not None
        assert asset.structuredContent["asset_id"] == body["asset_id"]
        assert asset.structuredContent["version"] == body["version"]
        assert asset.structuredContent["locator"] == {
            "asset_id": body["asset_id"],
            "source_region": FULL_REGION,
        }
        images = [part for part in asset.content if part.type == "image"]
        assert len(images) == 1
        assert base64.b64decode(images[0].data) == PNG_BYTES
        assert requests == 1
        assert processor_calls == [[FULL_REGION]]
        assert len(list(tmp_path.iterdir())) == 1

    assert list(tmp_path.iterdir()) == []


async def test_image_advance_regions_builds_atomic_version_and_preserves_old_version(
    tmp_path: Path,
) -> None:
    requests = 0
    calls = 0
    target_a = {"x": 0.0, "y": 0.0, "width": 0.5, "height": 0.5}
    target_b = {"x": 0.5, "y": 0.5, "width": 0.5, "height": 0.5}

    def source(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, headers={"content-type": "image/png"}, content=PNG_BYTES)

    async def processor(
        artifact_path: Path,
        regions: list[dict[str, float]],
        deadline: float,
    ) -> ImageExtraction:
        nonlocal calls
        calls += 1
        if calls == 1:
            return extraction(OcrBlock("Initial image text for cursor.", 0.99, FULL_REGION))
        return ImageExtraction(
            width=640,
            height=360,
            format="PNG",
            mime_type="image/png",
            blocks=[
                OcrBlock(
                    "Region A 专名 ORCHID-4096",
                    0.94,
                    {"x": 0.05, "y": 0.05, "width": 0.35, "height": 0.10},
                )
            ],
            failures=[
                {
                    "kind": "region_ocr_failed",
                    "message": "Injected OCR failure.",
                    "locator": {"region": target_b},
                    "next_action": "asset",
                }
            ],
            warnings=[],
            runtime=extraction().runtime,
            processed_regions=[target_a],
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
            {"url": "https://example.org/regions.png", "max_output_chars": 8},
        )
        assert opened.structuredContent is not None
        old = opened.structuredContent
        advanced = await session.call_tool(
            "web_read",
            {
                "action": "advance",
                "read_id": old["read_id"],
                "version": old["version"],
                "targets": [{"region": target_a}, {"region": target_b}],
                "max_regions": 2,
            },
        )
        assert advanced.structuredContent is not None
        invalid = await session.call_tool(
            "web_read",
            {
                "action": "advance",
                "read_id": old["read_id"],
                "targets": [{"region": target_a}, {"region": target_b}],
                "max_regions": 1,
            },
        )
        server_limited = await session.call_tool(
            "web_read",
            {
                "action": "advance",
                "read_id": old["read_id"],
                "targets": [
                    {
                        "region": {
                            "x": index / 10,
                            "y": 0.0,
                            "width": 0.05,
                            "height": 0.05,
                        }
                    }
                    for index in range(5)
                ],
                "max_regions": 5,
            },
        )
        old_cursor = await session.call_tool(
            "web_read",
            {
                "action": "read",
                "read_id": old["read_id"],
                "version": old["version"],
                "cursor": old["next_cursor"],
                "max_output_chars": 8,
            },
        )
        current_find = await session.call_tool(
            "web_read",
            {
                "action": "find",
                "read_id": old["read_id"],
                "version": advanced.structuredContent["version"],
                "query": "ORCHID-4096",
            },
        )

    body = advanced.structuredContent
    assert body["version"] != old["version"]
    assert body["processed_targets"] == [{"region": target_a}]
    assert body["unprocessed_ranges"] == [
        {
            "kind": "unprocessed_region",
            "message": "Image region OCR has not completed.",
            "locator": {"region": target_b},
            "next_action": "advance",
        }
    ]
    assert body["failures"][-1]["locator"] == {"region": target_b}
    assert body["processing"]["source_acquisition"] is False
    assert body["processing"]["ocr_used"] is True
    assert invalid.isError
    assert invalid.structuredContent is not None
    assert invalid.structuredContent["error"]["category"] == "invalid_request"
    assert server_limited.isError
    assert server_limited.structuredContent is not None
    assert server_limited.structuredContent["error"]["category"] == "invalid_request"
    assert not old_cursor.isError
    assert old_cursor.structuredContent is not None
    assert old_cursor.structuredContent["version"] == old["version"]
    assert current_find.structuredContent is not None
    assert current_find.structuredContent["matches"][0]["text"] == "ORCHID-4096"
    assert requests == 1
    assert calls == 2


async def test_real_cpu_ocr_reads_controlled_english_and_chinese_images(
    tmp_path: Path,
) -> None:
    fixture_root = Path(__file__).parent / "fixtures"
    cases = [
        ("image-en.png", ["AX-2026-0917", "12345.67", "ORCHID"]),
        ("image-zh.png", ["京东20260917", "12345.67", "兰花"]),
    ]
    for filename, references in cases:
        payload = (fixture_root / filename).read_bytes()

        def source(request: httpx.Request, data: bytes = payload) -> httpx.Response:
            return httpx.Response(200, headers={"content-type": "image/png"}, content=data)

        async with connected(
            source,
            api_key=None,
            url_policy=allow_public_url,
            artifact_directory=tmp_path,
            timeout_seconds=30,
        ) as session:
            opened = await session.call_tool("web_read", {"url": f"https://example.org/{filename}"})

        assert not opened.isError, opened.model_dump_json()
        assert opened.structuredContent is not None
        body = opened.structuredContent
        assert all(reference in body["content_markdown"] for reference in references)
        assert body["processing"]["execution_providers"] == ["CPUExecutionProvider"]
        assert all(
            item["execution_providers"] == ["CPUExecutionProvider"]
            for item in body["processing"]["sessions"]
        )
        assert all(len(item["sha256"]) == 64 for item in body["processing"]["models"])
        assert all(item["license"] == "Apache-2.0" for item in body["processing"]["models"])


async def test_real_cpu_ocr_discloses_columns_low_resolution_and_rotation(
    tmp_path: Path,
) -> None:
    cases = [
        ("columns-en.png", ["Left A: 101", "Right B: 202"]),
        ("lowres-en.png", ["AX-2026-0917", "12345.67"]),
        ("rotated-zh.png", ["京东20260917", "兰花"]),
    ]
    for filename, references in cases:
        payload = (Path(__file__).parent / "fixtures" / filename).read_bytes()

        def source(request: httpx.Request, data: bytes = payload) -> httpx.Response:
            return httpx.Response(200, headers={"content-type": "image/png"}, content=data)

        async with connected(
            source,
            api_key=None,
            url_policy=allow_public_url,
            artifact_directory=tmp_path,
            timeout_seconds=30,
        ) as session:
            opened = await session.call_tool("web_read", {"url": f"https://example.org/{filename}"})

        assert not opened.isError, opened.model_dump_json()
        assert opened.structuredContent is not None
        body = opened.structuredContent
        assert all(reference in body["content_markdown"] for reference in references)
        assert body["status"] == "partial"
        assert body["extraction_status"] == "partial"
        assert any(warning["kind"] == "structure_incomplete" for warning in body["warnings"])
        assert "|" not in body["content_markdown"]


async def test_real_cpu_ocr_isolates_too_small_region_failure(
    tmp_path: Path,
) -> None:
    payload = (Path(__file__).parent / "fixtures" / "image-en.png").read_bytes()
    valid = {"x": 0.0, "y": 0.0, "width": 1.0, "height": 0.5}
    too_small = {"x": 0.9, "y": 0.9, "width": 1e-12, "height": 1e-12}

    def source(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "image/png"}, content=payload)

    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
        timeout_seconds=30,
    ) as session:
        opened = await session.call_tool(
            "web_read", {"url": "https://example.org/region-failure.png"}
        )
        assert opened.structuredContent is not None
        advanced = await session.call_tool(
            "web_read",
            {
                "action": "advance",
                "read_id": opened.structuredContent["read_id"],
                "version": opened.structuredContent["version"],
                "targets": [{"region": valid}, {"region": too_small}],
                "max_regions": 2,
            },
        )

    assert not advanced.isError
    assert advanced.structuredContent is not None
    body = advanced.structuredContent
    assert body["processed_targets"] == [{"region": valid}]
    assert "AX-2026-0917" in body["content_markdown"]
    assert body["failures"][-1]["locator"] == {"region": too_small}
    assert body["unprocessed_ranges"][-1]["locator"] == {"region": too_small}


async def test_image_decode_failure_does_not_publish_state_or_leave_artifact(
    tmp_path: Path,
) -> None:
    def source(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "image/png"},
            content=b"not-an-image",
        )

    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
    ) as session:
        failed = await session.call_tool("web_read", {"url": "https://example.org/broken.png"})

    assert failed.isError
    assert failed.structuredContent is not None
    assert failed.structuredContent["error"]["category"] == "extraction_failed"
    assert failed.structuredContent["capture_status"] == "complete"
    assert failed.structuredContent["extraction_status"] == "failed"
    assert list(tmp_path.iterdir()) == []


async def test_image_file_size_limit_precedes_decode_and_ocr(tmp_path: Path) -> None:
    processor_called = False

    def source(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "image/png"},
            content=b"x" * 2_000_001,
        )

    async def processor(
        artifact_path: Path,
        regions: list[dict[str, float]],
        deadline: float,
    ) -> ImageExtraction:
        nonlocal processor_called
        processor_called = True
        return extraction()

    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
        image_processor=processor,
    ) as session:
        failed = await session.call_tool("web_read", {"url": "https://example.org/oversized.png"})

    assert failed.isError
    assert failed.structuredContent is not None
    assert failed.structuredContent["error"]["category"] == "resource_exhausted"
    assert processor_called is False
    assert list(tmp_path.iterdir()) == []


async def test_image_partial_ocr_keeps_reliable_text_and_discloses_review_asset(
    tmp_path: Path,
) -> None:
    failed_region = {"x": 0.5, "y": 0.0, "width": 0.5, "height": 1.0}

    def source(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "image/png"}, content=PNG_BYTES)

    async def processor(
        artifact_path: Path,
        regions: list[dict[str, float]],
        deadline: float,
    ) -> ImageExtraction:
        return ImageExtraction(
            width=640,
            height=360,
            format="PNG",
            mime_type="image/png",
            blocks=[
                OcrBlock(
                    "Reliable caption 2026-Q3",
                    0.72,
                    {"x": 0.05, "y": 0.1, "width": 0.4, "height": 0.1},
                )
            ],
            failures=[
                {
                    "kind": "region_ocr_failed",
                    "message": "Complex table columns were not reliably recognized.",
                    "locator": {"region": failed_region},
                    "next_action": "asset",
                }
            ],
            warnings=[
                {
                    "kind": "structure_incomplete",
                    "message": "Image OCR does not preserve a reliable table structure.",
                    "locator": {"region": failed_region},
                    "next_action": "asset",
                }
            ],
            runtime=extraction().runtime,
            processed_regions=[{"x": 0.0, "y": 0.0, "width": 0.5, "height": 1.0}],
        )

    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
        image_processor=processor,
    ) as session:
        opened = await session.call_tool(
            "web_read", {"url": "https://example.org/complex-table.png"}
        )

    assert not opened.isError
    assert opened.structuredContent is not None
    body = opened.structuredContent
    assert body["status"] == "partial"
    assert body["extraction_status"] == "partial"
    assert body["content_markdown"] == "Reliable caption 2026-Q3"
    assert body["unprocessed_ranges"][0]["locator"] == {"region": failed_region}
    assert body["failures"][0]["next_action"] == "asset"
    assert body["warnings"][0]["kind"] == "structure_incomplete"
    assert "|" not in body["content_markdown"]


async def test_image_pixel_limit_rejects_before_inference_and_cleans_capture(
    tmp_path: Path,
) -> None:
    output = BytesIO()
    Image.new("1", (4000, 4000)).save(output, format="PNG")

    def source(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "image/png"}, content=output.getvalue())

    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
    ) as session:
        failed = await session.call_tool(
            "web_read", {"url": "https://example.org/too-many-pixels.png"}
        )

    assert failed.isError
    assert failed.structuredContent is not None
    assert failed.structuredContent["error"]["category"] == "resource_exhausted"
    assert failed.structuredContent["extraction_status"] == "not_started"
    assert list(tmp_path.iterdir()) == []


async def test_image_advance_timeout_preserves_committed_version(
    tmp_path: Path,
) -> None:
    calls = 0

    def source(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "image/png"}, content=PNG_BYTES)

    async def processor(
        artifact_path: Path,
        regions: list[dict[str, float]],
        deadline: float,
    ) -> ImageExtraction:
        nonlocal calls
        calls += 1
        if calls == 1:
            return extraction(OcrBlock("Committed OCR text.", 0.99, FULL_REGION))
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    async with connected(
        source,
        api_key=None,
        url_policy=allow_public_url,
        artifact_directory=tmp_path,
        image_processor=processor,
        timeout_seconds=0.1,
    ) as session:
        opened = await session.call_tool("web_read", {"url": "https://example.org/timeout.png"})
        assert opened.structuredContent is not None
        initial = opened.structuredContent
        timed_out = await session.call_tool(
            "web_read",
            {
                "action": "advance",
                "read_id": initial["read_id"],
                "version": initial["version"],
                "targets": [{"region": {"x": 0.0, "y": 0.0, "width": 0.5, "height": 0.5}}],
            },
        )
        preserved = await session.call_tool(
            "web_read",
            {
                "action": "read",
                "read_id": initial["read_id"],
                "version": initial["version"],
                "block_id": initial["locators"][0]["block_id"],
            },
        )

    assert timed_out.isError
    assert timed_out.structuredContent is not None
    assert timed_out.structuredContent["error"]["category"] == "timeout"
    assert timed_out.structuredContent["version"] == initial["version"]
    assert not preserved.isError
    assert preserved.structuredContent is not None
    assert preserved.structuredContent["content_markdown"] == "Committed OCR text."
