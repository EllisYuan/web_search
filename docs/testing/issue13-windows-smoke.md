# #13 Windows MCP smoke

2026-09-13 在 Windows CPU-only 环境完成单 query 切片验证。需求来源为 [#13](https://github.com/EllisYuan/web_search/issues/13)，完整 client 输出见 [issue13-smoke.json](issue13-smoke.json)。

目标 MCP client 是 MCP Inspector CLI 2.6.0，runtime 为 Node.js 24.11.1；server 使用 Python 3.12.4 和 MCP Python SDK 1.30.0，transport 为真实 subprocess `stdio`。这是独立 Node MCP client 与 Python server 的实际连接验证。

| 场景 | 结果 |
| --- | --- |
| production server discovery | 发现唯一 tool `web_search`，`queries` 必填且 `minItems=maxItems=1`，无额外 Search 参数 |
| 单 query 成功 | `中文 MCP smoke` 原样回显，`partial=false`、`status="ok"`，candidate 保留 metadata 与 `rank=1` |
| HTTP 401 fixture | `partial=false`、`status="error"`、`error.category="invalid_or_missing_key"`；client text 与 structured output 一致 |
| 凭据隔离 | 三次 Inspector stdout/stderr 均未包含 dummy key；401 fixture 故意在 upstream body 回显 Authorization header |

client 使用临时 `mcpServers` 配置文件，在 `env.TAVILY_API_KEY` 传入 dummy key。production discovery 启动实际 `python -m web_search`；成功和 401 使用 `tests/fixture_stdio_server.py`，它复用生产 server 的 `serve`，仅将 HTTP transport 换为 HTTPX `MockTransport`。fixture 不是公网或 loopback HTTP service，没有进行 live Tavily Search，也不代表真实账户的 401 或搜索质量已验证。server 没有公开 endpoint override 或测试模式环境变量。

## 复现

先按根目录 README 执行 `uv sync --locked`。首次下载 Inspector 需要 npm registry 访问；安装后 smoke 无需公网或真实 key：

```powershell
npm install --prefix .scratch/issue13-inspector --no-save --ignore-scripts --package-lock=false --registry https://registry.npmjs.org --cache .scratch/issue13-npm-cache @modelcontextprotocol/inspector@2.6.0
.venv\Scripts\python tests/inspector_smoke.py --inspector-package .scratch/issue13-inspector/node_modules/@modelcontextprotocol/inspector --output .scratch/issue13-smoke.json
```

脚本从 Inspector package 的 `bin` 找到 CLI，逐场景执行 `--method tools/list` 或 `tools/call`，通过 `--config` 向 client 提供临时 server 配置，通过 `--tool-args-json` 提交 Search 输入。它验证响应、text/structured 一致性、退出状态与凭据隔离，并输出 JSON evidence。参考 [Inspector CLI 官方说明](https://github.com/modelcontextprotocol/inspector/blob/main/clients/cli/README.md)。

额外自动验证：`tests/test_stdio.py` 使用 MCP Python `ClientSession` 连接真实 subprocess，在同一 session 完成 discovery、正常调用和 401。`tests/test_startup.py` 检查缺失/空 key 时 exit code 2、无 stdout、无 traceback；主要 contract cases 在 `tests/test_web_search.py` 中通过 MCP session 和 HTTP fixtures 执行。

本次全量 `pytest` 共 50 项通过；`mypy`、`ruff check`、`ruff format --check` 均通过。`uv build --offline` 成功生成 sdist 与 wheel，并检查了 package 文件清单。sdist 显式限定 production source、tests、使用说明和 smoke evidence，避免把本地研究资料、prototypes 或工作目录打包。Standards、Spec 与凭据/HTTP security review 未发现待修问题。
