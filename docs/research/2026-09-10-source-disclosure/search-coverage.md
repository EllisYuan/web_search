---
title: Search 覆盖、排序与可测方案
status: research-proposal
researched_on: 2026-09-10
scope: SearXNG Google engine、查询族、结果排序与多样性评测
---

# Search 覆盖、排序与可测方案

> 本文是面向 v1 Search schema 与验收的研究 memo。除明确标为 **事实** 的内容外，数字、字段、算法组合、阈值与实验设计均为 **建议 / proposed / unvalidated**，不是已确认的产品约束，也不是已实现能力。本文没有执行 live SERP experiment、没有接入 Google provider、没有改动生产代码。

## 结论摘要

1. **SearXNG 的 Google engine 只能承诺一次有边界的 upstream 尝试，不应承诺 Web 全量、稳定排序或客观 relevance。** 官方 adapter 显示 `pageno` 以 10 个结果为步长、最多配置 50 页，并把 locale、language restriction、country、time-range 与 SafeSearch 映射到 Google 请求；同时会识别 CAPTCHA / `sorry` / block。这个边界是 adapter capability，不是 Google SLA。[S1][S2][S3]
2. **v1 应把 route/backend/engine 写进每次请求与结果。** `route=searxng`、`backend=google` 是调用方显式选择；不能把 SearXNG 的聚合层说成 source independence，也不能加入隐式 multi-engine fallback。仅启用 Google 时，所有结果仍来自同一 upstream；“多个来源”要按网站 / publisher / ownership group 评估，不按 engine 数量评估。[S4][S5]
3. **不应把 `score` 当作 relevance 概率。** SearXNG 的 `calculate_score()` 是 engine weight、出现位置、重复合并与 priority 的启发式；其结果还会经过 category/template/image 分组调整。建议对单 Google 结果优先暴露 `position_in_page` / `derived_rank`，若保留分数则命名为 `aggregation_score` 并带 `score_basis` 与 `score_version`。[S6]
4. **Search coverage 的核心不是盲目翻页，而是 agent 规划的 query family。** 对每个研究问题，caller agent 应显式产生 facet、术语变体、official/primary、measurement、contrary evidence、failure/limitation 与 time-sensitive 变体；Search Batch 仅并行执行和分组返回，不做规划、读取正文或综合答案。[ADR-0001][ADR-0004]
5. **排序研究要同时测 relevance、facet coverage、novelty、source-group diversity 与 drift。** MMR / xQuAD 提供 relevance–redundancy 与 aspect coverage 的候选思想；TREC / `ndeval.c` 给出可复核的 subtopic qrels、`alpha-nDCG` 与 `IA-P` 计算路径。它们应作为评测工具，不应被包装成 server-side “可信度分数”。[S7][S8][S9]
6. **所谓 Recall 必须标注参照系。** 只有单 Google engine、有限 query family 和有限 page pool 时，无法测 Web 全量 recall；可以测 `pool-relative recall`、facet coverage、source-group coverage，以及 judged pooled corpus 上的排序质量。未判断结果在 NIST `ndeval.c` 中会按未相关处理，因此必须同时报告 pool construction、unjudged rate 与 topic averaging 规则。[S9]

## 1. 事实边界：SearXNG、Google 与结果排序

### 1.1 SearXNG 是 aggregator，不是独立 Google index

**事实。** SearXNG 官方将自身定义为 metasearch engine，聚合多个 search services / databases；自建实例可以控制代码、日志和配置，但请求仍会发往配置的 external search services，instance IP 对 upstream 可见。公开实例还要求用户信任 operator；上游 CAPTCHA 或 block 可能减少结果。[S4][S5]

因此要区分三个概念：

| 概念 | v1 可记录的内容 | 不能由它推出的内容 |
|---|---|---|
| `backend=google` | 该 attempt 请求了 SearXNG 的 Google adapter | 不是 Google 官方 API、不是固定 snapshot、不是完整 Google index |
| SearXNG aggregation | 可能对多 engine 结果做去重和 score/order | engine 数量不等于 source independence；单 Google 不会产生独立 source |
| website / publisher coverage | 结果 host、publisher、候选 ownership group | host 数量不等于独立事实来源；镜像、syndication、同一 publisher 可能重复 |

**对本项目的直接含义。** v1 保持已接受边界：调用方显式选择 `route/backend`，先用 SearXNG / Google 且只启用 Google，不在一次请求内混用其他 upstream engine；不要通过 MCP 直接旁路 SearXNG 调用 provider，也不要把 provider fallback 写成 server 默认行为。[ADR-0004]

### 1.2 SearXNG Search API 与 Google adapter 的能力

**事实。** SearXNG Search API 文档列出 `q`、`categories`、`language`、`pageno`、`time_range`、`format`、`safesearch`、`theme` 等参数；`pageno` 从 1 开始，`time_range` 与 `safesearch` 只对支持它们的 engine 生效，query syntax 也可能因外部 service 不同而变化；机器格式还可能被 instance 配置关闭并返回 `403`。[S1] 当前通用 API 文档列出的 `time_range` 值为 `day`、`month`、`year`；Google adapter source 另有 `week` 映射，因此 `week` 不应被写成所有 API / engine 的通用保证。[S2][S3]

**事实。** 官方 Google engine 文档 / source 显示：

