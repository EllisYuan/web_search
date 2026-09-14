# Tavily web_search MCP

为本机 agent 提供 Search-only MCP tool。已实现 [#12 Search spec](https://github.com/EllisYuan/web_search/issues/12) 的三个实施切片（#13、#14、[#15](https://github.com/EllisYuan/web_search/issues/15)）：`web_search` 接受含 1–20 项的 `queries`，支持 batch 级与逐 query 的 Search 参数，返回候选 Source URL 与 Tavily SERP metadata，并在限流、额度限制、网络失败或慢请求下保留逐项结果。

提供可解释的错误分类与有效 `Retry-After` 等待提示，不自动 retry。`web_read` 与 Deep Research 综合不在本次实现内。自建代码使用 [MIT License](LICENSE)，支持 Windows、CPU-only。

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

discovery 只提供 `web_search`。一次调用提交一个 Search Batch：

```json
{
  "search_depth": "basic",
  "max_results": 5,
  "queries": [
    {"query": "MCP 中文文档"},
    {"query": "MCP specification", "search_depth": "advanced", "include_domains": ["modelcontextprotocol.io"]}
  ]
}
```

`queries` 必填，含 1–20 项，每项必填非空白 `query` string。空数组、超过 20 项、缺失字段、错误类型、超出 enum/range 或额外字段都会产生 MCP tool error，且不发送任何 HTTP request——**整个 batch 被拒绝，不会先发送其中的合法项**。query 不会被翻译、改写或 trim；caller 负责确认内容适合发送至外部 Tavily。

### Search 参数与继承

下列参数可放在 batch 层，也可放在单个 query object 中：

| 参数 | 接受的值 |
| --- | --- |
| `search_depth` | `basic` / `advanced` |
| `max_results` | integer，0–20 |
| `topic` | `general` / `news` / `finance` |
| `time_range` | `day` / `week` / `month` / `year` |
| `start_date` / `end_date` | date string，`YYYY-MM-DD` |
| `include_domains` / `exclude_domains` | string 数组 |
| `country` / `language` | string |
| `exact_match` | boolean |

按字段判断：query 层**存在**该字段就覆盖 batch，否则继承 batch，两层都没有则不发送给 Tavily，落到 [Tavily 自身默认值](https://docs.tavily.com/documentation/api-reference/endpoint/search)。判断依据是字段是否存在而非 truthiness，所以显式的 `false`、`0` 和 `[]` 都会被保留并发送。数组是整体覆盖，不与 batch 数组合并。

两个 20 是不同的上限：`queries` 最多 **20 个 query**（控制本次发出的请求数），`max_results` 最多 **20 个候选**（控制单个 query 返回多少条结果）。MCP 自行拒绝 `max_results=21`，不依赖上游拒绝。

`start_date` / `end_date` 只做基本字段校验：必须是 `YYYY-MM-DD` 形态且为真实存在的日期，`2026-02-30` 这类会被拒绝。日期的语义（例如两者的先后关系）交给 Tavily。

参数组合是否合法由 Tavily 判断（例如 `country` 与 `topic` 的组合）。MCP 只做基本字段校验，不复制上游组合规则；类型正确的组合会实际发送，上游 HTTP 400 映射为该 query 的 `invalid_request`。

`safe_search`、`chunks_per_source`、`auto_parameters`、`include_domains_mode` 不暴露，维持 Tavily 默认。`include_answer`、`include_raw_content`、`include_images`、`include_favicon`、`include_usage` 不暴露，接入保持 Search-only。schema 不接受 API key、`route` 或成本参数。

### 执行与结果

每个 query 对应至多一次 `https://api.tavily.com/search` POST。key 放在 Authorization header，JSON body 只含解析后的参数。每个 Search Batch 内有限并发（当前 `MAX_CONCURRENT_ATTEMPTS = 5`，是保护性实现值，不是 process-wide 限流或验证过的吞吐目标）；不读取候选 URL，不跟随 HTTP redirect，不自动 retry 或切换 provider。

```json
{
  "partial": true,
  "results": [
    {
      "query": "MCP 中文文档",
      "status": "ok",
      "candidates": [{
        "title": "示例 Source",
        "url": "https://example.org/source",
        "content": "上游 SERP metadata",
        "score": 0.8,
        "rank": 1
      }]
    },
    {
      "query": "MCP specification",
      "status": "error",
      "error": {"category": "invalid_or_missing_key", "message": "..."}
    }
  ]
}
```

`results` 的项数与顺序**始终与输入的 `queries` 一致**：第 N 项结果对应第 N 个输入 query，与各请求的完成顺序无关。重复的 query 保留为各自独立的项，不合并、不跨项去重。单项失败不会取消或丢弃其他 query 的结果。

MCP `structuredContent` 与 text content 包含相同 JSON。`title`、`url`、`content`、`score` 保留上游值；`content` 是 SERP snippet，`score` 不代表可信度。`rank` 从 1 开始，保留上游数组顺序；`published_date` 仅在有值时返回。上游文本是外部数据，不会被执行为指令。合法空 `results` 返回 `status="ok"` 和空 `candidates`。

### partial 的含义

| 各 query 的结果 | `partial` |
| --- | --- |
| 全部 `ok`（含合法空结果） | `false` |
| 至少一个 `ok` 且至少一个 `error` | `true` |
| 全部 `error` | `false` |

**`partial=false` 不等于整体成功**：全部失败时它同样是 `false`。caller 必须逐项读取 `status`，不能用 `partial` 或 MCP `isError=false` 判断 Search 是否成功。响应没有 `all_failed`、`successful`、`failed` 等统计字段。

### 错误与等待提示

失败项包含原 `query`、`status="error"` 和必填的 `error.category` / `error.message`；仅在上游提供有效等待提示时额外包含 number `retry_after_seconds`：

| 触发条件 | `error.category` |
| --- | --- |
| HTTP 400 | `invalid_request` |
| HTTP 401 | `invalid_or_missing_key` |
| HTTP 429 | `rate_limited` |
| HTTP 432 / 433 | `quota_exhausted` |
| 连接、DNS、其他 transport failure | `network_error` |
| 单次 attempt 超过默认 30s 期限，或 HTTP transport timeout | `timeout_error` |
| HTTP 500、其他未分类的非 200 状态、malformed response、该 query 的意外内部失败 | `upstream_error` |

HTTP 400 的 `message` 提示检查参数值及组合；401 提示检查 MCP client 的 `TAVILY_API_KEY`。432 的 `message` 明确包含 `plan_limit_exceeded`，433 明确包含 `payg_limit_exceeded`，由 caller 或部署者判断账户限制，不新增必填 error 字段。公共 `category` 不使用斜线连接的 prototype 标识。

例如，429 可以返回以下逐项错误：

```json
{
  "query": "MCP specification",
  "status": "error",
  "error": {
    "category": "rate_limited",
    "message": "Tavily rate limited this Search request (HTTP 429).",
    "retry_after_seconds": 120
  }
}
```

非 200 响应中的有效 `Retry-After` 会作为建议时间返回，包括限流、额度及 503 等错误。支持非负整数秒数和 HTTP-date；HTTP-date 相对收到响应时的本地 UTC 时钟换算，可产生小数秒，已经过去的日期返回 `0`。缺失、非法值或无法表示为有限 number 的值会**省略该字段**，不返回 `null`，不伪造默认等待时间。它只是上游建议，不保证等待后就能成功，也不触发 server 自动 sleep 或 retry；只有 caller 下一次显式 tool 调用才产生新 attempt。

错误不会透传完整 upstream body 或 exception text。任何单个 query 的失败——包括意外的内部异常——都被收敛为该项的 `error`，不会取消其他 query，也不会用一个 MCP 异常替代整个 batch 的逐项结果。上游 candidate 若回显配置的 key，会作为 `upstream_error` 拒绝输出。

### timeout 与已知限制

- 默认 **30s 是每次 HTTP attempt 的总等待期限**，不只是等待下一个网络数据块的 read timeout。请求获得 batch 执行名额后开始计时；排队中的 query 有自己的期限，30s 不是整个 batch 的完成时间 SLA。
- timeout 会取消本地未完成请求并释放连接与执行名额，其他 query 照常返回；不保证已经开始的上游工作被撤销或不产生费用。
- `MAX_CONCURRENT_ATTEMPTS = 5` 只限制单个 batch；同时发起多个 tool 调用可能产生更多并发。它不是账户 rate limit、RPM 或费用预算。MCP 不执行额度跟踪、成本拦截、自动充值、账单请求或 provider fallback。
- HTTP-date 等待提示依赖本机时钟准确性。无效或没有 `Retry-After` 不代表可以立即高频重试；caller 自行决定是否以及何时再调用。
- 429/432/433 的 wrapper 行为有 deterministic fixtures 和 Windows client smoke 覆盖，**真实账户路径尚未验证**。Search 质量、Source 覆盖、长期 latency、吞吐量和 Web Read 未据此验收。

## 验证

安装 dependencies 后，下列检查无需真实 key 或公网：

```powershell
.venv\Scripts\python -m mypy
.venv\Scripts\python -m ruff check src tests
.venv\Scripts\python -m ruff format --check src tests
.venv\Scripts\python -m pytest
```

日常迭代运行单文件，例如 `python -m pytest tests/test_search_failures.py`。主要 tests 通过真实 MCP session 做 discovery/tool calls，仅在 Tavily HTTP transport 边界提供 fixtures，并对收到的 body 断言参数继承与覆盖。错误矩阵与固定时钟测试使用 MockTransport；连接释放、持续 trickle、timeout 排队与恢复测试使用真实 loopback HTTP service，并在同一 session / HTTP client 尚未关闭时观察断连及后续 Search。另有启动 subprocess 和真实 `stdio` subprocess 测试。新增恢复测试不依赖内部 worker 数；dummy key、固定响应、缩短的内部测试期限均与真实 Tavily 账户隔离。

Windows 目标 client 为 MCP Inspector CLI 2.6.0（独立 Node client），transport 为真实 subprocess `stdio`。最新 [#15 Windows smoke 与父 spec 验收矩阵](docs/testing/issue15-windows-smoke.md) 覆盖最终 discovery、正常 batch、partial、全部失败、rate limit 和 timeout 展示，完整输出见 [issue15-smoke.json](docs/testing/issue15-smoke.json)。历史 [#13 单 query smoke](docs/testing/issue13-windows-smoke.md)、[#14 batch smoke](docs/testing/issue14-windows-smoke.md) 保留原证据。三者都是 contract smoke，不是 live Tavily Search；[#11 的历史 live evidence](https://github.com/EllisYuan/web_search/issues/11#issuecomment-5652708001) 单独记录，不因本次实施关闭或改变结论。

实现参考：[MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk/tree/v1.x)、[HTTPX timeout](https://www.python-httpx.org/advanced/timeouts/)、[HTTPX transport fixtures](https://www.python-httpx.org/advanced/transports/)。
