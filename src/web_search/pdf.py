"""Bounded born-digital PDF extraction from the native text layer."""

from __future__ import annotations

import re
import secrets
import time
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


@dataclass(frozen=True)
class PdfBlock:
    block_id: str
    section_id: str
    markdown: str
    text: str
    page: int


@dataclass(frozen=True)
class PdfExtraction:
    title: str
    metadata: dict[str, str]
    outline: list[dict[str, Any]]
    blocks: list[PdfBlock]
    total_pages: int
    processed_pages: frozenset[int]
    unprocessed_ranges: list[dict[str, Any]]
    failures: list[dict[str, Any]]
    warnings: list[dict[str, Any]]


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


def _has_layout_ambiguity(text_page: Any) -> bool:
    count = text_page.count_rects()
    if count > MAX_LAYOUT_RECTS:
        return True
    rects = [text_page.get_rect(index) for index in range(count)]
    for index, left_rect in enumerate(rects):
        left, bottom, right, top = left_rect
        for other_left, other_bottom, other_right, other_top in rects[index + 1 :]:
            same_row = min(top, other_top) > max(bottom, other_bottom)
            horizontal_gap = max(other_left - right, left - other_right)
            if same_row and horizontal_gap > 16:
                return True
    return False


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
        warnings: list[dict[str, Any]] = []
        try:
            metadata = {
                key.lower(): value for key, value in document.get_metadata_dict().items() if value
            }
        except Exception:
            metadata = {}
            warnings.append(
                {
                    "kind": "metadata_unavailable",
                    "message": (
                        "PDF metadata could not be read; native page text may still be available."
                    ),
                    "locator": {"document": True},
                    "next_action": "read",
                }
            )
        title = metadata.get("title") or "Untitled PDF"
        metadata["title"] = title
        outline: list[dict[str, Any]] = []
        try:
            for bookmark in document.get_toc():
                item: dict[str, Any] = {
                    "title": bookmark.get_title(),
                    "level": bookmark.level + 1,
                }
                destination = bookmark.get_dest()
                if destination is not None:
                    item["page"] = destination.get_index() + 1
                outline.append(item)
        except Exception:
            outline = []
            warnings.append(
                {
                    "kind": "outline_unavailable",
                    "message": (
                        "PDF outline could not be read; native page text may still be available."
                    ),
                    "locator": {"document": True},
                    "next_action": "read",
                }
            )

        blocks: list[PdfBlock] = []
        processed_pages: set[int] = set()
        failures: list[dict[str, Any]] = []
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
            if (
                layout_ambiguous
                or "\t" in text
                or any(re.search(r"\S {3,}\S", line) for line in text.splitlines())
            ):
                warnings.append(
                    {
                        "kind": "structure_incomplete",
                        "message": (
                            "Column or table-like spacing was preserved as plain text; "
                            "reading order and table structure are not verified."
                        ),
                        "locator": {"page": page_number},
                        "next_action": "read",
                    }
                )

        frozen_pages = frozenset(processed_pages)
        text_pages = {block.page for block in blocks}
        for item in outline:
            page = item.get("page")
            if isinstance(page, int) and page in text_pages:
                item["section_id"] = f"pdf-page-{page}"

    return PdfExtraction(
        title=title,
        metadata=metadata,
        outline=outline,
        blocks=blocks,
        total_pages=total_pages,
        processed_pages=frozen_pages,
        unprocessed_ranges=_unprocessed_ranges(total_pages, processed_pages),
        failures=failures,
        warnings=warnings,
    )
