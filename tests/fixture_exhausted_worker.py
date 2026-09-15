"""Exercise production worker JSON using a real Windows Job Object allocation refusal."""

from pathlib import Path

from web_search import image_worker
from web_search.image import ImageExtraction
from web_search.limits import MAX_WORKER_COMMIT_BYTES


def exhaust(path: Path, regions: list[dict[str, float]]) -> ImageExtraction:
    allocation = bytearray(MAX_WORKER_COMMIT_BYTES + 1)
    raise AssertionError(f"Windows allowed allocation beyond worker limit: {len(allocation)}")


setattr(image_worker, "run_cpu_ocr", exhaust)
image_worker.main()
