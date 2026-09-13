# #14 Windows MCP smoke

2026-09-13 在 Windows CPU-only 环境完成 Search Batch 切片验证。需求来源为 [#14](https://github.com/EllisYuan/web_search/issues/14)，完整 client 输出见 [issue14-smoke.json](issue14-smoke.json)。#13 的单 query 记录见 [issue13-windows-smoke.md](issue13-windows-smoke.md)。

目标 MCP client 是 MCP Inspector CLI 2.6.0，runtime 为 Node.js 24.11.1；server 使用 Python 3.12.4 和 MCP Python SDK 1.30.0，transport 为真实 subprocess `stdio`。这是独立 Node MCP client 与 Python server 的实际连接验证。

| 场景 | 结果 |
| --- | --- |
| production server discovery | 发现唯一 tool `web_search`，`queries` 为 `minItems=1`、`maxItems=20`；`max_results` 上限为 20；schema 无 `route`、无 key 参数 |
| 带逐 query 覆盖的正常 batch | batch `search_depth="basic"`、`max_results=5`；第二项覆盖为 `advanced`。三项全部 `status="ok"`，`partial=false`，candidate URL 回显实际发送的 depth（`basic` / `advanced` / `basic`） |
| 重复 query | 同一 query 提交两次，得到两项独立结果且 candidates 相同，未被合并或去重 |
| 成功/失败混合 batch | `partial=true`；`ok`、`invalid_or_missing_key`（401）、`invalid_request`（400）三项均按输入顺序保留 |
| 全部失败 batch | `partial=false`，两项错误全部返回，无 `all_failed` 字段 |
| 凭据隔离 | 四次 Inspector stdout/stderr 均未包含 dummy key；401 与 400 fixture 故意在 upstream body 回显 Authorization header |

client 使用临时 `mcpServers` 配置文件，在 `env.TAVILY_API_KEY` 传入 dummy key，不按 query 传 key。production discovery 启动实际 `python -m web_search`；batch 场景使用 `tests/fixture_stdio_server.py`，它复用生产 server 的 `serve`，仅将 HTTP transport 换为 HTTPX `MockTransport`。fixture 按 query 返回受控 200/401/400，并在成功响应的 URL 中回显收到的 `search_depth`，使 client 侧可直接观察参数继承与覆盖。

这是 **contract smoke**：使用受控 Tavily HTTP responses，没有 live Tavily Search，不代表真实账户的 401/400 路径或搜索质量已验证。fixture 不是公网或 loopback HTTP service，server 也没有公开 endpoint override 或测试模式环境变量。

## 复现

先按根目录 README 执行 `uv sync --locked`。首次下载 Inspector 需要 npm registry 访问；安装后 smoke 无需公网或真实 key：

```powershell
npm install --prefix .scratch/issue13-inspector --no-save --ignore-scripts --package-lock=false --registry https://registry.npmjs.org --cache .scratch/issue13-npm-cache @modelcontextprotocol/inspector@2.6.0
.venv\Scripts\python tests/inspector_smoke.py --inspector-package .scratch/issue13-inspector/node_modules/@modelcontextprotocol/inspector --output docs/testing/issue14-smoke.json
```

脚本逐场景执行 `--method tools/list` 或 `tools/call`，通过 `--config` 提供临时 server 配置，通过 `--tool-args-json` 提交 batch 输入，并验证响应、text/structured 一致性、退出状态与凭据隔离。参考 [Inspector CLI 官方说明](https://github.com/modelcontextprotocol/inspector/blob/main/clients/cli/README.md)。

额外自动验证：`tests/test_stdio.py` 通过真实 subprocess 在同一 session 完成 discovery、单 query、401 和带覆盖的混合 batch；`tests/test_search_batch.py` 覆盖 1/20/0/21 边界、enum/type/range 拒绝、全部参数的继承与覆盖、有限并发、相反完成顺序、重复 query、合法空结果与三种 `partial` 情况；`tests/test_startup.py` 检查缺失/空 key 的启动失败。
