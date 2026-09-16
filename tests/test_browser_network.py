"""Real Chromium regression tests for the BrowserSession acquisition boundary."""

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, suppress
from pathlib import Path

import pytest

from web_search.browser import BrowserFailure, BrowserSession, URLPolicy
from web_search.resources import CURRENT_WORK, AdmissionController

Response = tuple[int, dict[str, str], bytes]


@asynccontextmanager
async def network_site(
    respond: Callable[[str], Response],
) -> AsyncIterator[tuple[str, list[str]]]:
    received: list[str] = []

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            head = await reader.readuntil(b"\r\n\r\n")
            path = head.split(b" ", 2)[1].decode("ascii")
            received.append(path)
            status, headers, body = respond(path)
            headers = {"Content-Length": str(len(body)), "Connection": "close", **headers}
            writer.write(
                f"HTTP/1.1 {status} Response\r\n".encode()
                + "".join(f"{name}: {value}\r\n" for name, value in headers.items()).encode()
                + b"\r\n"
                + body
            )
            await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        finally:
            writer.close()
            with suppress(ConnectionError):
                await writer.wait_closed()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    async with server:
        yield f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}", received


@asynccontextmanager
async def browser_session(policy: URLPolicy, directory: Path) -> AsyncIterator[BrowserSession]:
    admission = AdmissionController()
    lease = admission.acquire(directory)
    assert lease is not None
    token = CURRENT_WORK.set(lease)
    browser = BrowserSession(policy, 15, admission=admission, artifact_directory=directory)
    try:
        yield browser
    finally:
        await browser.close()
        CURRENT_WORK.reset(token)
        admission.release(lease)


async def test_browser_rejects_redirect_before_contacting_forbidden_target(tmp_path: Path) -> None:
    def respond(path: str) -> Response:
        if path == "/redirect":
            return 302, {"Location": "/hop"}, b""
        if path == "/hop":
            return 307, {"Location": "/private"}, b""
        return 200, {"Content-Type": "text/html"}, b"<main>PRIVATE_SENTINEL</main>"

    async with network_site(respond) as (base_url, received):

        async def policy(url: str) -> bool:
            return url in {f"{base_url}/redirect", f"{base_url}/hop"}

        async with browser_session(policy, tmp_path) as browser:
            failure = None
            try:
                await browser.open(f"{base_url}/redirect")
            except BrowserFailure as error:
                failure = error

        assert "/private" not in received
        assert "/redirect" in received and "/hop" in received
        assert failure is not None and failure.category == "access_blocked"


async def test_browser_blocks_websocket_before_handshake(tmp_path: Path) -> None:
    def respond(path: str) -> Response:
        if path == "/page":
            return (
                200,
                {"Content-Type": "text/html"},
                b"""<main>Public content</main>
                <script>
                const socket = new WebSocket('ws://' + location.host + '/private-ws');
                socket.onclose = () => document.title = 'WebSocket closed';
                </script>""",
            )
        return 400, {}, b"Forbidden handshake reached server"

    async with network_site(respond) as (base_url, received):

        async def policy(url: str) -> bool:
            return url == f"{base_url}/page"

        async with browser_session(policy, tmp_path) as browser:
            rendered = await browser.open(f"{base_url}/page")

        assert "/private-ws" not in received
        assert "Public content" in rendered.html
        assert rendered.blocked_requests >= 1
        assert rendered.title == "WebSocket closed"


async def test_browser_keeps_final_url_and_relative_scripts_after_allowed_redirects(
    tmp_path: Path,
) -> None:
    def respond(path: str) -> Response:
        if path == "/redirect":
            return 302, {"Location": "/hop"}, b""
        if path == "/hop":
            return 308, {"Location": "/final/page"}, b""
        if path == "/final/page":
            return (
                200,
                {"Content-Type": "text/html"},
                (b'<main>Allowed content</main><script src="./script.js"></script>'),
            )
        if path == "/final/script.js":
            return 200, {"Content-Type": "text/javascript"}, b"document.title = 'Script loaded';"
        return 404, {}, b""

    async with network_site(respond) as (base_url, received):

        async def policy(url: str) -> bool:
            return url.startswith(base_url + "/")

        async with browser_session(policy, tmp_path) as browser:
            rendered = await browser.open(f"{base_url}/redirect")

        assert rendered.url == f"{base_url}/final/page"
        assert rendered.title == "Script loaded"
        assert "Allowed content" in rendered.html
        assert "/hop" in received and "/final/script.js" in received
        assert rendered.blocked_requests == 0


@pytest.mark.parametrize("source", ["fetch", "iframe", "cross_origin_iframe"])
async def test_browser_blocks_redirects_from_subresources(tmp_path: Path, source: str) -> None:
    def respond(path: str) -> Response:
        if path == "/page":
            if source == "fetch":
                script = "fetch('/redirect').catch(() => {});"
            else:
                target = (
                    "/redirect"
                    if source == "iframe"
                    else base_url.replace("127.0.0.1", "localhost") + "/frame"
                )
                script = (
                    f"document.body.appendChild(document.createElement('iframe')).src = '{target}';"
                )
            return (
                200,
                {"Content-Type": "text/html"},
                (f"<main>Reliable body</main><script>{script}</script>".encode()),
            )
        if path == "/frame":
            return (
                200,
                {"Content-Type": "text/html"},
                (b"<main>Frame content</main><script>fetch('/redirect').catch(() => {});</script>"),
            )
        if path == "/redirect":
            return 302, {"Location": "/private"}, b""
        return 200, {"Content-Type": "text/html"}, b"<main>PRIVATE_SENTINEL</main>"

    async with network_site(respond) as (base_url, received):

        async def policy(url: str) -> bool:
            return not url.endswith("/private")

        async with browser_session(policy, tmp_path) as browser:
            rendered = await browser.open(f"{base_url}/page")

        assert "/redirect" in received
        assert "/private" not in received
        assert "Reliable body" in rendered.html
        assert rendered.blocked_requests >= 1


async def test_browser_blocks_redirects_in_popup_before_forbidden_connection(
    tmp_path: Path,
) -> None:
    def respond(path: str) -> Response:
        if path == "/page":
            return (
                200,
                {"Content-Type": "text/html"},
                (b"<main>Reliable body</main><script>window.open('/redirect');</script>"),
            )
        if path == "/redirect":
            return 302, {"Location": "/private"}, b""
        return 200, {"Content-Type": "text/html"}, b"<main>PRIVATE_SENTINEL</main>"

    async with network_site(respond) as (base_url, received):

        async def policy(url: str) -> bool:
            return url != f"{base_url}/private"

        async with browser_session(policy, tmp_path) as browser:
            rendered = await browser.open(f"{base_url}/page")

        assert "/private" not in received
        assert "Reliable body" in rendered.html
        assert rendered.blocked_requests >= 1
