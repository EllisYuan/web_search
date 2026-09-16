"""Bounded Playwright rendering and explicit interaction for one public page."""

from __future__ import annotations

import asyncio
import hashlib
import os
import secrets
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import anyio
import psutil
from playwright.async_api import (
    Browser,
    BrowserContext,
    CDPSession,
    Frame,
    Locator,
    Page,
    Playwright,
    Route,
    WebSocketRoute,
    async_playwright,
)
from playwright.async_api import (
    Error as PlaywrightError,
)
from playwright.async_api import (
    TimeoutError as PlaywrightTimeoutError,
)

from web_search.limits import MAX_BROWSER_TEMPORARY_BYTES
from web_search.resources import PROCESS_ADMISSION, AdmissionController, ResourceExhausted

URLPolicy = Callable[[str], Awaitable[bool]]
Operation = Literal["expand", "select_tab", "load_more", "scroll"]

MAX_BROWSER_REQUESTS = 100
MAX_SCROLL_STEPS = 5
MAX_RENDERED_DOM_BYTES = 2_000_000
MAX_BROWSER_RESPONSE_BYTES = 10_000_000
MAX_BROWSER_RSS_BYTES = 512_000_000


class BrowserFailure(Exception):
    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category


@dataclass(frozen=True)
class InteractionTarget:
    target_id: str
    operation: Operation
    description: str
    selector: str
    operation_values: tuple[str, ...] = ()
    value_selectors: tuple[tuple[str, str], ...] = ()

    def public(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "target_id": self.target_id,
            "operation": self.operation,
            "description": self.description,
        }
        if self.operation_values:
            result["operation_values"] = list(self.operation_values)
        if self.operation == "scroll":
            result["operation_value"] = {"type": "integer", "minimum": 1, "maximum": 5}
        return result


@dataclass(frozen=True)
class RenderedPage:
    url: str
    html: str
    title: str
    language: str | None
    digest: str
    targets: tuple[InteractionTarget, ...]
    blocked_requests: int


