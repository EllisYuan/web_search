import asyncio
import hashlib
import time
from collections.abc import Awaitable, Callable

import httpx
import pytest
from browser_fixture import javascript_site
from mcp.shared.memory import create_connected_server_and_client_session

import web_search.web_read as web_read_module
from web_search.browser import BrowserFailure, BrowserSession, InteractionTarget, RenderedPage
from web_search.server import create_server
from web_search.web_read import WebReadService

pytestmark = pytest.mark.asyncio


async def allow_fixture_url(_: str) -> bool:
    return True


class InjectedBrowser(BrowserSession):
    def __init__(
        self,
        _: Callable[[str], Awaitable[bool]],
        __: float,
        *,
        blocked_requests: int = 0,
        fail_open: str | None = None,
    ) -> None:
        self.calls: list[str] = []
        self.blocked_requests = blocked_requests
        self.fail_open = fail_open
        self.invalid = False

    async def open(self, url: str) -> RenderedPage:
        self.calls.append("open")
        if self.fail_open is not None:
            raise BrowserFailure(self.fail_open, "Injected browser open failure.")
        return self._rendered_page(url)

    async def interact(
        self,
        target_id: str,
        operation: str,
        operation_value: str | int | None,
    ) -> RenderedPage:
        self.calls.append("interact")
        if self.invalid:
            raise BrowserFailure("browser_state_invalid", "Injected browser is invalid.")
        self.invalid = True
        raise BrowserFailure("timeout", "Injected interaction timeout.")

    async def close(self) -> None:
        self.calls.append("close")

    def _rendered_page(self, url: str) -> RenderedPage:
        html = "<html><body><main><h1>Injected</h1><p>Stored artifact</p></main></body></html>"
        return RenderedPage(
            url=url,
            html=html,
            title="Injected",
            language="en",
            digest=hashlib.sha256(html.encode()).hexdigest(),
            targets=(InteractionTarget("opaque-target", "expand", "Expand", "#expand"),),
            blocked_requests=self.blocked_requests,
        )


class CancellableBrowser(InjectedBrowser):
    def __init__(self, policy: Callable[[str], Awaitable[bool]], timeout: float) -> None:
        super().__init__(policy, timeout)
        self.started = asyncio.Event()

    async def interact(
        self,
        target_id: str,
        operation: str,
        operation_value: str | int | None,
    ) -> RenderedPage:
        self.calls.append("interact")
        if self.invalid:
            raise BrowserFailure("browser_state_invalid", "Injected browser is invalid.")
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.invalid = True
            raise
        raise AssertionError("unreachable")


class OpenCancellationProbe(BrowserSession):
    def __init__(self) -> None:
        super().__init__(allow_fixture_url, 1.0)
        self.started = asyncio.Event()
        self.closed = asyncio.Event()

    async def _open(self, url: str) -> RenderedPage:
        self.started.set()
        await self.closed.wait()
        raise BrowserFailure("browser_state_invalid", "Closed by cancellation.")

    async def close(self) -> None:
        self.closed.set()


async def test_open_renders_english_and_chinese_javascript_pages_in_real_browser() -> None:
    async with javascript_site() as base_url:
        async with httpx.AsyncClient(trust_env=False) as http:
            server = create_server(api_key=None, http=http, url_policy=allow_fixture_url)
            async with create_connected_server_and_client_session(server) as session:
                english = await session.call_tool("web_read", {"url": f"{base_url}/en"})
                chinese = await session.call_tool("web_read", {"url": f"{base_url}/zh"})

    assert not english.isError and not chinese.isError
    assert english.structuredContent is not None
    assert chinese.structuredContent is not None
    assert "English body rendered by browser" in english.structuredContent["content_markdown"]
    assert "浏览器渲染的中文正文" in chinese.structuredContent["content_markdown"]
    for body in (english.structuredContent, chinese.structuredContent):
        assert body["processing"] == {
            "path": ["http_fetch", "browser_render", "rendered_dom_extract"],
            "browser_rendered": True,
            "ocr_used": False,
        }
        assert body["capture_status"] == "complete"
        assert body["extraction_status"] == "complete"
        assert body["output_status"] == "complete"
        assert body["interaction_targets"]


async def test_open_cancellation_invalidates_before_waiting_for_browser_work() -> None:
    browser = OpenCancellationProbe()
    pending = asyncio.create_task(browser.open("https://example.org"))
    await asyncio.wait_for(browser.started.wait(), timeout=1)
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(pending, timeout=1)
    assert browser.closed.is_set()


