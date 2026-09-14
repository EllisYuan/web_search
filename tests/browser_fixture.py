"""Real loopback HTTP fixture used by Chromium Web Read tests."""

# ruff: noqa: E501

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


@asynccontextmanager
async def javascript_site() -> AsyncIterator[str]:
    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            head = await reader.readuntil(b"\r\n\r\n")
            path = head.split(b" ", 2)[1].decode("ascii")
            language = "zh" if path.startswith("/zh") else "en"
            text = (
                "浏览器渲染的中文正文" if language == "zh" else "English body rendered by browser"
            )
            if path.startswith("/interactions"):
                script = """
                const app = document.querySelector('#app');
                app.innerHTML = `
                  <h1>Initial</h1><p>Original version text</p>
                  <button id="expand" aria-expanded="false">Expand details</button>
                  <div role="tablist"><button role="tab">Overview</button><button role="tab">Evidence</button></div>
                  <p id="tab-body" hidden>Selected tab evidence</p>
                  <button id="more">Load more</button><div id="tail" style="height:2000px"></div>`;
                document.querySelector('#expand').onclick = event => {
                  event.currentTarget.setAttribute('aria-expanded', 'true');
                  event.currentTarget.insertAdjacentHTML('afterend', '<p>Expanded evidence</p>');
                };
                document.querySelector('[role=tablist]').onclick = event => {
                  if (event.target.textContent === 'Evidence') {
                    document.querySelector('#tab-body').hidden = false;
                  }
                };
                document.querySelector('#more').onclick = event => {
                  event.currentTarget.insertAdjacentHTML('beforebegin', '<p>Loaded additional record</p>');
                  event.currentTarget.remove();
                };
                addEventListener('scroll', () => {
                  if (!document.querySelector('#scroll-body')) {
                    document.querySelector('#tail').insertAdjacentHTML('beforebegin', '<p id="scroll-body">Bounded scroll result</p>');
                  }
                }, {once: true});
                """
            elif path.startswith("/disappearing"):
                script = """
                const app = document.querySelector('#app');
                app.innerHTML = '<h1>Transient</h1><p>Stable text</p><button aria-expanded="false">Temporary target</button>';
                setTimeout(() => document.querySelector('button').remove(), 1500);
                """
            elif path.startswith("/changing"):
                script = """
                const app = document.querySelector('#app');
                app.innerHTML = '<h1>Changing</h1><p id="value">Before</p><button aria-expanded="false">Still present</button>';
                setTimeout(() => document.querySelector('#value').textContent = 'After', 1500);
                """
            elif path.startswith("/placeholder"):
                script = """
                document.querySelector('#app').innerHTML =
                  '<h1>Hydrated</h1><p>Content replaced after hydration</p>';
                """
            elif path.startswith("/blocked-resource"):
                script = """
                document.querySelector('#app').innerHTML =
                  '<h1>Partial</h1><p>Reliable rendered text</p><img src="http://127.0.0.1:9/private">';
                """
            elif path.startswith("/empty-js"):
                script = "document.querySelector('#app').textContent = ''"
            else:
                script = (
                    "document.querySelector('#app').innerHTML='<h1>Rendered</h1><p>"
                    + text
                    + "</p>'"
                )
            body = (
                "<!doctype html><html lang='" + language + "'><head><meta charset='utf-8'>"
                "<title>Rendered fixture</title></head><body><main id='app'>"
                + ("<p>Loading...</p>" if path.startswith("/placeholder") else "")
                + "</main>"
                "<script>" + script + "</script></body></html>"
            ).encode("utf-8")
            writer.write(
                b"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n"
                + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
                + body
            )
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    try:
        port = server.sockets[0].getsockname()[1]
        yield f"http://127.0.0.1:{port}"
    finally:
        server.close()
        await server.wait_closed()