- `paging = True`，`max_page = 50`；这个值是 adapter 的 page bound，不是 Google 对所有请求的可用结果保证。
- 后续页用 `start = (params["pageno"] - 1) * 10`，即 adapter 以 10 为 page offset。
- locale 映射到 `hl`（interface language）、`lr`（language restriction）和在适用时的 `cr`（country restriction）；`ie` / `oe` 设置为 UTF-8。
- `day/week/month/year` 映射到 `tbs=qdr:d/w/m/y`；SafeSearch 映射为 `off/medium/high`。
- adapter 使用 Google 的 XML-oriented layout（source 采用 Nokia user agent；normal web version 需要 JavaScript）；解析 title、destination URL、text snippet 与 thumbnail，并解包 `/url?q=` redirect URL。
- `sorry.google.com`、`/sorry`、HTTP `302` 或短响应中的 `/sorry/` 会触发 CAPTCHA / block 识别。[S2][S3]

**解释。** 这些是“能发出什么请求、如何识别返回、何时标记失败”的事实，不是“过滤严格满足、排名稳定、结果完整”的证据。SearXNG API 文档的 engine-dependent caveat 反而要求结果中保留 `requested_filter` 与 `effective_support`，不能只回显调用方入参。

### 1.3 单 Google engine 实际可以承诺什么

建议 v1 对外只承诺以下四类可审计事实：

1. **Attempt identity：** `route=searxng`、`backend=google`、query、language / locale、time-range、page number、request timestamp、instance / adapter version（若可得）。
2. **Returned candidate order：** 记录 adapter 返回的 page-local position；若跨页组合 rank，明确是 derived rank，不声称 Google 官方 rank 的长期稳定性。
3. **Upstream state：** success、empty、timeout、rate-limited、CAPTCHA / blocked、instance format disabled、parse failure 等，按 query 独立返回。
4. **Continuation hint：** 当前 `pageno` 与绑定约束下的 opaque continuation token；明确 continuation 可能受到 live SERP 漂移影响，不是 snapshot cursor。

不应承诺：

- Google index 的全量 recall 或对某一事实领域的覆盖率；
- 结果排序的跨时间、跨地点、跨用户可复现性；
- `language` 严格限制所有结果语言；
- `time_range` 证明正文发布时间或实时抓取；
- 同一 SERP 中的 host / publisher 是独立 source；
- SearXNG `score` 是 calibrated relevance、概率或可信度；
- page 2 是 page 1 之后稳定、不重复、不遗漏的集合。

**外部事实依据。** Google 官方说明 Search 使用“hundreds of factors”，结果会受 location、language、device 影响，且被处理并不保证进入 index；官方 ranking guide 还说明存在多套 ranking systems、freshness systems、deduplication 与 site diversity。官方 support 文档说明 time、context、personalization 和 rollout 会造成结果差异。[S10][S11][S12] 这些材料支持“结果是 context-sensitive live retrieval”这一边界，但不提供本项目所需的稳定性 SLA。

## 2. Agent-driven query strategy

### 2.1 规划原则

Query planning 属于 caller agent，不属于 Search server。每次计划应保存 `query_plan_hash` 与 query family metadata，便于解释为何发出某次 Search Batch。建议每个 research question 至少显式区分：

- `facet`：问题的独立子问题或用户意图；
- `variant_type`：术语、实体、证据类型或反例路径；
- `evidence_goal`：定义、机制、数据、官方原文、反方、限制、复现；
- `language` / `locale`：调用方选择的语言与地区提示，不等于结果严格同语种；
- `time_intent`：是否需要 freshness，及其允许的 date window；
- `stop_reason`：为何停止继续发 query 或翻页。

Server 只做基本 input validation 与受控 upstream call，不重写 query、不脱敏、不替 caller 判断是否适合外发；这与 ADR-0003 一致。

### 2.2 建议的 query family

以下是可供 agent 组合的 family；它们是 **proposed planning vocabulary**，不是 server 自动生成器：

| family | 目标 | 典型变体 |
|---|---|---|
| `definition` | 固定概念边界与同义词 | 全称 / acronym、术语变体、历史名称、不同语种写法 |
| `mechanism` | 找实现、流程与原始技术说明 | `how`, `architecture`, `implementation`, 标准章节名、repository / docs |
| `primary_official` | 优先寻找 owning institution / 原始数据 | `site:gov`、监管机构、maintainer、original paper、官方 dataset |
| `measurement` | 找指标、数据、实验与可复现细节 | `benchmark`, `evaluation`, `dataset`, `methodology`, `limitations` |
| `counterevidence` | 主动寻找反例与冲突 | `criticism`, `failure`, `negative result`, `does not work`, `replication` |
| `freshness` | 处理时效问题 | 年份 / 起止时间、recent policy / release / incident；只在问题需要时使用 |
| `entity_alias` | 处理实体别名、地域与语言 | 原名、缩写、旧名、繁简体、英文产品名与本地名称 |
| `operational` | 找可执行的接口或限制 | API reference、error、rate limit、pagination、source code |

建议先用低歧义的 `definition` + `primary_official` 建立候选 pool，再根据已见 facets / source groups 追加 `measurement`、`counterevidence` 与缺失语言或时间变体。不要让 agent 只做 query rewrite 的同义词扩张：同义词扩张容易扩大重复而不增加 facet coverage。

### 2.3 面向 facet coverage 的最小循环

