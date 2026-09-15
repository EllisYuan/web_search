"""Public MCP recovery assertions; stage barriers are controlled failure injection."""

import asyncio
import time
from pathlib import Path
from typing import Any, cast

import anyio
import httpx
import psutil
import pytest
from mcp import ClientSession, types
from mcp.shared.exceptions import McpError
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.shared.session import RequestResponder
from pdf_fixture import scanned_pdf, text_pdf
from test_webpage_image_ocr import FULL_REGION, PNG_BYTES, GrowingImageBrowser, allow_public_url

from web_search.image import ImageExtraction, OcrBlock
from web_search.mcp_delivery import ReadServer
from web_search.server import create_server
from web_search.web_read import WebReadService


async def ocr(path: Path, regions: list[dict[str, float]], deadline: float) -> ImageExtraction:
    return ImageExtraction(
        1400,
        420,
        "PNG",
        "image/png",
        [OcrBlock("Committed image evidence.", 0.99, FULL_REGION)],
        [],
        [],
        {"execution_providers": ["CPUExecutionProvider"]},
        regions,
    )


def source(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.endswith(".png"):
        mime, data = "image/png", PNG_BYTES
    elif path == "/text.pdf":
        mime, data = "application/pdf", text_pdf("Committed page one.", "Completed page two.")
    elif path == "/scan.pdf":
        mime, data = "application/pdf", scanned_pdf(PNG_BYTES, PNG_BYTES)
    elif path == "/app":
        mime, data = "text/html", b'<div id="root"></div><script src="/app.js"></script>'
    else:
        mime, data = (
            "text/html",
            b"<h1>Committed heading</h1><p>Committed body.</p>"
            b'<img src="/first.png"><img src="/second.png">',
        )
    return httpx.Response(200, headers={"content-type": mime}, content=data)


def server_for(http: httpx.AsyncClient, directory: Path) -> ReadServer:
    return cast(
        ReadServer,
        create_server(
            api_key=None,
            http=http,
            artifact_directory=directory,
            url_policy=allow_public_url,
            image_processor=ocr,
            browser_factory=GrowingImageBrowser,
        ),
    )


@pytest.mark.parametrize(
    "arguments",
    [
        {"action": []},
        {"action": "read", "read_id": [], "page": 1},
        {"action": "find", "read_id": {}, "query": "x"},
    ],
)
async def test_recovery_observation_does_not_bypass_input_validation(
    tmp_path: Path,
    arguments: dict[str, Any],
) -> None:
    async with httpx.AsyncClient(transport=httpx.MockTransport(source)) as http:
        async with create_connected_server_and_client_session(
            server_for(http, tmp_path)
        ) as session:
            result = await session.call_tool("web_read", arguments)
            assert result.isError and result.structuredContent
            assert result.structuredContent["error"]["category"] == "invalid_request"


async def wait_for_cleanup(service: WebReadService) -> None:
    async with asyncio.timeout(5):
        while service._admission._leases:
            await asyncio.sleep(0.01)


async def cancel_request(session: ClientSession, call: asyncio.Task[Any]) -> None:
    # SDK has no public cancel helper; requests in this fixture are issued serially.
    request_id = session._request_id - 1
    call.cancel()
    with pytest.raises(asyncio.CancelledError):
        await call
    await session.send_notification(
        types.ClientNotification(
            types.CancelledNotification(
                params=types.CancelledNotificationParams(
                    requestId=request_id, reason="Injected cancellation"
                )
            )
        )
    )


@pytest.mark.parametrize("fault", ["timeout", "cancelled"])
async def test_completed_pdf_prefix_is_recoverable_after_interruption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    started = asyncio.Event()
    pdf = text_pdf("Committed page one.", "Completed page two.", "Pending page three.")
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                headers={"content-type": "application/pdf"},
                content=pdf,
            )
        )
    ) as http:
        server = server_for(http, tmp_path)
        service = server.read_service
        original = service._pdf_target

        async def target(operation: str, data: bytes, args: dict[str, Any], deadline: float) -> Any:
            if args["page_number"] == 3:
                started.set()
                if fault == "timeout":
                    raise TimeoutError
                await asyncio.Event().wait()
            return await original(operation, data, args, deadline)

        async with create_connected_server_and_client_session(server) as session:
            opened = await session.call_tool(
                "web_read",
                {"url": "https://example.org/text.pdf", "max_pages": 1, "max_output_chars": 8},
            )
            assert opened.structuredContent and not opened.isError
            initial = opened.structuredContent
            identity = {"read_id": initial["read_id"]}
            monkeypatch.setattr(service, "_pdf_target", target)
            call = asyncio.create_task(
                session.call_tool(
                    "web_read",
                    {"action": "advance", **identity, "targets": [{"page": 2}, {"page": 3}]},
                )
            )
            await asyncio.wait_for(started.wait(), 5)
            if fault == "cancelled":
                await cancel_request(session, call)
                await wait_for_cleanup(service)
            else:
                result = await call
                assert not result.isError and result.structuredContent
                assert result.structuredContent["status"] == "partial"
            recovered = await session.call_tool(
                "web_read", {"action": "find", **identity, "query": "Completed"}
            )
            assert recovered.structuredContent and not recovered.isError
            body = recovered.structuredContent
            assert body["version"] != initial["version"]
            assert body["matches"] and body["matches"][0]["page"] == 2
            assert any(
                item["kind"] == fault and item["locator"]["page"] == 3 for item in body["failures"]
            )
            assert body["unprocessed_ranges"]
            assert body["recovery"]["action"] == "advance"
            old = await session.call_tool(
                "web_read",
                {
                    "action": "read",
                    **identity,
                    "version": initial["version"],
                    "cursor": initial["next_cursor"],
                },
            )
            assert old.structuredContent and not old.isError
            assert old.structuredContent["version"] == initial["version"]
            monkeypatch.setattr(service, "_pdf_target", original)
            retried = await session.call_tool(
                "web_read", {"action": "advance", **identity, "targets": [{"page": 3}]}
            )
            assert retried.structuredContent and not retried.isError
            assert not retried.structuredContent["unprocessed_ranges"]


