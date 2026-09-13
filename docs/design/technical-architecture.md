---
title: Web Search MCP 技术架构决策与设计文档
status: consolidated-reference
consolidated_on: 2026-09-11
supersedes: none
---

# Web Search MCP 技术架构决策与设计文档

## 0. 文档定位

这份文档做一件事：把散落在 `docs/adr/`、`docs/design/`、`docs/research/`、GitHub Issues 和两个 prototype branch 里的业务背景、架构选择、实现方案和决策依据，汇总成一份可以从头读到尾理解整个项目的技术文档。

它**不**做另一件事：它不批准任何新决策，也不把 proposed 设计升级为 accepted contract。本文档中的每一段内容都标注了状态，并在可能的地方指回原始来源；当原始文档更新时，本文档需要跟着更新，而不是成为脱离原始决策记录的第二真相来源。

### 0.1 状态标注约定

沿用项目已有的证据纪律，本文档中的每个结论都属于以下四类之一：

| 标注 | 含义 | 可以做什么 |
|---|---|---|
| **Accepted** | 已经过用户在 grill-with-docs 会话或 issue 评论中逐项确认，并落入某个 status: accepted 的 ADR | 可以当作实现的硬约束 |
| **Proposed** | 已完成一手资料研究和独立 adversarial verification，写入 `docs/design/` 的具体机制、字段或数值 | 可以作为下一步实现的起点，但需要在 contract review 后才能转正 |
| **Prototype evidence** | 来自 `prototype/free-search` 或 `prototype/cpu-web-read` 分支的真实运行观测 | 可以证明"某条路径能跑通"或"某类失败会发生"，不能外推成性能 SLA 或质量 benchmark |
| **Open** | 已识别但尚未验证的问题 | 不能默认往任何方向假设答案 |

### 0.2 与既有文档的关系

本文档是索引与综合，不是替代品。完整的一手依据、JSON schema 示例、primary source ledger 仍以下列文件为准：