class BrowserSession:
    """An isolated page whose network and actions stay inside explicit bounds."""

    def __init__(
        self,
        url_policy: URLPolicy,
        deadline_seconds: float,
        *,
        admission: AdmissionController = PROCESS_ADMISSION,
        artifact_directory: Path | None = None,
    ) -> None:
        self._url_policy = url_policy
        self._deadline_seconds = deadline_seconds
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._cdp: CDPSession | None = None
        self._browser_cdp: CDPSession | None = None
        self._targets: dict[str, InteractionTarget] = {}
        self._target_ids: dict[tuple[Any, ...], str] = {}
        self._request_count = 0
        self._blocked_requests = 0
        self._policy_blocked = False
        self._navigation_locked = False
        self._valid = True
        self._current_digest = ""
        self._resource_failure: BrowserFailure | None = None
        self._response_bytes = 0
        self._browser_pids: set[int] = set()
        self._memory_task: asyncio.Task[None] | None = None
        self._admission = admission
        self._artifact_directory = artifact_directory
        self._temporary_path: Path | None = None
        self._network_tasks: set[asyncio.Task[Any]] = set()
        self._guarded_targets: set[str] = set()
        self._guard_lock = asyncio.Lock()

    async def open(self, url: str) -> RenderedPage:
        task = asyncio.create_task(self._open(url))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            with anyio.CancelScope(shield=True):
                await self.invalidate()
                with suppress(Exception, asyncio.CancelledError):
                    await asyncio.shield(task)
            raise

    async def _open(self, url: str) -> RenderedPage:
        try:
            async with asyncio.timeout(self._deadline_seconds):
                self._temporary_path = self._admission.browser_directory(self._artifact_directory)
                self._playwright = await async_playwright().start()
                self._ensure_valid()
                self._context = await self._playwright.chromium.launch_persistent_context(
                    user_data_dir=self._temporary_path / "profile",
                    headless=True,
                    service_workers="block",
                    accept_downloads=False,
                    downloads_path=self._temporary_path / "downloads",
                    traces_dir=self._temporary_path / "traces",
                    env={
                        **os.environ,
                        "TMP": str(self._temporary_path),
                        "TEMP": str(self._temporary_path),
                    },
                    args=[
                        "--renderer-process-limit=2",
                        "--js-flags=--max-old-space-size=256",
                        "--disk-cache-size=1048576",
                        "--media-cache-size=1048576",
                    ],
                )
                self._ensure_valid()
                self._browser = self._context.browser
                assert self._browser is not None
                self._ensure_valid()
                await self._context.route("**/*", self._route)
                await self._context.route_web_socket("**/*", self._block_websocket)
                self._page = self._context.pages[0]
                self._ensure_valid()
                self._page.on("popup", lambda popup: asyncio.create_task(popup.close()))
                self._page.on("download", lambda download: asyncio.create_task(download.cancel()))
                await self._guard_frame(self._page.main_frame)
                self._cdp = await self._context.new_cdp_session(self._page)
                await self._cdp.send("Network.enable")
                self._cdp.on("Network.dataReceived", self._record_response_bytes)
                self._browser_cdp = await self._browser.new_browser_cdp_session()
                process_info = await self._browser_cdp.send("SystemInfo.getProcessInfo")
                self._browser_pids = {
                    int(item["id"])
                    for item in process_info.get("processInfo", [])
                    if isinstance(item, dict) and isinstance(item.get("id"), int | float)
                }
                self._memory_task = asyncio.create_task(self._monitor_memory())
                await self._page.goto(url, wait_until="domcontentloaded")
                try:
                    await self._page.wait_for_load_state("networkidle", timeout=1_000)
                except PlaywrightTimeoutError:
                    pass
                self._raise_resource_failure()
                rendered = await self._snapshot()
                self._navigation_locked = True
                return rendered
        except TimeoutError as error:
            await self.invalidate()
            raise BrowserFailure("timeout", "Browser rendering timed out.") from error
        except (ResourceExhausted, MemoryError, OSError) as error:
            await self.invalidate()
            raise BrowserFailure(
                "resource_exhausted", "Browser resources are unavailable."
            ) from error
        except BrowserFailure:
            await self.invalidate()
            raise
        except Exception as error:
            await self.invalidate()
            if self._resource_failure is not None:
                raise self._resource_failure from error
            category = "access_blocked" if self._policy_blocked else "extraction_failed"
            raise BrowserFailure(category, "Browser rendering failed.") from error

    def _record_response_bytes(self, event: dict[str, Any]) -> None:
        encoded = event.get("encodedDataLength", 0)
        if isinstance(encoded, int | float):
            self._response_bytes += int(encoded)
        if self._response_bytes > MAX_BROWSER_RESPONSE_BYTES:
            self._fail_resource("Browser responses exceed the transfer limit.")

    async def _monitor_memory(self) -> None:
        while self._valid:
            try:
                browser_cdp = self._browser_cdp
                if browser_cdp is None:
                    return
                process_info = await browser_cdp.send("SystemInfo.getProcessInfo")
                self._browser_pids = {
                    int(item["id"])
                    for item in process_info.get("processInfo", [])
                    if isinstance(item, dict) and isinstance(item.get("id"), int | float)
                }
                rss = sum(
                    psutil.Process(pid).memory_info().rss
                    for pid in self._browser_pids
                    if psutil.pid_exists(pid)
                )
                if rss > MAX_BROWSER_RSS_BYTES:
                    self._fail_resource("Browser memory exceeds the process limit.")
                    return
                if self._temporary_path is not None:
                    size = sum(
                        path.stat().st_size
                        for path in self._temporary_path.rglob("*")
                        if path.is_file()
                    )
                    if size > MAX_BROWSER_TEMPORARY_BYTES:
                        self._fail_resource("Browser temporary storage exceeds the session limit.")
                        return
            except (psutil.Error, OSError):
                pass
            except Exception:
                if self._valid:
                    self._fail_resource("Browser memory monitoring became unavailable.")
                return
            await asyncio.sleep(0.05)

    def _fail_resource(self, message: str) -> None:
        if self._resource_failure is None:
            self._resource_failure = BrowserFailure("resource_exhausted", message)
        page = self._page
        if page is not None and not page.is_closed():
            asyncio.create_task(page.close())

    def _raise_resource_failure(self) -> None:
        if self._resource_failure is not None:
            raise self._resource_failure

    def _ensure_valid(self) -> None:
        if not self._valid:
            raise BrowserFailure("browser_state_invalid", "The browser session was cancelled.")

    async def _route(self, route: Route) -> None:
        request = route.request
        self._request_count += 1
        try:
            allowed = await self._url_policy(request.url)
        except Exception:
            allowed = False
        if not allowed:
            self._blocked_requests += 1
            self._policy_blocked = True
            await route.abort("blockedbyclient")
            return
        if self._request_count > MAX_BROWSER_REQUESTS:
            self._blocked_requests += 1
            await route.abort("blockedbyclient")
            return
        if request.resource_type in {"font", "image", "media"}:
            self._blocked_requests += 1
            await route.abort("blockedbyclient")
            return
        if self._navigation_locked and request.is_navigation_request():
            self._blocked_requests += 1
            await route.abort("blockedbyclient")
            return
        try:
            frame = request.frame
        except PlaywrightError:
            # A popup's first request can precede its Frame. Such navigation is
            # outside this session's page; reject it before any upstream I/O.
            self._blocked_requests += 1
            await route.abort("blockedbyclient")
            return
        if frame.page is not self._page:
            self._blocked_requests += 1
            await route.abort("blockedbyclient")
            return
        await self._guard_frame(frame)
        await route.continue_()

    async def _block_websocket(self, route: WebSocketRoute) -> None:
        # WebSockets are outside the bounded page acquisition scope. HTTP route
        # handlers never see their handshake; do not connect to the upstream.
        self._blocked_requests += 1
        await route.close(code=1008, reason="WebSocket acquisition is disabled")

    async def _guard_frame(self, frame: Frame) -> None:
        # Playwright routes only the first request of a redirect chain. A second
        # CDP session checks the actual URL before Chromium sends every hop.
        async with self._guard_lock:
            assert self._context is not None and self._page is not None
            # Same-process frames share the nearest ancestor's target; after
            # navigation a frame can move to a new target, so resolve it anew.
            while True:
                if frame is self._page.main_frame and self._guarded_targets:
                    return
                try:
                    session = await self._context.new_cdp_session(frame)
                    break
                except PlaywrightError as error:
                    if "part of the parent frame's session" not in str(error):
                        raise
                    parent = frame.parent_frame
                    if parent is None:
                        raise
                    frame = parent
            info = await session.send("Target.getTargetInfo")
            target_id = info["targetInfo"]["targetId"]
            if target_id in self._guarded_targets:
                # Detaching while this target has paused requests can stall
                # Chromium. The context owns this session until close().
                return
            else:
                session.on(
                    "Fetch.requestPaused", lambda event: self._schedule_request(session, event)
                )
                await session.send("Fetch.enable", {"patterns": [{"urlPattern": "*"}]})
                self._guarded_targets.add(target_id)

    def _schedule_request(self, session: CDPSession, event: dict[str, Any]) -> None:
        task = asyncio.create_task(self._check_request(session, event))
        self._network_tasks.add(task)
        task.add_done_callback(self._network_tasks.discard)

    async def _check_request(self, session: CDPSession, event: dict[str, Any]) -> None:
        try:
            try:
                async with asyncio.timeout(self._deadline_seconds):
                    allowed = self._valid and await self._url_policy(event["request"]["url"])
            except Exception:
                allowed = False
            if event.get("redirectedRequestId"):
                self._request_count += 1
            if not self._valid or not allowed or self._request_count > MAX_BROWSER_REQUESTS:
                self._blocked_requests += 1
                self._policy_blocked = self._policy_blocked or not allowed
                await session.send(
                    "Fetch.failRequest",
                    {"requestId": event["requestId"], "errorReason": "BlockedByClient"},
                )
            else:
                await session.send("Fetch.continueRequest", {"requestId": event["requestId"]})
        except Exception:
            # A detached/closed target cannot continue its pending requests.
            if self._valid:
                self._fail_resource("Browser network policy became unavailable.")

    async def interact(
        self,
        target_id: str,
        operation: str,
        operation_value: str | int | None,
    ) -> RenderedPage:
        task = asyncio.create_task(self._interact(target_id, operation, operation_value))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            with anyio.CancelScope(shield=True):
                await self.invalidate()
                task.cancel()
                with suppress(Exception, asyncio.CancelledError):
                    await task
            raise

    async def _interact(
        self,
        target_id: str,
        operation: str,
        operation_value: str | int | None,
    ) -> RenderedPage:
        if not self._valid or self._page is None or self._page.is_closed():
            self._valid = False
            raise BrowserFailure("browser_state_invalid", "The browser session is unavailable.")
        target = self._targets.get(target_id)
        if target is None:
            raise BrowserFailure("not_found", "The interaction target no longer exists.")
        if operation != target.operation:
            raise BrowserFailure("invalid_request", "operation does not match the target.")
        self._validate_value(target, operation_value)
        action_started = False
        try:
            async with asyncio.timeout(self._deadline_seconds):
                self._raise_resource_failure()
                if target.operation == "select_tab":
                    assert isinstance(operation_value, str)
                    locator = self._page.locator(dict(target.value_selectors)[operation_value])
                else:
                    locator = self._page.locator(target.selector)
                if target.operation != "scroll" and await locator.count() != 1:
                    await self.invalidate()
                    raise BrowserFailure("not_found", "The interaction target no longer exists.")
                if await self._visible_digest() != self._current_digest:
                    await self.invalidate()
                    raise BrowserFailure(
                        "version_mismatch", "The live page changed after the committed version."
                    )
                if target.operation == "scroll":
                    assert isinstance(operation_value, int)
                    action_started = True
                    for _ in range(operation_value):
                        await self._page.evaluate("window.scrollBy(0, window.innerHeight)")
                        await self._page.wait_for_timeout(100)
                else:
                    action_started = True
                    await locator.click()
                    await self._page.wait_for_timeout(100)
                self._raise_resource_failure()
                return await self._snapshot()
        except TimeoutError as error:
            await self.invalidate()
            raise BrowserFailure("timeout", "Browser interaction timed out.") from error
        except BrowserFailure:
            if action_started:
                await self.invalidate()
            raise
        except Exception as error:
            await self.invalidate()
            if self._resource_failure is not None:
                raise self._resource_failure from error
            raise BrowserFailure("browser_state_invalid", "Browser interaction failed.") from error

    @staticmethod
    def _validate_value(target: InteractionTarget, value: str | int | None) -> None:
        if target.operation == "select_tab":
            if not isinstance(value, str) or value not in target.operation_values:
                raise BrowserFailure("invalid_request", "operation_value must name an offered tab.")
        elif target.operation == "scroll":
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not 1 <= value <= MAX_SCROLL_STEPS
            ):
                raise BrowserFailure(
                    "invalid_request", "scroll operation_value must be from 1 to 5."
                )
        elif value is not None:
            raise BrowserFailure(
                "invalid_request", "operation_value is not accepted by this target."
            )

    async def _snapshot(self) -> RenderedPage:
        assert self._page is not None
        targets = await self._discover_targets()
        self._targets = {target.target_id: target for target in targets}
        html = await self._visible_html()
        if len(html.encode("utf-8")) > MAX_RENDERED_DOM_BYTES:
            raise BrowserFailure("resource_exhausted", "Rendered DOM exceeds the size limit.")
        language = await self._page.locator("html").get_attribute("lang")
        digest = hashlib.sha256(html.encode("utf-8")).hexdigest()
        self._current_digest = digest
        return RenderedPage(
            url=self._page.url,
            html=html,
            title=await self._page.title(),
            language=language,
            digest=digest,
            targets=targets,
            blocked_requests=self._blocked_requests,
        )

    async def _visible_html(self) -> str:
        assert self._page is not None
        html = await self._page.evaluate(
            """() => {
                const clone = document.documentElement.cloneNode(true);
                const source = [
                    document.documentElement,
                    ...document.documentElement.querySelectorAll('*')
                ];
                const copied = [clone, ...clone.querySelectorAll('*')];
                for (let i = copied.length - 1; i >= 0; i--) {
                    const item = source[i];
                    const style = getComputedStyle(item);
                    const closedDetails = item.closest('details:not([open])');
                    const hiddenDetails = closedDetails && item !== closedDetails &&
                        item.tagName !== 'SUMMARY';
                    if (item.hidden || item.getAttribute('aria-hidden') === 'true' ||
                        style.display === 'none' || style.visibility === 'hidden' ||
                        hiddenDetails) {
                        copied[i].remove();
                    } else {
                        copied[i].removeAttribute('data-web-read-target');
                    }
                }
                const attributes = [...clone.attributes]
                    .map(a => ` ${a.name}="${a.value}"`).join('');
                return '<html' + attributes +
                    '>' + clone.innerHTML + '</html>';
            }"""
        )
        if not isinstance(html, str):
            raise BrowserFailure("extraction_failed", "Rendered DOM could not be serialized.")
        return html

    async def _visible_digest(self) -> str:
        html = await self._visible_html()
        return hashlib.sha256(html.encode("utf-8")).hexdigest()

    async def _discover_targets(self) -> tuple[InteractionTarget, ...]:
        assert self._page is not None
        targets: list[InteractionTarget] = []
        expanded = self._page.locator(
            "button[aria-expanded='false'], details:not([open]) > summary"
        )
        for index in range(min(await expanded.count(), 20)):
            locator = expanded.nth(index)
            if not await locator.is_visible() or not await locator.is_enabled():
                continue
            text = (await locator.inner_text()).strip() or "Expand hidden content"
            targets.append(self._target("expand", text, await self._selector(locator)))

        tablists = self._page.get_by_role("tablist")
        for index in range(min(await tablists.count(), 10)):
            tablist = tablists.nth(index)
            labels_list: list[str] = []
            value_selectors: list[tuple[str, str]] = []
            tabs = tablist.locator("button[role='tab']")
            for tab in range(min(await tabs.count(), 20)):
                tab_locator = tabs.nth(tab)
                if not await tab_locator.is_visible() or not await tab_locator.is_enabled():
                    continue
                label = (await tab_locator.inner_text()).strip()
                if label and len(label) <= 200:
                    labels_list.append(label)
                    value_selectors.append((label, await self._selector(tab_locator)))
            labels = tuple(labels_list)
            if labels and len(set(labels)) == len(labels):
                targets.append(
                    self._target(
                        "select_tab",
                        "Select a visible tab",
                        "",
                        operation_values=labels,
                        value_selectors=tuple(value_selectors),
                    )
                )

        buttons = self._page.locator("button")
        for index in range(min(await buttons.count(), 50)):
            button = buttons.nth(index)
            if not await button.is_visible() or not await button.is_enabled():
                continue
            text = (await button.inner_text()).strip()
            if text and any(
                term in text.casefold() for term in ("load more", "show more", "加载更多")
            ):
                targets.append(self._target("load_more", text, await self._selector(button)))

        targets.append(self._target("scroll", "Scroll the current page by viewport steps", "html"))
        return tuple(targets)

    @staticmethod
    async def _selector(locator: Locator) -> str:
        existing = await locator.get_attribute("data-web-read-target")
        token = existing or "web-read-" + secrets.token_urlsafe(8)
        await locator.evaluate(
            "(element, value) => element.setAttribute('data-web-read-target', value)", token
        )
        return f'[data-web-read-target="{token}"]'

    def _target(
        self,
        operation: Operation,
        description: str,
        selector: str,
        *,
        operation_values: tuple[str, ...] = (),
        value_selectors: tuple[tuple[str, str], ...] = (),
    ) -> InteractionTarget:
        signature: tuple[Any, ...] = (
            operation,
            description[:200],
            selector,
            operation_values,
            tuple(selector for _, selector in value_selectors),
        )
        target_id = self._target_ids.setdefault(signature, secrets.token_urlsafe(12))
        return InteractionTarget(
            target_id,
            operation,
            description[:200],
            selector,
            operation_values,
            value_selectors,
        )

    async def invalidate(self) -> None:
        self._valid = False
        await self.close()

    async def close(self) -> None:
        with anyio.CancelScope(shield=True):
            await self._close()

    async def _close(self) -> None:
        self._valid = False
        network_tasks = self._network_tasks - {asyncio.current_task()}
        for task in network_tasks:
            task.cancel()
        if network_tasks:
            await asyncio.gather(*network_tasks, return_exceptions=True)
        self._guarded_targets.clear()
        context, browser, playwright = self._context, self._browser, self._playwright
        memory_task = self._memory_task
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None
        self._cdp = None
        self._browser_cdp = None
        self._memory_task = None
        if memory_task is not None and memory_task is not asyncio.current_task():
            memory_task.cancel()
            with suppress(asyncio.CancelledError):
                await memory_task
        if context is not None:
            try:
                await context.close()
            except Exception:
                pass
        if browser is not None:
            try:
                await browser.close()
            except Exception:
                pass
        if playwright is not None:
            try:
                await playwright.stop()
            except Exception:
                pass
        if self._temporary_path is not None:
            self._admission.remove_browser(self._temporary_path)
            self._temporary_path = None
