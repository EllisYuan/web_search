"""Loopback Tavily fixtures using real HTTP sockets, never a public endpoint."""

import asyncio
import json
from types import TracebackType
from typing import Any, Self

import httpx


class LoopbackTransport(httpx.AsyncBaseTransport):
    def __init__(self, port: int, *, max_connections: int = 2) -> None:
        self.port = port
        self.http = httpx.AsyncHTTPTransport(
            retries=0,
            limits=httpx.Limits(max_connections=max_connections),
        )

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == "https://api.tavily.com/search"
        local = httpx.Request(
            request.method,
            request.url.copy_with(scheme="http", host="127.0.0.1", port=self.port),
            headers=request.headers,
            stream=request.stream,
            extensions=request.extensions,
        )
        return await self.http.handle_async_request(local)

    async def aclose(self) -> None:
        await self.http.aclose()


class TavilyHTTPFixture:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.completed: list[str] = []
        self.disconnected: asyncio.Queue[str] = asyncio.Queue()
        self.trickle_chunks = 0
        self.tasks: set[asyncio.Task[None]] = set()
        self.gates: dict[str, asyncio.Event] = {}

    async def __aenter__(self) -> Self:
        self.server = await asyncio.start_server(self._accept, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.server.close()
        await self.server.wait_closed()
        remaining = list(self.tasks)
        for task in remaining:
            task.cancel()
        await asyncio.gather(*remaining, return_exceptions=True)

    def _accept(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.create_task(self._handle(reader, writer))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            head = await reader.readuntil(b"\r\n\r\n")
            request_line, *lines = head.decode("latin-1").strip().split("\r\n")
            headers = dict(line.split(": ", 1) for line in lines)
            headers = {name.lower(): value for name, value in headers.items()}
            body = json.loads(await reader.readexactly(int(headers["content-length"])))
            query = body["query"]
            self.requests.append({"request_line": request_line, "body": body})
            if query in self.gates:
                await self.gates[query].wait()
            if query in {"fixture-timeout", "fixture-trickle"}:
                await self._wait_for_disconnect(query, headers["authorization"], reader, writer)
                return
            if query == "fixture-reset":
                writer.transport.abort()
                self.completed.append(query)
                return
            status = {
                "fixture-400": 400,
                "fixture-401": 401,
                "fixture-429": 429,
                "fixture-432": 432,
                "fixture-433": 433,
                "fixture-500": 500,
                "fixture-503": 503,
                "fixture-418": 418,
            }.get(query, 200)
            payload: dict[str, Any]
            if status != 200 or query == "fixture-malformed":
                payload = {"error": headers["authorization"], "results": [{}]}
            else:
                payload = {
                    "results": [
                        {
                            "title": "受控 Search fixture",
                            "url": "https://example.org/source?depth="
                            + body.get("search_depth", "unset"),
                            "content": f"Offline SERP metadata for {query}",
                            "score": 0.8,
                            "published_date": "2026-09-13",
                        }
                    ]
                }
            data = json.dumps(payload, ensure_ascii=False).encode()
            retry_after = "Retry-After: 120\r\n" if status in {429, 432, 433, 503} else ""
            writer.write(
                f"HTTP/1.1 {status} Fixture\r\nContent-Length: {len(data)}\r\n"
                f"Content-Type: application/json\r\nConnection: close\r\n{retry_after}\r\n".encode()
                + data
            )
            await writer.drain()
            self.completed.append(query)
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except ConnectionError:
                pass

    async def _wait_for_disconnect(
        self,
        query: str,
        authorization: str,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        if query == "fixture-timeout":
            await reader.read()
        else:
            writer.write(
                b"HTTP/1.1 200 Fixture\r\nTransfer-Encoding: chunked\r\n"
                b"Content-Type: application/json\r\n\r\n"
            )
            prefix = json.dumps({"error": authorization}).encode()[:-1] + b', "results": ['
            writer.write(f"{len(prefix):x}\r\n".encode() + prefix + b"\r\n")
            await writer.drain()
            while True:
                try:
                    await asyncio.wait_for(reader.read(1), timeout=0.02)
                    break
                except TimeoutError:
                    writer.write(b"1\r\n \r\n")
                    await writer.drain()
                    self.trickle_chunks += 1
                except ConnectionError:
                    break
        self.completed.append(query)
        self.disconnected.put_nowait(query)
