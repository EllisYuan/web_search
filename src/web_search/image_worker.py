"""Subprocess entry point for bounded CPU-only image OCR."""

import json
import sys
from pathlib import Path

from web_search.image import extraction_to_json, run_cpu_ocr
from web_search.worker_limits import limit_worker_memory


def main() -> None:
    try:
        limit_worker_memory()
        artifact = Path(sys.argv[1])
        regions = json.loads(sys.argv[2])
        result = {"ok": True, "extraction": extraction_to_json(run_cpu_ocr(artifact, regions))}
    except Exception as error:
        result = {
            "ok": False,
            "category": (
                "resource_exhausted"
                if isinstance(error, (MemoryError, OverflowError, OSError))
                else "extraction_failed"
            ),
            "message": str(error),
            "pixel_limit": isinstance(error, OverflowError),
        }
    sys.stdout.write(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