拟议的 agent 循环如下，**不构成 server-side `deep_search`**：

1. **Scope：** 从问题中列出 facets，并标出哪些 facet 需要 official / data / contrary evidence。
2. **Seed：** 每个高优先级 facet 产生至少一个可读 query 和一个 source-type query；保留原文 query，不把多个 facet 拼成一个不可审计的大 query。
3. **Batch：** 以独立 query group 提交 Search Batch；不合并结果集，不把一个 query 的失败覆盖成 batch 全部失败。
4. **Triage：** 根据 title、snippet、URL、初步 source-group 线索标出已覆盖 facet、疑似重复、缺失 source type 和失败状态；正文由后续 `web_read` 验证。[ADR-0001][ADR-0004]
5. **Gap / contrary：** 只对未覆盖 facet、独立 publisher 不足、时间范围不满足或缺少反方证据的项追加 query。
6. **Continuation：** 只有当第一页带来新 facet / 新 source group / 高价值 official candidate 时继续翻页；翻页结果须记录 drift 与重复，而不是默认“越多越完整”。
7. **Stop：** 由 agent 基于覆盖、边际新增、预算和失败状态决定；Search server 不自行判断研究已经完成。

## 3. Search Batch 与 schema 建议

下面是用于讨论的 schema 草案；字段名保持 English，所有限制数字均应通过 prototype validation 决定。

### 3.1 Request

```text
SearchBatchRequest {
  batch_id: string,
  route: "searxng",
  backend: "google",
  query_plan_hash?: string,
  queries: [
    {
      query_id: string,
      query: string,
      facet_id?: string,
      variant_type?: string,
      evidence_goal?: string,
      language?: string,
      locale?: string,
      time_range?: "day" | "week" | "month" | "year",
      domains?: string[],
      pageno?: integer,
      page_size_hint?: integer,
      continuation_token?: string
    }
  ],
  bounds?: {
    max_queries?: integer,
    max_pages_per_query?: integer,
    max_results_per_query?: integer,
    deadline_ms?: integer
  }
}
```

- `route` / `backend` 必填且不可由 server 静默改写。
- `queries` 必须保留 query-level identity；不接受一个混合自然语言问题后由 server 自行拆分。
- `time_range` 应区分 API contract 支持值与 Google adapter 实际映射；若某 instance / version 不支持，结果必须显式说明。
- `domains` 是否映射为 Google syntax 或 SearXNG engine-specific parameter，应在 adapter contract 中固定并在 request metadata 中记录，不能假设所有 query syntax 跨 engine 一致。[S1]
- `continuation_token` 必须 opaque；不要让 caller 解析 token 内部的 page number 或 query hash。

一个可用于第一轮 prototype 的 **candidate bound** 可以是“每 batch 少量 query、每 query 少量 page、每 query 有明确结果上限”，但具体数值未验证，不应写成 accepted quota。Acceptance 应测试多组 bound 下的 facet coverage、partial rate、latency 与 context growth，再决定默认值。

### 3.2 Response

```text
SearchBatchResponse {
  batch_id: string,
  route: "searxng",
  backend: "google",
  status: "complete" | "partial" | "failed",
  partial: boolean,
  queries: [
    {
      query_id: string,
      status: "complete" | "partial" | "failed",
      requested: {
        query: string,
        language?: string,
        locale?: string,
        time_range?: string,
        pageno: integer
      },
      effective?: {
        engine: "google",
        page_size?: integer,
        filter_support: {
          language: "applied" | "unknown" | "unsupported",
          time_range: "applied" | "unknown" | "unsupported",
          safesearch: "applied" | "unknown" | "unsupported"
        }
      },
      results: [
        {
          result_id: string,
          url_original: string,
          title?: string,
          snippet?: string,
          thumbnail_url?: string,
          position_in_page: integer,
          derived_rank?: integer,
          published_at?: string,
          aggregator_score?: number,
          score_basis?: "searxng_aggregation_heuristic",
          canonicalization?: {
            strict_key?: string,
            semantic_key?: string,
            declared_canonical_url?: string,
            evidence?: string[]
          },
          source_identity?: {
            authority: string,
            ownership_group_id?: string,
            independence_status: "unknown" | "tentative_related" | "tentative_same_publisher",
            confidence?: "low" | "medium" | "high",
            basis?: string[]
          }
        }
      ],
      continuation?: {
        next_cursor?: string,
        current_page: integer,
        drift_status: "unknown" | "possible" | "observed"
      },
      upstream: {
        engine: "google",
        http_status?: integer,
        state: "ok" | "empty" | "timeout" | "rate_limited" | "captcha_or_blocked" | "parse_failed" | "format_disabled" | "unknown_error",
        request_id?: string,
        retry_performed: false
      },
      warnings: string[]
    }
  ],
  warnings: string[]
}
```

### 3.3 Score 字段的约束

建议不要返回未加限定的 `score`。对 Google adapter：

- `position_in_page` 是最接近可观测 upstream ordering 的字段；
- `derived_rank` 只有在 page size 与 page offset 可确认时才计算，并标为 derived；
- `aggregator_score` 仅在 SearXNG 真实执行 aggregation score 时返回，并带 `score_basis` / `score_version`；
- `aggregator_score` 不应被下游解释为 relevance、probability、authority 或 source reliability；
- 若未来引入 reranking，应另命名并保存 `reranker_version`、输入 pool 与训练 / heuristic basis，不覆盖 upstream rank。

