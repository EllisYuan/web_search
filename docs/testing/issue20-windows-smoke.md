# Issue #20 Windows browser smoke

## Windows CPU-only stdio 验收

2026-09-15 在 Windows 11 10.0.26200、Python 3.12.4、MCP Python SDK 1.30.0、Playwright 1.62.0 与其 Chromium 151.0.7922.34 binary 上运行 `tests/test_stdio.py::test_real_stdio_renders_and_interacts_with_javascript_page`。client 与 server 通过真实 subprocess stdio transport 通信；server 在 CPU-only headless Chromium 中打开真实 loopback HTTP JavaScript fixture，没有公网请求、Tavily key 或注入 browser success。

smoke 确认静态 response 为空壳时，JavaScript 生成的英文正文由 rendered DOM 抽取，`processing.path` 与 `browser_rendered` 披露实际路径。caller 使用响应中的 opaque `target_id` 和当前 `version` 执行 `expand`；响应只返回新增正文，`previous_version` 与新 `version` 对应实际变化。同一 subprocess 还验证 rendered DOM 为空时返回 `extraction_failed`。stdio 断开后 server lifecycle 关闭 browser context/process，stderr 为空。

## Contract 与 failure 覆盖

`tests/test_browser_web_read.py` 还通过公开 MCP call 覆盖中英文真实 Chromium fixture、loading shell、四种 operation、strict operation/value/version 校验、target 消失、无新增内容、旧 version/locator/cursor、正常与 partial 状态。timeout、`browser_state_invalid` 和 cancellation 使用注入 browser failure；cancellation 在 service action boundary 验证，因为当前 MCP Python SDK 的 in-memory client 不暴露可稳定控制的 request cancellation notification。既有 static HTML、text PDF 与 Search tests 保持原路径。

browser context 不携带 host cookies 或 credentials，block service worker/download 和 interaction navigation；每个 browser request 继续通过 URL policy。边界包括 30 秒默认 deadline、100 次 browser request、10,000,000-byte 累计 browser response、2,000,000-byte rendered DOM、512,000,000-byte browser process RSS、5 个 scroll step、16 个 immutable version、单 page、最多 2 个 renderer process 和 256 MiB V8 old-space。response 由 Chromium DevTools Protocol 累计；RSS 每 50 ms 采样并在超限时关闭 page，可能存在一个采样周期内的瞬时超量。
