"""Bounded born-digital PDF extraction and page crop rendering."""

from __future__ import annotations

import re
import secrets
import struct
import time
import zlib
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium  # type: ignore[import-untyped]

MAX_PDF_TOTAL_PAGES = 10_000
MAX_PDF_PAGE_CHARS = 1_000_000
MAX_PDF_EXTRACTED_CHARS = 2_000_000
MAX_LAYOUT_RECTS = 512


class PdfExtractionError(Exception):
    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category


class PdfTextUnavailableError(ValueError):
    """The selected PDF target has no native text layer to reuse."""


@dataclass(frozen=True)
class PdfBlock:
    block_id: str
    section_id: str
    markdown: str
    text: str
    page: int
    source_region: dict[str, float] | None = None


@dataclass(frozen=True)
class PdfExtraction:
    title: str
    metadata: dict[str, str]
    outline: list[dict[str, Any]]
    blocks: list[PdfBlock]
    total_pages: int
    processed_pages: frozenset[int]
    ocr_regions: list[dict[str, Any]]
    unprocessed_ranges: list[dict[str, Any]]
    failures: list[dict[str, Any]]
    warnings: list[dict[str, Any]]


@dataclass(frozen=True)
class PdfTextArtifact:
    page: int
    text: str
    region: dict[str, float] | None = None
    structure_incomplete: bool = False


def _unprocessed_ranges(total_pages: int, processed_pages: set[int]) -> list[dict[str, Any]]:
    ranges: list[dict[str, Any]] = []
    for page in range(1, total_pages + 1):
        if page in processed_pages:
            continue
        if ranges and ranges[-1]["locator"]["end_page"] == page - 1:
            ranges[-1]["locator"]["end_page"] = page
        else:
            ranges.append(
                {
                    "kind": "unprocessed_pages",
                    "message": "PDF page text has not been processed.",
                    "locator": {"start_page": page, "end_page": page},
                    "next_action": "advance",
                }
            )
    return ranges


def unprocessed_page_ranges(
    total_pages: int, processed_pages: frozenset[int] | set[int]
) -> list[dict[str, Any]]:
    return _unprocessed_ranges(total_pages, set(processed_pages))


def _has_layout_ambiguity(text_page: Any) -> bool:
    count = text_page.count_rects()
    if count > MAX_LAYOUT_RECTS:
        return True
    rects = [text_page.get_rect(index) for index in range(count)]
    for index, (left, bottom, right, top) in enumerate(rects):
        for other_left, other_bottom, other_right, other_top in rects[index + 1 :]:
            same_row = min(top, other_top) > max(bottom, other_bottom)
            horizontal_gap = max(other_left - right, left - other_right)
            if same_row and horizontal_gap > 16:
                return True
    return False


def _page_image_regions(page: Any) -> list[dict[str, float]]:
    width, height = page.get_size()
    regions: list[dict[str, float]] = []
    for image in page.get_objects(filter=[pdfium.raw.FPDF_PAGEOBJ_IMAGE]):
        try:
            left, bottom, right, top = image.get_bounds()
        except pdfium.PdfiumError:
            continue
        left = max(0.0, min(width, left))
        right = max(0.0, min(width, right))
        bottom = max(0.0, min(height, bottom))
        top = max(0.0, min(height, top))
        if right <= left or top <= bottom:
            continue
        region = {
            "x": left / width,
            "y": (height - top) / height,
            "width": (right - left) / width,
            "height": (top - bottom) / height,
        }
        if region["width"] * region["height"] < 0.001:
            continue
        if not any(
            all(abs(region[key] - existing[key]) < 1e-6 for key in region) for existing in regions
        ):
            regions.append(region)
    return sorted(regions, key=lambda item: (item["y"], item["x"]))


def pdf_image_regions(
    data: bytes,
    page_number: int,
    selection: dict[str, float] | None = None,
) -> list[dict[str, float]]:
    """Locate raster regions on one captured PDF page, optionally clipped to a selection."""
    with closing(pdfium.PdfDocument(data)) as document:
        if page_number < 1 or page_number > len(document):
            raise IndexError("PDF page is outside the captured document.")
        with closing(document[page_number - 1]) as page:
            regions = _page_image_regions(page)
    if selection is None:
        return regions
    clipped: list[dict[str, float]] = []
    selection_right = selection["x"] + selection["width"]
    selection_bottom = selection["y"] + selection["height"]
    for region in regions:
        left = max(selection["x"], region["x"])
        top = max(selection["y"], region["y"])
        right = min(selection_right, region["x"] + region["width"])
        bottom = min(selection_bottom, region["y"] + region["height"])
        if right > left and bottom > top:
            clipped.append(
                {
                    "x": left,
                    "y": top,
                    "width": right - left,
                    "height": bottom - top,
                }
            )
    return clipped


