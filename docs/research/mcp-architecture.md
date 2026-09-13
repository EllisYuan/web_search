# Model-neutral Deep Web Search MCP 架构与 SDK 边界

> 对应 ticket：[调研 MCP 技术栈与 Deep Research 的架构边界](https://github.com/EllisYuan/web_search/issues/4)。  
> 事实核验日期：2026-09-08。本文只写架构结论与接口草案；未运行 tests，未调用收费 API，也没有把 preview、extension 或 host 行为当作普遍可用能力。

## 结论先行

MCP 应作为 **model-neutral 的检索与证据边界**，而不是默认承载一个隐式 agent。建议的默认形态是 **hybrid = host-driven intelligence + server-controlled retrieval**：不是在 server 内置另一个 LLM agent，而是由 host 负责 research planning、query rewrite、冲突判断与 synthesis，server 负责受控抓取、规范化、证据定位、缓存和预算边界。

- MCP server 提供无 LLM 的 `search`、`read`、证据定位和资源读取；不保存 provider-specific prompt，不要求 server 自己拥有 LLM key。
- host/外部 agent 负责研究计划、查询改写、并行调用、冲突判断和最终综合，因此可以替换模型、模型厂商与 UI。
- 只有当 server 明确拥有领域政策、凭据、审计责任或固定工作流时，才把受限的 server-driven orchestration 放入 server；这时也应直接使用 provider API 或普通后端 job，不应新建在已 deprecated 的 MCP Sampling 上。

不能替用户在 host-driven、server-driven、hybrid 中作无条件选择：若目标是多个 host 和多模型复用，偏 host-driven；若必须保证领域流程、权限和输出一致，偏 server-driven；若需要共享检索缓存、长任务和审计，同时保留模型可替换性，选 hybrid，但 hybrid 的 intelligence 仍在 host，server 只拥有受控 retrieval/job 能力。

## 1. 当前 stable MCP 基线

官方当前 stable specification 是 **2026-07-28**；`draft` 与旧日期版本不能作为新实现的唯一依据。[版本索引](https://modelcontextprotocol.io/specification/2026-07-28/index.md)显示，2026 revision 改为每个 request 携带 `_meta.io.modelcontextprotocol/protocolVersion`、client capabilities 和可选 identity，不再依赖旧式 `initialize` handshake；实现双时代兼容时，应通过 `server/discover` 或现代 request 探测，而不是把某一个错误码硬编码成 SSE fallback。[Versioning](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning)

### Transport

- **stdio**：host 启动 subprocess；stdout 只能是逐行 JSON-RPC，日志写 stderr。适合本机、桌面 host 和开发环境；取消必须发送 `notifications/cancelled`。进程崩溃后 in-flight request 丢失，若要恢复必须依靠应用自己的 durable handle，而不是依靠连接状态。[stdio](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio)
- **Streamable HTTP**：单一 MCP endpoint，每个 JSON-RPC request/notification 独立 POST；request 的响应可以是单个 JSON，也可以是 request-scoped SSE。2026 revision 删除 GET stream、protocol-level session、`Mcp-Session-Id` 和 `Last-Event-ID` resumability；关闭 response SSE 本身就是取消。HTTP 客户端必须带 `MCP-Protocol-Version`、`Mcp-Method`，调用具体 tool/resource/prompt 时还要带 `Mcp-Name`，并校验 header 与 body 一致。server 必须校验 `Origin`，本机应绑定 localhost。[Streamable HTTP](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http)
- **legacy HTTP+SSE**：2024-11-05 的独立 SSE + POST endpoint 已自 2025-03-26 deprecated；新实现 SHOULD NOT 采用，只做兼容 adapter。不要把旧的 GET/SSE/session/resume 行为写进新的 Streamable HTTP 客户端。[Deprecated registry](https://modelcontextprotocol.io/specification/2026-07-28/deprecated)

### 能力与稳定性

- **Tools** 是 model-controlled；`inputSchema`、可选 `outputSchema` 和 `structuredContent` 是稳定核心。若有 structured output，仍 SHOULD 附带 serialized JSON 的 TextContent，兼容只理解文本的 host；`structuredContent` 与 provider 的 LLM structured output 不是同一件事。[Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)
- **Resources** 是 application-driven，适合暴露不可变 source snapshot、evidence ledger 和 run manifest；支持 `resources/list`、`resources/read`、templates、可选订阅，但不是所有 host/model 都会自动发现、展示或注入 resource context。大列表使用 opaque `nextCursor`，不得解析 cursor；MCP 的 pagination 只规范 `tools/list`、`resources/list`、`resources/templates/list`、`prompts/list` 等 list operation，并不会自动给自定义 `search` 结果分页。因此 `search` 必须自己定义 `cursor`/`next_cursor`，同时保留 `read` 的分页、section 参数或 `read_section` 降级路径。[Resources](https://modelcontextprotocol.io/specification/2026-07-28/server/resources)、[Pagination](https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/pagination)
- **Progress** 是 optional：client 在 request metadata 放唯一 `progressToken`，server MAY 发送递增的 `progress`/`total`/`message`。它不是完成保证，仍必须有总 timeout 和最大 wall-clock。[Progress](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/progress)
- **Cancellation** 是 optional、cooperative；server 可能已经完成，双方必须容忍 race。对所有 request 设置 per-request timeout，并始终设置 absolute maximum。[Cancellation](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/cancellation)
- **Tasks** 不是 core tool result 的普遍必备字段，而是 opt-in extension。它提供 durable `taskId`、`working`、`input_required`、`completed`、`failed`、`cancelled`，以及 `tasks/get`、`tasks/result`、`tasks/cancel`/input update 语义；取消仍是 cooperative。客户端支持必须由双方声明，host 支持会变化，因此 baseline 不能只返回 task。[Tasks extension](https://modelcontextprotocol.io/specification/2026-07-28/basic/utilities/tasks)
- **Sampling** 在 2026-07-28 已 deprecated；新实现 SHOULD NOT adopt，应直接集成 LLM provider API。它保留至少一个 lifecycle window 是为了迁移，不是 server-driven research 的默认依赖。[Sampling](https://modelcontextprotocol.io/specification/2026-07-28/client/sampling)、[Deprecated registry](https://modelcontextprotocol.io/specification/2026-07-28/deprecated)
- **Authorization** 是 optional；HTTP 实现若启用，应使用 Protected Resource Metadata、AS/OIDC discovery、PKCE、OAuth Resource Indicators，并校验 token audience，禁止 token passthrough。stdio 通常从 host environment 取 credential，不套 HTTP OAuth 流程。[Authorization](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization)

## 2. SDK 选择矩阵（截至核验日）

| 选项 | 已核验 release / package | 适合 | 主要边界 |
|---|---|---|---|
| Official Python SDK | `mcp` **v2.2.0**，2026-09-07；v1.30.0 仍是 v1 legacy line | 需要直接控制 protocol、transport、错误和 schemas 的 Python server/client | v2 移除了 `mcp.server.fastmcp.FastMCP`，高层入口是 `mcp.server.MCPServer`；v1 示例不可直接当 v2 API。v2.2.0 release 的 **Known gaps** 明确未实现 Tasks extension（SEP-2663）、DPoP（SEP-1932）和 `jwt-bearer` grant；因此 Python official SDK 不能把 Tasks 当作已支持候选能力，需用普通 tool/resource polling 或另行验证的实现。 [v2.2.0](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.2.0) |
| Standalone FastMCP | `fastmcp` **v4.0.3**，2026-09-05 | 想用 decorator、type hints、自动 schema、middleware/composition 的 Python 应用 | 它是 Prefect 维护的 framework，不等于 official SDK；FastMCP 4 依赖 `mcp>=2,<3`，但仍隐藏 protocol 层。需要 wire-level control 时用 official SDK。[release](https://github.com/PrefectHQ/fastmcp/releases/tag/v4.0.3)、[migration](https://gofastmcp.com/getting-started/upgrading/from-low-level-sdk-v1) |
| Official TypeScript SDK v1 | `@modelcontextprotocol/sdk` **1.30.0**，2026-07-27 | Node/edge host、原生 `fetch`、Zod schema、已知 v1 host 生态 | stable v1 文档仍以 Streamable HTTP 为主并保留 SSE fallback；使用 `zod` peer dependency。 [release](https://github.com/modelcontextprotocol/typescript-sdk/releases/tag/1.30.0) |
| TypeScript SDK v2 | `@modelcontextprotocol/*` **2.0.0** package tags，2026-07-27 | 明确愿意跟随 2026-07-28 wire、锁版本并做 conformance 的新项目 | release body 明确称为 **first beta release**，不是 alpha，也不是可假定兼容的 stable v2；package 拆为 `client`、`server`、`core` 等。[release](https://github.com/modelcontextprotocol/typescript-sdk/releases/tag/%40modelcontextprotocol/server%402.0.0) |

TypeScript v2 的成熟度信号不一致：Context7 索引的 main README 称 stable line，GitHub release metadata 为 `prerelease: false`，但 release body 仍明确写 first beta。不能只靠版本号或其中一条描述宣称已全面稳定；本报告按保守候选处理。Python 可评估锁定 `mcp==2.2.0`；TS 的 v1 `@modelcontextprotocol/sdk@1.30.0` 是 legacy 兼容候选，不代表已支持全部 2026 wire。选 TS v2 时需核实维护方状态并做目标 host matrix；这不是已经完成兼容验证的 production lock。

Python 的 **Pydantic + asyncio** 适合后端数据清洗、类型模型和同步/异步 I/O；检索层可选并锁定 `httpx`。Official Python SDK 内部可能使用 `httpx2`，这是 SDK 依赖边界，不应与应用层无解释地混用；应按目标 SDK 的 dependency lock 与兼容矩阵决定是否统一版本。TypeScript 的 **Zod + fetch** 适合 Node/edge/browser 共享 schema、流式 HTTP 和 host 集成。性能差异通常小于 upstream web latency，决定因素应是部署 runtime、团队类型系统、OAuth/streaming 依赖和目标 host，而不是语言偏好。不要默认加入 LangChain、LangGraph 或 vector DB；它们只有在评测显示需要复杂 workflow、图状态或高规模语义召回时才引入。

SDK API 的“存在”也不等于“host 可用”：同一 feature 可能已经出现在某个 SDK 的 helper、beta package 或 extension 中，但目标 host 没有声明 capability。实现时应把 protocol core、SDK stable API、SDK beta/experimental helper、host extension 四层分别记录；依赖清单和设计文档写清楚哪一层是硬依赖。尤其不要因为 TypeScript v2 已有 package tag，或某个 FastMCP extra 提供 tasks，就把 Tasks、Sampling 或 v2 wire 当成跨 host 的共同最小公分母。版本升级前重新核对 release notes、spec changelog 和目标 host 的实际 capability；不能只依赖缓存文档或包管理器的 latest 标签，也不能把编译通过当作跨 host 互操作已经成立；最终仍要用真实 host 做最小回归，并保存失败样例，作为后续回归基线，与版本变更一起维护。

## 3. 三种 research 架构

| 架构 | 控制面 | 优点 | 风险 / 适用条件 |
|---|---|---|---|
| Host-driven | host 规划、调用 `search/read`、综合 | model-neutral；预算、审批、模型替换和 UI 都在 host；server 无 LLM key | 各 host 需要重复 orchestration；host 不支持 tasks/resources 时需降级。适合通用 MCP 与多模型产品。 |
| Server-driven | server 内置 planner、抓取、综合 | 领域 policy、credential、缓存和审计一致；客户只接一个 workflow | provider/prompt/model coupling；server 成为 agent runtime；页面 prompt injection 影响更大；Sampling 已 deprecated。只在 server 真正拥有领域责任、固定 workflow 和可审计预算时采用。 |
| Hybrid | server 做受控 fan-out/job，host 做计划与最终综合 | 共享 cache、证据 ledger、长任务和权限；仍保持 model-neutral | 需要明确边界、run state 和版本化 schema；tasks 兼容性不稳定。默认推荐。 |

因此建议首版：`search` 与 `read` 保持无 LLM 且可单独评测；支持分页，但不宣称天然幂等。重复调用可能遇到网页变化、不同 upstream 结果或重复计费；`idempotency_key` 也不能保证第三方不执行或不计费。host 通过多次调用建立 evidence；昂贵 fan-out 作为可选 `research_start`，只有协商到 Tasks 且当前实现确实支持 Tasks 时才返回 task 形态，否则同步返回 bounded partial result。server 可以提供 deterministic rerank、canonicalization 和 content extraction，但不要把“最终可信度”伪装成模型事实。

### 架构边界的具体判据

把“检索事实”和“研究判断”分开。server 可以决定 HTTP retry、robots 遵守、canonical URL、去重、正文抽取、字符/字节上限和证据位置；这些决策可复现，也不要求模型。host 才决定问题拆解、是否继续追查、哪些来源足以回答、如何处理相互矛盾的 evidence，以及最终回答的语气。这样同一组 evidence 可以被不同 provider、不同 UI 或人工 reviewer 重用。

如果 server 自带 planner，它必须把 planner 的输入输出当作版本化应用协议，而不是隐藏在 tool description 里的 prompt。至少要记录 `planner_version`、`model_hint`、`query_plan_hash`、`source_policy_version` 和每次调用的预算消耗；否则同一个 `run_id` 无法复盘。server-driven 还要承担更高的 prompt-injection 责任：网页中的指令只能进入不可信 content channel，不能改变系统规则、可访问 domain、token 或预算。

三种形态的成本边界也不同。host-driven 的 LLM cost 由 host 统一计量，server 只计 upstream fetch；server-driven 要把 planner、synthesis、重试和并发都纳入 server billing，且必须能在每个 upstream call 前拒绝超预算；hybrid 需要把两边的 `budget_ref`、request id 和 usage 汇总到同一个 run ledger。没有统一 ledger 时，“低成本”只能是猜测，不能作为选型依据。

### 工具与资源的职责

不要把一个名为 `deep_research` 的大工具暴露成黑盒：模型无法知道它何时会发出多少请求、怎样收费、哪些证据被舍弃，也难以取消或重试。首版工具应能单独评测和缓存。`search` 只发现候选来源，`read` 只读取并规范化指定来源；evidence extraction 可以由 host 基于 `read` 返回的 offset 完成。若确实需要 server-side fan-out，另设 `research_start`，输出 run/task 状态而非直接伪装成一条同步答案。

把大文本优先放在 resource，而不是塞进 tool result：tool 返回摘要元数据、`source_id`、`snapshot_uri` 和有限 preview；支持 resources 的 host 需要全文时调用 `resources/read`。但 resources 不是所有 host/model 自动可用，所以 `read` 必须保留 `cursor`/section 的 tool fallback，必要时提供 `read_section`。这同时降低上下文消耗、允许 content hash 去重，并让资源权限、缓存 TTL 和变更订阅有明确位置。`structuredContent` 用于机器消费，TextContent 用于兼容和人类可读性，二者必须来自同一份结果，不能各自生成导致引用漂移。

## 4. 小工具表面与 schema 草案

字段保持英文，以便 JSON Schema、Python Pydantic、TypeScript Zod 共用。

```text
search(input):
  { query, domains?, recency_days?, language?, page_size?, cursor?, budget_ref? }
  -> { run_id, results[], next_cursor?, partial, warnings[] }

read(input):
  { url, run_id?, section_hint?, cursor?, page_size?, max_bytes?, max_chars? }
  -> { source, content, content_hash, retrieved_at, truncated, next_cursor?, warnings[] }

read_section(input) [可选降级工具]:
  { source_id, section_hint, cursor?, page_size?, max_chars? }
  -> { source, section, content, locator, next_cursor?, warnings[] }

research_start(input):
  { question, constraints?, budget, output_mode: "evidence_only", idempotency_key }
  -> { run_id, task_id?, status, next_poll_ms?, budget_snapshot }
```

推荐的 `SourceRecord`：

```text
{ source_id, url, canonical_url, title, publisher?, published_at?, retrieved_at,
  content_hash, mime_type, http_status, language?, extraction_method,
  robots_or_access_notes?, snapshot_uri }
```

推荐的 `Evidence`：

```text
{ evidence_id, source_id, claim, quote, locator,
  support: "supports" | "contradicts" | "context",
  retrieved_at, content_hash, source_reliability_notes? }
```

`locator` 必须是可复核位置：HTML normalized text 的 `start_char/end_char`、PDF 的 `page_number` + offset，或稳定 section heading；不能只给“第 3 段”。`claim` 是待支持的短断言，`quote` 原样保留，`canonical_url` 与 `content_hash` 用于去重和后续审计。最终回答引用 `evidence_id`，不能只引用模型生成的裸 URL。

schema 需要明确哪些值是 server 事实、哪些值是估算：`retrieved_at`、`http_status`、`content_hash`、`locator` 是 server 事实；`source_reliability_notes` 只是提示，不是可信度分数；`claim` 与 `support` 若由 host model 生成，应标记 `extraction_method` 或 `created_by`，不能让下游误认为 server 已验证。对跨源冲突，保留多条 `Evidence`，不要在 server 侧悄悄合并成一个“最佳答案”。

`cursor` 必须原样透传并视为 opaque；分页请求应在同一 `run_id` 和同一查询约束下继续，查询约束变化就创建新 cursor。`page_size` 只能是 hint，server 仍可按 upstream 限制返回更小页。结果中有 `partial: true` 时必须同时给出 `warnings` 与已消耗的预算；不能让空的 `next_cursor` 与“没有更多结果”混淆。

`Budget` 不是 MCP 标准字段，必须由 host/server 实际执行：

```text
{ deadline_ms, max_tool_calls, max_pages, max_bytes, max_concurrency,
  max_retries, max_output_tokens?, max_cost_usd? }
```

`max_cost_usd` 只有在 provider/search billing 可观测并能原子计数时才宣称 hard cap；在每次 upstream call 前预留额度，超过即停止新调用并返回 `budget_exceeded`，事后用真实 usage 对账。LLM prompt 中写“请省钱”不是限制。所有预算都要返回 `budget_snapshot`（reserved、used、remaining、estimated），避免把估算当账单。

## 5. 可恢复任务、错误与安全

每个 run 保存 `run_id`、schema version、query plan hash、source/evidence ledger、budget counter 和 per-call idempotency key。若使用 Tasks，持久化 `task_id` 与最后状态，按 `pollIntervalMs` backoff；断线后用同一 ID 继续 `tasks/get`。若 host 不支持 Tasks，不能返回 host 无法解释的异步句柄，应在 deadline 内返回 partial result 或明确 `unsupported_capability`。

错误应区分 JSON-RPC protocol error 与 tool result 的 `isError: true`。建议应用错误状态：`invalid_request`、`unauthorized`、`forbidden`、`rate_limited`、`upstream_timeout`、`content_unavailable`、`parse_failed`、`budget_exceeded`、`cancelled`、`partial`。只有 transient network/429/5xx 可有限 retry；`invalid_request`、`forbidden`、SSRF/robots 拒绝不可盲重试。`partial` 必须保留已经取得的 evidence，不以空答案覆盖。

错误响应还应带 `retryable`、`retry_after_ms?`、`request_id`、`source_id?` 和 `budget_snapshot`，但不要把这些应用字段冒充 JSON-RPC error code。对于 `read`，应区分“URL 不存在”“响应被策略拒绝”“正文抽取为空”“内容被截断”；对于 `research_start`，应区分“任务已创建但暂未完成”和“任务根本未创建”。幂等键只绑定真正创建外部 job 的操作；重复 `search/read` 应通过 canonical URL、content hash 和 cache policy 去重，而不是依赖模型记忆。

Web content 一律是不可信输入：隔离 page text 与 system/tool instruction，禁止页面内容改变 tool policy；限制 URL scheme、redirect、DNS rebinding、内网地址、response size 和 content type。Streamable HTTP 校验 `Origin`；OAuth token 必须 audience-bound，不能把 host token passthrough 给上游。敏感 tool 仍需 host UI 的确认，MCP tool annotations 不能代替信任判断。

Host compatibility 也要作为运行时能力探测，而不是安装时假设。连接后记录 server 支持的 protocol version、transport、tools/resources 能力与 extension；若没有 `structuredContent`、progress 或 Tasks，客户端应退回 TextContent、同步 bounded call 或明确 partial，而不是把不完整能力包装成成功。官方 extension matrix 本身是 community-maintained，不能替代目标 host 的 smoke/conformance 测试。

## 6. 评测矩阵与衡量方式

用同一 query seed、source allowlist、model、预算和 host adapter 对三种架构做 A/B；不凭直觉声称某种更快或更便宜。

| 维度 | 指标 |
|---|---|
| Evidence quality | claim-level citation precision/recall、quote locator 可复核率、unsupported-claim rate、冲突发现率 |
| Reliability | successful completion、partial/failed/cancelled 比例、retry rate、HTTP/parse error 分布、任务恢复成功率 |
| Latency | first-result latency、tool p50/p95、end-to-end p50/p95、fan-out concurrency、time-to-final |
| Cost / budget | provider/search 实际 cost per completed task、input/output tokens、bytes/pages、预算 overshoot（目标为 0）、cache hit rate |
| Compatibility | stdio/Streamable HTTP、v1 legacy fallback、structuredContent、resources/pagination、progress/cancel、Tasks opt-in 的 host pass rate |
| Safety | prompt-injection escape、SSRF block、auth audience failure、PII/token leakage、用户拒绝后的停止率 |

最低 acceptance gate：引用必须能回到 snapshot locator；hard cap 不得超支；取消后不能继续发送新请求；断线后 run 不产生重复 evidence；不支持 extension 的 host 仍能完成同步 baseline。事实查找、跨源冲突、长页面/JS 页面、限流和断线恢复应分别成 workload bucket。

评测顺序建议分三层。第一层是 protocol conformance：验证 stdout 无杂讯、Streamable HTTP headers、JSON Schema、cursor、错误分类、取消和超时；这一层不需要 LLM。第二层是 retrieval quality：用人工标注的 source set 测 candidate recall、正文抽取、locator 稳定性、重复率和跨源冲突保留。第三层才比较 research architecture：固定同一批 sources、同一模型和相同 hard budget，测最终答案的 citation precision、unsupported claim 和 cost per completed task。把 tool latency 与 model latency 分开记录，否则会把 planner 差异误判成 HTTP 性能。

建议分阶段交付：先完成 `search`/`read` + evidence schema + 同步 partial；再加 resources 与 cache；最后根据真实长任务比例加入 Tasks adapter。每一阶段都保留无 extension 的 fallback。不要先建 vector DB 或多 agent graph：只有当 source 数量、重复查询命中率或跨轮语义召回的实测瓶颈明确，才增加索引和 orchestration 基础设施。

## 条件式路线建议

- **先做通用 server / 多 host**：优先 official SDK，Python 用 `mcp==2.2.0`；本机优先 stdio，远程才用 Streamable HTTP；保留 legacy adapter，不把 HTTP+SSE 当新协议。
- **Python 应用重视开发速度**：可选 standalone `fastmcp==4.0.3`；接受其 framework abstraction，并把 `mcp` 版本锁在兼容范围。需要精确 wire、错误或 transport 行为时回到 official SDK。
- **Node/edge/browser 或现有 TS host**：使用 stable v1 `@modelcontextprotocol/sdk@1.30.0`。只有已准备 2026 wire、package split、conformance 和 host 升级时，才试用 v2.0.0 beta。
- **长任务**：先设计自有 durable run state；Tasks 作为 capability-gated 优化，而不是唯一 API。**Server-driven synthesis** 只在领域 policy、凭据、审计和 hard budget 都属于 server 时采用；否则保持 host-driven/hybrid。

## 一手来源与版本核验

- MCP stable 2026-07-28：[spec index](https://modelcontextprotocol.io/specification/2026-07-28/index.md)、[transports](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http)、[tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)、[resources](https://modelcontextprotocol.io/specification/2026-07-28/server/resources)、[progress](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/progress)、[cancellation](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/cancellation)、[tasks](https://modelcontextprotocol.io/specification/2026-07-28/basic/utilities/tasks)、[sampling](https://modelcontextprotocol.io/specification/2026-07-28/client/sampling)、[authorization](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization)、[deprecated registry](https://modelcontextprotocol.io/specification/2026-07-28/deprecated)。
- Official Python SDK：[v2.2.0 release](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.2.0)、[v1.30.0 release](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v1.30.0)、[Python docs](https://py.sdk.modelcontextprotocol.io/)。
- Official TypeScript SDK：[v1.30.0 release](https://github.com/modelcontextprotocol/typescript-sdk/releases/tag/1.30.0)、[v2.0.0 beta release](https://github.com/modelcontextprotocol/typescript-sdk/releases/tag/%40modelcontextprotocol/server%402.0.0)、[v1 docs](https://ts.sdk.modelcontextprotocol.io/)。
- Standalone FastMCP：[v4.0.3 release](https://github.com/PrefectHQ/fastmcp/releases/tag/v4.0.3)、[SDK v1 migration](https://gofastmcp.com/getting-started/upgrading/from-mcp-sdk-v1)、[low-level SDK relation](https://gofastmcp.com/getting-started/upgrading/from-low-level-sdk-v1)。
- Host compatibility：[official extension support matrix](https://modelcontextprotocol.io/extensions/client-matrix)。该矩阵由 community 维护，且 extension 支持不能推导出 core feature 支持；Tasks 页面也明确要求 client/server opt-in。
