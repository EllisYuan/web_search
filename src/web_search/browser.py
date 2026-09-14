"""Bounded Playwright rendering and explicit interaction for one public page."""

from __future__ import annotations

import asyncio
import hashlib
import re
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

from playwright.async_api import (
    Browser,
    BrowserContext,
    Locator,
    Page,
    Playwright,
    Route,
    async_playwright,
)
from playwright.async_api import (
    TimeoutError as PlaywrightTimeoutError,
)

URLPolicy = Callable[[str], Awaitable[bool]]
Operation = Literal["expand", "select_tab", "load_more", "scroll"]

MAX_BROWSER_REQUESTS = 100
MAX_SCROLL_STEPS = 5
MAX_RENDERED_DOM_BYTES = 2_000_000


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

    def __init__(self, url_policy: URLPolicy, deadline_seconds: float) -> None:
        self._url_policy = url_policy
        self._deadline_seconds = deadline_seconds
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._targets: dict[str, InteractionTarget] = {}
        self._request_count = 0
        self._blocked_requests = 0
        self._policy_blocked = False
        self._navigation_locked = False
        self._valid = True

    async def open(self, url: str) -> RenderedPage:
        try:
            async with asyncio.timeout(self._deadline_seconds):
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(
                    headless=True,
                    args=[
                        "--renderer-process-limit=2",
                        "--js-flags=--max-old-space-size=256",
                    ],
                )
                self._context = await self._browser.new_context(
                    service_workers="block",
                    accept_downloads=False,
                )
                await self._context.route("**/*", self._route)
                self._page = await self._context.new_page()
                self._page.on("popup", lambda popup: asyncio.create_task(popup.close()))
                await self._page.goto(url, wait_until="domcontentloaded")
                try:
                    await self._page.wait_for_load_state("networkidle", timeout=1_000)
                except PlaywrightTimeoutError:
                    pass
                rendered = await self._snapshot()
                self._navigation_locked = True
                return rendered
        except TimeoutError as error:
            await self.invalidate()
            raise BrowserFailure("timeout", "Browser rendering timed out.") from error
        except BrowserFailure:
            await self.invalidate()
            raise
        except Exception as error:
            await self.invalidate()
            category = "access_blocked" if self._policy_blocked else "extraction_failed"
            raise BrowserFailure(category, "Browser rendering failed.") from error

    async def _route(self, route: Route) -> None:
        request = route.request
        self._request_count += 1
        if self._navigation_locked and request.is_navigation_request():
            self._blocked_requests += 1
            await route.abort("blockedbyclient")
            return
        if self._request_count > MAX_BROWSER_REQUESTS:
            self._blocked_requests += 1
            await route.abort("blockedbyclient")
            return
        if request.resource_type in {"font", "media", "websocket"}:
            self._blocked_requests += 1
            await route.abort("blockedbyclient")
            return
        try:
            allowed = await self._url_policy(request.url)
        except Exception:
            allowed = False
        if not allowed:
            self._blocked_requests += 1
            self._policy_blocked = True
            await route.abort("blockedbyclient")
            return
        await route.continue_()

    async def interact(
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
        try:
            async with asyncio.timeout(self._deadline_seconds):
                if target.operation == "select_tab":
                    assert isinstance(operation_value, str)
                    locator = self._page.locator(dict(target.value_selectors)[operation_value])
                else:
                    locator = self._page.locator(target.selector)
                if target.operation == "scroll":
                    assert isinstance(operation_value, int)
                    for _ in range(operation_value):
                        await self._page.evaluate("window.scrollBy(0, window.innerHeight)")
                        await self._page.wait_for_timeout(100)
                else:
                    if await locator.count() != 1:
                        raise BrowserFailure(
                            "not_found", "The interaction target no longer exists."
                        )
                    await locator.click()
                    await self._page.wait_for_timeout(100)
                return await self._snapshot()
        except TimeoutError as error:
            await self.invalidate()
            raise BrowserFailure("timeout", "Browser interaction timed out.") from error
        except BrowserFailure:
            raise
        except asyncio.CancelledError:
            await self.invalidate()
            raise
        except Exception as error:
            await self.invalidate()
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
        html = await self._page.content()
        html = re.sub(r' data-web-read-target="[^"]*"', "", html)
        if len(html.encode("utf-8")) > MAX_RENDERED_DOM_BYTES:
            raise BrowserFailure("resource_exhausted", "Rendered DOM exceeds the size limit.")
        language = await self._page.locator("html").get_attribute("lang")
        return RenderedPage(
            url=self._page.url,
            html=html,
            title=await self._page.title(),
            language=language,
            digest=hashlib.sha256(html.encode("utf-8")).hexdigest(),
            targets=targets,
            blocked_requests=self._blocked_requests,
        )

    async def _discover_targets(self) -> tuple[InteractionTarget, ...]:
        assert self._page is not None
        targets: list[InteractionTarget] = []
        expanded = self._page.locator(
            "button[aria-expanded='false'], details:not([open]) > summary"
        )
        for index in range(min(await expanded.count(), 20)):
            locator = expanded.nth(index)
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
            text = (await button.inner_text()).strip()
            if text and any(
                term in text.casefold() for term in ("load more", "show more", "加载更多")
            ):
                targets.append(self._target("load_more", text, await self._selector(button)))

        targets.append(self._target("scroll", "Scroll the current page by viewport steps", "html"))
        return tuple(targets)

    @staticmethod
    async def _selector(locator: Locator) -> str:
        token = "web-read-" + secrets.token_urlsafe(8)
        await locator.evaluate(
            "(element, value) => element.setAttribute('data-web-read-target', value)", token
        )
        return f'[data-web-read-target="{token}"]'

    @staticmethod
    def _target(
        operation: Operation,
        description: str,
        selector: str,
        *,
        operation_values: tuple[str, ...] = (),
        value_selectors: tuple[tuple[str, str], ...] = (),
    ) -> InteractionTarget:
        return InteractionTarget(
            secrets.token_urlsafe(12),
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
        context, browser, playwright = self._context, self._browser, self._playwright
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None
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
