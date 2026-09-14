# #17 Web Read static HTML 验收记录

需求来源：[#17](https://github.com/EllisYuan/web_search/issues/17)；契约基线：`docs/specs/2026-09-14-web-read-v1.md`。

## Windows stdio smoke

2026-09-14 在 Windows NT 10.0.26200、CPU-only 环境，以 Python 3.12.4、MCP Python SDK 1.30.0、HTTPX 0.28.1 运行 `tests/test_stdio.py::test_real_stdio_discovery_and_mixed_batch`。client 与 server 使用真实 subprocess `stdio`；只在 HTTP boundary 注入 deterministic `MockTransport`，没有公网请求、真实 Tavily key 或付费调用。

同一 MCP session 完成以下业务链路：

1. discovery 在非空 dummy `TAVILY_API_KEY` 下返回 `web_search`、`web_read`；
2. `web_search` 返回受控 candidate URL；
3. caller 选择该 URL 并调用 `web_read open`，得到 truncated output 与 cursor；
4. `read` 使用固定 budget 续读，`find` 以不同大小写命中原文；
5. `release` 返回幂等成功契约。

测试同时检查 stdout JSON text 与 `structuredContent`、stderr 以及 dummy key 隔离。无 key / 空白 key 的 production entry point 启动行为由 `tests/test_startup.py` 覆盖；process 收到 EOF 后正常退出，不输出 traceback。

## Deterministic contract coverage

`tests/test_web_read.py` 全部通过公开 MCP `list_tools` / `call_tool` seam 验证：中英文 HTML、heading outline、table header / unit、footnote 原文、section / block / cursor、无重复或静默丢失、无 refetch 的 `read/find`、NFKC + casefold matching、document / section scope、idle expiry、幂等 release、version / cursor error、严格字段与 budget 校验、URL/userinfo/private IP/redirect boundary、resource gate、403、unsupported format、timeout 与后续恢复。

最终验证命令与结果记录：

```powershell
uv run mypy
uv run ruff check src tests --no-cache
uv run ruff format --check src tests --no-cache
uv run pytest -q -p no:cacheprovider
```

最终结果：mypy strict、Ruff check / format check 全部通过，**171 tests passed**（9.60s），无 skip。

本记录只验收 #17 的 static HTML vertical slice，不宣称 JavaScript rendering、PDF、OCR、`advance`、`interact` 或 `asset` 已实现，也不构成 extraction quality 或 latency SLA。