async def test_cancellation_during_os_launch_reaps_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    started = asyncio.Event()
    return_handle = asyncio.Event()
    original = asyncio.create_subprocess_exec
    children: list[asyncio.subprocess.Process] = []

    async def launch(*args: Any, **kwargs: Any) -> asyncio.subprocess.Process:
        child = await original(*args, **kwargs)
        children.append(child)
        started.set()
        await return_handle.wait()
        return child

    monkeypatch.setattr(asyncio, "create_subprocess_exec", launch)
    call = asyncio.create_task(
        WebReadService._run_worker(
            "fixture_wait_worker",
            [],
            asyncio.get_running_loop().time() + 10,
        )
    )
    try:
        await asyncio.wait_for(started.wait(), 5)
        call.cancel()
        # A cancelled parent still owns the launch and must await its handle to kill/reap it.
        await asyncio.sleep(0)
        return_handle.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(call, 5)
        assert children and children[0].returncode is not None
        assert not psutil.pid_exists(children[0].pid)
    finally:
        return_handle.set()
        for child in children:
            if child.returncode is None:
                child.kill()
                await child.wait()


async def test_http_stream_is_closed_before_cancelled_request_finishes(tmp_path: Path) -> None:
    started = asyncio.Event()
    closed = asyncio.Event()

    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self) -> Any:
            yield b"<h1>Incomplete"
            started.set()
            await asyncio.Event().wait()

        async def aclose(self) -> None:
            await asyncio.sleep(0)
            closed.set()

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, headers={"content-type": "text/html"}, stream=Stream()
            )
        )
    ) as http:
        server = server_for(http, tmp_path)
        async with create_connected_server_and_client_session(server) as session:
            call = asyncio.create_task(
                session.call_tool("web_read", {"url": "https://example.org/stream"})
            )
            await asyncio.wait_for(started.wait(), 5)
            await cancel_request(session, call)
            await asyncio.wait_for(closed.wait(), 5)
            await wait_for_cleanup(server.read_service)
            assert not server.read_service._states