SearXNG source 的 score 会把 engine weight、positions 和 duplicate merge 纳入计算，再按 score 初排并执行 category/template/image grouping。[S6] 这意味着它适合解释“为什么此 instance 把结果排在这里”，不适合解释“结果正确概率是多少”。

### 3.4 Failure 与 partial

每个 query 都应有独立 `status`、`upstream.state`、`warnings` 与已返回结果。batch 顶层 `partial=true` 的含义是“至少一个 query 未完整完成”，不是“全部结果不可用”。默认不 retry；调用方若要重试，应生成新的 attempt / batch identity，并保留上一 attempt 的失败原因。这样可以区分：

- query A 成功、query B CAPTCHA、query C timeout；
- query A page 1 成功、page 2 drift / parse failure；
- instance 不允许 JSON format；
- 无结果与请求失败。

这与 ADR-0004 的“可解释失败优先、按 query 保留 partial、无隐式 fallback”一致。

## 4. URL canonicalization 与 source independence

### 4.1 三层 URL identity

RFC 3986 将 URI 拆为 scheme、authority、path、query、fragment，并区分 syntax-based、scheme-based、protocol-based normalization；equivalence 依赖应用语义，不能只凭字符串或域名后缀推断。[S13]

建议保存三层 key，而不是用一个 aggressive `canonical_url` 覆盖所有语义：

1. **`strict_key`：** 只做 generic normalization：scheme / host 小写、明确的 default port 处理、dot-segment normalization、unreserved percent-encoding 规范化；用于稳定去重。
2. **`semantic_key`：** 在 strict key 基础上加入站点已验证的参数规则；默认保留 query 参数、重复参数、空值与顺序，除非有明确 application-specific 证据证明某项是 non-semantic。
3. **`observed_equivalence`：** 由 redirect chain、相同 representation hash、publisher 声明、`rel=canonical` 或多次读取观察支持的关联；不自动把关联变成删除原始 URL。

HTML Standard 对 `rel=canonical` 的定义是文档的 preferred URL、帮助 search engines 减少 duplicate content；它不是通用 URL equivalence algorithm，也不是 authority / ownership 证明。[S14] 因此建议保留 `declared_canonical_url` 和 `canonicalization_evidence`，不要直接用它覆盖 `url_original`。

### 4.2 为什么不能只保留 URL 的最后两个 domain label

“最后两个 label 相同则同一来源”的规则会误合并公共 suffix 下的不同 operator、托管平台的不同客户、delegated subdomain 和国际化域名，也无法识别跨域 mirror / syndication。建议把 **host identity** 与 **ownership hypothesis** 分离：

```text
host_identity = normalized scheme + authority + port
ownership_hypothesis = {
  group_id?,
  status: unknown | tentative_related | tentative_same_publisher,
  confidence?,
  basis: [redirect | canonical_declared | repeated_same_content |
          publisher_statement | same_feed | same_legal_entity | ...]
}
```

可以把 Public Suffix List / registrable-domain 作为候选线索，但 `same_registrable_domain` 只能是低置信度 `basis`，不等于 same owner。独立性判断应允许 `unknown`，并支持 conservative（可能同 owner 合并）与 liberal（只按 host 分开）两种 sensitivity analysis。

### 4.3 Source group 的评测含义

结果数量、host 数量和 source-group 数量分别报告：

- `unique_strict_url_count`：严格 URL 去重后的候选数；
- `unique_host_count`：normalized authority 数；
- `tentative_source_group_count`：按证据聚类后的 group 数；
- `independence_unknown_rate`：无法判断的比例；
- `same_group_repeat_rate`：同一 group 在 top-k 中的重复比例。

只有最后两项能帮助回答“是否多源覆盖”，但也只是 tentative grouping 的指标。对高影响结论，source group 仍应由 agent 通过 `web_read` 和 publisher evidence 复核，不能由 Search server 生成可信度判断。

## 5. Pagination、ordering 与 live SERP drift

### 5.1 Page number 不是稳定 cursor

SearXNG Search API 对外暴露 `pageno`；Google adapter 将其转换为 `start=(pageno-1)*10`。[S1][S2] 这是一种重复请求参数，不是 provider 返回的 immutable cursor。Google 官方说明 Search 结果会受到时间、context、personalization 与 ranking rollout 影响，且 index 持续更新。[S10][S11][S12]

因此 continuation token 应绑定以下约束，并在 server 内 opaque 保存：

```text
continuation_binding = hash(
  route, backend, engine,
  normalized_query,
  language, locale, time_range,
  domains, safe_search,
  page_size_hint,
  adapter_version
)
```

上述结构是建议；token 内部是否使用 hash、签名或数据库 handle 尚未决定。约束变化必须开始新的 continuation chain。续读响应应记录 `current_page`、`retrieved_at`、`adapter_version` 与 `drift_status`，不能声称同一个 token 保证同一个候选集合。

### 5.2 有界 drift 实验

未来 acceptance 可用少量、固定 query 做重复 attempt，不做 bulk load：

- 同一 query 在短时间窗口重复 page 1；
- 同一 query 跨时间窗口重复 page 1 / page 2；
- page 1 与 page 2 交界处检查 duplicate / skip；
- 记录 overlap@k、Jaccard、intersection 上的 rank correlation、top-rank retention、page-boundary duplicate rate；
- 另记录 `http_status`、CAPTCHA / timeout、locale 与 instance version。

