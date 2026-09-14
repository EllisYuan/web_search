# #19 PDF advance 与 page crop 验收记录

需求来源：[#19](https://github.com/EllisYuan/web_search/issues/19)；契约基线：`docs/specs/2026-09-14-web-read-v1.md`。

## Windows stdio trace

2026-09-14 在 Windows CPU-only 环境使用 Python 3.12.4 与 MCP Python SDK 1.30.0 运行：

```powershell
python -m pytest -p no:cacheprovider tests/test_stdio.py::test_real_stdio_pdf_advance_and_asset_without_key -q
```

client 与 server 使用真实 subprocess `stdio`，只在 HTTP boundary 使用 deterministic `MockTransport`。同一 MCP session 完成：

1. 无 `TAVILY_API_KEY` discovery 只返回 `web_read`；
2. `open(max_pages=1)` 捕获三页 PDF，只 extraction page 1；
3. `read/find` 读取 page 1，并确认 page 2 尚未处理；
4. 非法 normalized region 在 processing 前返回 `invalid_request`；
5. `advance(targets=[{"page":3},{"page":2}])` 从 capture artifact 非顺序处理 page 3，并在 page 2 无 text layer 时原子保留成功结果、返回 failure locator、新 `version` 和 `source_acquisition=false`；
6. 新 `version` 使用旧 cursor 返回 `version_mismatch`；
7. `asset(asset_type="pdf_page_crop", page=3)` 返回 PNG `ImageContent`；
8. `release` 后用于 capture 的临时目录不含 PDF artifact，stderr 为空。

结果：**1 passed**。public MCP contract tests 另覆盖 normalized region、partial target success、failed region retry、并发 commit 冲突、重复 target、旧 version / cursor / selector、无额外 acquisition、timeout、cancellation、state expiry 与 PNG signature；timeout / cancellation tests 断言中断前已提交正文保持一致。

该 trace 使用受控 born-digital text PDF，不代表 mixed/scanned PDF、OCR、JavaScript rendering 或 extraction quality SLA。