@pytest.mark.parametrize("path", ["/text.pdf", "/scan.pdf", "/first.png", "/article", "/app"])
@pytest.mark.parametrize("release", [False, True])
async def test_cancel_processing_preserves_old_version_or_finishes_release(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    release: bool,
) -> None:
    started = asyncio.Event()
    async with httpx.AsyncClient(transport=httpx.MockTransport(source)) as http:
        server = server_for(http, tmp_path)
        service = server.read_service
        async with create_connected_server_and_client_session(server) as session:
            opened = await session.call_tool(
                "web_read",
                {
                    "url": "https://example.org" + path,
                    "max_pages": 1,
                    "max_regions": 1,
                    "max_output_chars": 8,
                },
            )
            assert opened.structuredContent and not opened.isError
            initial = opened.structuredContent
            identity = {"read_id": initial["read_id"]}
            state = service._states[initial["read_id"]]
            args: dict[str, Any]
            if path == "/app":
                assert state.browser
                target: Any = state.browser
                method = "interact"
                args = {"action": "interact", "target_id": "expand-target", "operation": "expand"}
            else:
                target = service
                method = "_pdf_target" if path.endswith(".pdf") else "_process_image"
                args = {
                    "action": "advance",
                    "targets": [{"page": 2}]
                    if path.endswith(".pdf")
                    else [{"region": {"x": 0, "y": 0, "width": 0.5, "height": 0.5}}],
                }
                if path == "/article":
                    args["asset_id"] = initial["locators"][-1]["asset_id"]
            original = getattr(target, method)

            async def barrier(*args: Any, **kwargs: Any) -> Any:
                started.set()
                await asyncio.Event().wait()

            monkeypatch.setattr(target, method, barrier)
            call = asyncio.create_task(
                session.call_tool("web_read", {**args, **identity, "version": initial["version"]})
            )
            await asyncio.wait_for(started.wait(), 5)
            processing_request_id = session._request_id - 1
            releasing = (
                asyncio.create_task(
                    session.call_tool("web_read", {"action": "release", **identity})
                )
                if release
                else None
            )
            # Explicit release waits for in-flight cleanup, while expiry skips a busy state.
            state.last_access = -1e20
            await service._purge_expired()
            assert service._states[initial["read_id"]] is state
            state.last_access = service._clock()
            call.cancel()
            with pytest.raises(asyncio.CancelledError):
                await call
            await session.send_notification(
                types.ClientNotification(
                    types.CancelledNotification(
                        params=types.CancelledNotificationParams(requestId=processing_request_id)
                    )
                )
            )
            await wait_for_cleanup(service)
            monkeypatch.setattr(target, method, original)
            if releasing:
                released = await asyncio.wait_for(releasing, 5)
                assert not released.isError
                assert not service._states and not list(tmp_path.iterdir())
            else:
                state.last_access = service._clock()
                retained = await session.call_tool(
                    "web_read",
                    {
                        "action": "read",
                        **identity,
                        "cursor": initial["next_cursor"],
                        "version": initial["version"],
                    },
                )
                assert retained.structuredContent and not retained.isError
                assert retained.structuredContent["version"] == initial["version"]
                assert retained.structuredContent["recovery"]["category"] == "cancelled"
                assert len(state.versions) == 1