这些指标只能描述该测试窗口、地点、instance 与 query set 的 drift，不能转成长期 SLA。没有稳定性门槛前，UI / agent 应把续读作为“best effort continuation”，并允许重新发起可审计 attempt。

## 6. Judged pooled corpus 与 diversity 评测

### 6.1 Pool 的定义与限制

建议为一组代表性 research questions 建立 **judged pooled corpus**：

1. 由多个 query family、术语变体、official / measurement / contrary query 和有限 page continuation 形成候选 pool；
2. 用 strict URL key 去重，但保留 query provenance、page、position 与 raw result metadata；
3. 由 assessor 对每个候选按 facet / subtopic 判定；
4. 对 source independence 单独标记 ownership hypothesis 与置信度；
5. 保存 pool version、query_plan_hash、attempt IDs、时间与 instance / adapter version。

必须把它命名为 `pool-relative`：pool 之外的未发现页面不在 denominator 中，所以不能声称 Web recall。更准确的指标包括：

```text
pool_relative_recall@k
  = judged relevant candidates retrieved in evaluated top-k
    / judged relevant candidates present in the constructed pool

facet_coverage@k
  = covered judged facets in top-k
    / judged facets represented in the pool

source_group_coverage@k
  = distinct tentative groups in top-k
    / distinct groups represented in the pool
```

这些公式是 proposal；分母、top-k、是否按 query family 还是 merged pool 计算，都应在 acceptance plan 中预注册，避免看完结果后选择有利定义。

### 6.2 Assessor 与 relevance scale

建议采用两层 judgment：

- **Primary binary facet qrels：** 对每个候选文档与 facet 标 `0=does not satisfy`、`1=satisfies`，便于与 TREC `alpha-nDCG` / `ndeval.c` 的 binary interpretation 对齐。
- **Secondary graded usefulness：** 可另设 `0–2` 或 `0–3` 的 relevance / usefulness scale，表示不相关、部分、有用、强支持；它是产品评测 proposal，不能与 `ndeval.c` 的 binary qrel 直接混用。

每条 judgment 建议保存：

```text
{ topic_id, facet_id, result_id, label,
  assessor_id, judged_at, confidence, adjudication_status,
  evidence_note? }
```

标题 / snippet 不足以判断事实正确性时，assessor 可以进入 `web_read` 复核，但要把“Search candidate relevance”与“正文 evidence support”分开记录。这样不会把 Search 的 snippet 相关性误当成 source 事实已验证。

### 6.3 TREC / alpha-nDCG 对本项目的启发

NIST TREC 2009 / 2010 Web Track 数据页提供 diversity-task qrels 与 `ndeval.c`；source code 读入四字段 qrel（topic、subtopic、docno、judgment），对非零 judgment 按 Boolean relevant 处理。`ndeval.c` 输出 `alpha-ndcg@5/@10/@20` 与 `IA-P@5/@10/@20`；默认 `alpha=0.5`，同一 subtopic 被前面文档覆盖后，后续 gain 乘以 `1-alpha`；ideal ordering 使用 greedy novelty-weighted gain。未出现在 qrels 的 run document 没有 qrel relevance、不会贡献 gain / intent count，但仍占据 rank，因此在这些指标中具有等价于 non-relevant 的效果；默认 topic averaging 使用 qrel/run 的交集，`-c` 才改为 complete qrel-topic set。[S8][S9]

这给出三个具体设计约束：

1. **必须保存 subtopic/facet qrels，而不只保存一个 overall relevance。** 否则无法衡量 coverage 与 redundancy。
2. **必须报告 unjudged rate 与 averaging denominator。** 在 pooled corpus 外的结果被当作不相关会产生 pool bias；不能只报一个漂亮的 alpha-nDCG 数字。
3. **alpha 参数与 metric version 要随报告保存。** `alpha=0.5` 是 NIST evaluator 的 default，不是本项目已批准的最优值；应把 sensitivity analysis 作为 validation。

### 6.4 MMR 与 xQuAD 的适用位置

MMR 的原始论文将 relevance 与已选文档相似度 / redundancy 放入迭代 reranking；xQuAD 的原始论文以显式 query aspects / sub-queries 表达 coverage 与 novelty。它们适合作为 **候选 reranking / evaluation baseline**，不适合作为“server 已判断 source 可信”的黑盒。

本次环境中：

- Carbonell & Goldstein 的 CMU-hosted MMR PDF 能取得 binary PDF，但 WebFetch 无法读取正文；ACM 页面返回 `403`。公式与参数只能视为 primary-source lead，不能标记为 full-text verified。[S7]
- Santos et al. 的 ECIR 2010 xQuAD PDF 同样返回 compressed PDF object；WebSearch 只能看到来源和公式片段，不能声称已读取全文。[S7]
- 因此本文只采用两者共同的保守抽象：`relevance + novelty/redundancy penalty + explicit aspects`；不把论文中的参数、实验结果或具体 superiority 当作已验证事实。

拟议 baseline：

```text
baseline-A: upstream order only
baseline-B: deterministic MMR-like rerank
  relevance = normalized upstream position signal
  redundancy = same strict URL / same host / same tentative group / text similarity
baseline-C: aspect-aware rerank
  coverage gain = uncovered judged or agent-declared facet evidence
```

