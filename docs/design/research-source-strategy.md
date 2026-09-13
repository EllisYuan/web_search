---
title: Research Source Search 设计
status: proposed
proposal_date: 2026-09-10
implementation_status: not implemented / unvalidated
runtime_experiments: none
related_research: ../research/research-source-strategy.md
---

# Research Source Search 设计

> 这是基于 `research-source-strategy.md` 的具体 Search 方案草案，不是新的 `deep_search` tool，也不是 production contract。本设计只建议 caller agent 如何规划和调用 v1 `web_search`，以及如何与 standalone `web_read` 组合。除”已接受要求”小节明确列出的项目决策外，所有 mechanism、字段、schema、数字、ranking、source grouping、stop criteria 和 evaluation gate 均为 **Proposed / unvalidated**。本轮没有新增 runtime experiment（没有新的 Search 调用、目标 instance 接入、正文读取、benchmark、OCR 或 MCP host conformance）；引用的既有观测来自 [免费 Search prototype](../../prototypes/free-search/REPORT.md) 与 [#7 constrained smoke](https://github.com/EllisYuan/web_search/issues/7#issuecomment-5599723724)。

## 1. Design intent and boundaries

### 1.1 Accepted requirements

以下内容来自仓库已接受的 ADR/scope，设计只做映射，不重新批准：

- Deep Research 的 planning、query selection、source selection、conflict judgment 和 synthesis 由 caller agent 负责；v1 不实现 server-side `deep_search` facade。
- `web_search` 只发现候选 URL 和 SERP metadata，不读取目标正文，不生成综合答案。
- `web_read` 独立接受 caller 提供的 URL；首次返回 metadata、outline（若有）和限长原文，后续按 section/position/keyword 继续读取；原文抽取不依赖模型摘要。
- route/backend 由 caller 显式选择；v1 采用 SearXNG route、Google backend/engine，不在一次 request 混合其他 upstream engine，不做隐式 fallback。
- batch 逐 query 分组返回；部分成功保留已完成项并标记 top-level/per-query partial。
- Search v1 默认不 automatic retry，不做隐式 backend fallback；retry 由 caller 显式发起新的可审计 attempt。
- Search 的 query 仅做基本 input validation；query 内容是否适合外发由 caller 负责，server 不脱敏、不改写语义。
- 首版必须覆盖公开静态 HTML、JavaScript-rendered pages、PDF 和 OCR；OCR 范围包含扫描 PDF、网页文字图片和 standalone image URL。支持范围不等于任意页面无损成功。
- Search 的首要承诺是可解释失败，而不是始终返回结果；request 内 health 检查不能被 process/container 存活替代。

### 1.2 Proposed design goal

建议把 Search 设计成 **claim-driven candidate acquisition**：

```text
research question
  -> caller claim/facet map
  -> query families and counterevidence plan
  -> bounded Google-only Search Batch
  -> candidate triage + provenance hypotheses
  -> standalone web_read for pivotal sources
  -> evidence matrix update
  -> gap/contrary/version/language/modality loop
  -> caller-owned stop with explicit gaps
```

Search server 不知道研究是否完成；它只能返回 candidate、metadata、capability mismatch、upstream state 和 partial failure。最终 report 是否足够由 caller 依据 claim-level evidence 判断。

## 2. Why this is the differentiator

研究报告的 Source 需求不是“尽量多的 URL”。报告需要把 material claims 映射到合适的 source roles，并解释 directness、provenance、independence、counterevidence、recency/version、language/geography 和 access completeness。依据见 [研究型报告的 Source 策略](../research/research-source-strategy.md)（内部研究文档，其 primary sources 见该文 ledger）。

因此本设计有三个 deliberately separate 的层次：

1. **Search discovery**：扩大可观察 candidate pool，保留 query/page/rank/upstream provenance；
2. **Read evidence**：由 `web_read` 提供原文、locator、representation 和 continuation；
3. **Agent judgment**：caller 判断 source role、独立性、矛盾、覆盖 gap 和 stop。

这个边界避免三种误报：

- SERP snippet 被当成正文或方法；
- SearXNG `score` 被当成 relevance、authority 或 truth；
- 多个域名或同一 syndicated story 被当成 independent corroboration。

## 3. Caller-side research plan

### 3.1 Claim map

caller 在第一次 Search 前建立 `ClaimMap`。以下字段是 **proposed agent-side record**，不是 server schema：

```text
ClaimMap {
  research_question,
  as_of,
  claims: [
    {
      claim_id,
      claim_text,
      claim_type,
      decision_consequence,
      version,
      geography,
      language,
      required_source_roles[],
      facets[],
      counterevidence_paths[],
      status
    }
  ],
  query_plan_hash
}
```

建议的 `claim_type`：`definition`、`historical_fact`、`measurement`、`causal_or_impact`、`comparison`、`legal_or_policy_status`、`uncertainty`。`decision_consequence` 只帮助 caller 排序高影响 claim，不建议在 v1 设 universal numeric weight。

### 3.2 Source-role worksheet

对每个 claim 建立一行或一个小表，**proposed / unvalidated**：

| Field | caller 需要回答的问题 |
|---|---|
| `claim_id` | 哪一个 material claim？ |
| `claim_text` | 可单独被 evidence 支持或反驳吗？ |
| `preferred_roles` | 需要 `primary-record`、`primary-method`、`primary-data`、replication、commentary 或 counterevidence？ |
| `facets` | claim 的独立子问题/intent 是什么？ |
| `required_directness` | version、population、jurisdiction、outcome 是否匹配？ |
| `query_families_run` | definition/primary、measurement、counterevidence、version、language/modality 哪些已运行？ |
| `candidate_source_groups` | 可能有多少 ownership/provenance clusters？是否只是 host count？ |
| `read_status` | snippet、abstract、full、section-only、OCR partial、truncated、unavailable？ |
| `supports_or_contradicts` | evidence 是 `supports`、`contradicts` 还是 `context`？ |
| `unresolved_gaps` | access、version、language/geography、method、independence、counterevidence？ |
| `stop_reason` | 为什么停止，剩余 gap 如何披露？ |

不要把 `source_count` 作为 pass condition。一个 official legal text 可以充分回答 wording，但不能单独证明 policy effect；一个 benchmark 可以充分回答指定 workload observation，但不能证明 universal performance。

### 3.3 Query family vocabulary

以下是 caller 的规划语言，Search server 不自动扩展：

| `family` | 目标 | 示例模板 |
|---|---|---|
| `definition_primary` | owning source、规范、release、原始记录 | `site:official-domain exact term specification/release/notice` |
| `direct_evidence` | dataset、test、benchmark、filing、transcript、source | `exact version + benchmark/dataset/filing/transcript` |
| `counterevidence` | limitation、failure、critique、negative result、retraction | `term + limitation/issue/critique/failure/retraction` |
| `independent_corroboration` | 不同 provenance 的 institution/region/dataset | `claim/event + second institution/region/dataset` |
| `version_recency` | superseded、effective、amended、updated | `term + version/date/effective/amended` |
| `language_geography` | locale、native-language、jurisdiction gap | `native-language term + country/region` |
| `modality` | PDF、registry、image、archive、source code | `title/identifier + PDF/registry/archive/source` |
| `operational_failure` | API limit、unsupported、error、block | `product/version + error/limit/unsupported/issue` |

建议先用 `definition_primary` + `direct_evidence` 建 candidate pool，再只针对未覆盖 facet、独立性不足、反例不足、版本过期、语言/地区缺口或 modality 缺口追加 query。不要为了增加 URL 数而无限 synonym expansion。

## 4. Explicit Google-only bounded Search

### 4.1 Request policy

每次 request 使用 caller 明确填写的：

```text
route = "searxng"
backend = "google"
engine = "google"
```

server 不：

- 把 Google-only failure 静默切换到其他 engine/provider；
- 把一个混合自然语言研究问题自行拆成 query；
- 改写 query、做敏感信息脱敏或猜测 caller 语义；
- 读取候选 URL body；
- 根据 Search score 判断 source authority/truth；
- 自动把 partial result 丢弃；
- 默认 retry。

SearXNG Search API 的 `language`、`time_range`、`safesearch` 等参数是 engine/instance-dependent；Google adapter source snapshot 还显示 `week` mapping，不能把它写成 generic Search API guarantee。[S1][S2] 所以 response 必须同时保留 requested/effective/filter support。

### 4.2 Bounded batches

建议采用 **small bounded batches**，但具体数字属于 pilot configuration，不是 accepted quota。可以从以下未验证配置开始比较：

```text
pilot_bound_A:
  max_queries_per_batch = 4
  max_pages_per_query = 1
  max_results_per_query = 10

pilot_bound_B:
  max_queries_per_batch = 8
  max_pages_per_query = 2
  max_results_per_query = 20
```

以上仅用于 G2/G3 实验；不能从这两个 configuration 推出最终 default。评测应比较 facet coverage、new source-group rate、duplicate rate、partial rate、latency 和 context growth，再决定是否需要不同 report type 的 bounds。任何 deadline、page cap、result cap、context cap 都必须标成 proposed，并随实验 version 保存。

Batch 的核心语义：

- 每个 query 有 `query_id`、原文 query、facet/family metadata 和独立 status；
- 一条 query timeout/CAPTCHA 不抹掉其他 query 的结果；
- top-level `partial=true` 表示至少一个 query 未完整完成，不表示所有结果不可用；
- caller 想 retry 时建立新的 `attempt_id`/`batch_id`，不覆盖原失败；
- 每一页只在预期可能带来新 facet、新 source group 或 high-value primary candidate 时请求；
- page continuation 是 live SERP best effort，不是 immutable snapshot。

### 4.3 Candidate triage without body reads

Search response 只用于 triage：

1. 保存 `url_original`、title、snippet、page/position、query provenance、requested/effective filter 和 upstream state。
2. 运行 conservative strict URL normalization；保留原始 URL，不以 aggressive canonicalization 删除 query semantics。
3. 标记候选可能的 `source_role`、facet、version/date 和 ownership hypothesis；这些都不是正文证据。
4. 选择 pivotal candidates 后调用 `web_read`，把 support/contradiction/locator 写入 caller evidence matrix。
5. Search `rank`、`position_in_page` 和可选 `aggregator_score` 只影响 triage 顺序，不进入 truth/reliability score。

SearXNG 官方 source 的 `score` 是 aggregation mechanics；Google 官方也说明排序会受 context、location、language、device、time 和多系统影响。[S3][S4][S5] 因此建议优先返回 `position_in_page`；若保留 score，应重命名并明确 basis/version。

## 5. Proposed Search request/response shape

以下是用于设计讨论的 schema 示例，**proposed / unvalidated**。它不是已实现 MCP tool contract。

### 5.1 Request

```json
{
  "batch_id": "batch-2026-09-10-001",
  "attempt_id": "attempt-01",
  "route": "searxng",
  "backend": "google",
  "engine": "google",
  "query_plan_hash": "sha256:...",
  "queries": [
    {
      "query_id": "q-c1-primary",
      "query": "site:official.example exact term specification",
      "claim_id": "C1",
      "facet_id": "definition",
      "query_family": "definition_primary",
      "evidence_goal": "owning_source",
      "language": "en",
      "locale": "en-US",
      "time_range": null,
      "domains": ["official.example"],
      "pageno": 1
    },
    {
      "query_id": "q-c1-counter",
      "query": "exact term limitation failure",
      "claim_id": "C1",
      "facet_id": "limitations",
      "query_family": "counterevidence",
      "evidence_goal": "counterevidence",
      "language": "en",
      "locale": "en-US",
      "time_range": null,
      "domains": [],
      "pageno": 1
    }
  ],
  "bounds": {
    "max_queries": 8,
    "max_pages_per_query": 2,
    "max_results_per_query": 20,
    "deadline_ms": null
  }
}
```

`max_*` 数字仅用于 pilot experiment。`domains` 的 syntax mapping 必须由 adapter contract 验证；不能假设跨 engine/query syntax 一致。`continuation_token` 若使用必须 opaque，caller 不解析其内部。

`claim_id`、`facet_id`、`query_family`、`evidence_goal` 和 `query_plan_hash` 是 caller-only 的 planning metadata：server 只透传并原样回显，用于 caller 的 evidence matrix 对账，不解析、不校验语义，也不据此改写 query 或安排执行顺序。transport 真正需要的输入只有 `route`、`backend`/`engine`、`query`、requested filters 和 `pageno`；MCP server 不承载 claim planner。

### 5.2 Response

```json
{
  "batch_id": "batch-2026-09-10-001",
  "attempt_id": "attempt-01",
  "route": "searxng",
  "backend": "google",
  "engine": "google",
  "status": "partial",
  "partial": true,
  "queries": [
    {
      "query_id": "q-c1-primary",
      "status": "complete",
      "requested": {
        "query": "site:official.example exact term specification",
        "language": "en",
        "locale": "en-US",
        "time_range": null,
        "pageno": 1
      },
      "effective": {
        "engine": "google",
        "filter_support": {
          "language": "unknown",
          "time_range": "unsupported",
          "safesearch": "unknown"
        }
      },
      "results": [
        {
          "result_id": "r-01",
          "url_original": "https://official.example/spec?id=1",
          "title": "Specification",
          "snippet": "...",
          "position_in_page": 1,
          "derived_rank": 1,
          "retrieved_at": "2026-09-10T00:00:00Z",
          "aggregator_score": null,
          "score_basis": null,
          "canonicalization": {
            "strict_key": "https://official.example/spec?id=1",
            "semantic_key": null,
            "declared_canonical_url": null,
            "evidence": []
          },
          "source_identity": {
            "ownership_group_id": null,
            "independence_status": "unknown",
            "confidence": null,
            "basis": []
          }
        }
      ],
      "continuation": {
        "current_page": 1,
        "next_cursor": "opaque",
        "drift_status": "unknown"
      },
      "observation": {
        "instance": {
          "transport_status": "ok",
          "instance_http_status": 200,
          "observed_at": "2026-09-10T00:00:00Z",
          "instance_request_count": 1
        },
        "engine": {
          "engine": "google",
          "state": "ok",
          "state_basis": "results_present_and_engine_not_listed_in_unresponsive_engines"
        },
        "upstream": {
          "upstream_http_status": null,
          "upstream_request_id": null,
          "upstream_request_count": null,
          "evidence_status": "not_observed",
          "observation_source": "searxng_json_response"
        },
        "retry_performed": false
      },
      "warnings": []
    },
    {
      "query_id": "q-c1-counter",
      "status": "failed",
      "requested": {
        "query": "exact term limitation failure",
        "pageno": 1
      },
      "results": [],
      "observation": {
        "instance": {
          "transport_status": "ok",
          "instance_http_status": 200,
          "observed_at": "2026-09-10T00:00:02Z",
          "instance_request_count": 1
        },
        "engine": {
          "engine": "google",
          "state": "suspended_or_rate_limited",
          "state_basis": "unresponsive_engines: [\"google\", \"Suspended: too many requests\"]"
        },
        "upstream": {
          "upstream_http_status": null,
          "upstream_request_id": null,
          "upstream_request_count": null,
          "evidence_status": "not_observed",
          "observation_source": "searxng_json_response"
        },
        "retry_performed": false
      },
      "warnings": ["No implicit fallback or retry was performed."]
    }
  ],
  "warnings": []
}
```

这个失败示例刻意对应 prototype 已经观察到的形态：本地 SearXNG instance 返回 HTTP 200，JSON 的 `unresponsive_engines` 报告 engine 被 suspend；SearXNG JSON 并没有透传 Google 的原始 HTTP status，也不返回 upstream request id，所以这两个字段为 `null`，`evidence_status=not_observed`。示例中的第一条 query 成功、第二条失败，因此顶层 `partial=true` 与 per-query `status` 一致。

### 5.3 Field semantics

- `position_in_page` 是 adapter 返回的 page-local ordering；`derived_rank` 只有 page size/offset 确认时才计算。
- `aggregator_score` 若真实执行并返回，必须带 `score_basis` / `score_version`；它不是 relevance probability、authority、source reliability 或 truth score。
- `requested` 与 `effective.filter_support` 分离，避免回显输入被误读为 filter actually applied。
- `observation` 分三个层级，各自只记录本层实际观察到的事实：
  - `instance`：本地 SearXNG instance 的 transport/HTTP 观测。`transport_status` 区分 `ok`、`timeout`、`transport_error`（例如 `RemoteDisconnected`，此时 `instance_http_status=null`）、`format_disabled`（instance 未启用 JSON 时的 403）；`instance_http_status` 是 adapter 真正收到的状态码。
  - `engine`：从 SearXNG JSON 的 `unresponsive_engines`、结果集和解析结果分类得到的 engine state，至少区分 `ok`、`empty_or_parse_failure`、`suspended_or_rate_limited`、`captcha_or_blocked`、`timeout`、`unknown_error`；`state_basis` 记录分类依据。`empty_or_parse_failure` 表示本地拿到 200 但没有可解析结果，不能当作 upstream 已确认的空结果集。
  - `upstream`：只有 instance 明确透传 Google 侧 status、request id 或请求计数时才填写；否则一律 `null`，`evidence_status=not_observed`。`observation_source` 说明这些字段来自哪一层证据（JSON response、instance log、trace 等）。
- `instance_request_count` 是 adapter 向 instance 发出的请求数；`upstream_request_count` 只有在 instance 日志或 trace 可观测时才填写。server 默认不 retry 并不证明 upstream 只被访问了一次——instance 内部的 redirect、engine 重试或其他操作可能产生额外 upstream 请求。
- `retry_performed=false` 是 v1 default；retry 只能由 caller 以新 attempt 发起。
- `next_cursor` 若存在，绑定 route/backend/engine/normalized query/filter/page/adapter context，但只能表达 continuation hint；不能承诺相同 candidate set。

## 6. URL identity and source grouping

### 6.1 Three URL layers

RFC 3986 说明 query 是非层级数据，URI equivalence 依赖 application semantics；WHATWG `rel=canonical` 只是 preferred URL/duplicate-content hint，不是 general ownership/equivalence proof。[S6][S7]

建议保存三层：

1. `strict_key`：做保守 generic normalization，用于去重；
2. `semantic_key`：只有在站点规则有 evidence 时才应用 query parameter semantics；默认保留 query、重复参数、空值和顺序；
3. `observed_equivalence`：redirect chain、representation hash、publisher statement、declared canonical 或 repeated same content 等 observed basis。

永远保留 `url_original`，不要用单个 aggressive `canonical_url` 覆盖 provenance。

Search 阶段不会为了去重而访问候选 URL：redirect chain、`rel=canonical`、representation hash 这些 `observed_equivalence` 只能来自两种途径——已返回的 SERP metadata（若 upstream 提供），或 caller 之后显式调用 `web_read` 得到的观测。Search response 中没有观测到的值一律为 `null`/`unknown`，不做推断。

### 6.2 Source identity is a hypothesis

建议候选字段：

```text
source_identity = {
  url_authority,          # RFC 3986 意义上的 URI authority（host[:port]），仅是 URL 组成部分
  ownership_group_id?,
  independence_status: unknown | tentative_related | tentative_same_publisher,
  confidence?,
  basis[]
}
```

`url_authority` 只是 URI 的 authority component，与来源的 epistemic authority 无关；后者的 appraisal 属于 caller 的 evidence matrix（`authority_basis`），Search 不输出这类判断。

`same_registrable_domain` 只能是低置信度 clue，不等于 same owner；跨域 mirror/syndication 也不一定能靠 domain suffix 发现。后续可用 Public Suffix/metadata 作为 candidate clue，但 library choice、license、版本、precision 和 adjudication protocol 尚未验证。

报告应分别统计：

- `unique_strict_url_count`；
- `unique_host_count`；
- `tentative_source_group_count`；
- `independence_unknown_rate`；
- `same_group_repeat_rate`。

它们不能直接转为 source reliability。高影响 claim 的 grouping 需要 `web_read` 复核 publisher/provenance evidence。

## 7. Pagination, capability negotiation and live drift

### 7.1 Capability negotiation

因为 API、adapter、instance 和 live upstream 的能力可能不同，建议每 query 返回三层信息：

```text
requested: caller requested language/time/country/safesearch/page
configured: instance/adapter declared support, if observable
effective: observed application/unknown/unsupported + warnings
```

`effective=applied` 只表示 adapter/instance 采用了该 request mapping，不代表正文语言或日期已满足；正文 publish date/language 需要 `web_read`/agent judgment。

### 7.2 Continuation caveat

SearXNG Google adapter 使用 page offset；Google 官方说明 result set 会随 context、time、index 和 ranking systems 变化。[S2][S4][S5] 所以：

- page number 不是 immutable cursor；
- `next_cursor` 必须 opaque；
- continuation response 应记录 `current_page`、`retrieved_at`、adapter/instance version（若可得）和 `drift_status`；
- page 2 可能重复、跳过或重排，不能默认“更完整”；
- 如 drift 或 failure 显著，caller 可新建 attempt，不静默重试旧失败。

建议的 continuation binding（**proposed / unvalidated**）：

```text
hash(
  route, backend, engine,
  normalized_query,
  language, locale, time_range,
  domains, safesearch,
  page_size_hint,
  adapter_version
)
```

这只是 server implementation option；是否使用 hash/signature/database handle、cursor TTL、snapshot retention 和 stale behavior，需在 G3/G7 实验后决定。

## 8. Agent-owned stop / continue policy

### 8.1 Continue when

caller 应继续 Search 或 `web_read`，当任一高影响条件成立：

- material claim 只有 snippet、summary、commentary 或 abstract，没有可复核 direct source；
- supporting pages 可能全属同一 provenance cluster；
- contradiction 尚未定位到 version、date、population、jurisdiction、measurement 或 definition difference；
- source stale/superseded，或 effective date/version 不符合问题；
- language/geography 与问题不匹配；
- JS/PDF/scanned/OCR/image modality 尚未读取，且可能改变 claim；
- pivotal performance/behavior 只有 maintainer/vendor assertion 或一次不可复现 measurement；
- funding/ownership/sponsor role/data provenance 可能影响解读但未披露；
- access failure 可能造成 systematic coverage gap。

### 8.2 Stop with explicit gap

caller 可以停止，当：

1. 所有 material claims 都有适配的 source role 或明确无法取得的 direct source；
2. support/contradiction/context 关系、locator、retrieved time、version/locale 和 access state 已记录；
3. 适当的 counterevidence、version、language/geography 和 modality query 已执行，或跳过理由已记下；
4. 继续 Search 的 candidates 只重复已有 provenance groups 或背景 commentary；
5. 剩余 gap 已标成 `unresolved`、`unavailable`、`stale` 或 `coverage_gap`。

该 stop 规则不证明 claim truth，只表示相对于当前 scope/access/time budget 的 evidence state 已解释。

### 8.3 Source-coverage worksheet example

```text
claim_id: C4
claim_text: "截至 as_of date，某 policy obligation 对某 jurisdiction 的 deployer 已 effective"
claim_type: legal_or_policy_status
as_of: 2026-09-10
jurisdiction: <explicit>
preferred_roles: [primary-record, implementation-guidance, counterevidence]
query_families_run:
  - definition_primary
  - version_recency
  - counterevidence
  - language_geography
supporting_evidence:
  - source_id: src-law-01
    role: primary-record
    access_status: full
    support: supports
    locator: <quote/position>
    effective_date: <observed>
contradicting_or_context:
  - source_id: src-court-01
    role: counterevidence
    access_status: section_only
    support: contradicts
unresolved_gaps:
  - implementation practice outside official guidance
provenance_clusters:
  - cluster-01: official record
  - cluster-02: syndicated commentary (not independent)
status: supported_with_gap
stop_reason: material wording/effective date resolved; practice evidence remains bounded
```

## 9. Integration with standalone `web_read`

Search 与 `web_read` 的组合必须保持单向、可审计：

```text
Search candidate
  -> caller selects source
  -> web_read(requested_url or direct URL)
  -> metadata + outline + bounded original text
  -> section/position/keyword continuation
  -> caller evidence matrix
```

`web_read` proposed obligations：

- 不要求 URL 必须来自 Search；
- 返回 `requested_url`、`final_url`、redirect chain、retrieved time、content type、publisher/version metadata（若可得）；
- 返回 `coverage`、`truncated`、`next_cursor`、unavailable reason、JS/PDF/OCR method 和 warnings；
- 尽量抽取完整主要正文，输出结构化 Markdown；不把 LLM summary 当作原文；
- HTML/JS/PDF/OCR/image representation 保留 lineage 和 block/page/quote locator；
- cursor 绑定 representation/snapshot/extraction config；source 改变时标记 stale/new snapshot，不把旧 offset 静默指向新文本；
- 对 scanned PDF、web text image、standalone image 保存 OCR state/boxes/confidence/asset relation；OCR confidence 不进入 truth score；
- 不做最终 synthesis、authority judgment、independence judgment 或 claim stop。

format-fidelity 专题研究（[内部 memo](../research/2026-09-10-source-disclosure/format-fidelity.md)，含独立 [verification](../research/2026-09-10-source-disclosure/format-fidelity-verification.md)）支持：单一 converter 不应被承诺为所有 HTML/JS/PDF/OCR 无损；建议 raw-first、native text before OCR、browser observable fallback、分层 representation 和 coverage/failure 分离。目标 Windows/CPU、license、真实 corpus fidelity 和 MCP continuation 仍是 open validation；已有 [#7 constrained smoke](https://github.com/EllisYuan/web_search/issues/7#issuecomment-5599723724) 只证明功能路径曾运行。[S16][S17][S18]

## 10. Experimental worklist and decision gates

以下不是 implementation tickets，而是 **proposed validation gates**。每一 gate 只支持其测试 scope 内的 observation。

| Gate | Controlled study | Record | Gate question |
|---|---|---|---|
| G1 | Google adapter capability matrix：少量 query 测 locale/language/country、time filters、page、empty、CAPTCHA/block、format disabled、timeout/parse failure | requested/effective/filter support、instance/adapter/version、upstream state | schema 是否需要 capability mismatch 与 per-query error state |
| G2 | Query-family study：`primary + gap/counterevidence` vs synonym-only baseline | facet coverage、new-group rate、duplicate rate、partial rate、query count/context cost | query planning 是否增加 evidence coverage，而非只增加 URLs |
| G3 | Pagination drift：same query repeated page 1；page 1/page 2 boundary；short/cross-time attempts | overlap/skip/rank drift、page state、CAPTCHA/timeout、locale/time/instance | continuation 是否只能 best-effort；page bound/提示如何选 |
| G4 | URL/source adversarial fixtures：redirect/canonical/query semantics/mirror/syndication/hosted platform | false merge、unknown rate、human adjudication agreement | 是否能输出 tentative source group 而不伪造 independence |
| G5 | Judged facet pool：assessor 标 facet/subtopic、必要时进入 web_read | qrels、unjudged、pool denominator、alpha/metric version、adjudication work | upstream order/离线 rerank 是否增加 facet coverage；rerank 是否只留 caller-side |
| G6 | Access-bias sampling：按 report type/language/geography/modality 记录 access failure | not found/not indexed/access denied/parse/OCR partial/truncated distribution | coverage disclosure minimum fields，是否存在方向性 missingness |
| G7 | Target MCP host conformance：tool discovery、batch partial、cursor/stale、resource limits | transport/protocol/capability observations | schema/continuation 是否适合 target host；不从 generic docs 推断 |
| G8 | License/dependency inventory：pinned SearXNG/extractors/OCR/models/runtime | exact version/license/source/terms | 免费/开源和最终 distribution model 是否满足；不把 repo license 等同 models/dependencies license |

### 10.1 Decision rules

- G1 未完成前，不把 `language`/`time_range`/`safesearch` 的回显当作 applied guarantee。
- G2/G4/G6 未完成前，不批准 universal source quota、ownership threshold 或 numeric truth score。
- G3/G7 未完成前，不把 `pageno`/opaque token 描述成 immutable snapshot cursor。
- G5 只能批准 offline evaluation baseline；不自动批准 Search server reranking。MMR/xQuAD primary text 在本轮不可读，不能引入论文参数或 superiority claim。[S8]
- G8 未完成前，不把任何具体 library/model/binary 写成 approved dependency；尤其 PyMuPDF AGPL/commercial、Docling/PaddleOCR models/dependencies、SearXNG target release 均需单独核对。
- 任何实验结果都必须带 query set、pool、locale、time window、adapter/instance、hardware/config 和 access limitations；不能变成跨环境 SLA。
- #6 不在本设计中声明 resolved；本方案只是为后续验证提供 Search-side research strategy。

## 11. Chronology and ADR alignment

### 11.1 Earlier retry wording versus later ADR

较早 scope text 里出现过”有限自动重试”，2026-09-10 的 [ADR-0004](../adr/0004-v1-search-read-boundary.md) 已将其改为 v1 **默认不 automatic retry**，retry 由 caller 以新的可审计 attempt 显式发起。本文其余章节（§4.1、§5 的 JSON 示例）均按此决策撰写；这是 chronology 记录，不是重新打开 ADR。

### 11.2 No server-side deep research

本设计没有新增 `deep_search`，也没有把 query planning、source selection、counterevidence、synthesis 或 stop judgement 塞进 Search server。Search Batch 只是 bounded execution primitive；caller agent 通过多轮调用实现 Deep Research。

### 11.3 Query disclosure ownership

MCP 仅做 basic validation；query 的外发适宜性、敏感信息边界和 query rewriting 由 caller agent 负责。Search response 应记录 query/attempt metadata 以便审计，但不应暗中修改 query。

## 12. Adversarial cases and expected behavior

| Case | Incorrect interpretation to avoid | Proposed observable behavior |
|---|---|---|
| Google returns only large sites | “small sites do not exist” / “coverage sufficient” | source-group and site-diversity notes；追加 official/entity-specific query；不声称 Web recall |
| Same press release syndicated | “many independent sources” | tentative related cluster；保留 each URL/position，但不增加 independent count |
| `rel=canonical` differs | “URLs permanently equivalent” | 保留 `url_original` + declared canonical + evidence；不静默删除 |
| Query parameters stripped | page/entity/locale semantics lost | 默认 preserve query；site-specific rule must be evidenced/versioned |
| Page 2 overlaps/skips | “pagination complete” or “provider bug” | `drift_status` + overlap/skip evidence；best-effort continuation |
| Language filter mixed | “filter failed” or “all results same language” | requested/effective/judged language 分离 |
| Date filter hits old page | “document published inside window” | only upstream filter claim；正文 date by web_read |
| CAPTCHA/429 | “retry transparently” | per-query explicit failure；default no retry；new attempt if caller chooses |
| High aggregator score | “more reliable/correct” | expose score basis only；not truth/authority |
| qrel misses result | “result irrelevant” | report unjudged rate；expand pool or sensitivity analysis |
| OCR returns no text | “image has no text” | `ocr_low_signal`/partial state；retain image; do not infer absence |
| JS render succeeds | “page semantics complete” | rendered method + coverage warning；record actual DOM/network/download scope |

## 13. Open high-impact uncertainties

1. **Target SearXNG release/instance variance**：当前 primary verification 固定在 commit `3fdc6d753a339b5f4a7dc5842c94c0d8324726f1`，与免费 Search prototype 实际运行的 image revision 一致；但 production 部署版本尚未选定，也没有验证目标 instance 的 format、timeout、locale、Google parser 和 upstream policy。
2. **Google-only coverage**：中文、English、mixed-language、news、technical docs、policy、regional queries 的 domain coverage、freshness、duplicate、block 和 filter precision 未测。
3. **Source independence**：没有跨领域 validated provenance clustering algorithm、ownership metadata choice 或 adjudication protocol。
4. **Report-type transfer**：Cochrane/PRISMA-S/GRADE/National Academies 的最小适用概念需要真实 claim sets 验证；不能自动形成 universal rubric。
5. **Missing-not-at-random**：paywall、regional block、JS-only、scanned PDF、OCR failure、language barrier 对不同 source role/region/topic 的方向性影响未测。
6. **Metadata availability**：HTML/JS/PDF/scanned PDF/web image/standalone image 能否稳定提供 publisher/version/date/page/block/quote locator 未测。
7. **Continuation identity**：cursor TTL、snapshot retention、content hash、extractor version、source mutation 和 target MCP host semantics 未测。
8. **Reranking**：MMR/xQuAD 是否只作为 caller/offline baseline、是否需要 text similarity/facet classifier、是否提升 judged pool metrics 未测；本设计不批准 server-side reranking。
9. **Retention and terms**：raw SERP metadata、HTML/PDF/image/OCR artifact 的 retention、版权、ToS、robots 与公开分享边界未完成法律/产品审查。
10. **No numeric acceptance yet**：batch/page/result/deadline/context budget、stop threshold、source-group confidence 和 metrics denominator 都需预注册 validation；本设计不提供 accepted numbers。

## 14. Primary source ledger

访问日期均为 **2026-09-10**；本设计引用的原始来源如下。内部 ADR/研究报告用于项目边界与拟议映射，不替代这些 primary sources。

| ID | Owning source | URL | Access state | Supporting fact / limit |
|---|---|---|---|---|
| S1 | SearXNG maintainers, Search API docs | https://docs.searxng.org/dev/search_api.html | Full | `q`、`language`、`pageno`、`time_range`、`format`、`safesearch`；engine support caveat；format may be disabled/403 |
| S2 | SearXNG maintainers, Google engine docs/source | https://docs.searxng.org/dev/engines/online/google.html；https://raw.githubusercontent.com/searxng/searxng/3fdc6d753a339b5f4a7dc5842c94c0d8324726f1/searx/engines/google.py | Full source at pinned commit `3fdc6d753a339b5f4a7dc5842c94c0d8324726f1` | `max_page=50`、10-result offset、locale/time/SafeSearch mapping、CAPTCHA/`sorry` detection；commit is not selected project release |
| S3 | SearXNG maintainers, result aggregation source | https://raw.githubusercontent.com/searxng/searxng/3fdc6d753a339b5f4a7dc5842c94c0d8324726f1/searx/results.py | Full source at same commit | score mechanics/duplicate merge/grouping；supports `aggregator_score` caveat, not calibrated relevance |
| S4 | Google Search Central, How Search works | https://developers.google.com/search/docs/fundamentals/how-search-works | Full | context/location/language/device signals；indexing not guaranteed；no project coverage SLA |
| S5 | Google Search Central + Google Search Help | https://developers.google.com/search/docs/appearance/ranking-systems-guide；https://support.google.com/websearch/answer/12412910?hl=en | Full | freshness/dedup/site diversity；time/context/personalization differences；no stable ordering SLA |
| S6 | IETF, RFC 3986 | https://www.rfc-editor.org/rfc/rfc3986 | Full | query semantics/application-dependent URI equivalence and normalization |
| S7 | WHATWG, HTML Standard canonical link type | https://html.spec.whatwg.org/multipage/links.html#link-type-canonical | Full | `rel=canonical` preferred URL/duplicate hint, not ownership/equivalence proof |
| S8 | Carbonell & Goldstein; Santos et al. | https://doi.org/10.1145/290941.291025；https://www.cs.cmu.edu/afs/cs/Web/People/jgc/publication/MMR_DiversityBased_Reranking_SIGIR_1998.pdf；https://terrierteam.dcs.gla.ac.uk/publications/ecir2010_rodrygo_div.pdf | PDFs obtained but binary/unreadable in this pass | conservative relevance/novelty/aspect abstraction only；no formula/parameter/experiment claim |
| S9 | NIST TREC Web Track | https://trec.nist.gov/data/web09.html；https://trec.nist.gov/data/web/09/ndeval.c | Full HTML/source | qrels/`ndeval.c`，alpha-nDCG/IA-P and unjudged/denominator caveats；not project assessor protocol |
| S10 | Cochrane Handbook Chapter 4 | https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-04 | Partial official page | multiple source types/high sensitivity/grey literature/uncertain unpublished evidence；healthcare scope/truncation |
| S11 | Rethlefsen et al., PRISMA-S | https://pmc.ncbi.nlm.nih.gov/articles/PMC7839230/；https://doi.org/10.1186/s13643-020-01542-z | Full via PMC | 16 search reporting items；“guide reporting, not conduct”；not quality score |
| S12 | ACRL/ALA Framework | https://www.ala.org/acrl/standards/ilframework | Partial official page | contextual authority; not calibrated ranking |
| S13 | GRADE Working Group 2004 | https://pmc.ncbi.nlm.nih.gov/articles/PMC428525/；https://doi.org/10.1136/bmj.328.7454.1490 | Full via PMC | quality of evidence dimensions/directness; healthcare scope |
| S14 | W3C PROV-DM | https://www.w3.org/TR/prov-dm/ | Full | provenance entities/activities/agents/derivation; no truth/quality inference |
| S15 | W3C Web Annotation | https://www.w3.org/TR/annotation-model/ | Full | quote/position/time selectors; no immutable identity/authenticity |
| S16 | pypdf extraction docs | https://pypdf.readthedocs.io/en/stable/user/extract-text.html | Full | PDF semantic/table/scan limitations; OCR requirement |
| S17 | Playwright intro/network/download docs | https://playwright.dev/python/docs/intro；https://playwright.dev/docs/network；https://playwright.dev/docs/downloads | Full | JS/browser/network/download capability; routing not isolation; service-worker caveat |
| S18 | Tesseract repository/CLI docs | https://github.com/tesseract-ocr/tesseract；https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html | Full | OCR formats/geometry/confidence; confidence not semantic truth; no target benchmark |

## 15. Final proposed contract boundary

建议将 v1 Search 的 promise 收窄为：

- caller-selected Google attempt；
- bounded, query-grouped candidate discovery；
- observable requested/effective filter state；
- preserved upstream/page-local order；
- explicit per-query and top-level partial/failure state；
- opaque best-effort continuation hint；
- no body read, no synthesis, no truth/authority score, no implicit fallback/retry。

把“研究型报告是否达到证据充分”留给 caller agent 的 claim/evidence loop；把“来源正文、locator、representation 和继续读取”留给 standalone `web_read`。这使 Search 成为可审计的 discovery primitive，而不是隐式的 Deep Research facade。
