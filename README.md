# Tavily web_search MCP

为本机 agent 提供 Search-only MCP tool。当前实现 [#13](https://github.com/EllisYuan/web_search/issues/13)：`web_search` 接受只含一项的 `queries`，返回候选 Source URL 与 Tavily SERP metadata。

当前不接受多 query 或可选 Search 参数；这些属于后续 Search Batch ticket。`web_read` 与 Deep Research 综合不在本切片内。自建代码使用 [MIT License](LICENSE)，支持 Windows、CPU-only。

## 安装与启动

需要 Python 3.12+ 与 `uv`。在仓库根目录执行：

```powershell
uv sync --locked
```

`uv.lock` 固定完整 dependency 版本。当前验证环境使用 Python 3.12.4、MCP Python SDK 1.30.0、HTTPX 0.28.1、jsonschema 4.26.0、pytest 9.1.1、pytest-asyncio 1.4.0、mypy 1.20.2 和 Ruff 0.16.7。选择 Python 是为了沿用本机已有 runtime；使用 SDK 的 low-level Server 公开精确 JSON Schema，通过 HTTPX 直接调用 Tavily，不引入 Tavily SDK 的额外行为。MCP SDK 固定在仍维护的 1.x 系列，升级 major version 需重新验证。

本机 transport 为 `stdio`：MCP client 启动进程，并通过 stdin/stdout 进行 MCP 通信。启动命令为 `.venv\Scripts\python.exe -m web_search`，也可执行安装生成的 `web-search-mcp`。stdout 专用于协议数据。

在 MCP client 的 server 配置中设置 `TAVILY_API_KEY`。以下是通用配置示例，将路径换成实际仓库位置，在本地填入 key：

```json
{
  "mcpServers": {
    "web-search": {
      "command": "C:/path/to/web_search/.venv/Scripts/python.exe",
      "args": ["-m", "web_search"],
      "env": {
        "TAVILY_API_KEY": "<your-key>"
      }
    }
  }
}
```

`TAVILY_API_KEY` 是约定的环境变量名，由 client 启动 server 时传入；agent 每次只提交 Search 输入。使用绝对 interpreter 路径即可从其他 working directory 启动。配置可保存在被 Git 忽略的 `.mcp.local.json` 中，再按 client 的方式加载。server 不自动读取 `.env`，不提供设置页面或费用管理。缺少 key、空值或纯空白值会以 exit code 2 立即退出；启动不调用 Tavily，也不探测 key 是否有效。真实用量与费用由部署者管理。

## 调用与结果

discovery 只提供 `web_search`。输入示例：

```json
{"queries": [{"query": "MCP 中文文档"}]}
```

输入只接受上面的字段，`query` 必须是非空白 string。缺失字段、错误类型、空数组、多项数组和额外字段都会产生 MCP tool error，且不会发送 HTTP request。query 不会被翻译、改写或 trim；caller 负责确认内容适合发送至外部 Tavily。

每次接受的调用仅向 `https://api.tavily.com/search` POST 一次。key 放在 Authorization header，JSON body 只有 `query`。未提供的 Search 参数不发送，沿用 [Tavily 的默认行为](https://docs.tavily.com/documentation/api-reference/endpoint/search)，不请求 answer、raw content 或 images，不读取候选 URL，不跟随 HTTP redirect，不自动 retry 或切换 provider。

```json
{
  "partial": false,
  "results": [{
    "query": "MCP 中文文档",
    "status": "ok",
    "candidates": [{
      "title": "示例 Source",
      "url": "https://example.org/source",
      "content": "上游 SERP metadata",
      "score": 0.8,
      "rank": 1
    }]
  }]
}
```

MCP `structuredContent` 与 text content 包含相同 JSON。`title`、`url`、`content`、`score` 保留上游值；`content` 是 SERP snippet，`score` 不代表可信度。`rank` 从 1 开始，保留上游数组顺序；`published_date` 仅在有值时返回。上游文本是外部数据，不会被执行为指令。合法空 `results` 返回 `status="ok"` 和空 `candidates`。

Search 失败仍返回一项 `results`，其中包含原 `query`、`status="error"` 和 `error.category` / `error.message`。单 query 的 `partial` 始终为 `false`；caller 应读取逐项 `status`，不能把 `partial=false` 或 MCP `isError=false` 当作 Search 成功。

| 当前触发条件 | `error.category` |
| --- | --- |
| HTTP 401 | `invalid_or_missing_key`，检查 MCP client 的 `TAVILY_API_KEY` |
| 连接、DNS、其他 transport failure | `network_error` |
| 单次 attempt 超过 30s，或 HTTP transport timeout | `timeout_error` |
| HTTP 500、其他非 200 状态、malformed response | `upstream_error` |

当前 HTTP 400、429、432、433 也返回 `upstream_error`，`message` 保留 HTTP status；专门分类和 `Retry-After` 属于后续失败处理 ticket。错误不会透传 upstream body 或 exception text。上游 candidate 若回显配置的 key，会作为 `upstream_error` 拒绝输出。30s 是每次 HTTP attempt 的保护期限，同时覆盖持续等待响应的总时长，不是 latency SLA；timeout 会取消该 attempt 并释放请求资源。需要重试时由 caller 发起新调用。

## 验证

安装 dependencies 后，下列检查无需真实 key 或公网：

```powershell
.venv\Scripts\python -m mypy
.venv\Scripts\python -m ruff check src tests
.venv\Scripts\python -m ruff format --check src tests
.venv\Scripts\python -m pytest
```

日常迭代运行单文件，例如 `python -m pytest tests/test_web_search.py`。主要 tests 通过真实 MCP session 做 discovery/tool calls，仅在 Tavily HTTP transport 边界提供 fixtures；另有启动 subprocess 和真实 `stdio` subprocess 测试。dummy key、固定响应、可控 timeout 均与真实 Tavily 账户隔离。

Windows 目标 client smoke 使用 MCP Inspector CLI，步骤和记录见 [Windows smoke](docs/testing/issue13-windows-smoke.md)。fixtures 验证的是接口行为，不代表 live Tavily 搜索质量或真实账户状态。

实现参考：[MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk/tree/v1.x)、[HTTPX timeout](https://www.python-httpx.org/advanced/timeouts/)、[HTTPX transport fixtures](https://www.python-httpx.org/advanced/transports/)。