baseline-B/C 只能在实验集上比较 `alpha-nDCG`、facet coverage、source-group coverage、duplicate rate 与 top-k usefulness；生产 schema 必须保留 upstream order，不覆盖原始 rank。

## 7. Acceptance experiments（均为 proposed / unvalidated）

### A. Google adapter capability matrix

目标：验证“能请求什么”而不是声称“质量有多高”。固定少量 query，逐项测试：

- language / locale / country 组合；
- day / week / month / year 与无 time filter；
- page 1 / 后续 page；
- empty、CAPTCHA / block、format disabled、timeout、parse failure 的错误归类；
- response field presence（title、snippet、URL、thumbnail、published date）。

记录 `requested`、`effective`、`upstream.state`，不把某次通过当作永久上游保证。

### B. Query-family coverage study

目标：比较 query planning family 是否增加 facets 与 source groups，而不是只增加 URL 数。

- 预先建立 topic/facet set；
- 对每个 topic 固定 family budget 与 query_plan_hash；
- 先执行 seed families，再按 gap / contrary rule 追加；
- 与只做同义词扩张的 baseline 比较；
- 报告 pool-relative recall、facet coverage、new-group rate、duplicate rate、partial rate 和每 query 的 candidates。

不应把 agent 的综合答案质量混入 Search score；最终 synthesis 属于 agent-owned Deep Research。

### C. Ordering 与 continuation drift

目标：测 live SERP 的可重复程度与 page continuation 风险。

- 同 query 多次 bounded attempt；
- 以 URL strict key 对齐；
- 分别报告 exact order、top-k overlap、rank correlation、page boundary duplicate / missing；
- 记录 query time、locale、instance、adapter version、upstream error。

测试结果只用于确定是否需要向 agent 显示 `drift_status`、何时提示重新检索，不能未经长期数据变成 SLA。

### D. Canonicalization / ownership adversarial set

构造离线 URL fixture，覆盖：

- fragment 差异；
- default port、percent-encoding、dot-segment；
- 有语义的 `id`、`page`、`lang`、重复 query 参数；
- tracking-like 参数但无站点证据；
- redirect / `rel=canonical` / mirror / syndication；
- public suffix、hosted platform、跨域同文档。

验收目标不是最大去重率，而是低 false merge；同时输出 strict key、semantic key、observed evidence，禁止只返回一个无法解释的 canonical URL。

### E. Judged diversity evaluation

用 assessor qrels 对候选 pool 做 facet / subtopic labeling；至少比较 upstream order、MMR-like baseline、aspect-aware baseline。报告：

- `alpha-nDCG@k` 与 `IA-P@k`，明确 alpha、qrel version、topic denominator；
- facet coverage、pool-relative recall、source-group coverage；
- unjudged rate、same-group repeat rate、canonicalization false-merge review；
- assessor agreement / adjudication workload；
- query family、page depth 与 budget 的边际增益。

只要 pool construction、assessor scope 或 source grouping 改变，metric 结果就应视为新 evaluation version。

## 8. Adversarial cases 与 trade-offs

| 情况 | 可能的错误结论 | 建议记录 / 处理 |
|---|---|---|
| Google 只返回大站 | “小站不存在”或“Google coverage 足够” | 记录 site diversity / pool limitation；追加 official / entity-specific query，不宣称 Web recall |
| 同一新闻被多站 syndicate | “独立 source 很多” | `ownership_hypothesis` 标记 related / unknown；以 publisher evidence 分组 |
| `rel=canonical` 指向另一个 URL | “两个 URL 永远等价” | 保留原 URL、声明 canonical 与 observed evidence；不直接删除候选 |
| query 参数被 aggressive stripping | 丢失 page / locale / entity 语义 | default preserve query；站点规则需有证据并 versioned |
| page 2 与 page 1 重复或跳过 | “pagination bug”或“已完整翻页” | 记录 page-boundary duplicate / missing；continuation 标为 best effort |
| language filter 产生混语结果 | “Google filter 失效”或“所有结果符合语言” | 分开 requested / effective / judged language；保留 mixed-language result |
| date filter 命中旧页 | “正文在窗口内发布” | 只称 upstream date filter；正文 publish date 需 `web_read` 复核 |
| CAPTCHA / 429 后盲 retry | “临时失败可透明恢复” | 默认不 retry；新 attempt 可审计，保留原失败状态 |
| aggregator score 高 | “更可靠 / 更相关” | 只解释 aggregation heuristic；不得下游升格为 credibility |
| qrels 未覆盖的 result | “不相关” | 报告 unjudged rate；增加 pool 或做 sensitivity analysis |
| 只有一个 Google engine | “多引擎一致” | 明确 source independence 与 engine count 分离；不写 cross-engine agreement |

## 9. Open high-impact gaps

