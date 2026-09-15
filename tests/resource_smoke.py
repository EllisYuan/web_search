"""Windows CPU/RAM/disk measurement using real MCP stdio and local Source fixtures.

Run: python tests/resource_smoke.py --output docs/testing/issue24-smoke.json
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import os
import platform
import sys
import tempfile
import threading
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import psutil
from browser_fixture import javascript_site
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pdf_fixture import mixed_page_pdf, scanned_pdf, text_pdf
from pypdf import PdfReader


class Usage:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.stop = threading.Event()
        self.peak_rss = 0
        self.peak_children_rss = 0
        self.peak_children = 0
        self.peak_child_private = 0
        self.peak_temporary = 0
        self.cpu: dict[tuple[int, float], float] = {}
        self.initial_cpu: dict[tuple[int, float], float] = {}
        self.process_names: set[str] = set()
        self.thread = threading.Thread(target=self.sample, daemon=True)
        self.started = time.perf_counter()
        self.sample_once()
        self.initial_cpu = self.cpu.copy()

    def sample_once(self) -> None:
        root = psutil.Process()
        processes = [root, *root.children(recursive=True)]
        rss = children_rss = children = 0
        for process in processes:
            try:
                memory = process.memory_info().rss
                rss += memory
                if process.pid != root.pid:
                    children_rss += memory
                    children += 1
                    self.peak_child_private = max(
                        self.peak_child_private, int(getattr(process.memory_info(), "private", 0))
                    )
                times = process.cpu_times()
                self.cpu[(process.pid, process.create_time())] = times.user + times.system
                self.process_names.add(process.name())
            except psutil.Error:
                continue
        self.peak_rss = max(self.peak_rss, rss)
        self.peak_children_rss = max(self.peak_children_rss, children_rss)
        self.peak_children = max(self.peak_children, children)
        size = 0
        for path in self.directory.rglob("*"):
            try:
                if path.is_file():
                    size += path.stat().st_size
            except OSError:
                pass
        self.peak_temporary = max(self.peak_temporary, size)

    def sample(self) -> None:
        while not self.stop.wait(0.05):
            self.sample_once()

    def finish(self) -> dict[str, Any]:
        self.stop.set()
        self.thread.join()
        self.sample_once()
        elapsed = time.perf_counter() - self.started
        cpu_seconds = sum(value - self.initial_cpu.get(key, 0) for key, value in self.cpu.items())
        return {
            "elapsed_seconds": round(elapsed, 3),
            "cpu_seconds": round(cpu_seconds, 3),
            "mean_cpu_percent_one_core": round(cpu_seconds / elapsed * 100, 1),
            "peak_process_tree_rss_bytes": self.peak_rss,
            "peak_children_rss_bytes": self.peak_children_rss,
            "peak_children": self.peak_children,
            "peak_child_private_bytes": self.peak_child_private,
            "peak_temporary_bytes": self.peak_temporary,
            "process_names": sorted(self.process_names),
        }


def corpus() -> dict[str, tuple[str, bytes]]:
    image = (Path(__file__).parent / "fixtures" / "image-en.png").read_bytes()
    chinese = (Path(__file__).parent / "fixtures" / "image-zh.png").read_bytes()
    return {
        "/static": (
            "text/html",
            (
                "<h1>Evidence</h1><p>Retained original evidence. "
                + "Sample paragraph. " * 500
                + "</p>"
            ).encode(),
        ),
        "/text.pdf": (
            "application/pdf",
            text_pdf("Original page evidence.", "Second page evidence."),
        ),
        "/mixed.pdf": ("application/pdf", mixed_page_pdf(image, "Native mixed page evidence.")),
        "/scan.pdf": ("application/pdf", scanned_pdf(chinese, image)),
        "/image.png": ("image/png", image),
        "/webpage": ("text/html", b'<p>Native webpage evidence.</p><img src="/image.png">'),
    }


@asynccontextmanager
async def sources(entries: dict[str, tuple[str, bytes]]) -> AsyncIterator[str]:
    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            head = await reader.readuntil(b"\r\n\r\n")
            path = head.split(b" ", 2)[1].decode("ascii")
            mime, data = entries[path]
            writer.write(
                f"HTTP/1.1 200 OK\r\nContent-Type: {mime}\r\nContent-Length: {len(data)}\r\n"
                "Connection: close\r\n\r\n".encode()
                + data
            )
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    try:
        yield f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}"
    finally:
        server.close()
        await server.wait_closed()


async def run(output: Path) -> None:
    entries = corpus()
    report: dict[str, Any] = {
        "date_utc": datetime.now(UTC).isoformat(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "logical_cpus": psutil.cpu_count(),
        "physical_cpus": psutil.cpu_count(logical=False),
        "physical_memory_bytes": psutil.virtual_memory().total,
        "available_memory_before_bytes": psutil.virtual_memory().available,
        "completed": False,
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("mcp", "playwright", "rapidocr", "onnxruntime", "pypdfium2", "psutil")
        },
        "sampling_interval_seconds": 0.05,
        "conditions": "First pass starts a new MCP process; second pass reuses it and OS caches. "
        "Each OCR call still starts a fresh CPU worker/engine. No cache flush, "
        "network benchmark or arbitrary-source quality claim.",
        "corpus": {
            path: {
                "content_type": mime,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                **(
                    {
                        "page_points": [
                            [float(page.mediabox.width), float(page.mediabox.height)]
                            for page in PdfReader(BytesIO(data)).pages
                        ]
                    }
                    if mime == "application/pdf"
                    else {}
                ),
            }
            for path, (mime, data) in entries.items()
        },
        "image_pixels": [1400, 420],
        "pdf_raster_dpi": 144,
        "region": {"x": 0, "y": 0, "width": 1, "height": 1},
        "calls": [],
    }
    with tempfile.TemporaryDirectory(prefix="web-read-resource-smoke-") as temporary:
        root = Path(temporary)
        artifacts = root / "artifacts"
        artifacts.mkdir()
        report["disk_free_before_bytes"] = psutil.disk_usage(str(artifacts)).free
        control = root / "control"
        control.write_text("normal", encoding="utf-8")
        async with sources(entries) as base, javascript_site() as browser_base:
            params = StdioServerParameters(
                command=sys.executable,
                args=[str(Path(__file__).with_name("fixture_resource_stdio_server.py"))],
                env={
                    **os.environ,
                    "WEB_READ_SMOKE_CONTROL": str(control),
                    "WEB_READ_SMOKE_ARTIFACTS": str(artifacts),
                    "WEB_READ_SMOKE_SOURCES": f"{base},{browser_base}",
                    "TAVILY_API_KEY": "",
                },
            )
            async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
                await session.initialize()
                report["tools"] = (await session.list_tools()).model_dump(mode="json")

                async def call(label: str, arguments: dict[str, Any]) -> dict[str, Any]:
                    usage = Usage(artifacts)
                    usage.thread.start()
                    try:
                        result = await session.call_tool("web_read", arguments)
                    finally:
                        measurement = usage.finish()
                    body = result.structuredContent
                    assert body is not None, result.model_dump_json()
                    report["calls"].append(
                        {
                            "label": label,
                            "arguments": arguments,
                            "isError": result.isError,
                            "result": body,
                            "measurement": measurement,
                        }
                    )
                    output.write_text(
                        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                    print(
                        label,
                        body["status"],
                        measurement["peak_process_tree_rss_bytes"],
                        flush=True,
                    )
                    return body

                for condition in ("cold", "warm"):
                    opened: dict[str, dict[str, Any]] = {}
                    for path in entries:
                        body = await call(
                            f"{condition}:{path}",
                            {
                                "url": base + path,
                                "max_output_chars": 12,
                                "max_pages": 1,
                                "max_regions": 1,
                            },
                        )
                        assert body["status"] in {"ok", "partial"}, body
                        opened[path] = body
                    browser = await call(
                        f"{condition}:browser", {"url": browser_base + "/image-app"}
                    )
                    assert browser["processing"]["browser_rendered"]
                    opened["browser"] = browser
                    for mode in ("gate", "ram", "disk"):
                        control.write_text(mode, encoding="utf-8")
                        for action in (
                            {"url": base + "/static"},
                            {
                                "action": "advance",
                                "read_id": opened["/text.pdf"]["read_id"],
                                "targets": [{"page": 2}],
                            },
                            {
                                "action": "interact",
                                "read_id": browser["read_id"],
                                "version": browser["version"],
                                "target_id": next(
                                    item["target_id"]
                                    for item in browser["interaction_targets"]
                                    if item["operation"] == "load_more"
                                ),
                                "operation": "load_more",
                            },
                        ):
                            denied = await call(f"{condition}:injected_{mode}", action)
                            assert denied["error"]["category"] == "resource_exhausted", denied
                        old = opened["/static"]
                        found = await call(
                            f"{condition}:{mode}:find",
                            {
                                "action": "find",
                                "read_id": old["read_id"],
                                "query": "Retained",
                            },
                        )
                        assert found["matches"]
                        viewed = await call(
                            f"{condition}:{mode}:read",
                            {
                                "action": "read",
                                "read_id": old["read_id"],
                                "cursor": old["next_cursor"],
                            },
                        )
                        old["next_cursor"] = viewed["next_cursor"]
                        assert viewed["status"] in {"ok", "partial"}
                        control.write_text("normal", encoding="utf-8")
                    control.write_text("gate", encoding="utf-8")
                    for body in opened.values():
                        released = await call(
                            f"{condition}:release",
                            {
                                "action": "release",
                                "read_id": body["read_id"],
                            },
                        )
                        assert released["released"]
                    assert not list(artifacts.iterdir())
                    control.write_text("normal", encoding="utf-8")
                # Exercise defaults and boundary budgets on newly generated, reproducible inputs.
                entries["/limits.pdf"] = (
                    "application/pdf",
                    text_pdf(*(f"Bounded page {page}." for page in range(1, 101))),
                )
                image = entries["/image.png"][1]
                entries["/four-scans.pdf"] = (
                    "application/pdf",
                    scanned_pdf(image, image, image, image),
                )
                for path in ("/limits.pdf", "/four-scans.pdf"):
                    mime, data = entries[path]
                    report["corpus"][path] = {
                        "content_type": mime,
                        "bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest(),
                        "page_points": [
                            [float(page.mediabox.width), float(page.mediabox.height)]
                            for page in PdfReader(BytesIO(data)).pages
                        ],
                    }
                defaults = await call("defaults:100_page_pdf", {"url": base + "/limits.pdf"})
                assert len({item["page"] for item in defaults["locators"]}) == 10
                maximum = await call(
                    "limits:100_page_pdf",
                    {
                        "url": base + "/limits.pdf",
                        "max_pages": 100,
                        "max_output_chars": 100_000,
                    },
                )
                assert len({item["page"] for item in maximum["locators"]}) == 100
                regions = await call(
                    "limits:four_ocr_regions",
                    {
                        "url": base + "/four-scans.pdf",
                        "max_regions": 4,
                    },
                )
                assert len(regions["processed_targets"]) == 4
                advanced = await call(
                    "recovery:advance",
                    {
                        "action": "advance",
                        "read_id": defaults["read_id"],
                        "targets": [{"page": 11}],
                    },
                )
                assert advanced["version"] != defaults["version"]
                for body in (defaults, maximum, regions):
                    await call("limits:release", {"action": "release", "read_id": body["read_id"]})
                concurrent = await asyncio.gather(
                    call("concurrent:browser", {"url": browser_base + "/image-app"}),
                    call("concurrent:ocr", {"url": base + "/image.png"}),
                )
                assert all(body["status"] in {"ok", "partial"} for body in concurrent)
                browser = concurrent[0]
                interacted = await call(
                    "recovery:interact",
                    {
                        "action": "interact",
                        "read_id": browser["read_id"],
                        "version": browser["version"],
                        "target_id": next(
                            item["target_id"]
                            for item in browser["interaction_targets"]
                            if item["operation"] == "load_more"
                        ),
                        "operation": "load_more",
                    },
                )
                assert interacted["version_changed"]
                for body in concurrent:
                    await call(
                        "concurrent:release", {"action": "release", "read_id": body["read_id"]}
                    )
                report["artifacts_after_release"] = [str(path) for path in artifacts.iterdir()]
        report["artifacts_after_exit"] = [str(path) for path in artifacts.iterdir()]
    report["completed"] = True
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    asyncio.run(run(parser.parse_args().output))