def extract_pdf_text(
    data: bytes,
    page_number: int,
    region: dict[str, float] | None = None,
) -> PdfTextArtifact:
    with closing(pdfium.PdfDocument(data)) as document:
        if page_number < 1 or page_number > len(document):
            raise IndexError("PDF page is outside the captured document.")
        with closing(document[page_number - 1]) as page:
            with closing(page.get_textpage()) as text_page:
                if text_page.count_chars() > MAX_PDF_PAGE_CHARS:
                    raise OverflowError("PDF page exceeds the native text character limit.")
                structure_incomplete = _has_layout_ambiguity(text_page)
                if region is None:
                    text = text_page.get_text_range()
                else:
                    width, height = page.get_size()
                    left = region["x"] * width
                    right = (region["x"] + region["width"]) * width
                    top = (1 - region["y"]) * height
                    bottom = (1 - region["y"] - region["height"]) * height
                    text = text_page.get_text_bounded(left, bottom, right, top)
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        raise PdfTextUnavailableError("PDF target has no readable text layer.")
    structure_incomplete = (
        structure_incomplete
        or "\t" in normalized
        or any(re.search(r"\S {3,}\S", line) for line in normalized.splitlines())
    )
    return PdfTextArtifact(page_number, normalized, region, structure_incomplete)


def make_pdf_block(artifact: PdfTextArtifact) -> PdfBlock:
    return PdfBlock(
        block_id=secrets.token_urlsafe(9),
        section_id=f"pdf-page-{artifact.page}",
        markdown=f"## Page {artifact.page}\n\n{artifact.text}",
        text=artifact.text,
        page=artifact.page,
        source_region=artifact.region,
    )


def pdf_structure_warning(artifact: PdfTextArtifact) -> dict[str, Any] | None:
    if not artifact.structure_incomplete:
        return None
    locator: dict[str, Any] = {"page": artifact.page}
    if artifact.region is not None:
        locator["region"] = artifact.region
    return {
        "kind": "structure_incomplete",
        "message": (
            "Column or table-like spacing was preserved as plain text; "
            "reading order and table structure are not verified."
        ),
        "locator": locator,
        "next_action": "asset",
    }


def render_pdf_crop(
    data: bytes,
    page_number: int,
    region: dict[str, float] | None,
    *,
    dpi: int,
    max_pixels: int,
    max_bytes: int,
) -> tuple[bytes, int, int]:
    with closing(pdfium.PdfDocument(data)) as document:
        if page_number < 1 or page_number > len(document):
            raise IndexError("PDF page is outside the captured document.")
        with closing(document[page_number - 1]) as page:
            width, height = page.get_size()
            if region is None:
                crop = (0.0, 0.0, 0.0, 0.0)
                output_width, output_height = width, height
            else:
                left = region["x"] * width
                right = (1 - region["x"] - region["width"]) * width
                top = region["y"] * height
                bottom = (1 - region["y"] - region["height"]) * height
                crop = (left, bottom, right, top)
                output_width = region["width"] * width
                output_height = region["height"] * height
            scale = dpi / 72
            pixels = int(output_width * scale) * int(output_height * scale)
            if pixels <= 0 or pixels > max_pixels:
                raise OverflowError("PDF crop exceeds the raster pixel limit.")
            with closing(page.render(scale=scale, crop=crop)) as bitmap:
                rendered_width, rendered_height = bitmap.width, bitmap.height
                payload = _bitmap_png(
                    bytes(bitmap.buffer),
                    width=bitmap.width,
                    height=bitmap.height,
                    stride=bitmap.stride,
                    mode=bitmap.mode,
                )
    if len(payload) > max_bytes:
        raise OverflowError("PDF crop exceeds the output byte limit.")
    return payload, rendered_width, rendered_height


def _bitmap_png(data: bytes, *, width: int, height: int, stride: int, mode: str) -> bytes:
    channels = 4 if mode in {"BGRx", "BGRA"} else 3
    if mode not in {"BGR", "BGRx", "BGRA"}:
        raise OverflowError("PDFium produced an unsupported raster format.")
    rows = bytearray()
    for row_index in range(height):
        row = data[row_index * stride : row_index * stride + width * channels]
        rows.append(0)
        for pixel in range(0, len(row), channels):
            blue, green, red = row[pixel : pixel + 3]
            rows.extend((red, green, blue))
            if mode == "BGRA":
                rows.append(row[pixel + 3])

    color_type = 6 if mode == "BGRA" else 2
    header = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)

    def chunk(kind: bytes, body: bytes) -> bytes:
        return (
            struct.pack(">I", len(body))
            + kind
            + body
            + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(rows), level=6))
        + chunk(b"IEND", b"")
    )