1. **SearXNG version / instance variance。** 本文核对了 official docs / source，但没有锁定项目版本，也没有验证目标 Windows instance 的 enabled format、locale traits、timeouts 或具体 Google parser 行为。
2. **Google upstream stability。** Google 官方资料解释 context-sensitive ranking，但没有为 SearXNG adapter 提供稳定 pagination、coverage、date-filter precision 或 language-filter precision 保证；必须做小规模、可审计 validation。
3. **Source-group ownership evidence。** 目前没有决定使用哪一个 Public Suffix / DNS / publisher metadata library，也没有建立人工 adjudication protocol；任何 ownership grouping 只能先标 tentative。
4. **Assessor protocol。** facet taxonomy、binary vs graded label、assessor 是否访问 `web_read`、agreement 统计与 adjudication 成本尚未确定。
5. **Default bounds。** batch query 上限、page 上限、result cap、deadline 与 context budget 均未验证；本 memo 的 schema 只保留可表达位置，不把候选数字写成 accepted quota。
6. **Reranking 是否属于 v1。** MMR / xQuAD baseline 可用于离线评测，但是否进入 Search server、是否只由 caller agent 使用、是否需要 text similarity / facet classifier，都没有批准决定。建议先不把它作为 v1 server promise。
7. **Filter semantics.** `language`、`time_range` 在 SearXNG API、Google adapter 与实际 SERP 的语义可能不同；需要把 requested / effective / judged 三层字段纳入 prototype，再决定 contract。
8. **Cross-attempt dedupe 与 retention。** 如何保存 raw SERP metadata、hash、query plan 和 retry attempt，仍需结合 provider terms、privacy policy 与本项目 evidence retention 决定。

## 10. Concrete implications for the v1 schema

- 顶层必须有 `route`、`backend`、`batch_id`、`partial` 与 per-query status；不能把 SearXNG / Google 隐藏成一个无来源的 `search`。
- 每条 result 至少保留 `query_id`、`url_original`、`title`、`snippet`、`position_in_page`、`retrieved_at`、`upstream.state`；正文交给独立 `web_read`。
- `score` 若保留，改成 `aggregator_score`，带 `score_basis`；单 Google 不应伪造 provider relevance score。
- 分页使用 opaque `next_cursor`，但 response 明确 `current_page` 与 `drift_status`；不要承诺 immutable snapshot。
- URL 需同时支持 `strict_key`、可选 `semantic_key`、`declared_canonical_url` 与 `canonicalization_evidence`；默认不抹掉 query 参数。
- source identity 需区分 `authority`、`ownership_group_id?`、`independence_status`、`confidence`、`basis[]`；group 是 hypothesis，不是事实表。
- filter 需同时返回 `requested`、`effective.filter_support` 与 warnings；不把 Google 参数回显当作过滤已满足。
- Search Batch 按 query 分组返回，允许 query-level `partial` 与 top-level `partial`；默认不 retry，重试由 caller 以新 attempt 发起。
- schema 不应出现 `deep_search` 或最终 synthesis 字段；这会与 ADR-0001 / ADR-0004 的 agent-owned Deep Research 边界冲突。

---

## Citation ledger

访问日期均为 **2026-09-10**。`Full` 表示本次可读取官方 HTML / source text；`Binary-unreadable` 表示取得 PDF 但正文无法从工具返回的 compressed object 中读取；`Search-snippet` 表示只看到搜索结果摘录，未声称读取 URL 正文。

