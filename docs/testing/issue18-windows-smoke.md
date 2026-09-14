# #18 第一阶段 Web Read text PDF 验收记录

需求来源：[#18](https://github.com/EllisYuan/web_search/issues/18)；契约基线：`docs/specs/2026-09-14-web-read-v1.md`，Q1–Q16。该记录只覆盖第一阶段 static HTML + born-digital text PDF。

## Windows MCP stdio 验收

2026-09-14 在 Windows 11 10.0.26200、Python 3.12.4、MCP Python SDK 1.30.0、HTTPX 0.28.1、pypdfium2 5.13.0 的 CPU-only 本地环境运行 `tests/test_stdio.py::test_real_stdio_first_phase_html_and_text_pdf_without_key`。client 与 server 是真实 subprocess stdio session；HTTP boundary 使用受控 `MockTransport`，没有公网请求或真实 Tavily key。此项是 Windows 本机验收，不声称 clean-machine 或真实网站 PDF corpus 验证。

无 key discovery 仅有 `web_read`；同一 session 打开 static HTML 和两页 text PDF。PDF `max_pages=1` 时捕获两页、只处理第一页；`max_output_chars=10` 使 output truncated。client 用固定 `version`、budget 和 cursor 拼回第一页 Markdown；`find(scope=page,page=1)` 命中原文，`read(page=2)` 明确报告未处理，`release` 释放 state。`structuredContent` 与 TextContent JSON 一致。已有 `test_real_stdio_discovery_and_mixed_batch` 验证有 key 时同时注册 `web_search`、`web_read`。

## Contract 与失败覆盖

`tests/test_web_read.py` 通过公开 MCP `call_tool` seam 使用真实 PDF parser 与受控 PDF bytes，覆盖中英文 text layer、metadata、outline、page/block locator、page budget 与 output budget 分离、cursor 拼接、page-scoped find、无 refetch 的 state read、无 text layer、mixed page、加密/损坏 PDF，以及 release、idle expiry、process exit、restart 后旧 handle 不恢复。fixture 由 `tests/pdf_fixture.py` 用 pypdf 生成；它是 dev-only 依赖，不参与 production extraction。空 text layer、加密和损坏属于受控 failure fixture；不是对公开 corpus 的成功率测量。

PDF text layer 中的 table/column-like 布局保留为 plain text，并发出带 page locator 的 `structure_incomplete` warning；普通多行文字不因此误报，也不把 table 标为可靠结构。当前不实现 OCR、rendered JavaScript、`advance`、`interact` 或 `asset`，也不宣称 mixed/scanned PDF 全部可读。`unprocessed_ranges.next_action=advance` 指向后续阶段能力；第一阶段若需更多 page，caller 必须显式重新 `open` 并增加 `max_pages`，不会由 `read/find/cursor` 自动补抓。

Server 保护上限：acquisition 2,000,000 bytes，caller `max_pages` 最大 100、默认 10，captured PDF 最多 10,000 pages，单页 native text 最多 1,000,000 chars，整份 extracted text 最多 2,000,000 chars；默认 `open` deadline 30 秒，HTTP acquisition 与 PDF extraction 共用同一 deadline。PDFium 在隔离 worker 中执行；即使单页 native call 未返回，父进程也会在 deadline 到达时终止 worker 并清理临时 PDF。受控短 deadline 测试验证了 `timeout` 分类与 artifact cleanup。

## 最终本机检查

```powershell
uv run mypy src tests
uv run ruff check src tests --no-cache
uv run ruff format --check src tests --no-cache
uv run pytest -q -p no:cacheprovider
```

结果：mypy strict、Ruff check/format check 全部通过；**180 tests passed**（25.31s），无 skip。此结果仅说明 deterministic contract 与本机 stdio 路径通过，不代表 PDF reading-order、table fidelity 或长期 performance SLA。