async def test_open_does_not_accept_a_javascript_loading_shell_as_final_content() -> None:
    async with javascript_site() as base_url:
        async with httpx.AsyncClient(trust_env=False) as http:
            server = create_server(api_key=None, http=http, url_policy=allow_fixture_url)
            async with create_connected_server_and_client_session(server) as session:
                opened = await session.call_tool("web_read", {"url": f"{base_url}/placeholder"})

    assert not opened.isError
    assert opened.structuredContent is not None
    assert opened.structuredContent["content_markdown"] == (
        "# Hydrated\n\nContent replaced after hydration"
    )
    assert opened.structuredContent["processing"]["browser_rendered"] is True


async def test_open_renders_arbitrary_inline_javascript_with_static_blocks() -> None:
    async with javascript_site() as base_url:
        async with httpx.AsyncClient(trust_env=False) as http:
            server = create_server(api_key=None, http=http, url_policy=allow_fixture_url)
            async with create_connected_server_and_client_session(server) as session:
                opened = await session.call_tool(
                    "web_read", {"url": f"{base_url}/substantive-inline"}
                )

    assert not opened.isError
    assert opened.structuredContent is not None
    assert "Ready after arbitrary inline JavaScript" in opened.structuredContent["content_markdown"]
    assert "Loading server text" not in opened.structuredContent["content_markdown"]
    assert opened.structuredContent["processing"]["browser_rendered"] is True


async def test_real_browser_discloses_blocked_subresources_and_empty_render_failure() -> None:
    checked_urls: list[str] = []

    async with javascript_site() as base_url:

        async def allow_only_fixture(url: str) -> bool:
            checked_urls.append(url)
            return url.startswith(base_url)

        async with httpx.AsyncClient(trust_env=False) as http:
            server = create_server(api_key=None, http=http, url_policy=allow_only_fixture)
            async with create_connected_server_and_client_session(server) as session:
                partial = await session.call_tool(
                    "web_read", {"url": f"{base_url}/blocked-resource"}
                )
                failed = await session.call_tool("web_read", {"url": f"{base_url}/empty-js"})

    assert partial.structuredContent is not None
    assert partial.structuredContent["status"] == "partial"
    assert partial.structuredContent["warnings"][0]["kind"] == "browser_scope_limited"
    assert "Reliable rendered text" in partial.structuredContent["content_markdown"]
    assert "http://127.0.0.1:9/private" in checked_urls
    assert failed.isError
    assert failed.structuredContent is not None
    assert failed.structuredContent["error"]["category"] == "extraction_failed"


async def test_interact_executes_only_selected_operations_and_preserves_old_version() -> None:
    async with javascript_site() as base_url:
        async with httpx.AsyncClient(trust_env=False) as http:
            server = create_server(api_key=None, http=http, url_policy=allow_fixture_url)
            async with create_connected_server_and_client_session(server) as session:
                opened = await session.call_tool(
                    "web_read",
                    {"url": f"{base_url}/interactions", "max_output_chars": 10},
                )
                assert not opened.isError, opened.structuredContent
                assert opened.structuredContent is not None
                original = opened.structuredContent
                assert "Selected tab evidence" not in original["content_markdown"]
                descriptions = {item["description"] for item in original["interaction_targets"]}
                assert "Hidden expand" not in descriptions
                assert "Disabled expand" not in descriptions
                assert "Load more hidden" not in descriptions
                tab_target = next(
                    item
                    for item in original["interaction_targets"]
                    if item["operation"] == "select_tab"
                )
                assert "Disabled tab" not in tab_target["operation_values"]
                original_version = original["version"]
                original_cursor = original["next_cursor"]
                original_block = original["locators"][1]["block_id"]
                current = original
                additions = {
                    "expand": "Expanded evidence",
                    "select_tab": "Selected tab evidence",
                    "load_more": "Loaded additional record",
                    "scroll": "Bounded scroll result",
                }
                stale_target = next(
                    target
                    for target in current["interaction_targets"]
                    if target["operation"] == "expand"
                )
                for operation, addition in additions.items():
                    target = next(
                        item
                        for item in current["interaction_targets"]
                        if item["operation"] == operation
                    )
                    arguments = {
                        "action": "interact",
                        "read_id": current["read_id"],
                        "version": current["version"],
                        "target_id": target["target_id"],
                        "operation": operation,
                    }
                    if operation == "select_tab":
                        arguments["operation_value"] = "Evidence"
                    if operation == "scroll":
                        arguments["operation_value"] = 1
                    interacted = await session.call_tool("web_read", arguments)
                    assert not interacted.isError
                    assert interacted.structuredContent is not None
                    current = interacted.structuredContent
                    assert current["content_markdown"] == addition
                    assert current["previous_version"] != current["version"]

                old = await session.call_tool(
                    "web_read",
                    {
                        "action": "read",
                        "read_id": original["read_id"],
                        "version": original_version,
                        "block_id": original_block,
                    },
                )
                stale = await session.call_tool(
                    "web_read",
                    {
                        "action": "interact",
                        "read_id": original["read_id"],
                        "version": original_version,
                        "target_id": stale_target["target_id"],
                        "operation": "expand",
                    },
                )
                continued_old = await session.call_tool(
                    "web_read",
                    {
                        "action": "read",
                        "read_id": original["read_id"],
                        "cursor": original_cursor,
                        "max_output_chars": 10,
                    },
                )

    assert old.structuredContent is not None
    assert old.structuredContent["content_markdown"] == "# Initial\n\nOriginal version text"
    assert stale.isError
    assert stale.structuredContent is not None
    assert stale.structuredContent["error"]["category"] == "version_mismatch"
    assert continued_old.structuredContent is not None
    assert continued_old.structuredContent["version"] == original_version
    assert continued_old.structuredContent["content_markdown"]