def extract_pdf(path: Path, *, max_pages: int, deadline_seconds: float) -> PdfExtraction:
    deadline = time.monotonic() + deadline_seconds
    try:
        document = pdfium.PdfDocument(path)
    except pdfium.PdfiumError as error:
        encrypted = error.err_code == pdfium.raw.FPDF_ERR_PASSWORD
        raise PdfExtractionError(
            "access_blocked" if encrypted else "extraction_failed",
            (
                "The PDF is encrypted and cannot be read without credentials."
                if encrypted
                else "The PDF is damaged or unreadable."
            ),
        ) from error

    with closing(document):
        total_pages = len(document)
        if total_pages <= 0:
            raise PdfExtractionError("extraction_failed", "The captured PDF has no pages.")
        if total_pages > MAX_PDF_TOTAL_PAGES:
            raise PdfExtractionError(
                "resource_exhausted", "The PDF exceeds the server page-count limit."
            )
        metadata = {
            key.lower(): value for key, value in document.get_metadata_dict().items() if value
        }
        title = metadata.get("title") or path.stem
        metadata["title"] = title
        outline: list[dict[str, Any]] = []
        for bookmark in document.get_toc():
            item: dict[str, Any] = {
                "title": bookmark.get_title(),
                "level": bookmark.level + 1,
            }
            destination = bookmark.get_dest()
            if destination is not None:
                item["page"] = destination.get_index() + 1
            outline.append(item)

        blocks: list[PdfBlock] = []
        processed_pages: set[int] = set()
        failures: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        ocr_regions: list[dict[str, Any]] = []
        extracted_chars = 0
        for page_number in range(1, min(total_pages, max_pages) + 1):
            if time.monotonic() >= deadline:
                warnings.append(
                    {
                        "kind": "processing_deadline",
                        "message": "PDF extraction reached the server deadline.",
                        "locator": {"page": page_number},
                        "next_action": "advance",
                    }
                )
                break
            try:
                with closing(document[page_number - 1]) as page:
                    page_image_regions = _page_image_regions(page)
                    with closing(page.get_textpage()) as text_page:
                        if text_page.count_chars() > MAX_PDF_PAGE_CHARS:
                            failures.append(
                                {
                                    "kind": "page_size_limit",
                                    "message": "The page exceeds the native text character limit.",
                                    "locator": {"page": page_number},
                                    "next_action": "read_other_page",
                                }
                            )
                            continue
                        layout_ambiguous = _has_layout_ambiguity(text_page)
                        text = text_page.get_text_range()
                text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
            except pdfium.PdfiumError:
                failures.append(
                    {
                        "kind": "page_extraction_failed",
                        "message": "Native text extraction failed for this page.",
                        "locator": {"page": page_number},
                        "next_action": "read_other_page",
                    }
                )
                continue
            processed_pages.add(page_number)
            if not text and not page_image_regions:
                page_image_regions = [{"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}]
            ocr_regions.extend(
                {"page": page_number, "region": region} for region in page_image_regions
            )
            if not text:
                failures.append(
                    {
                        "kind": "text_layer_unavailable",
                        "message": "This processed page has no readable native text layer.",
                        "locator": {"page": page_number},
                        "next_action": "advance",
                    }
                )
                continue
            if extracted_chars + len(text) > MAX_PDF_EXTRACTED_CHARS:
                processed_pages.remove(page_number)
                failures.append(
                    {
                        "kind": "document_text_limit",
                        "message": "PDF extraction reached the server text character limit.",
                        "locator": {"page": page_number},
                        "next_action": "open",
                    }
                )
                break
            extracted_chars += len(text)
            section_id = f"pdf-page-{page_number}"
            blocks.append(
                PdfBlock(
                    block_id=secrets.token_urlsafe(9),
                    section_id=section_id,
                    markdown=f"## Page {page_number}\n\n{text}",
                    text=text,
                    page=page_number,
                )
            )
            warning = pdf_structure_warning(
                PdfTextArtifact(
                    page_number,
                    text,
                    structure_incomplete=(
                        layout_ambiguous
                        or "\t" in text
                        or any(re.search(r"\S {3,}\S", line) for line in text.splitlines())
                    ),
                )
            )
            if warning is not None:
                warnings.append(warning)

        frozen_pages = frozenset(processed_pages)
        for item in outline:
            page = item.get("page")
            if isinstance(page, int) and page in frozen_pages:
                item["section_id"] = f"pdf-page-{page}"

    return PdfExtraction(
        title=title,
        metadata=metadata,
        outline=outline,
        blocks=blocks,
        total_pages=total_pages,
        processed_pages=frozen_pages,
        ocr_regions=ocr_regions,
        unprocessed_ranges=_unprocessed_ranges(total_pages, processed_pages),
        failures=failures,
        warnings=warnings,
    )