@pytest.mark.parametrize("action", ["read", "find"])
async def test_read_find_timeout_never_schedules_processing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    action: str,
) -> None:
    async with httpx.AsyncClient(transport=httpx.MockTransport(source)) as http:
        server = server_for(http, tmp_path)
        service = server.read_service
        async with create_connected_server_and_client_session(server) as session:
            opened = await session.call_tool("web_read", {"url": "https://example.org/text.pdf"})
            assert opened.structuredContent
            initial = opened.structuredContent
            original = getattr(service, "_" + action)

            def slow(arguments: dict[str, Any]) -> Any:
                time.sleep(0.03)
                return original(arguments)

            async def forbidden(*args: Any, **kwargs: Any) -> Any:
                raise AssertionError("read/find must not schedule processing")

            monkeypatch.setattr(service, "_" + action, slow)
            for method in ("_fetch", "_pdf_target", "_process_image"):
                monkeypatch.setattr(service, method, forbidden)
            service._timeout_seconds = 0.01
            result = await session.call_tool(
                "web_read",
                {
                    "action": action,
                    "read_id": initial["read_id"],
                    **({"page": 1} if action == "read" else {"query": "Committed"}),
                },
            )
            assert result.isError and result.structuredContent
            assert result.structuredContent["error"]["category"] == "timeout"
            assert result.structuredContent["version"] == initial["version"]