async def test_post_action_snapshot_failure_invalidates_browser_and_preserves_version() -> None:
    async with javascript_site() as base_url:
        async with httpx.AsyncClient(trust_env=False) as http:
            server = create_server(api_key=None, http=http, url_policy=allow_fixture_url)
            async with create_connected_server_and_client_session(server) as session:
                opened = await session.call_tool(
                    "web_read", {"url": f"{base_url}/oversize-interaction"}
                )
                assert opened.structuredContent is not None
                body = opened.structuredContent
                target = next(
                    item for item in body["interaction_targets"] if item["operation"] == "load_more"
                )
                interaction = {
                    "action": "interact",
                    "read_id": body["read_id"],
                    "version": body["version"],
                    "target_id": target["target_id"],
                    "operation": "load_more",
                }
                failed = await session.call_tool("web_read", interaction)
                invalid = await session.call_tool("web_read", interaction)
                preserved = await session.call_tool(
                    "web_read",
                    {
                        "action": "find",
                        "read_id": body["read_id"],
                        "version": body["version"],
                        "query": "Committed evidence",
                    },
                )

    assert failed.isError and failed.structuredContent is not None
    assert failed.structuredContent["error"]["category"] == "resource_exhausted"
    assert invalid.isError and invalid.structuredContent is not None
    assert invalid.structuredContent["error"]["category"] == "browser_state_invalid"
    assert preserved.structuredContent is not None
    assert preserved.structuredContent["version"] == body["version"]
    assert preserved.structuredContent["matches"]


