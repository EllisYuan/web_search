"""One bounded native operation against captured PDF bytes; stdout is only JSON."""

import base64
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from web_search.pdf import (
    PdfTextUnavailableError,
    extract_pdf_text,
    pdf_image_regions,
    render_pdf_crop,
)
from web_search.worker_limits import limit_worker_memory


def main() -> None:
    result: dict[str, Any]
    try:
        limit_worker_memory()
        data = Path(sys.argv[1]).read_bytes()
        operation = sys.argv[2]
        arguments = json.loads(sys.argv[3])
        if operation == "text":
            value = asdict(extract_pdf_text(data, **arguments))
        elif operation == "regions":
            value = {"regions": pdf_image_regions(data, **arguments)}
        elif operation == "crop":
            payload, width, height = render_pdf_crop(data, **arguments)
            value = {
                "payload": base64.b64encode(payload).decode("ascii"),
                "width": width,
                "height": height,
            }
        else:
            raise ValueError("Unknown PDF operation")
        result = {"ok": True, "value": value}
    except PdfTextUnavailableError:
        result = {"ok": False, "category": "text_unavailable"}
    except OverflowError:
        result = {"ok": False, "category": "pixel_limit"}
    except (MemoryError, OSError):
        result = {"ok": False, "category": "resource_exhausted"}
    except Exception:
        result = {"ok": False, "category": "extraction_failed"}
    sys.stdout.write(json.dumps(result))


if __name__ == "__main__":
    main()