| 领域 | Accepted 决策 | Proposed 设计 | 一手研究 | Prototype 证据 |
|---|---|---|---|---|
| 产品边界 | [ADR-0001~0004](../adr/) | — | — | — |
| Search | ADR-0004 | [research-source-strategy.md](research-source-strategy.md) | [research-source-strategy.md](../research/research-source-strategy.md) | [free-search REPORT.md](../../prototypes/free-search/REPORT.md)、[失败传播博客](../blog/searxng-vs-ddgs-failure-propagation.md) |
| Web Read / Progressive Disclosure | ADR-0004 | [progressive-disclosure.md](progressive-disclosure.md) | [progressive-disclosure.md](../research/progressive-disclosure.md) | `prototype/cpu-web-read` @ `4c210d1`（[#7 resolution](https://github.com/EllisYuan/web_search/issues/7#issuecomment-5599723724)） |
| MCP 协议边界 | — | — | [mcp-architecture.md](../research/mcp-architecture.md) | — |
| 内容抽取与 evidence 路线 | — | — | [retrieval-evidence.md](../research/retrieval-evidence.md) | — |

---

## 1. 业务背景

### 1.1 问题陈述

这个项目要解决的问题很具体：**给一个 Deep Search agent 提供联网检索与网页读取的能力，但不能用付费 API，不能假装网页读取比实际更完整，也不能让 MCP server 悄悄替 agent 做研究规划。**

背景是这样的：市面上不缺"能联网搜索"的方案——无论是付费 Search API，还是把 Search、抓取、摘要、综合全部塞进一个工具调用的 hosted 服务。但这类方案通常把三件事焊在一起：*发现候选来源*、*读取候选来源的正文*、*判断这些来源是否足以支撑一个结论*。焊在一起的代价是：agent 拿到的是别人已经嚼过的结论，而不是可以自己核实的证据；一旦这个黑盒判断错了，agent 没有办法看见错在哪一步。

因此本项目从一开始就把边界画在"证据获取"和"研究判断"之间：MCP server 负责把这两件事做扎实、做诚实、做可审计；agent 负责决定研究什么问题、读哪些来源、什么时候算研究够了。

### 1.2 目标用户与使用场景

- **首要用户**：项目作者本人的 Deep Search agent 工作流。这不是一个面向多租户的产品，首版也不考虑陌生用户的使用体验或计费。
- **集成测试入口**：Claude Code。MCP 是通用协议，Claude Code 在这里只是验证 transport、协议版本和能力协商能否落地的测试对象，不是产品绑定的目标平台——[mcp-architecture.md](../research/mcp-architecture.md) 的研究已经确认，同一份 MCP 协议在不同 host 上的扩展能力和运行限制并不相同，因此不能把"能在 Claude Code 里跑"直接等同于"协议实现完整"。
- **运行环境**：Windows 本机开发部署；后续计划发布到服务器，但服务器形态和资源预算尚未确定（Accepted，ADR-0002）。
- **使用场景**：覆盖一个或多个研究问题，目标是多个独立网站的信息覆盖，而不是"调用了多少个搜索引擎"（Accepted，见 CONTEXT.md 中 **Source** 的定义）。

### 1.3 核心价值主张

如果只看"能不能联网搜索"，这个项目没有任何差异化——免费的 SearXNG、DDGS 已经能做到。真正的价值主张在三件事上：

1. **对失败诚实，而不是对成功率乐观。** `web_search` 的首要承诺是可解释失败，而不是始终返回结果（Accepted，ADR-0004）。这不是一句口号：[免费 Search prototype 的实测](../../prototypes/free-search/REPORT.md)已经证明，"HTTP 200"这个信号本身可能什么都不代表——SearXNG 在 Brave 被限流时返回的正是本地 HTTP 200，业务失败被压缩进了 JSON 里的一个字符串（见第 6 节和[失败传播博客](../blog/searxng-vs-ddgs-failure-propagation.md)的详细分析）。一个诚实的系统必须把这种情况和真正的成功区分开。
2. **把"发现"和"读懂"拆成两个正交、可独立验证的能力。** `web_search` 只做候选 URL 与 SERP metadata 的发现，不读正文，不生成综合答案；`web_read` 独立读取 caller 提供的任意 URL，不要求来自 `web_search`（Accepted，ADR-0001/0004）。这个边界让两个子系统可以分别测试、分别演进，也让 agent 能在不调用 Search 的情况下直接读取一个已知 URL。
3. **Progressive Disclosure 作为项目的核心亮点。** 这不是简单的分页，而是让 agent 在同一份可复核的证据表示（representation）上，逐步获得刚好足以做出下一步判断的原文、定位和上下文——第 5 节详细展开这个设计。

### 1.4 明确的非目标

以下内容被明确排除在首版范围之外，理由已记录在对应 ADR 或研究文档中：

- **不做 server-side `deep_search` facade。** Deep Research 的 planning、query 选择、source 选择、冲突判断和最终综合，全部由 caller agent 负责；MCP 只提供可组合的 `web_search` 与 `web_read`（Accepted，ADR-0001）。这个边界在 2026-09-10 被再次确认：即使用户要求"具体的深度搜索方案"，方案也是 agent 侧的策略，而不是新增一个 tool。
- **不依赖付费 API 或 GPU。** 自建组件必须开源，允许使用公开搜索引擎和本机资源；CPU 即可运行（Accepted，ADR-0002）。
- **不在 MCP 层做 query 脱敏或内容改写。** query 内容是否适合外发，由调用方模型负责；MCP 只做基本入参校验（Accepted，ADR-0003）。
- **不用模型生成摘要代替原文抽取。** `web_read` 的 v1 baseline 是 deterministic structured extraction，不调用 LLM 做抽取、reordering、摘要或来源质量判断（Proposed，[progressive-disclosure.md](progressive-disclosure.md) §10.1）。
- **不自建全网索引，不绕过登录、paywall、CAPTCHA 或网站访问控制。**

---

## 2. 领域语言

完整术语表见 [CONTEXT.md](../../CONTEXT.md)；这里给出简要案例帮助理解边界。

**Search**（`web_search`）：为 query 获取并整合候选 URL 的操作，结果包含用于选择来源的相关信息，不包含目标网页的正文读取。*例子：给定 query "SearXNG JSON API 配置"，Search 返回若干 URL + title + snippet，不返回这些页面的完整正文。*

**Web Read**（`web_read`）：读取指定 URL 的正文并呈现为结构化 Markdown 的操作；URL 可以来自 Search，也可以由 agent 直接提供，长正文可通过渐进式披露继续读取。*例子：agent 已经知道某个 GitHub issue 的 URL，可以直接调用 `web_read`，完全不需要先调用 Search。*

**Search Batch**：一次提交的一组数量受限的 query，各 query 的搜索结果分别成组呈现，避免合并问题或混合结果集。

**Source**：agent 获取信息的来源网站；"多个来源"指多个独立网站的信息覆盖，不要求来自多个搜索引擎。*这是一个容易被误解的边界：SearXNG 聚合了 Google、Brave、DuckDuckGo 等 engine，但这只是查询路由的聚合，不构成来源独立性——十个搜索结果可能全部指向同一篇被转载的通稿。*

**Progressive Disclosure**：agent 逐步获取所需网页内容的交互方式，而非首次读取就接收全部内容。*这不是"分页"的同义词——第 5 节会说明为什么。*

**Deep Research**：agent 围绕研究问题循环搜索、评估信息并形成结论的过程；这个过程完全由 agent 拥有，MCP 不参与规划或综合。

---

## 3. 架构总览

### 3.1 架构定位：model-neutral 的检索与证据边界

[mcp-architecture.md](../research/mcp-architecture.md) 的研究比较了三种 MCP research 架构：

| 架构 | 控制面 | 本项目适用性 |
|---|---|---|
| Host-driven | host 规划、调用 `search`/`read`、综合；server 无 LLM key | 与本项目边界一致：server 不做 LLM 推理 |
| Server-driven | server 内置 planner、抓取、综合 | 与 ADR-0001 冲突：会把 Deep Research 规划塞进 server |
| Hybrid | server 做受控 fan-out/job，host 做计划与最终综合 | 本项目的 `web_search`/`web_read` 组合更接近 host-driven 一端的 hybrid：server 只提供受控的检索原语，不做 fan-out 编排 |

本项目的选择落在 **host-driven** 这一端：MCP server 提供无 LLM 的 `search`、`read`；host（即 caller agent）负责研究计划、查询改写、并行调用、冲突判断和最终综合。这个选择的直接后果是：server 不保存 provider-specific prompt，不要求自己拥有 LLM key，因此模型、模型厂商和 UI 都可以在不改动 server 的情况下替换。

### 3.2 职责分离：三个层次

```text
research question (caller agent)
  -> claim / facet map (caller agent)
  -> web_search: bounded candidate discovery (server)
  -> candidate triage + provenance hypothesis (caller agent)
  -> web_read: bounded, evidence-preserving read (server)
  -> evidence matrix update (caller agent)
  -> gap / counterevidence / stop decision (caller agent)
```

这个循环里，server 只出现在两处：`web_search` 返回候选 URL 与 SERP metadata；`web_read` 返回指定 URL 的结构化正文与证据定位。**server 不知道研究是否完成**——它只能返回 candidate、metadata、capability mismatch、upstream state 和 partial failure。研究是否足够，完全由 caller agent 依据 claim 级别的证据判断。

这个边界要防止三种具体的误报（Proposed，[research-source-strategy.md 设计](research-source-strategy.md) §2）：

1. SERP snippet 被当成正文或方法证据；
2. SearXNG 的 `score` 被当成 relevance、authority 或 truth；
3. 多个域名或同一条被转载的报道被当成 independent corroboration（独立佐证）。

### 3.3 系统组件图

```text
┌─────────────────────────────────────────────────────────────┐
│                     Caller Agent (host)                     │
│   claim/facet planning · query strategy · evidence matrix   │
│   source-role judgment · counterevidence · stop/continue    │
└───────────────┬───────────────────────────┬─────────────────┘
                │ web_search(query, ...)     │ web_read(url, action, ...)
                ▼                            ▼
┌───────────────────────────┐   ┌────────────────────────────────┐
│   web_search (MCP tool)   │   │      web_read (MCP tool)        │
│  route/backend explicit   │   │  policy/acquisition             │
│  bounded Search Batch     │   │  source snapshot                │
│  no body read, no rank    │   │  extraction representation      │
│  = truth score            │   │  structural IR + navigation     │
└──────────────┬────────────┘   │  bounded view + context closure │
               │                │  continuation / citation        │
               ▼                └───────────────┬──────────────────┘
    ┌─────────────────────┐                     │
    │ SearXNG (self-host)  │        ┌────────────┴─────────────────┐
    │ route=searxng         │        │  Trafilatura / Playwright /   │
    │ backend=google only   │        │  pypdfium2 / RapidOCR+ONNX    │
    │ (v1)                  │        │  Runtime CPU (baseline)       │
    └─────────────────────┘        └───────────────────────────────┘
```

两个 tool 各自向下依赖一组免费开源组件；两者在 MCP 层完全解耦——`web_read` 不要求输入来自 `web_search`。

### 3.4 MCP 协议层的具体约束

以下事实来自 [mcp-architecture.md](../research/mcp-architecture.md) 对 2026-07-28 stable spec 的核验，决定了本项目 tool 设计的若干边界：

- **Sampling 已 deprecated**：新实现不应依赖它做 server-driven research，这进一步支持"server 不内置 LLM"的选择。
- **Tasks 是 opt-in extension，不是核心能力**：不能假设所有 host 都支持异步任务句柄，因此 `web_read` 的操作被设计为同步、有界（见第 5.4 节的 `advance` 机制），而不是依赖后台 job。
- **Resources 是 application-driven，不是所有 host 的最低能力**：因此 `web_read` 必须能在纯 tool result 上完整工作，Resources 只能是可选的传输优化（Proposed，[progressive-disclosure.md 设计](progressive-disclosure.md) §11）。
- **Pagination 的 cursor 是 opaque，由 server 决定 page size**：这个语义被借鉴到 `web_read` 的 `next_cursor` 设计，但标准 pagination 只覆盖 `list` 类操作，不会自动定义 `tools/call` 正文的续读，因此 `next_cursor`/`processing_continuation` 是本项目自定义的应用层协议，不是协议规定。

---

## 4. Web Search 子系统设计

### 4.1 已确认的职责边界（Accepted，ADR-0004）

- `web_search` 的首要承诺是**可解释失败**，而不是始终返回结果。
- route / backend 由调用方显式选择，server **不做隐式 fallback**。
- v1 先实现 SearXNG / Google，且只启用 Google engine；不在一次请求内混合多个 upstream engine。
- 返回候选 URL 与 SERP metadata（包括 title、snippet、rank、upstream 状态），**不自动读取正文**，也不生成综合答案。
- batch 逐 query 返回独立结果；部分成功时保留已完成项，并在顶层标记 `partial`。
- **默认不 retry**。调用方若需重试，应发起新的可审计 attempt。
- health 只在请求内检查；process 或 container 存活不能作为 HTTP service 可用的证明。

### 4.2 为什么"发现"不是"URL 数量"：Search 策略的研究结论

[research-source-strategy.md](../research/research-source-strategy.md) 的核心结论是：**Source 是否充分是 claim 级别的闭合问题，不是 URL 数量问题**。一份 report 是否有足够 Source，取决于每个 material claim 是否有匹配的直接证据、可追溯的 provenance、恰当的来源角色（primary-record / primary-data / primary-method / independent-replication / methodological-synthesis / commentary / counterevidence）、主动的反证，以及已披露的时效性、语言/地区和模态缺口。

这个结论直接排除了一种直觉性的做法：**不建议在 v1 定义"每个 claim 至少 N 个 URL"或"每个 report 至少 M 个 domain"**（Proposed）。原因很实际：一份权威法律文本可能足以确认"文本写了什么"，但不能确认"政策效果"；十个被转载的页面可能只对应一个 provenance cluster。固定数字只会制造虚假的完成感。

因此 v1 的 Search 设计把"具体深度搜索方案"落在 **agent-owned 的 claim 驱动策略**上，而不是 server 侧的自动扩展：

```text
research question
  -> caller claim/facet map
  -> query families (definition_primary / direct_evidence / counterevidence /
     independent_corroboration / version_recency / language_geography /
     modality / operational_failure)
  -> bounded Google-only Search Batch
  -> candidate triage + provenance hypotheses
  -> standalone web_read for pivotal sources
  -> evidence matrix update
  -> gap/contrary/version/language/modality loop
  -> caller-owned stop with explicit gaps
```

Search server 全程只做候选发现；query family 的规划语言（`claim_id`、`facet_id`、`evidence_goal` 等）是 caller-only 的 planning metadata，server 只透传回显，不解析、不据此改写 query（Proposed）。

### 4.3 Observation 模型：为什么"HTTP 200"不够用

这是本项目从 prototype 实测中学到的最重要的教训。[失败传播博客](../blog/searxng-vs-ddgs-failure-propagation.md)记录了一个具体案例：同一个上游 Brave 被限流，DDGS route 拿到的是原始 HTTP 429，SearXNG route 拿到的却是本地 HTTP 200，业务失败被压缩进 JSON 里的 `unresponsive_engines` 字符串。如果 adapter 只检查 HTTP status code，这次真实的限流会被记成一次成功的空结果。

据此，Search 响应的 `observation` 字段被设计成三层，每层只记录**该层实际观察到的事实**（Proposed）：

```text
observation = {
  instance: {          # 本地 SearXNG instance 的 transport/HTTP 观测
    transport_status: ok | timeout | transport_error | format_disabled,
    instance_http_status: <adapter 实际收到的状态码>
  },
  engine: {             # 从 unresponsive_engines 与解析结果分类得到的 engine state
    engine: "google",
    state: ok | empty_or_parse_failure | suspended_or_rate_limited |
           captcha_or_blocked | timeout | unknown_error,
    state_basis: <分类依据>
  },
  upstream: {           # 只有 instance 明确透传时才填写，否则 null
    upstream_http_status: null,
    upstream_request_id: null,
    evidence_status: not_observed
  },
  retry_performed: false
}
```

`instance_request_count` 与 `upstream_request_count` 也刻意分开：前者是 adapter 向本地 instance 发出的请求数，后者只有在 instance 日志或 trace 可观测时才能填写——server 默认不 retry 并不证明 upstream 只被访问了一次，instance 内部的 redirect 或 engine 内部重试都可能产生额外的 upstream 请求。

这套三层模型不是凭空设计的，而是直接对应 prototype 已经观察到的两类真实失败：本地 HTTP 200 伴随 engine suspension，以及 `RemoteDisconnected`（无 HTTP status 的 transport 失败）。schema 必须能诚实表达这两类情况，而不是把本地状态冒充成 upstream 状态。

### 4.4 Batch 语义

- 每个 query 有独立的 `query_id`、原始 query 文本、facet/family metadata 和独立 `status`；
- 一条 query 的 timeout 或 CAPTCHA 不影响其他 query 的结果；
- 顶层 `partial=true` 表示至少一条 query 未完整完成，不表示所有结果都不可用；
- caller 想重试时建立新的 `attempt_id`/`batch_id`，不覆盖原失败记录；
- page continuation 是 live SERP 的 best-effort，不是 immutable snapshot——SERP 排序会随时间、地区、个性化因素变化，`next_cursor` 必须是 opaque 的 continuation hint，不能承诺相同的 candidate set。

推荐的 pilot bounds（Proposed，需要通过 G2/G3 实验验证后才能定为 default）：

```text
pilot_bound_A: max_queries_per_batch=4, max_pages_per_query=1, max_results_per_query=10
pilot_bound_B: max_queries_per_batch=8, max_pages_per_query=2, max_results_per_query=20
```

### 4.5 URL identity 与 source grouping

RFC 3986 说明 URI equivalence 依赖应用语义，`rel=canonical` 只是 preferred URL 的 hint，不是 ownership proof。因此设计上保留三层 URL 表示（Proposed）：

1. `strict_key`：保守的 generic normalization，用于去重；
2. `semantic_key`：只有在站点规则有证据时才应用 query parameter 语义，默认保留全部 query 参数；
3. `observed_equivalence`：redirect chain、`rel=canonical`、内容 hash 等观察到的等价性证据。

`source_identity.independence_status` 的取值只能是 `unknown | tentative_related | tentative_same_publisher`——目前没有已验证的跨领域 provenance clustering 算法，`ownership_group_id` 只能是 hypothesis，不能伪装成确定性判断。

### 4.6 验证 gate（G1–G8）

以下每个 gate 只支持其测试范围内的 observation，不产生 universal SLA（Proposed 验证计划）：

| Gate | 内容 | 决策问题 |
|---|---|---|
| G1 | Google adapter capability matrix | schema 是否需要暴露 capability mismatch |
| G2 | Query family 策略 vs synonym-only baseline | facet loop 是否比单纯增加结果数带来可测增益 |
| G3 | Pagination drift（重复 attempt 观察 overlap/skip） | continuation 是否只能 best-effort |
| G4 | URL/source adversarial fixtures | 能否安全输出 tentative source group |
| G5 | Judged diversity pool | upstream order 或离线 rerank 是否改善 facet coverage |
| G6 | Access bias sampling（按类型/语言/地区记录失败分布） | coverage disclosure 最低字段规则 |
| G7 | Target MCP host conformance | schema/cursor 是否适合实际 host |
| G8 | License/dependency inventory | 免费开源约束是否满足 |

在 G2/G4/G6 完成前，不批准 universal source quota、独立性阈值或数值化 truth score；在 G3/G7 完成前，不把 `pageno` 或 opaque token 描述成 immutable cursor。

---

## 5. Web Read / Progressive Disclosure 子系统设计

### 5.1 设计论点：为什么不是"更多分页"

**Progressive Disclosure 的可行 differentiator 不是"返回更少 token"，而是让 caller agent 在同一份可复核的 source representation 上，逐步获得刚好足以做下一步判断的原文、定位、上下文和失败状态**（Proposed，[progressive-disclosure.md](../research/progressive-disclosure.md) §1.1）。

普通 pagination 只回答"下一段在哪里"；Progressive Disclosure 还要回答四个问题：当前看到的是什么 representation？这段内容为什么值得继续读？哪些限定条件必须一起读？继续读取是否仍针对同一份内容快照？这个设计假设目前只有间接证据支持（ReAct 的 observation loop、SWE-agent 的 interface shape、Lost in the Middle 的 context-position 效应），**没有直接的 research-agent A/B 实验证明它优于全文阅读或固定分段**——这是全部研究中最重要的未解决问题，第 9.1 节会详细说明。

### 5.2 四个必须分开的对象

这是整个设计的基石。一次网页读取表面上是一件事，实际上要拆成四个独立可能失败的环节（Proposed）：

1. **Capture（获取）**：是否取得了 response bytes、redirect hops、PDF/image payload 或 rendered DOM。
2. **Extraction coverage（抽取覆盖）**：在已获取的内容中，哪些 page、DOM region、table、figure 成功解析。
3. **Rendered output truncation（输出截断）**：本次响应因预算上限截止，但相同 representation 可能还有可继续读取的内容。
4. **Semantic adequacy（语义完整性）**：即使前三者都完整，reading order、table 重建、footnote 关联仍可能是推断而非确定。

一个具体的例子说明为什么这四层不能合并：一份 PDF 的 bytes 完全下载成功（capture=fetched），native text 抽取只覆盖了 10 页里的 7 页（extraction=partial），本次响应只返回了其中 2 页（output=complete，因为没有触及预算上限）。如果只用一个笼统的 `status` 字段，这三件事会互相掩盖。

### 5.3 核心数据模型

完整字段定义见 [progressive-disclosure.md 设计文档](progressive-disclosure.md) §4；这里给出概念摘要（Proposed，均需 contract review）：

```text
SourceSnapshot                       # 一次 retrieval 的不可变身份
  source_snapshot_id, requested_url, final_url, redirect_chain,
  retrieved_at, retrieval_status, raw_sha256, retention_class

  └── ExtractionRepresentation       # 每种抽取方式各自独立的版本化产物
        representation_id, source_snapshot_id, parent_representation_id,
        representation_kind: raw_bytes | static_dom | rendered_dom |
          pdf_native_text | pdf_layout | ocr_text | image_asset |
          normalized_text | markdown_projection
        extractor_name, extractor_version, extraction_config_hash,
        extraction_status, coverage, content_digest

        └── DocumentNode             # 结构化节点：heading/paragraph/table/figure/...
              node_id, kind, structural_path, source_locators, source_method

              └── Locator + Citation # 可复核的定位与引用
                    representation_id, kind, offset_unit, quote/position,
                    citation_id, rehydration_status
```

四个关键 invariant：

- raw bytes、rendered DOM、抽取文本、OCR 文本、Markdown 都是**不同的 representation**；抽取器或渲染配置一变，就是新 representation，不覆盖旧的。
- 一旦某个 representation 被某次 view 或 citation 引用过，就视为 **frozen（immutable）**：后续新的抽取只产生新的 child representation，不会原地修改或"长大"已发布的内容。
- `raw_sha256`（原始字节的身份摘要）与某个 representation 的 `content_digest`（抽取内容的摘要）是两个不同层级的东西，不能混成一个笼统的"hash"；即使 raw bytes 相同，也不能推断不同 extractor 配置会产生相同输出，这需要独立的 determinism test 验证。
- `node_id` 不跨 snapshot/representation 复用，也不能因为文本相同就发生 collision。

### 5.4 操作集与增量处理机制

`web_read` 的候选操作（Proposed，是否收敛为一个 `action` 字段或拆成多个 tool 尚未决定）：

- **`initial`**：与已确认的首读边界兼容——metadata + outline（若可得）+ 有限正文 + coverage/warnings。
- **`find`**：在已固定的 representation 上做 deterministic 精确匹配，返回原文命中、定位和 negative-result 的准确含义（"在已搜索的 representation 中未找到"，不是"来源中不存在"）。
- **`read`**：按 section/page/block/table/footnote/range 读取有界的结构化内容。
- **`expand`**：围绕命中做 context closure（见 5.5），不是无条件扩大全文。
- **`asset`**：把 image/page bytes 或 crop 交给 caller 的可选暴露方式——但图片获取与 OCR 覆盖本身是 accepted scope 的必需能力，不因为 `asset` 是可选操作就意味着 OCR 可以缺失。

**增量处理机制 `advance`** 是本设计对"增量 OCR"问题选定的唯一默认机制（Proposed）：一个同步、有界、由 caller 显式发起的动作，只对已经 capture 的 pages/regions 做新的有限抽取，**不是后台 job，不产生 queued 状态**。它和普通的 `next_cursor` 续读有本质区别：

```text
next_cursor          # 只读已发布内容，不触发任何新处理
processing_continuation  # 提示还有已 capture 但未处理的素材，需显式调用 advance
advance               # 对未处理素材做有限抽取，产生新的 child representation
```

`advance` 成功后返回一个新的 representation revision，其 `parent_representation_id` 指向旧 representation；旧的 cursor 和 citation **继续解析到旧 representation，不会被静默重定向**。当新旧内容的对齐关系无法确定性判断时，返回 `alignment_status: ambiguous` 并保留旧 citation，不能靠猜测把旧定位映射到新内容。

一个具体场景：一份 5 页的 mixed PDF，前 2 页有 native text，后 3 页是扫描图像。`initial` 首读只返回前 2 页的正文，并在响应中携带 `processing_continuation` 提示后 3 页尚未 OCR；caller 显式调用 `advance` 处理第 3–4 页后得到新的 representation，第 5 页仍留在 `pending_ranges` 里——它既不是缺失，也不是未命中，只是这次 `advance` 没有选择它。完整的四步交互序列见 [progressive-disclosure.md 设计](progressive-disclosure.md) §6.7。

### 5.5 Context Closure：确定性边界，不是语义完整性

`expand` 操作的能力边界必须明确说清楚：它**只能补齐结构或索引中可确定性找到的链接**——heading ancestry、table 的 caption/header/unit、通过 marker 显式关联的 footnote。它**不能**发现散落在正文别处、没有结构链接的限定语或语义例外（Proposed）。

每个补入的 context block 都携带 `closure_basis`，标注凭什么规则被补入；响应携带恒为 `unknown` 的 `semantic_completeness` 字段，提醒 caller：**空的 `unknown_context` 列表从不意味着语义完整**。这是一条克制而诚实的设计原则——与其让一个"看起来完整"的响应误导 agent，不如明确告诉它这只是规则能发现的部分。

### 5.6 三条独立状态轴

```text
capture_status:    fetched | partial_bytes | unavailable | policy_refused | failed
extraction_status: complete | partial | failed | unsupported
output_status:     complete | truncated
```

附加 `semantic_warnings`（`reading_order_inferred`、`ocr_approximate`、`figure_not_interpreted` 等）。这三条轴的分离直接对应第 5.2 节的四层拆分，是整个 schema 设计能否诚实表达失败的关键。

### 5.7 格式支持范围与组件选型策略

**首版内容支持范围（Accepted，ADR-0004 结合产品边界文档）**：静态 HTML、需要执行 JavaScript 的页面、PDF（含扫描件），以及 OCR 覆盖的扫描 PDF、网页文字图片和独立图片 URL。这个范围经过一次纠正——设计初期曾建议先只做静态 HTML、把 JS 和 PDF 推迟到后续版本，但这与已经确认的产品边界冲突，用户在 2026-09-10 明确要求不能因为技术实现方便而排除高价值来源，因此完整范围被恢复。

组件选型采用 **baseline-first** 策略（Proposed）：`prototype/cpu-web-read`（pinned commit `4c210d1`）已经在受限条件下跑通了 Trafilatura（static HTML）、Playwright/Chromium（JS 渲染）、pypdfium2（native PDF text）、RapidOCR + ONNX Runtime CPU（OCR）这一条覆盖全部必需格式的路径。后续实验的第一优先级是在同一 corpus 上**复现这条已验证路径**，而不是从候选列表里另选组件——"已经跑通"本身就是证据，不应无反证地被替换。只有在同一 corpus 上发现具体、可复现的缺陷时，才逐一评估 pypdf/PyMuPDF、Tesseract、Docling、PaddleOCR、Mozilla Readability 这些候选，且每次只针对暴露出问题的那类输入做对比，不做整体替换。

许可证是这套选型里必须单独审查的一环：PyMuPDF 是 AGPL/commercial 双许可，不能因为功能更强就默认采用；Docling 和 PaddleOCR 官方文档列出 Windows 支持，但不等于目标 Windows CPU-only 环境已经过验证。

### 5.8 安全边界

- **SSRF/DNS**：scheme allowlist 仅 `http`/`https`；解析全部 A/AAAA 记录并拒绝内网、link-local 地址；每个 redirect hop 重新校验。
- **Browser 隔离**：browser context 不继承 caller/host 的 cookies 或凭据；`route()` 只是拦截/观察 API，不是网络隔离边界。
- **Prompt injection**：页面正文、HTML comment、alt text、OCR 文本、PDF metadata 全部进入 untrusted data channel，不能修改 tool policy、query 隐私策略、credential、budget 或 retention 规则。
- **robots**：RFC 9309 明确 robots 规则不是访问授权（access authorization）；auth、paywall、CAPTCHA、anti-bot 的拒绝不能绕过。

### 5.9 验收 gate

以下 gate 必须全部通过，proposed 机制才能提交为 contract review（Proposed）：

1. 每个必需格式都有可运行的 acquisition/extraction route，并配有代表性的成功与失败 fixture——**只靠总是返回 `unsupported` 通过验收视为未满足此 gate**；
2. capture/extraction/output 三种状态可分别驱动恢复动作；
3. continuation 不做隐式重新抓取，状态绑定可审计；
4. 旧 citation 在 extractor 升级后仍指向旧 representation；
5. table/figure/footnote/reading-order 的局限有 locator/warning 可查；
6. target host 能消费 `structuredContent` 或兼容的 TextContent，不依赖 Resources picker；
7. Windows CPU clean-machine、license/model/dependency inventory 完成；
8. SSRF/access-control/raw-retention/prompt-injection 测试通过；
9. paired evaluation 在固定 quality floor 下显示净收益，或 Progressive route 被明确降级为可选模式；
10. 本文档中的任何数字或组件选择都没有被误写成已批准的产品决策。

---

## 6. 已有原型证据

### 6.1 免费 Search：两条 route 的失败形态对照

`prototype/free-search` 分支跑了一轮 smoke：2 条 route（DDGS、SearXNG）× 3 个 engine（Brave、DuckDuckGo、Google）× 6 个 query × 2 个窗口，共 72 次调用，另加 6 次时效补测，合计 78 次调用、458 条结果。**这是分钟级 smoke，不是 benchmark**，不能推出长期稳定性或跨天可用率。

最有价值的发现不是"哪条 route 更好"，而是**同一个上游的同一种失败，在两条 route 上呈现完全不同的可观测形态**：

| 观测事件 | DDGS route | SearXNG route |
|---|---|---|
| 上游 rate limit（Brave） | 原生 `status_code=429` | 本地 `status_code=200`，失败信息压缩进 JSON 的 `unresponsive_engines` |
| DuckDuckGo CAPTCHA | HTTP 202 + challenge HTML marker | 本地 HTTP 200 + `["duckduckgo", "CAPTCHA"]` |
| Google 无结果 | HTTP 200，5594 bytes，`upstream_parsed_results=[]`，归类为 `empty_or_parse_failure` | 核心窗口未观测到失败，但低频复测出现 `RemoteDisconnected`（无 HTTP status） |
| Container 生命周期 | 不适用 | `docker ps` 显示 `Up`，但 `/healthz` 连接后被意外关闭——**process 存活不等于 HTTP service 可用** |

六条 route/engine 组合的整体轮廓（不能用来排名，因为分钟级 latency 会把"实例快速拒绝"和"真正的性能优势"混在一起）：

| route / engine | 返回情况 | 主要失败形态 |
|---|---:|---|
| DDGS / Brave | 12/12 成功 | 补测中出现 1 次真实 429 |
| DDGS / DuckDuckGo | 3/12 成功 | 9 次 challenge |
| DDGS / Google | 7/12 成功 | 5 次 HTTP 200 但无可解析结果 |
| SearXNG / Brave | 7/12 成功 | 1 次 rate limit，随后 4 次 suspension |
| SearXNG / DuckDuckGo | 0/12 成功 | 12 次 JSON upstream failure，均为 CAPTCHA |
| SearXNG / Google | 12/12 成功 | 核心窗口无失败，低频复测另有 transport error |

这个证据直接催生了第 4.3 节的三层 observation 模型：如果不把 instance/engine/upstream 分开记录，"本地 200"这种信号会持续误导下游的成功率统计。

### 6.2 CPU-only Web Read：功能路径已验证，性能与真实互联网覆盖仍未验证

`prototype/cpu-web-read` 分支（pinned commit `4c210d1`，[#7 resolution](https://github.com/EllisYuan/web_search/issues/7#issuecomment-5599723724)）在用户授权的受限功能 smoke 条件下完成：

- 中英文的独立图片、扫描 PDF、网页文字图片均成功，CER=0（对受控 reference 而言），page/image locator 保留；
- 静态 HTML、JS 页面、text PDF 均成功；text layer 不重复 OCR，中文小页面使用透明 DOM fallback；
- 12 页扫描件的 Progressive Disclosure 首次 preview 约 2.37 秒（只处理第 1 页），全文完整处理约 17.6 秒；同参数的 eager（一次性处理全部）对照首次返回约 17.7 秒——**这是 Progressive Disclosure 能带来首次可用时间优势的第一手证据**；
- 混合 PDF 注入第 2 页的两次失败后，状态为 `partial`，第 1、3 页保留，failure locator 可见，`end_of_document=false`。

**这个证据的边界必须说清楚**：它证明的是候选 pipeline（RapidOCR + ONNX Runtime CPU-only、pypdfium2、Trafilatura、Playwright）在受控 fixture 上可以运行、Progressive Disclosure 的方向可以继续；它**不**证明真实互联网样本的 OCR 质量、生产环境资源预算、多栏/低清晰度/复杂表格的处理效果，也不是最终 tool schema 的验证。

### 6.3 这些证据回答了什么，还没回答什么

| 已经能回答 | 还需要时间序列复测或真实 corpus 才能回答 |
|---|---|
| 失败形态的分类：CAPTCHA / 429 / suspension / empty / transport closure | 跨天、跨时段的成功率 |
| 中间层（SearXNG）会不会改写 HTTP 语义 | suspension 到期后的恢复行为 |
| 候选 CPU-only pipeline 能否跑通全部必需格式 | 真实互联网样本的 OCR/抽取质量 |
| Progressive Disclosure 首次可用时间是否早于 eager 处理 | Progressive Disclosure 是否在固定 quality floor 下净优于全文阅读（尚无 research-agent A/B） |

---

## 7. 决策记录汇总

以下按 Decision Record 格式重述四份 ADR，补充上下文和被拒绝的替代方案；完整原文见 `docs/adr/`。

### ADR-0001：MCP 提供 `web_search` 与 `web_read`，Deep Research 由 agent 负责

- **Context**：MCP server 可以选择自己完成规划和综合、一次交付研究报告，也可以只做可组合的检索原语，把规划权留给 caller。
- **Decision**：MCP 提供 `web_search`（URL 获取整合）和 `web_read`（渐进式披露读取），多轮 Deep Research 由 caller agent 循环完成。`web_read` 独立可用，无需先调用 `web_search`。
- **Alternatives considered**：MCP 内完成规划和综合并一次交付报告——被拒绝，因为这会让 agent 无法决定搜索哪些问题、读取哪些来源、何时继续研究，也会让 server 背上 LLM 推理和 prompt 耦合的负担。
- **Consequences**："多个来源"以独立网站覆盖为目标，不以搜索引擎数量定义；`web_read` 首次返回 metadata、目录（若有）和限长正文，后续支持 section/位置续读和页内关键词定位，使用原文抽取不依赖模型摘要。

### ADR-0002：首版仅接受免费、开源方案

- **Context**：早期调研（[search-providers.md](../research/search-providers.md)）列出过付费 provider 的候选方案。
- **Decision**：自建组件必须开源、不依赖付费 API；允许使用公开搜索引擎和本机资源。首版 Windows 本机部署，CPU 即可运行，暂不引入 GPU。
- **Alternatives considered**：采用付费 Search API 或 hosted 抓取服务——被拒绝，付费服务的试用额度不能替代这一约束。
- **Consequences**：开源要求只适用于自建组件，不要求上游公开搜索引擎本身开源；服务器部署形态和资源预算留待后续决定。

### ADR-0003：query 内容约束由调用方模型负责

- **Context**：MCP 可以选择在内部对 query 做敏感信息检测或脱敏，也可以把这个责任完全交给 caller。
- **Decision**：MCP 只做基本入参校验，不对 query 内容做脱敏；query 的生成与外发适宜性由调用方模型负责，tool description 提供指引。
- **Alternatives considered**：在 MCP 中加入内容识别、改写或拦截机制——被拒绝，因为这会让 MCP 猜测和改变 query 的含义。
- **Consequences**：调用方传入的敏感内容不会被 MCP 自动移除；基本入参校验的具体规则留待工具契约设计时确定。

### ADR-0004：v1 `web_search` 与 `web_read` 边界

- **Context**：在完成产品边界确认（ADR-0001~0003）之后，需要进一步收窄 v1 首版的具体范围，尤其是是否要做 server-side `deep_search` facade。
- **Decision**：首版交付两个可组合工具，暂不实现 `deep_search`。`web_search` 首要承诺可解释失败；route/backend 由调用方显式选择，v1 只用 SearXNG/Google；batch 按 query 独立返回，默认不 retry；health 只做请求内检查。`web_read` 接受任意 URL，尽量抽取完整正文并转为结构化 Markdown，超长内容分段并提供 continuation。
- **Alternatives considered**：让 server 内置 research planning 和 synthesis 能力——被拒绝，理由与 ADR-0001 一致，且当前证据不足以支撑这类黑盒能力的质量保证。较早的"有限自动重试"表述也被这次决策取代为"默认不 retry"。
- **Consequences**：内容类型支持范围（HTML/JS/PDF/OCR）已确认，但 Source 覆盖验收方式、Web Read 完整性判定、渐进式披露的具体交互仍需后续研究——这正是第 4、5 节两组研究要回答的问题。

### 补充：高影响但仍是 Proposed 的设计选择

以下选择已完成一手资料研究与独立核验，但尚未经过 contract review 转正为 accepted：

| 选择 | 状态 | 理由摘要 |
|---|---|---|
| Search observation 三层模型（instance/engine/upstream） | Proposed | 直接回应 prototype 观测到的"本地 200 掩盖 upstream 失败"问题 |
| `advance` 作为增量处理的唯一机制 | Proposed | 避免引入后台 job/queued 状态，与 MCP Tasks 是 opt-in extension 的现实一致 |
| Context closure 仅限确定性结构链接 | Proposed | 防止无 LLM 的规则被误认为具备语义完整性判断能力 |
| 组件选型 baseline-first 策略 | Proposed | 已跑通的 pipeline 优先复现，避免无反证替换 |
| Search 不做 URL 数量配额 | Proposed | 医疗/学术领域的证据充分性框架不能直接迁移为固定数字 |

---

## 8. 实施路线图

### 8.1 当前状态矩阵

| 子系统 | 产品边界 | 技术方案 | 功能路径验证 | 性能/质量验证 | 生产 tool schema |
|---|---|---|---|---|---|
| Web Search | Accepted | Proposed | Prototype smoke 完成，[#6](https://github.com/EllisYuan/web_search/issues/6) 仍 open | 未开始（G1–G8） | 未开始 |
| Web Read | Accepted | Proposed | [#7 已关闭](https://github.com/EllisYuan/web_search/issues/7#issuecomment-5599723724) | 未开始（Phase D） | 未开始 |
| MCP 协议接入 | — | 研究完成 | 未开始（G7） | — | 未开始 |

### 8.2 Search 侧下一步（对应 G1–G8）

优先级建议：先做 G1（capability matrix）和 G3（分页漂移），因为这两项直接决定 schema 能否诚实表达 filter 和 continuation 的能力边界；再做 G6（access bias sampling），因为它关系到 coverage disclosure 的最低字段要求。G2/G4/G5 涉及人工标注和 adjudication，成本更高，可以在前三项稳定后再展开。

### 8.3 Web Read 侧的分阶段实施（Phase A–E）

1. **Phase A**：验证 source snapshot、representation lineage、typed block/locator、bounded full/fixed baseline、file-backed persistence 和 cursor invariant——用 text/静态 HTML/小型 PDF 建立可复核基础。
2. **Phase B**：加入 static HTML、rendered DOM、网页文字图片、独立 image asset/OCR；针对 JS shell、delayed hydration、infinite scroll 建 adversarial fixture。
3. **Phase C**：按 page classification 接入 native text、mixed/scanned OCR；**优先复测已有 RapidOCR/ONNX Runtime/pypdfium2/Playwright smoke**，再比较候选 backend。
4. **Phase D**：冻结跨格式 corpus，做 Progressive Disclosure 的 paired evaluation——这是回答"这个设计到底值不值"的关键阶段。
5. **Phase E**：target MCP host capability matrix、restart/TTL/eviction、SSRF/DNS/redirect/browser egress 和 prompt-injection corpus 的安全加固。

### 8.4 两条线汇合的前提

在下列条件全部满足前，不建议把 `web_search`/`web_read` 的具体字段、数值或组件选择固化为生产 tool schema：

- Search 完成 G1、G3、G6；
- Web Read 完成 Phase A、B、C，并至少启动 Phase D 的 paired evaluation；
- 两个子系统在同一个目标 MCP host（至少 Claude Code）上完成一次端到端的工具发现、调用、batch 返回、续读和错误处理集成测试。

### 8.5 服务器化（后续，非本版范围）

服务器部署形态和资源预算尚未确定（ADR-0002）。这部分工作要等 v1 本机版本的功能与质量证据积累到一定程度后再单独设计，本文档不做预判。

---

## 9. 未决高影响问题

按对整体设计的影响程度排序，汇总自两份研究文档的 "Open high-impact uncertainties"：

1. **没有直接的 research-agent A/B 证据**证明 `preview -> find -> evidence window` 优于全文阅读、固定分段或一次性大 context 输入——这是 Progressive Disclosure 差异化主张能否成立的核心悬念。
2. **Google-only 的实际覆盖范围**（中文、英文、混合语言、新闻、技术文档、政策类 query 的 domain coverage、时效性、重复率、CAPTCHA 概率）未经真实测量。
3. **Source independence 没有已验证的通用聚类算法**；不同域名、`rel=canonical`、相同文本 hash 都不足以单独证明独立佐证。
4. **HTML/JS/PDF/OCR 在目标 Windows CPU 环境的真实 fidelity**（reading order、table 重建、citation 定位复原）尚未在公开互联网样本上验证。
5. **Cursor 的生命周期语义**（TTL、进程重启恢复、并发续读、来源内容变化后的行为）只有概念设计，没有 target MCP host 的一致性测试。
6. **组件许可证与依赖清单**尚未完成——尤其 PyMuPDF 的 AGPL/commercial 双许可、Docling/PaddleOCR 的模型与运行时许可。
7. **缺失并非随机**（missing-not-at-random）：paywall、地域屏蔽、JS-only、扫描件、语言壁垒可能与研究主题、地区或机构系统性相关，这会让"覆盖率"这个指标本身产生方向性偏差。
8. **Target MCP host 的实际能力**（是否保留 `structuredContent`、resource link、tool execution error 的具体渲染方式）不能从协议文档推断，必须做针对目标 host 的一致性测试。

---

## 10. 文档索引

| 文件 | 状态 | 一句话内容 |
|---|---|---|
| `CONTEXT.md` | Accepted | 项目术语表 |
| `docs/adr/0001-agent-owns-deep-research.md` | Accepted | MCP 提供 web_search/web_read，Deep Research 归 agent |
| `docs/adr/0002-free-open-source-solutions-only.md` | Accepted | 首版仅接受免费开源方案 |
| `docs/adr/0003-caller-owns-query-disclosure.md` | Accepted | query 内容约束归调用方模型 |
| `docs/adr/0004-v1-search-read-boundary.md` | Accepted | v1 web_search/web_read 具体边界 |
| `docs/design/search-mcp-scope.md` | Accepted + 续议记录 | 产品边界原始 resolution 与后续对齐说明 |
| `docs/design/prototype-validation-plan.md` | 计划 | 两个 prototype ticket 的验证顺序索引 |
| `docs/research/research-source-strategy.md` | Proposed 研究 | 研究型报告的 Source 策略，含一手依据 ledger |
| `docs/design/research-source-strategy.md` | Proposed 设计 | 对应的 Search schema 与验证 gate |
| `docs/research/progressive-disclosure.md` | Proposed 研究 | Progressive Disclosure 深入研究，含一手依据 ledger |
| `docs/design/progressive-disclosure.md` | Proposed 设计 | web_read 完整数据模型、操作集与验收 gate |
| `docs/research/2026-09-10-source-disclosure/` | Proposed 研究支撑 | 五个专题 memo + 独立 verification + 完整性审查 |
| `docs/research/mcp-architecture.md` | 一手研究 | MCP 2026-07-28 协议边界与 SDK 选择 |
| `docs/research/retrieval-evidence.md` | 一手研究 | 内容抽取与可追溯 evidence 路线候选比较 |
| `docs/blog/searxng-vs-ddgs-failure-propagation.md` | Prototype 证据分析 | 两条 Search route 的失败形态对照 |
| `prototypes/free-search/REPORT.md` | Prototype 证据 | 免费 Search smoke 实测报告 |
| `prototype/cpu-web-read` 分支（`4c210d1`） | Prototype 证据 | CPU-only Web Read 受限功能 smoke |