async def test_interact_validates_target_operation_value_and_real_page_presence() -> None:
    async with javascript_site() as base_url:
        async with httpx.AsyncClient(trust_env=False) as http:
            server = create_server(api_key=None, http=http, url_policy=allow_fixture_url)
            async with create_connected_server_and_client_session(server) as session:
                opened = await session.call_tool("web_read", {"url": f"{base_url}/interactions"})
                assert opened.structuredContent is not None
                body = opened.structuredContent
                scroll = next(
                    target
                    for target in body["interaction_targets"]
                    if target["operation"] == "scroll"
                )
                wrong_operation = await session.call_tool(
                    "web_read",
                    {
                        "action": "interact",
                        "read_id": body["read_id"],
                        "version": body["version"],
                        "target_id": scroll["target_id"],
                        "operation": "expand",
                    },
                )
                bad_value = await session.call_tool(
                    "web_read",
                    {
                        "action": "interact",
                        "read_id": body["read_id"],
                        "version": body["version"],
                        "target_id": scroll["target_id"],
                        "operation": "scroll",
                        "operation_value": 6,
                    },
                )
                tab = next(
                    target
                    for target in body["interaction_targets"]
                    if target["operation"] == "select_tab"
                )
                unchanged = await session.call_tool(
                    "web_read",
                    {
                        "action": "interact",
                        "read_id": body["read_id"],
                        "version": body["version"],
                        "target_id": tab["target_id"],
                        "operation": "select_tab",
                        "operation_value": "Overview",
                    },
                )
                assert unchanged.structuredContent is not None
                unchanged_tab = next(
                    item
                    for item in unchanged.structuredContent["interaction_targets"]
                    if item["operation"] == "select_tab"
                )

                disappearing = await session.call_tool(
                    "web_read", {"url": f"{base_url}/disappearing"}
                )
                assert disappearing.structuredContent is not None
                disappearing_body = disappearing.structuredContent
                target = next(
                    item
                    for item in disappearing_body["interaction_targets"]
                    if item["operation"] == "expand"
                )
                await asyncio.sleep(1.6)
                gone = await session.call_tool(
                    "web_read",
                    {
                        "action": "interact",
                        "read_id": disappearing_body["read_id"],
                        "version": disappearing_body["version"],
                        "target_id": target["target_id"],
                        "operation": "expand",
                    },
                )

                changing = await session.call_tool("web_read", {"url": f"{base_url}/changing"})
                assert changing.structuredContent is not None
                changing_body = changing.structuredContent
                changing_target = next(
                    item
                    for item in changing_body["interaction_targets"]
                    if item["operation"] == "expand"
                )
                await asyncio.sleep(1.6)
                diverged = await session.call_tool(
                    "web_read",
                    {
                        "action": "interact",
                        "read_id": changing_body["read_id"],
                        "version": changing_body["version"],
                        "target_id": changing_target["target_id"],
                        "operation": "expand",
                    },
                )

    for response in (wrong_operation, bad_value):
        assert response.isError
        assert response.structuredContent is not None
        assert response.structuredContent["error"]["category"] == "invalid_request"
    assert unchanged.structuredContent is not None
    assert unchanged.structuredContent["version_changed"] is False
    assert unchanged.structuredContent["version"] == body["version"]
    assert unchanged.structuredContent["content_markdown"] == ""
    assert unchanged_tab["target_id"] == tab["target_id"]
    assert gone.isError
    assert gone.structuredContent is not None
    assert gone.structuredContent["error"]["category"] == "not_found"
    assert diverged.isError
    assert diverged.structuredContent is not None
    assert diverged.structuredContent["error"]["category"] == "version_mismatch"


async def test_read_and_find_use_committed_artifact_and_timeout_invalidates_browser() -> None:
    browsers: list[InjectedBrowser] = []

    def factory(policy: Callable[[str], Awaitable[bool]], timeout: float) -> BrowserSession:
        browser = InjectedBrowser(policy, timeout)
        browsers.append(browser)
        return browser

    def shell(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="<div id='app'></div><script></script>",
        )

    from harness import connected

    async with connected(
        shell,
        api_key=None,
        url_policy=allow_fixture_url,
        browser_factory=factory,
    ) as session:
        opened = await session.call_tool("web_read", {"url": "https://example.org/app"})
        assert opened.structuredContent is not None
        body = opened.structuredContent
        await session.call_tool(
            "web_read",
            {
                "action": "read",
                "read_id": body["read_id"],
                "version": body["version"],
                "block_id": body["locators"][1]["block_id"],
            },
        )
        await session.call_tool(
            "web_read",
            {
                "action": "find",
                "read_id": body["read_id"],
                "version": body["version"],
                "query": "artifact",
            },
        )
        timed_out = await session.call_tool(
            "web_read",
            {
                "action": "interact",
                "read_id": body["read_id"],
                "version": body["version"],
                "target_id": "opaque-target",
                "operation": "expand",
            },
        )
        invalid = await session.call_tool(
            "web_read",
            {
                "action": "interact",
                "read_id": body["read_id"],
                "version": body["version"],
                "target_id": "opaque-target",
                "operation": "expand",
            },
        )
        preserved = await session.call_tool(
            "web_read",
            {
                "action": "find",
                "read_id": body["read_id"],
                "version": body["version"],
                "query": "Stored artifact",
            },
        )

    assert browsers[0].calls == ["open", "interact", "close", "close"]
    assert timed_out.structuredContent is not None
    assert timed_out.structuredContent["error"]["category"] == "timeout"
    assert invalid.structuredContent is not None
    assert invalid.structuredContent["error"]["category"] == "browser_state_invalid"
    assert preserved.structuredContent is not None
    assert preserved.structuredContent["matches"][0]["text"] == "Stored artifact"