@pytest.mark.parametrize(
    "stage,path",
    [
        ("http", "/article"),
        ("pdf", "/text.pdf"),
        ("raster", "/scan.pdf"),
        ("ocr", "/scan.pdf"),
        ("ocr", "/first.png"),
        ("ocr", "/article"),
        ("browser", "/app"),
        ("commit_before", "/text.pdf"),
        ("commit_after", "/text.pdf"),
    ],
)
@pytest.mark.parametrize("interruption", ["cancel", "disconnect"])
async def test_cancel_open_at_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
    path: str,
    interruption: str,
) -> None:
    started = asyncio.Event()
    interrupted = asyncio.Event()
    async with httpx.AsyncClient(transport=httpx.MockTransport(source)) as http:
        server = server_for(http, tmp_path)
        service = server.read_service
        method = {
            "http": "_fetch",
            "pdf": "_extract_pdf_in_worker",
            "raster": "_pdf_target",
            "ocr": "_process_image",
            "browser": "unused",
            "commit_before": "_publish_state",
            "commit_after": "_publish_state",
        }[stage]
        target = GrowingImageBrowser if stage == "browser" else service
        method = "open" if stage == "browser" else method
        original = getattr(target, method)

        async def barrier(*args: Any, **kwargs: Any) -> Any:
            if stage == "raster" and args[0] != "crop":
                return await original(*args, **kwargs)
            if stage == "commit_after":
                await original(*args, **kwargs)
            started.set()
            await asyncio.Event().wait()

        original_interrupted = service.interrupted

        async def observe(*args: Any, **kwargs: Any) -> None:
            await original_interrupted(*args, **kwargs)
            interrupted.set()

        monkeypatch.setattr(target, method, barrier)
        monkeypatch.setattr(service, "interrupted", observe)
        async with create_connected_server_and_client_session(server) as session:
            call = asyncio.create_task(
                session.call_tool("web_read", {"url": "https://example.org" + path})
            )
            await asyncio.wait_for(started.wait(), 10)
            if interruption == "disconnect":
                # Close the real input stream, without cancelling the server task group.
                await session._write_stream.aclose()
                with pytest.raises(McpError, match="Connection closed"):
                    await asyncio.wait_for(call, 5)
            else:
                await cancel_request(session, call)
            await asyncio.wait_for(interrupted.wait(), 5)
            await wait_for_cleanup(service)
            if stage == "commit_after" and interruption == "cancel":
                # This ID is observable only to the test. The caller lost its first open response.
                assert len(service._states) == 1
                state = next(iter(service._states.values()))
                assert state.artifact_path and state.artifact_path.exists()
            else:
                if interruption == "disconnect":
                    async with asyncio.timeout(5):
                        while service._states:
                            await asyncio.sleep(0.01)
                assert not service._states
                assert not list(tmp_path.iterdir())
        assert not service._states
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("action", ["advance", "interact"])
@pytest.mark.parametrize("fault", ["cancel", "closed"])
async def test_lost_response_after_commit_keeps_versions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    action: str,
    fault: str,
) -> None:
    delivering = asyncio.Event()
    original = RequestResponder.respond

    async def respond(self: Any, response: Any) -> None:
        request = self.request.root
        if (
            isinstance(request, types.CallToolRequest)
            and (request.params.arguments or {}).get("action") == action
        ):
            delivering.set()
            if fault == "closed":
                raise anyio.BrokenResourceError
            await asyncio.Event().wait()
        await original(self, response)

    monkeypatch.setattr(RequestResponder, "respond", respond)
    async with httpx.AsyncClient(transport=httpx.MockTransport(source)) as http:
        server = server_for(http, tmp_path)
        service = server.read_service
        async with create_connected_server_and_client_session(server) as session:
            opened = await session.call_tool(
                "web_read",
                {
                    "url": "https://example.org/app"
                    if action == "interact"
                    else "https://example.org/text.pdf",
                    "max_output_chars": 8,
                    "max_pages": 1,
                },
            )
            assert opened.structuredContent and not opened.isError
            initial = opened.structuredContent
            identity = {"read_id": initial["read_id"]}
            arguments = {"action": action, **identity, "version": initial["version"]}
            arguments.update(
                {"targets": [{"page": 2}]}
                if action == "advance"
                else {
                    "target_id": "expand-target",
                    "operation": "expand",
                }
            )
            call = asyncio.create_task(session.call_tool("web_read", arguments))
            await asyncio.wait_for(delivering.wait(), 10)
            if fault == "closed":
                async with asyncio.timeout(5):
                    while service._states[initial["read_id"]].interruption is None:
                        await asyncio.sleep(0.01)
            await cancel_request(session, call)
            async with asyncio.timeout(5):
                while service._states[initial["read_id"]].interruption is None:
                    await asyncio.sleep(0.01)
            current = await session.call_tool(
                "web_read",
                {
                    "action": "find",
                    **identity,
                    "query": "evidence" if action == "interact" else "Completed",
                },
            )
            assert current.structuredContent and not current.isError
            assert current.structuredContent["version"] != initial["version"]
            assert current.structuredContent["matches"]
            assert current.structuredContent["recovery"]["phase"] == "delivery"
            retained = await session.call_tool(
                "web_read",
                {
                    "action": "read",
                    **identity,
                    "version": initial["version"],
                    "cursor": initial["next_cursor"],
                },
            )
            assert retained.structuredContent and not retained.isError
            assert retained.structuredContent["version"] == initial["version"]
            if action == "interact":
                # Restore delivery before asking the public tool to report invalid browser state.
                monkeypatch.setattr(RequestResponder, "respond", original)
                retry = await session.call_tool(
                    "web_read", {**arguments, "version": current.structuredContent["version"]}
                )
                assert retry.isError and retry.structuredContent
                assert retry.structuredContent["error"]["category"] == "browser_state_invalid"
            await session.call_tool("web_read", {"action": "release", **identity})
            assert not service._states
            assert not list(tmp_path.iterdir())


async def test_webpage_timeout_stops_scheduling_and_discloses_remaining_images(
    tmp_path: Path,
) -> None:
    requests: list[str] = []

    def capture(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        return source(request)

    async def slow_ocr(*args: Any) -> ImageExtraction:
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    async with httpx.AsyncClient(transport=httpx.MockTransport(capture)) as http:
        server = server_for(http, tmp_path)
        server.read_service._timeout_seconds = 0.15
        server.read_service._image_processor = slow_ocr
        async with create_connected_server_and_client_session(server) as session:
            result = await session.call_tool("web_read", {"url": "https://example.org/article"})
            assert result.structuredContent and not result.isError
            body = result.structuredContent
            assert body["status"] == "partial"
            assert requests == ["/article", "/first.png"]
            assert any(
                item["locator"].get("source_url", "").endswith("/second.png")
                for item in body["failures"]
            )
            assert body["unprocessed_ranges"]
            found = await session.call_tool(
                "web_read", {"action": "find", "read_id": body["read_id"], "query": "Committed"}
            )
            assert found.structuredContent and found.structuredContent["matches"]
            assert found.structuredContent["recovery"]["category"] == "timeout"
            assert requests == ["/article", "/first.png"]