| ID | 来源与 owning institution / authors | 版本 / publication | 证据状态与支持内容 |
|---|---|---|---|
| [S1] | [SearXNG Search API](https://docs.searxng.org/dev/search_api.html)，SearXNG maintainers | Official docs，访问 2026-09-10 | **Full HTML.** Sections “Search API” / “Parameters”。支持 `q`、`language`、`pageno`、`time_range`、`format`、`safesearch`；短引文：“time_range and safesearch affect only engines that support those features”；`pageno` starts at 1；format 需 instance enable。 |
| [S2] | [SearXNG Google engine docs](https://docs.searxng.org/dev/engines/online/google.html)，SearXNG maintainers | Official rendered source docs，访问 2026-09-10 | **Full HTML.** Google engine section。支持 `paging=True`、`max_page=50`、`start=(pageno-1)*10`、`hl/lr/cr`、`tbs=qdr`、SafeSearch；短引文：“Google supports up to 50 pages of results”；普通 web version 需要 JavaScript，因此 adapter 使用 XML-oriented path。 |
| [S3] | [SearXNG Google engine source](https://raw.githubusercontent.com/searxng/searxng/3fdc6d753a339b5f4a7dc5842c94c0d8324726f1/searx/engines/google.py)，SearXNG maintainers | commit `3fdc6d753a339b5f4a7dc5842c94c0d8324726f1`，commit date 2026-09-08，访问 2026-09-10；未锁 release | **Full source fetched from official raw file.** Functions `google_request`, `detect_google_sorry`, `response`；`max_page = 50`、`start` offset、locale/time/safe mappings、`/url?q=` unwrap、CAPTCHA / `sorry` detection。该 commit 可复核 source snapshot，但不是项目已选定的 SearXNG release；具体部署行为仍需目标 version validation。 |
| [S4] | [SearXNG project README](https://github.com/searxng/searxng)，SearXNG maintainers | Repository README，访问 2026-09-10 | **Full page partially available.** 明确 “SearXNG is a metasearch engine” and “aggregates results” from multiple services/databases。license 另由 commit-pinned [LICENSE][S15] 验证。 |
| [S5] | [SearXNG self-hosting docs](https://docs.searxng.org/own-instance.html)，SearXNG maintainers | Official docs，访问 2026-09-10 | **Full HTML.** 自建实例控制 source/logging/private data，但请求仍发往 external services；instance IP exposed upstream；public instance operator trust；CAPTCHA / block 可减少结果。 |
| [S6] | [SearXNG result container source](https://raw.githubusercontent.com/searxng/searxng/3fdc6d753a339b5f4a7dc5842c94c0d8324726f1/searx/results.py)，SearXNG maintainers | commit `3fdc6d753a339b5f4a7dc5842c94c0d8324726f1`，commit date 2026-09-08，访问 2026-09-10；未锁 release | **Full source fetched from official raw file.** `calculate_score()` 使用 engine weight、positions、priority；duplicate hash merge；`get_ordered_results()` 先 score sort 再 category/template/image grouping。支持“score 是 aggregation heuristic，不是 calibrated relevance”的解释；部署到其他 release 仍需复核。 |
| [S7] | Carbonell & Goldstein, [MMR paper DOI](https://doi.org/10.1145/290941.291025)；Santos et al., [xQuAD ECIR 2010 PDF](https://terrierteam.dcs.gla.ac.uk/publications/ecir2010_rodrygo_div.pdf) | MMR: SIGIR 1998；xQuAD: ECIR 2010 | **Binary-unreadable / Search-snippet.** 两个 primary PDF 均可取得但正文 compressed/unreadable；ACM MMR page 403；xQuAD 公式只见 search-result snippet，未声称 full-text verified。本文仅采用 relevance–redundancy–aspect 的保守抽象，不采用其参数或实验结论作为事实。 |
| [S8] | [TREC 2009 Web Track data](https://trec.nist.gov/data/web09.html)，NIST | TREC 2009 Web Track，访问 2026-09-10 | **Full HTML.** 页面列出 “Diversity task relevance judgments” 和 `ndeval.c (v1.3): source code for diversity task evaluation`，并说明编译方式；不包含完整 assessor protocol。 |
| [S9] | [NIST `ndeval.c`](https://trec.nist.gov/data/web/09/ndeval.c)，NIST | v1.3 source，访问 2026-09-10 | **Full C source.** `alpha-ndcg@5/@10/@20`、`IA-P@5/@10/@20`；default `alpha=0.5`；qrel 四字段 topic/subtopic/docno/judgment；nonzero Boolean relevant；unjudged run docs 无 gain / intent count 但占据 rank，因而在这些指标中等价于 non-relevant；rank sorting / `-traditional`；greedy ideal ordering。 |
| [S10] | [Google Search Central: How Search works](https://developers.google.com/search/docs/fundamentals/how-search-works)，Google | Official documentation，访问 2026-09-10 | **Full HTML.** “Serving search results”：Google evaluates relevance with “hundreds of factors”；results may depend on “location, language, and device”；“Indexing isn't guaranteed”。 |
| [S11] | [Google Search Central: Ranking systems guide](https://developers.google.com/search/docs/appearance/ranking-systems-guide)，Google | Official documentation，访问 2026-09-10 | **Full HTML.** Multiple systems / “many factors and signals”；page-level ranking；freshness；deduplication；site diversity。 |
| [S12] | [Google Search Help: Why search results differ](https://support.google.com/websearch/answer/12412910?hl=en)，Google | Official support documentation，访问 2026-09-10 | **Full HTML.** “Time causes differences in results” and “Search uses context to improve results”；location, language, device, recent searches and personalization can affect results。 |
| [S13] | [RFC 3986](https://www.rfc-editor.org/rfc/rfc3986)，IETF | URI Generic Syntax，§§3.4、6，访问 2026-09-10 | **Full HTML.** Query is non-hierarchical data; URI equivalence is application-dependent；normalization ranges from simple string to protocol-based。支持 preserve semantic query params、分层 key 与不以 suffix heuristic 判 ownership。 |
| [S14] | [HTML Standard: link type canonical](https://html.spec.whatwg.org/multipage/links.html#link-type-canonical)，WHATWG | Living Standard，访问 2026-09-10 | **Full HTML.** `rel=canonical` creates a hyperlink to the document’s “preferred URL” and helps search engines reduce duplicate content；standard 不定义 general URL-equivalence / ownership algorithm。 |
| [S15] | [SearXNG LICENSE at pinned commit](https://github.com/searxng/searxng/blob/3fdc6d753a339b5f4a7dc5842c94c0d8324726f1/LICENSE)，SearXNG maintainers | commit `3fdc6d753a339b5f4a7dc5842c94c0d8324726f1`，访问 2026-09-10 | **Full HTML.** Exact file identifies “GNU AFFERO GENERAL PUBLIC LICENSE, Version 3, 19 November 2007”。This verifies the source snapshot's license, not an unselected future or deployment release。 |

## 与既有决策的关系

- **符合 ADR-0001：** agent 负责 query planning、facet coverage、source selection、冲突判断与 synthesis；Search 只提供候选 URL / SERP metadata，`web_read` 继续独立提供原文渐进式读取。
- **符合 ADR-0002：** 研究只围绕开源、自托管与公开 Google upstream；没有引入付费 search API 或 hosted research。
- **符合 ADR-0003：** query disclosure 与内容边界由 caller agent 负责，server 不自行改写或脱敏 query。
- **符合 ADR-0004：** 不实现 server-side `deep_search`；route/backend 显式；Google-only v1；无隐式 fallback；默认不 retry；batch per-query partial；失败可解释。
- **需要后续设计决定但不构成 ADR 冲突：** batch / page bounds、source grouping、canonicalization evidence、judged pool、metric version 与是否引入 deterministic rerank。 