async def test_browser_partial_and_full_failures_are_disclosed() -> None:
    def shell(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="<div id='app'></div><script></script>",
        )

    def static_shell(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text=(
                "<article><h1>Reliable article</h1><p>Preserved static evidence.</p></article>"
                "<script>analytics()</script>"
            ),
        )

    from harness import connected

    async with connected(
        shell,
        api_key=None,
        url_policy=allow_fixture_url,
        browser_factory=lambda policy, timeout: InjectedBrowser(
            policy, timeout, blocked_requests=2
        ),
    ) as session:
        partial = await session.call_tool("web_read", {"url": "https://example.org/partial"})
    async with connected(
        shell,
        api_key=None,
        url_policy=allow_fixture_url,
        browser_factory=lambda policy, timeout: InjectedBrowser(
            policy, timeout, fail_open="timeout"
        ),
    ) as session:
        failed = await session.call_tool("web_read", {"url": "https://example.org/fail"})
    async with connected(
        static_shell,
        api_key=None,
        url_policy=allow_fixture_url,
        browser_factory=lambda policy, timeout: InjectedBrowser(
            policy, timeout, fail_open="timeout"
        ),
    ) as session:
        fallback = await session.call_tool("web_read", {"url": "https://example.org/article"})

    assert partial.structuredContent is not None
    assert partial.structuredContent["status"] == "partial"
    assert partial.structuredContent["extraction_status"] == "partial"
    assert partial.structuredContent["warnings"][0]["kind"] == "browser_scope_limited"
    assert failed.isError
    assert failed.structuredContent is not None
    assert failed.structuredContent["error"]["category"] == "timeout"
    assert not fallback.isError
    assert fallback.structuredContent is not None
    assert fallback.structuredContent["status"] == "partial"
    assert "Preserved static evidence" in fallback.structuredContent["content_markdown"]
    assert fallback.structuredContent["locators"]
    assert fallback.structuredContent["warnings"][0]["kind"] == "browser_render_failed"
    assert fallback.structuredContent["processing"]["browser_rendered"] is False


async def test_expired_browser_budget_preserves_static_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_extract = web_read_module.extract_html
    browser_created = False

    def slow_extract(html: str) -> web_read_module.ExtractedDocument:
        time.sleep(0.2)
        return original_extract(html)

    def factory(policy: Callable[[str], Awaitable[bool]], timeout: float) -> BrowserSession:
        nonlocal browser_created
        browser_created = True
        return InjectedBrowser(policy, timeout)

    def static_shell(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="<article><p>Deadline-safe static evidence.</p></article><script>run()</script>",
        )

    monkeypatch.setattr(web_read_module, "extract_html", slow_extract)
    async with httpx.AsyncClient(transport=httpx.MockTransport(static_shell)) as http:
        service = WebReadService(
            http,
            url_policy=allow_fixture_url,
            timeout_seconds=0.1,
            browser_factory=factory,
        )
        async with service.lifecycle():
            result, is_error = await service.dispatch({"url": "https://example.org/article"})

    assert not is_error
    assert not browser_created
    assert result["status"] == "partial"
    assert "Deadline-safe static evidence" in result["content_markdown"]
    assert result["locators"]
    assert result["warnings"][0]["kind"] == "browser_render_failed"


async def test_cancelled_interaction_invalidates_browser_and_preserves_artifact() -> None:
    browsers: list[CancellableBrowser] = []

    def factory(policy: Callable[[str], Awaitable[bool]], timeout: float) -> BrowserSession:
        browser = CancellableBrowser(policy, timeout)
        browsers.append(browser)
        return browser

    def shell(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="<div id='app'></div><script></script>",
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(shell)) as http:
        service = WebReadService(
            http,
            url_policy=allow_fixture_url,
            browser_factory=factory,
        )
        async with service.lifecycle():
            body, is_error = await service.dispatch({"url": "https://example.org/app"})
            assert not is_error
            interaction = {
                "action": "interact",
                "read_id": body["read_id"],
                "version": body["version"],
                "target_id": "opaque-target",
                "operation": "expand",
            }
            pending = asyncio.create_task(service.dispatch(interaction))
            await asyncio.wait_for(browsers[0].started.wait(), timeout=1)
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending
            invalid, invalid_error = await service.dispatch(interaction)
            preserved, preserved_error = await service.dispatch(
                {
                    "action": "find",
                    "read_id": body["read_id"],
                    "version": body["version"],
                    "query": "Stored artifact",
                }
            )

    assert invalid_error
    assert invalid["error"]["category"] == "browser_state_invalid"
    assert not preserved_error
    assert preserved["matches"]
