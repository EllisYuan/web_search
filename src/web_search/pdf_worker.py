"""Isolated PDFium worker; the parent enforces the operation deadline."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from web_search.pdf import PdfExtractionError, extract_pdf
from web_search.worker_limits import limit_worker_memory


def main() -> None:
    path = Path(sys.argv[1])
    max_pages = int(sys.argv[2])
    deadline_seconds = float(sys.argv[3])
    result: dict[str, Any]
    try:
        limit_worker_memory()
        extraction = extract_pdf(path, max_pages=max_pages, deadline_seconds=deadline_seconds)
        payload = asdict(extraction)
        payload["processed_pages"] = sorted(extraction.processed_pages)
        result = {"ok": True, "extraction": payload}
    except PdfExtractionError as error:
        result = {"ok": False, "category": error.category, "message": str(error)}
    except (MemoryError, OSError):
        result = {
            "ok": False,
            "category": "resource_exhausted",
            "message": "PDF worker resources are unavailable.",
        }
    except Exception:
        result = {
            "ok": False,
            "category": "extraction_failed",
            "message": "PDF extraction failed without a readable document state.",
        }
    sys.stdout.write(json.dumps(result, ensure_ascii=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
