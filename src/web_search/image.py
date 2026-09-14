"""CPU-only OCR value objects and worker boundary for captured images."""

from __future__ import annotations

import hashlib
import importlib.metadata as metadata
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

NormalizedRegion = dict[str, float]


@dataclass(frozen=True)
class OcrBlock:
    text: str
    confidence: float
    source_region: NormalizedRegion


@dataclass(frozen=True)
class ImageExtraction:
    width: int
    height: int
    format: str
    mime_type: str
    blocks: list[OcrBlock]
    failures: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    runtime: dict[str, Any]
    processed_regions: list[NormalizedRegion] | None = None


ImageProcessor = Callable[
    [Path, list[NormalizedRegion], float],
    Awaitable[ImageExtraction],
]

MAX_IMAGE_PIXELS = 12_000_000
OCR_INTRA_OP_THREADS = 2
OCR_INTER_OP_THREADS = 1

MODEL_SOURCES = {
    "ch_ppocr_mobile_v2.0_cls_mobile.onnx": (
        "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.2/"
        "onnx/PP-OCRv4/cls/ch_ppocr_mobile_v2.0_cls_mobile.onnx"
    ),
    "PP-OCRv6_det_small.onnx": (
        "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.2/"
        "onnx/PP-OCRv6/det/PP-OCRv6_det_small.onnx"
    ),
    "PP-OCRv6_rec_small.onnx": (
        "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.2/"
        "onnx/PP-OCRv6/rec/PP-OCRv6_rec_small.onnx"
    ),
}
MODEL_SHA256 = {
    "ch_ppocr_mobile_v2.0_cls_mobile.onnx": (
        "e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c"
    ),
    "PP-OCRv6_det_small.onnx": (
        "090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f"
    ),
    "PP-OCRv6_rec_small.onnx": (
        "6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884"
    ),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_cpu_ocr(path: Path, regions: list[NormalizedRegion]) -> ImageExtraction:
    """Decode and OCR selected normalized regions using CPUExecutionProvider only."""
    import cv2
    import numpy as np
    from PIL import Image, UnidentifiedImageError
    from rapidocr import RapidOCR
    from rapidocr.utils.output import RapidOCROutput

    cv2.setNumThreads(OCR_INTRA_OP_THREADS)
    try:
        with Image.open(path) as source:
            width, height = source.size
            image_format = source.format or "UNKNOWN"
            if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                raise OverflowError("decoded image exceeds pixel limit")
            source.load()
            rgb = source.convert("RGB")
    except (Image.DecompressionBombError, UnidentifiedImageError) as error:
        raise ValueError("captured bytes are not a supported image") from error

    package = Path(str(metadata.distribution("rapidocr").locate_file("rapidocr")))
    model_paths = {name: package / "models" / name for name in MODEL_SOURCES}
    params: dict[str, Any] = {
        "Global.log_level": "error",
        "EngineConfig.onnxruntime.intra_op_num_threads": OCR_INTRA_OP_THREADS,
        "EngineConfig.onnxruntime.inter_op_num_threads": OCR_INTER_OP_THREADS,
        "EngineConfig.onnxruntime.use_cuda": False,
        "EngineConfig.onnxruntime.use_dml": False,
        "EngineConfig.onnxruntime.use_cann": False,
        "EngineConfig.onnxruntime.use_coreml": False,
        "Det.model_path": str(model_paths["PP-OCRv6_det_small.onnx"]),
        "Rec.model_path": str(model_paths["PP-OCRv6_rec_small.onnx"]),
        "Cls.model_path": str(model_paths["ch_ppocr_mobile_v2.0_cls_mobile.onnx"]),
    }
    engine = RapidOCR(params=params)
    providers: set[str] = set()
    sessions: list[dict[str, Any]] = []
    for component in ("text_det", "text_cls", "text_rec"):
        session = getattr(engine, component).session.session
        active = session.get_providers()
        if active != ["CPUExecutionProvider"]:
            raise RuntimeError("OCR session did not use CPUExecutionProvider exclusively")
        providers.update(active)
        options = session.get_session_options()
        sessions.append(
            {
                "component": component,
                "execution_providers": active,
                "intra_op_num_threads": options.intra_op_num_threads,
                "inter_op_num_threads": options.inter_op_num_threads,
            }
        )

    blocks: list[OcrBlock] = []
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for requested in regions:
        left = round(requested["x"] * width)
        top = round(requested["y"] * height)
        right = round((requested["x"] + requested["width"]) * width)
        bottom = round((requested["y"] + requested["height"]) * height)
        crop = np.asarray(rgb.crop((left, top, right, bottom)))[:, :, ::-1]
        result = cast(RapidOCROutput, engine(crop))
        if result.txts is None or result.boxes is None or result.scores is None:
            failures.append(
                {
                    "kind": "region_ocr_failed",
                    "message": "No reliable text was detected in the requested image region.",
                    "locator": {"region": requested},
                    "next_action": "asset",
                }
            )
            continue
        for box, text, score in zip(result.boxes, result.txts, result.scores, strict=True):
            xs = [float(point[0]) + left for point in box]
            ys = [float(point[1]) + top for point in box]
            source_region = {
                "x": min(xs) / width,
                "y": min(ys) / height,
                "width": (max(xs) - min(xs)) / width,
                "height": (max(ys) - min(ys)) / height,
            }
            blocks.append(OcrBlock(str(text), float(score), source_region))
            if float(score) < 0.8:
                warnings.append(
                    {
                        "kind": "low_ocr_confidence",
                        "message": "OCR confidence is low; review the captured image asset.",
                        "locator": {"source_region": source_region},
                        "next_action": "asset",
                    }
                )

    models = []
    for name, model_source in MODEL_SOURCES.items():
        actual_hash = _sha256(model_paths[name])
        expected_hash = MODEL_SHA256[name]
        if actual_hash != expected_hash:
            raise RuntimeError(f"OCR model hash mismatch: {name}")
        models.append(
            {
                "file": name,
                "source": model_source,
                "sha256": actual_hash,
                "expected_sha256": expected_hash,
                "verified": True,
                "license": "Apache-2.0",
            }
        )
    return ImageExtraction(
        width=width,
        height=height,
        format=image_format,
        mime_type=Image.MIME.get(image_format, "application/octet-stream"),
        blocks=blocks,
        failures=failures,
        warnings=warnings,
        runtime={
            "engine": "RapidOCR",
            "engine_version": metadata.version("rapidocr"),
            "runtime": "ONNX Runtime",
            "runtime_version": metadata.version("onnxruntime"),
            "execution_providers": sorted(providers),
            "intra_op_num_threads": OCR_INTRA_OP_THREADS,
            "inter_op_num_threads": OCR_INTER_OP_THREADS,
            "sessions": sessions,
            "models": models,
            "model_license": "Apache-2.0",
        },
        processed_regions=[
            region
            for region in regions
            if not any(failure.get("locator", {}).get("region") == region for failure in failures)
        ],
    )


def extraction_to_json(extraction: ImageExtraction) -> dict[str, Any]:
    return {
        "width": extraction.width,
        "height": extraction.height,
        "format": extraction.format,
        "mime_type": extraction.mime_type,
        "blocks": [
            {
                "text": block.text,
                "confidence": block.confidence,
                "source_region": block.source_region,
            }
            for block in extraction.blocks
        ],
        "failures": extraction.failures,
        "warnings": extraction.warnings,
        "runtime": extraction.runtime,
        "processed_regions": extraction.processed_regions,
    }
