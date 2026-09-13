---
title: 研究型报告的 Source 策略
status: researched
research_date: 2026-09-10
implementation_status: proposed / unvalidated
runtime_experiments: none
scope: factual/technical investigation、comparative evaluation、current events/policy、academic/systematic review
---

# 研究型报告的 Source 策略

> 本报告回答：不同类型的研究报告实际需要什么 Source，如何把这些需求转成可审计的 Search strategy。它不是 `deep_search` tool 的设计，也不是 production contract。除明确标为 **Fact** 的内容外，新增机制、字段、schema、数字、stop criteria、评测指标和组件选择均为 **Proposed / unvalidated**。本轮没有新增 runtime experiment：没有新的 Search 调用、目标 SearXNG instance 接入、网页正文读取、OCR、MCP conformance 或 performance benchmark。项目已有的免费 Search smoke（[prototype 报告](../../prototypes/free-search/REPORT.md)）和 CPU-only Web Read constrained smoke（[#7 resolution](https://github.com/EllisYuan/web_search/issues/7#issuecomment-5599723724)）只作为既有观测引用，不代表本轮复测。

## 1. Executive conclusions

1. **Source sufficiency is claim-level closure, not URL count.** 一个 report 是否有足够 Source，取决于每个 material claim 是否有匹配的 direct evidence、可追溯 provenance、适当的 source role、主动的 counterevidence，以及已披露的 recency/version、language/geography、access 和 modality gaps。Cochrane 支持不要依赖单一 database，但它的 healthcare review 语境不能直接成为所有 report 的 universal checklist。[S1]
2. **Search transparency is not evidence quality.** PRISMA-S 的核心贡献是记录 source/platform、完整 query、limits、日期、records 和 deduplication；它明确用于 reporting，不是检索质量或 truth 的评分器。[S2]
3. **Authority and directness are contextual.** ACRL 说明 authority 取决于 information need 和 community；GRADE 2004 则把 `study design`、`study quality`、`consistency`、`directness` 分开，并区分 `quality of evidence` 与 `strength of recommendations`。可借用这种拆分，不能把医疗框架或“官方优先”规则原样迁移到所有问题。[S3][S4]
4. **Primary does not mean sufficient.** 官方规范通常足以回答“定义/版本/生效文本是什么”，但不能单独证明 latency、quality、coverage、causal effect 或 broad generalization。单次本地 run 也只能证明该 run 的 observation，不能外推 universal benchmark。这是对 GRADE 拆分 `directness` 与 `study design` 的 Interpretation，并与本项目 prototype 报告自身的口径一致，不是某一 healthcare 来源对 engineering evidence 的直接规定。[S4]
5. **Independence cannot be inferred from domains.** 十个域名可能共同复制一个 press release、wire、dataset 或 quote-chain。`domain_count`、`host_count` 和 SERP result count 只能是 discovery metadata，不能是 independent corroboration。[S6][S7]
6. **Google-only v1 can provide observable candidates, not Web recall.** SearXNG 的 Google adapter 有分页、locale/time/SafeSearch mapping 和 upstream failure signals，但这些是 adapter capability，不是 coverage、过滤 precision、稳定排序或 Google SLA。[S8][S9][S10]
7. **The concrete strategy should be agent-owned.** caller agent 先拆 `claim` 和 `facet`，再按 evidence gap 发出分组 query；Search 只返回候选 URL 与 SERP metadata；`web_read` 独立读取正文和 continuation。server 不规划 query、不读取正文、不综合答案、不生成 truth score。
8. **The most valuable evaluation target is coverage by facet and provenance, not raw result count.** 建议测 `pool-relative recall`、facet coverage、source-group coverage、duplicate/redundancy、pagination drift、partial rate 和 access status；不能声称 Web-wide recall。NIST `ndeval.c` 可作为多样性评测参考，但它的 qrel/pool/denominator 限制必须一并报告。[S11][S12]

## 2. Facts and evidence limits

### 2.1 Search breadth and reporting

**Fact.** Cochrane Handbook Chapter 4 的可见正文写明单一 MEDLINE search 不足，并强调按问题组合 databases、registries、grey literature、reference/citation checking；它还指出没有一种简单可靠的方法能发现所有未发表或终止研究。[S1] 这支持“按问题扩展 source type”，不支持固定的 universal URL quota。该页面在本轮存在截断，Cochrane 主要针对 healthcare intervention reviews。

**Fact.** PRISMA-S 提供 16 个 reporting items，覆盖 database/platform、完整 search strategy、limits、date、peer review、records、deduplication 和 supplementary searches，并明确“guide reporting, not conduct”。[S2] 因此记录 query 和 source metadata 是可审计性要求，不等于 retrieval quality 或 evidence truth。

**Fact.** National Academies Chapter 7 的可见内容支持报告 sources、last search date、eligibility、appraisal、synthesis、limitations、funding/sponsor role；页面末尾有截断，且语境是 healthcare systematic reviews。[S5]

### 2.2 Authority, quality, provenance

**Fact.** ACRL 的 “Authority Is Constructed and Contextual” 说明不同 community 可能承认不同 authority，合适的 authority 取决于 information need 与 context。[S3] 这不等于所有 source equally credible；它只反对脱离 claim type 的固定排名。

**Fact.** GRADE 2004 原文使用 `quality of evidence`，区分 `study design`、`study quality`、`consistency`、`directness`，并另行讨论 recommendation strength。[S4] 可借用“拆分判断维度”的结构，但不能把 healthcare 的 levels、downgrade/upgrade 规则直接迁移到 engineering/current-events report。

**Fact.** W3C PROV-DM 可表达 `Entity`、`Activity`、`Agent`、generation、usage、derivation 和 attribution。[S6] W3C Web Annotation 可用 `TextQuoteSelector` 的 `exact/prefix/suffix`、`TextPositionSelector` 的 zero-based `start/end` 和 `TimeState` 记录可复核 locator/state。[S7] 这些是 provenance/locator primitives，不是 source authenticity、authority、independence 或 truth proof；`content_hash` 是本项目 proposed 的 representation change-detection 字段。

**Interpretation.** 报告应把下列问题分开：

- Source 是否回答当前 claim（`relevance` / `directness`）；
- Source 对该类 claim 的能力、责任或方法位置（`authority_basis`）；
- Source 是否接近原始记录、数据、代码、规范或现场观察（`source_role`）；
- 谁产生、何时产生、经过哪些处理（`provenance`）；
- 是否与其他 evidence 独立（`provenance_cluster`，初期只能是 hypothesis）；
- 内容是否完整可访问、是否只读到摘要、snippet、OCR partial 或截断（`access_status`）；
- 是否有 counterevidence、版本冲突、地理/语言遗漏和 conflict-of-interest。

### 2.3 Search and ranking limits

**Fact.** SearXNG Search API 暴露 `q`、`language`、`pageno`、`time_range`、`format`、`safesearch` 等参数，但 `time_range` 和 SafeSearch 只对支持它们的 engine 生效，机器 format 也可能由 instance 禁用；通用 API 文档当前列出 `day`、`month`、`year`，Google adapter source 另有 `week` mapping。[S8][S9]

**Fact.** Google adapter source snapshot `3fdc6d753a339b5f4a7dc5842c94c0d8324726f1` 显示 `max_page = 50`、10-result page offset、locale/time/SafeSearch mapping 和 CAPTCHA/`sorry` detection；这只证明该 source snapshot 的实现，不是本项目已选 release 的 contract。[S9]

**Fact.** SearXNG 将自身定义为 metasearch engine；自建 instance 仍向 external services 发请求，upstream 可见 instance IP，CAPTCHA/block 可能减少结果。[S10] SearXNG `results.py` 的 `score` 由 engine weight、position、priority、duplicate merge 等 aggregation mechanics 形成，并可能经过 category/template/image grouping；它不是 calibrated relevance、authority 或 truth probability。[S14]

**Fact.** Google 官方说明 Search 使用许多 signals，结果可能受 location、language、device、time/context/personalization 影响，indexing 也不保证；ranking guide 说明 freshness、deduplication、site diversity 等系统。[S13][S15][S16] 因此 page number 不是 immutable snapshot cursor，跨时间翻页只能是 best-effort continuation。

### 2.4 Formats and access bias

**Fact.** pypdf 官方文档说明 PDF 通常缺少 paragraph/header/footer/table/caption 的 semantic layer，scanned PDF 需要 OCR；layout extraction 和 visitor callback 只是 approximation。[S18] Playwright 能执行 JS、观察 network/download，但官方文档不把 routing 说成 network isolation，service-worker request 还可能不出现在通常 route/events 中。[S19][S20] Tesseract 可返回 TSV/hOCR geometry/confidence，但 confidence 是 recognition signal，不是 semantic truth。[S21]

**Interpretation.** source coverage 必须把 modality 纳入，而非只记 URL：静态 HTML、JS-rendered page、born-digital/scanned PDF、web text image 和 standalone image 可能具有不同 metadata、locator 和 failure mode。`not found`、`not indexed`、`access denied`、`parse_failed`、`ocr_partial`、`truncated` 不能合并成“没有证据”。由于 paywall、地域 block、JS-only、scanned/image-only 和 language barrier 可能与主题/地区/机构相关，missingness 很可能是 **not missing at random**。

## 3. Report-type matrix

下表是 **proposed / unvalidated** 的 report-type matrix。它不是 hard checklist；跳过一类 Source 时，agent 应记录原因和残余 gap。

| Report type | Material claim examples | Preferred Source roles | Minimum evidence shape | Common false inference | Stop condition proposal |
|---|---|---|---|---|---|
| Factual / technical investigation | API definition、protocol、release、implementation limit、error semantics | `primary-spec`、maintainer docs/source/release、`primary-record`、reproduction、independent replication、issue/negative result | 版本/commit 可定位的 primary definition + direct behavior evidence；performance/quality 还需 controlled workload 或 independent observation | 官方 docs = actual performance；一次成功 run = general capability | definition/version claim 有 direct primary；behavior/performance claim 另有 workload/config/limits；remaining gaps explicit |
| Comparative evaluation | Windows CPU-only route A vs B、extractor fidelity、license/platform fit | 每个 candidate official docs/source/license；controlled comparison；independent benchmark/dataset；failure corpus；maintenance/license evidence | same corpus/hardware/config/stopping rule；保留 per-case failures，不把异设定合成总排名 | stars/marketing/一个样本或不同硬件的数字可直接比较 | comparison scope fixed；route × workload trade-offs visible；未测 modality/platform 不被写成 winner |
| Current events / policy | 某 jurisdiction 在 `as_of` date 的 effective obligation、事件状态 | original legal/official record；agency implementation guidance；court/filing/transcript；independent corroboration；counterparty/critique | jurisdiction + status/date fixed；区分 `proposed/enacted/effective/reported/confirmed/challenged`；保留 amendment/version | 首条新闻稿 = final legal fact；多个 syndication = independent sources | original record and effective date found or gap explicit；material contradiction resolved or marked contested |
| Academic / systematic review | 某方法整体 evidence、heterogeneity、publication bias | protocol/eligibility/analysis；multiple databases/registries/grey literature/citation chaining；primary studies；risk-of-bias/limitations；synthesis | reproducible search log；inclusion/exclusion；dedupe；study-level data/quality/directness；heterogeneity/update | paper count = evidence sufficiency；PRISMA-S = quality score | search boundary, included/excluded reasons, quality/heterogeneity and update status explainable |

### 3.1 Primary source 的 role-based 使用

建议不要使用二元规则 `primary = trustworthy` / `secondary = untrustworthy`，而使用 role：

- `primary-record`：法规、官方 filing、原始 transcript、原始 response；
- `primary-data`：dataset、measurement、实验结果、现场记录；
- `primary-method`：规范、论文方法、source code、protocol；
- `independent-replication`：不同作者/环境/数据的复现；
- `methodological-synthesis`：systematic review、方法综述、评测框架；
- `commentary/context`：解释、背景和二次报道；
- `counterevidence`：批评、失败结果、反例、amendment 或限制。

例如，maintainer release note 对“版本包含什么”是 primary，但对“性能是否提升”不是充分 evidence；systematic review 虽然是 secondary synthesis，却可能比单篇 primary study 更适合回答“整体 evidence pattern”。

## 4. Requirements: coverage versus count

### 4.1 Coverage worksheet

建议 caller agent 为每个 material claim 保持如下 worksheet；这只是 proposed working form，不是 server 自动评分：

| Field | 说明 |
|---|---|
| `claim_id` / `claim_text` | 可独立判断的 claim，避免一个 claim 混合多个事实 |
| `claim_type` | `definition`、`historical`、`measurement`、`causal`、`comparison`、`policy_status`、`uncertainty` |
| `decision_consequence` | claim 错误会改变什么决定；可用 `low/medium/high` 作为 caller-owned note，不设 universal weights |
| `as_of` / `version` / `jurisdiction` | 固定时点、版本、地区和语言边界 |
| `preferred_roles` | 需要 `primary-record`、`primary-method`、replication、counterevidence 等哪类 role |
| `facets` | claim 的子问题/意图；每个 facet 要有 query provenance |
| `supporting_evidence[]` | source、locator、quote、role、directness、access state |
| `counterevidence[]` | contrary query / failure / critique / alternate record |
| `provenance_clusters` | 共同 publisher、press release、dataset、quote-chain 等 hypothesis |
| `missingness` | access denied、not indexed、parse failed、OCR partial、truncated 等 |
| `status` | `open`、`supported`、`contested`、`context_only`、`unavailable`、`stale` |
| `stop_reason` | 为什么相对当前 scope/budget 停止，及未消除的 gap |

### 4.2 Why no universal source quotas

不建议在 v1 定义“每个 claim 至少 N 个 URL”或“每个 report 至少 M 个 domain”，原因是：

- 一份 authoritative legal text 可能足以确认“文本写了什么”，但不能确认 policy effect；
- 一个原始 benchmark 可能足以支持特定 workload observation，但不能支持 general performance claim；
- 10 个 syndicated pages 可能只有一个 provenance cluster；
- 高 consequence claim 需要不同 role 的 evidence，而低 consequence definition 不应被无意义的 URL 数拖慢；
- source 可访问性、语言、地区和 modality 差异使固定 count 产生 systematical bias。

如果 future validation 需要数字，应先建立真实 claim set、access-failure sample、ownership adjudication 和 assessor protocol，再预注册数字及其 scope。数字不能从本报告直接升级为 accepted product requirement。

## 5. Concrete Search strategy (agent-owned)

### Step 1: Claim map before URLs

caller agent 先将研究问题拆成 material claims，并标记 `claim_type`、consequence、`as_of`/version/geography/language、preferred source roles、directness 和 possible counterevidence。先处理会改变最终结论的 pivotal claims，再处理背景资料。

### Step 2: Query families by evidence gap

以下是 **proposed query-planning vocabulary**，不是 Search server 的自动 query expander：

| Query family | Evidence gap | Abstract template |
|---|---|---|
| `definition_primary` | owning source、定义、规范、原始记录 | `site:official-domain exact term specification/release/notice` |
| `direct_evidence` | data、test、code、document、measurement | `exact version + benchmark/dataset/filing/transcript` |
| `counterevidence` | limitation、critique、failure、negative result、retraction | `term + limitation/issue/critique/failure/retraction` |
| `independent_corroboration` | 不同 provenance 的 record/data/analysis | `claim/event + second institution/region/dataset` |
| `version_recency` | superseded、effective、amended、updated | `term + version/date/effective/amended` |
| `language_geography` | native-language、本地 jurisdiction、regional record | `native-language term + country/region` |
| `modality` | PDF、registry、image、archive、source code | `title/identifier + PDF/registry/archive/source` |
| `operational_failure` | API limits、errors、unsupported path、block | `product/version + error/limit/unsupported/issue` |

Query 要服务于未覆盖的 facet 或 evidence role，而不是为了增加结果数量。Search request 应保留原始 query、query family、route/backend、engine、执行时间和 status。SERP `rank` / `aggregator_score` 仅用于 triage。

### Step 3: Explicit Google-only Search Batch

v1 的推荐 route 是调用方显式选择的 `route=searxng`、`backend=google`；不隐式 fallback，不在一次 request 混入其他 upstream engine，不由 server 改写或脱敏 query。Search response 只返回 candidate URL/SERP metadata，不读取 body；正文由独立 `web_read` 读取。

建议的 **pilot bounds（proposed / unvalidated）**：每个 batch 可先测试少量 query（例如 4–8 个），每 query 先测试少量 page（例如 1–2 页）和有限结果数；具体值必须通过 query-family coverage、partial rate、latency 和 context-growth 实验决定，不能写入 accepted contract。调用方若需要更多结果，发起新的可审计 continuation/attempt。

### Step 4: Candidate triage and `web_read`

1. 先按 strict URL key、redirect 和明显 mirror 做 conservative dedupe；保留原始 URL、query provenance、page 和 position。
2. 根据 title/snippet/URL 初步标记 facet、source role、可能的 ownership group；不要把 triage 当正文证据。
3. 先 `web_read` 能改变 pivotal claim 判断的 primary candidates，再读 synthesis/context。
4. 对长正文使用 `web_read` 的 outline/preview/section/position/keyword continuation；保存 representation、`truncated`、`next_cursor`、access status、JS/PDF/OCR method 和 locator。
5. 同一 syndication cluster 的多个 pages 不增加 independent evidence count，但仍可帮助确认传播时间、版本和 wording differences。

### Step 5: Facet/counterevidence loop

推荐的 caller loop：

```text
scope claims and facets
  -> batch definition + primary queries
  -> triage candidates and source groups
  -> web_read pivotal primary sources
  -> update evidence matrix
  -> issue counterevidence / version / language / modality queries for gaps
  -> continue pagination only when it can add facet/group/high-value primary candidate
  -> stop with explicit gap when material claims are explainable
```

Continue 条件（proposed）：

- material claim 只有 snippet、commentary 或不可复核 summary；
- support evidence 属于同一 provenance cluster；
- 存在实质 contradiction，尚未定位到 version/population/date/jurisdiction/measurement 差异；
- source stale/superseded、language/geography 不匹配；
- JS/PDF/scanned/OCR modality 未读取且可能改变判断；
- pivotal behavior 只有 vendor/maintainer assertion 或一次不可复现 measurement；
- high-impact access/coverage gap 尚未解释。

Stop with explicit gap（proposed）：每个 material claim 都有适配的 evidence role，支持/反驳关系、locator、access state 和 provenance hypothesis 已记录，且剩余 gap 无法在当前 scope/access/budget 合理消除。最终报告应写 `unavailable`、`unresolved` 或 `coverage_gap`，不要写成“没有反例”。新增 candidates 只重复已覆盖 cluster 或仅增加背景 commentary 时，可以停止扩大 Search；这表示边际收益下降，不是证明为真。

## 6. Proposed evidence matrix and provenance model

以下 schema 是用于 agent-side ledger 的草案，**proposed / unvalidated**，不是 server contract：

```text
ClaimRecord {
  claim_id,
  claim_text,
  claim_type,
  decision_consequence,
  as_of,
  version,
  geography,
  language,
  status: open | supported | contested | context_only | unavailable | stale,
  source_ids[],
  unresolved_gaps[]
}

EvidenceRecord {
  evidence_id,
  claim_id,
  source_id,
  source_role,
  support: supports | contradicts | context,
  quote,
  locator,
  provenance_cluster,
  independence_notes,
  authority_basis,
  directness_notes,
  recency_version_notes,
  language_geography_notes,
  conflict_of_interest_notes,
  access_status,
  retrieved_at,
  representation_id,
  content_hash
}
```

`authority_basis`、`independence_notes` 和 `source_reliability_notes` 应是 explainable notes，不应由 Search server 算成 numeric truth score。`locator` 可采用 W3C selector primitives；`content_hash` 只用于 representation identity/change detection，不证明 authenticity。

## 7. Measurable evaluation proposal

所有数字、指标、pool 规则和 assessor protocol 均为 **proposed / unvalidated**。没有 runtime experiment，本报告不提供 benchmark result。

### 7.1 Search candidate and query strategy

建立 small judged pool：由固定的 query families、有限 page depth、official/measurement/contrary variants 组成；保存 `pool_version`、`query_plan_hash`、attempt IDs、time、instance/adapter version。对每个 candidate 按 facet/subtopic 和 tentative source group 标注，Search relevance 与正文 evidence support 分开。

推荐比较：

- `seed + gap/counterevidence` strategy；
- 只做同义词扩张的 baseline；
- upstream order；
- 离线 deterministic MMR-like / aspect-aware baseline（仅作 evaluation，不能覆盖 upstream rank）。

可报告：

```text
pool_relative_recall@k
  = judged relevant candidates retrieved in evaluated top-k
    / judged relevant candidates present in constructed pool

facet_coverage@k
  = covered judged facets in top-k
    / judged facets represented in the pool

source_group_coverage@k
  = distinct tentative groups in top-k
    / distinct groups represented in the pool
```

必须同时报告 pool construction、unjudged rate、same-group repeat rate、canonicalization false-merge review、partial rate 和 access-failure distribution。不能将 pool-relative 指标写成 Web recall。

### 7.2 Ordering, pagination and filters

- **Capability matrix**：少量 query 测 `language/locale/country`、`day/week/month/year`、page 1/continuation、empty、CAPTCHA/block、format disabled、timeout、parse failure；记录 `requested`、`effective`、`upstream.state`，不把一次成功写成永久 capability。
- **Pagination drift**：同 query 在短窗口重复 page 1；跨窗口重复 page 1/page 2；观察 page boundary overlap、duplicate/skip、top-k overlap、rank correlation；把时间、locale、instance、adapter version 和 error state 作为上下文。结果只能描述该测试窗口。
- **Filter semantics**：把 requested filter、effective support 和正文判定分开；Google/SearXNG 的 time filter 不等于正文 publish date，language filter 不等于 strict same-language output。

### 7.3 Source independence and canonicalization

建立离线 adversarial URL fixture，覆盖 fragment/default port/percent-encoding/dot-segment、有语义 query params、redirect、`rel=canonical`、mirror、syndication、public suffix 和 hosted platform。目标是低 false merge，不是最大 dedupe。保存：

- `url_original`；
- `strict_key`；
- 可选 `semantic_key`；
- `declared_canonical_url`；
- `canonicalization_evidence`；
- `ownership_hypothesis`：`unknown | tentative_related | tentative_same_publisher`。

RFC 3986 说明 URI equivalence 依赖应用语义，WHATWG 的 `rel=canonical` 只是 preferred URL/duplicate-content hint，不是 ownership proof。[S22][S23] Public Suffix/registrable-domain 若后续采用，只能作为低置信度 clue，不可等同 same owner。当前没有已验证的通用 provenance clustering algorithm 或阈值。

### 7.4 Diversity evaluation caveat

NIST TREC 2009 提供 diversity qrels 和 `ndeval.c v1.3`；source code 支持 qrel subtopic、`alpha-nDCG`、`IA-P` 和 default `alpha=0.5`。[S11][S12] 对本项目只能借用“保留 facet/subtopic qrels、报告 pool/unjudged/denominator、把 alpha 和 metric version 随 evaluation 保存”的方法。NIST evaluator 不是本项目已批准 assessor protocol，也不证明 Web recall。

## 8. One hypothetical research sequence

以下是 **hypothetical，不是 executed output**。

问题：`截至某日期，Windows CPU-only 的 PDF extraction route 是否能支持扫描中文技术报告？`

1. Agent 建立 claims：`C1` 支持哪些 PDF formats；`C2` native/scanned/混合 coverage；`C3` Chinese OCR quality；`C4` locator/citation fidelity；`C5` license/distribution fit。标记 C3/C4 为 high consequence。
2. Agent 发 `definition_primary` queries：各候选 official docs/source/license；Search 使用显式 `route=searxng/backend=google` 的一组独立 query，按 query 分组保留结果和 upstream status。
3. Agent triage candidates：按 official ownership、version、modality 和 source role 标记；不读取 body 的 Search result 不进入 evidence matrix 的 direct support。
4. Agent 对候选 official docs 用 `web_read`：先 preview/outline，再读取 OCR、Windows/CPU、license 相关 sections；若 PDF 是 scanned，记录 OCR partial/representation state/locator。
5. Agent 发 `measurement` queries 查公开 corpus、benchmark、failure cases；发 `counterevidence` queries 查 low-resolution、multicolumn、Chinese/English mixed、license/model dependency limits。
6. 若同一 press release 出现于多个 domains，标为同一 tentative cluster；不会把 domain count 写成 independent corroboration。
7. Agent 在 worksheet 中得出：C1 可由 official docs support；C3 只有外部 benchmark 摘要且未读全文，则状态 `unavailable`/`open`；C4 需要真实 fixture 才能验证，保持 `unvalidated`。
8. Agent 停止的理由是：每个 material claim 有 role-fit evidence 或 explicit gap，counterevidence 已执行；报告结论只写“在已读取的 Windows/CPU/语言/模态 scope 内的 proposed route trade-off”，不写 universal winner。

## 9. Proposed Search-side schema

以下示例与已接受的 v1 边界一致，但字段和 status 仍未锁定：

```json
{
  "batch_id": "b-2026-09-10-001",
  "route": "searxng",
  "backend": "google",
  "status": "partial",
  "partial": true,
  "queries": [
    {
      "query_id": "q-definition-01",
      "query": "site:example.org exact term specification",
      "facet_id": "C1",
      "evidence_goal": "definition_primary",
      "requested": {
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
          "url_original": "https://example.org/spec",
          "title": "Specification",
          "snippet": "...",
          "position_in_page": 1,
          "derived_rank": 1,
          "aggregator_score": null,
          "canonicalization": {
            "strict_key": "https://example.org/spec",
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
        "instance": {"transport_status": "ok", "instance_http_status": 200},
        "engine": {"engine": "google", "state": "ok"},
        "upstream": {"upstream_http_status": null, "upstream_request_id": null, "evidence_status": "not_observed"},
        "retry_performed": false
      },
      "warnings": []
    },
    {
      "query_id": "q-counter-01",
      "query": "exact term limitation failure",
      "status": "failed",
      "results": [],
      "observation": {
        "instance": {"transport_status": "ok", "instance_http_status": 200},
        "engine": {"engine": "google", "state": "suspended_or_rate_limited", "state_basis": "unresponsive_engines"},
        "upstream": {"upstream_http_status": null, "upstream_request_id": null, "evidence_status": "not_observed"},
        "retry_performed": false
      },
      "warnings": ["No implicit fallback or retry was performed."]
    }
  ]
}
```

设计约束：

- query 结果独立分组；query-level status 与顶层 `partial` 必须一致——示例中一条成功、一条失败，因此 `partial=true`；
- `route`/`backend` 显式记录，server 不 silent fallback；
- `facet_id`、`evidence_goal` 等是 caller-only planning metadata，server 只透传回显，不解析也不据此改写 query；
- `position_in_page` 是可观察 ordering；`derived_rank` 只有 page size/offset 确认才计算；
- `aggregator_score` 若保留，必须带 `score_basis`/`score_version`，不可解释为 relevance/authority/truth；
- requested filter 与 effective support 分离；
- `next_cursor` opaque，绑定 query/filter/route/backend/adapter version/representation context，但不承诺 immutable snapshot；
- `observation` 分 instance / engine / upstream 三层：instance 层记录本地 SearXNG 的 transport/HTTP 状态；engine 层从 `unresponsive_engines` 与解析结果分类为 `ok`、`empty_or_parse_failure`、`suspended_or_rate_limited`、`captcha_or_blocked`、`timeout`、`unknown_error`；upstream 层只有 instance 明确透传 Google 侧 status/request id 时才填写，否则为 `null` 并标 `evidence_status=not_observed`。prototype 已观察到本地 HTTP 200 伴随 engine suspension，以及 `RemoteDisconnected` 无 status 的情况，schema 必须能如实表达这两类而不是把本地状态冒充 upstream 状态；
- 默认 `retry_performed=false`；如 caller 需要 retry，必须新建可审计 attempt，保留旧失败。server 不 retry 也不证明 upstream 只被请求一次。

## 10. Integration boundary with standalone `web_read`

Search 只做 candidate discovery，永不因 title/snippet/score 自动读取 body。caller 选择 candidate 后调用 `web_read`，而 `web_read`：

- 接受 Search 结果或 caller 直接提供的 URL；
- 返回 metadata、outline（若可得）和 bounded preview；
- 使用原文抽取，不依赖 LLM-generated summary；
- 对 HTML、JS-rendered page、PDF、scanned PDF、web text image 和 standalone image 记录 representation、method、coverage、OCR/JS state、warnings 和 locator；
- 超长正文返回 `truncated` / opaque `next_cursor`，按 section/position/keyword 继续；
- 将 raw/extracted representation 与 cursor 绑定，source 变化时返回 stale/new snapshot，而不是静默把旧 offset 指向新文本；
- 不做最终 synthesis、authority judgment、source independence judgment 或 truth score。

`web_read` 的 extraction 组合、Windows CPU 和 OCR 选择仍需独立 validation；format-fidelity primary-source recheck 支持“分层 portfolio、raw first、native/OCR/JS lineage 分离”这一方向，但没有运行 benchmark，也没有批准具体 library/license/threshold。[S18][S19][S20][S21]

## 11. Experimental worklist and decision gates

以下是 **proposed validation plan**，不是 production tickets，也不是实现承诺。

| Gate | Experiment | Evidence to record | Decision question |
|---|---|---|---|
| G1 Capability | 固定少量 query 测 language/locale/country、time filters、page、empty、CAPTCHA/block、format disabled、timeout/parse failure | `requested`、`effective`、adapter/instance、upstream state | schema 是否必须暴露 capability mismatch、哪些字段可安全承诺 |
| G2 Query families | 用人工 facet set 比较 primary/measurement/counterevidence/gap loop 与 synonym-only baseline | facet coverage、new source-group rate、duplicate rate、partial rate、query cost | facet loop 是否比结果数量增长带来可测增益 |
| G3 Pagination | bounded repeated attempts，观察 page overlap/skip、rank drift、CAPTCHA/timeout | URL strict key、page boundary、time/locale/adapter/instance | continuation 是否仅提示 best effort，默认 page bound 如何选 |
| G4 Ownership | 离线 redirect/canonical/syndication/hosted-platform fixtures + human adjudication | false merge、unknown rate、group agreement | 是否能安全输出 tentative group，避免伪造 independence |
| G5 Judged diversity | topic/facet pooled candidates，assessor 可按需 `web_read` | qrels、unjudged、pool denominator、alpha/metric version、adjudication workload | upstream order 或离线 rerank 是否改善 facet coverage；是否进入 caller-only baseline |
| G6 Access bias | 按 report type/language/geography/modality 记录 paywall、JS、PDF/OCR、not-indexed 等 failures | failure distribution、missingness notes、access_status | coverage disclosure 最低字段与语言/地区 gap 规则 |
| G7 MCP integration | target host capability/conformance test | tool discovery、batch partial、cursor/stale behavior、resource limits | schema/cursor 是否适合实际 host；不从通用 MCP docs 推断 conformance |

### Decision-gate discipline

- G1–G7 只产生 scope-bound observations；不把一次实验升级成 universal SLA。
- 没有完成 G2/G4/G6 前，不批准 universal source quota、independence threshold 或 numeric truth score。
- 没有完成 G3/G7 前，不把 `pageno` 或 opaque token 描述成 immutable cursor。
- 没有完成 target Windows/CPU and license validation 前，不把 format-fidelity memo 中任何 component choice 写成 approved dependency。
- MMR/xQuAD 仅因可作为离线 baseline，不代表 v1 server reranking 已决定；其原始全文本轮不可读，不能引用具体参数或 superiority claim。[S24]
- 不声明 #6 resolved；本报告只补充 research strategy 与 validation gates。

## 12. Disagreements, chronology and evidence limits

### 12.1 Earlier design wording versus later no-retry decision

较早 scope text 曾写”有限自动重试”，2026-09-10 的 [ADR-0004](../adr/0004-v1-search-read-boundary.md) 已将其改为 v1 **默认不 automatic retry**，retry 由 caller 以新的可审计 attempt 显式发起。本文采用 ADR-0004 的这一决策；§9 JSON 示例的 `retry_performed: false` 即反映此假设。这不是重新打开 ADR，而是记录 chronology。

### 12.2 Framework transfer disagreement

Cochrane、PRISMA-S、GRADE、National Academies 都主要源自 healthcare/systematic-review context；它们支持“检索边界、透明记录、拆分证据维度和披露 limitations”的概念，但不自动提供 technical/current-events 的 source ranking、truth score 或 universal stop rule。IPCC Chapter 1 在本轮只有 official Search result/入口，未直接读取正文，因此不将其细粒度 `confidence`/`likelihood` 表述当作已验证规则；Reuters standards 只有 Search summary，本报告不依赖它作硬证据。

### 12.3 Provenance and source independence

目前没有已验证、跨新闻/technical docs/academic papers 的通用 provenance clustering algorithm。`ownership_group_id`、`provenance_cluster`、confidence 和 stop signals 只能是 agent-owned hypothesis + human/fixture validation input。不同域名、不同 publisher label、`rel=canonical` 或相同 text hash 都不足以单独证明 independent evidence。

### 12.4 Access limits and unverified claims

- Cochrane 官方页面相关段落存在 extraction 截断；不将 author/contact 细节写成已完全核验。
- IPCC Chapter 1 直接 HTML/PDF 本轮不可读；保留为未核验 conceptual lead。
- MMR/xQuAD primary PDFs 可取得但正文不可读；只采用 relevance/novelty/aspect 的保守抽象。
- Google-only coverage、pagination drift、filter precision、CAPTCHA rate、ownership grouping、assessor agreement、Windows CPU/OCR/JS/PDF fidelity、target MCP host conformance 均未实测。
- Access failure 可能不是随机缺失；本报告不把 Search absence 或 OCR absence 当作 factual absence。

## 13. Primary source ledger

访问日期统一为 **2026-09-10**。`Full` 表示本轮读取到官方正文/source；`Partial` 表示官方正文部分可读或有截断；`Search-only/unavailable` 不用于支持完整正文 claim。

| ID | Owning source / publication | Primary URL | Access status | 本报告使用的 supporting section / quote | Limitation |
|---|---|---|---|---|---|
| S1 | Cochrane, *Cochrane Handbook for Systematic Reviews of Interventions*, Chapter 4, v6.5.1 | https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-04 | Partial | Sections 4.2–4.5；“A search of MEDLINE alone is not considered adequate.”；“Searches should aim for high sensitivity…”；未发表研究难以完整发现 | 页面 extraction 有截断；healthcare intervention scope；不将 author/contact 细节写成 fully verified |
| S2 | Rethlefsen et al., *PRISMA-S*, *Systematic Reviews* 10:39 (2021) | https://pmc.ncbi.nlm.nih.gov/articles/PMC7839230/；DOI https://doi.org/10.1186/s13643-020-01542-z | Full via open PMC/Europe PMC path | 16 items；database/platform、complete strategy、limits、dates、records、dedupe；“It is intended to guide reporting, not conduct, of the search.” | supports transparency, not retrieval quality/truth |
| S3 | ACRL/ALA, *Framework for Information Literacy for Higher Education*, “Authority Is Constructed and Contextual” | https://www.ala.org/acrl/standards/ilframework | Partial official page | “Authority is constructed in that various communities may recognize different types of authority.”；context/information need determines required authority | information-literacy framework, not calibrated source ranking |
| S4 | GRADE Working Group, “Grading quality of evidence and strength of recommendations”, *BMJ* 328 (7454):1490 (2004) | https://pmc.ncbi.nlm.nih.gov/articles/PMC428525/；DOI https://doi.org/10.1136/bmj.328.7454.1490 | Full via PMC; BMJ landing 403 | `quality of evidence`；`study design`、`study quality`、`consistency`、`directness`；difference from recommendation strength | healthcare intervention context; no direct claim for technical reports |
| S5 | National Academies, *Finding What Works in Health Care*, Chapter 7 | https://www.nationalacademies.org/read/13059/chapter/7 | Partial, truncated near end | sources、last search date、eligibility、appraisal、synthesis、limitations、funder role | healthcare systematic-review reporting scope |
| S6 | W3C, *PROV-DM: The PROV Data Model*, Recommendation (2013) | https://www.w3.org/TR/prov-dm/ | Full | Entity/Activity/Agent；generation/usage/derivation/attribution | generic provenance vocabulary; project mapping proposed |
| S7 | W3C, *Web Annotation Data Model*, Recommendation | https://www.w3.org/TR/annotation-model/ | Full | `TextQuoteSelector` exact/prefix/suffix；`TextPositionSelector` start/end；`TimeState` | selectors/state do not prove authenticity or immutable identity |
| S8 | SearXNG, Search API docs | https://docs.searxng.org/dev/search_api.html | Full | `q`、`language`、`pageno`、`time_range`、`format`、`safesearch`；engine support caveat；format may be 403 | no live instance behavior; no generic page-size/cursor guarantee |
| S9 | SearXNG Google engine docs/source, maintainers | https://docs.searxng.org/dev/engines/online/google.html；https://raw.githubusercontent.com/searxng/searxng/3fdc6d753a339b5f4a7dc5842c94c0d8324726f1/searx/engines/google.py | Full source at commit `3fdc6d753a339b5f4a7dc5842c94c0d8324726f1`, 2026-09-08 | `max_page=50`、10-result offset、locale/time/SafeSearch mapping、CAPTCHA/`sorry` detection | snapshot is not selected project release; no live Google experiment |
| S10 | SearXNG README and self-hosting docs | https://github.com/searxng/searxng；https://docs.searxng.org/own-instance.html | Full / partial README; full self-hosting docs | metasearch/aggregation；external upstream requests；instance IP visibility；CAPTCHA/block caveat | no claim of independent index or coverage expansion |
| S11 | NIST TREC 2009 Web Track | https://trec.nist.gov/data/web09.html | Full | diversity qrels and `ndeval.c (v1.3)` availability | assessor/pool protocol not fully specified on page |
| S12 | NIST `ndeval.c` v1.3 | https://trec.nist.gov/data/web/09/ndeval.c | Full source | qrel fields；`alpha-nDCG`、`IA-P`；default `alpha=0.5`；unjudged docs occupy rank without gain | evaluator semantics do not prove Web recall; denominator/pool must be reported |
| S13 | Google Search Central, How Search works | https://developers.google.com/search/docs/fundamentals/how-search-works | Full | many factors；location/language/device effects；indexing not guaranteed | no project-specific coverage/stability SLA |
| S14 | SearXNG `results.py` source | https://raw.githubusercontent.com/searxng/searxng/3fdc6d753a339b5f4a7dc5842c94c0d8324726f1/searx/results.py | Full source at same commit | score mechanics、duplicate merge、category/template/image grouping | aggregation mechanics only; not relevance calibration |
| S15 | Google Search Central, Ranking systems guide | https://developers.google.com/search/docs/appearance/ranking-systems-guide | Full | multiple systems/signals；freshness；deduplication；site diversity | no cross-time ordering guarantee |
| S16 | Google Search Help, Why search results differ | https://support.google.com/websearch/answer/12412910?hl=en | Full | time/context/location/language/device/recent searches/personalization | context-specific support, not adapter contract |
| S18 | pypdf, Extract Text docs | https://pypdf.readthedocs.io/en/stable/user/extract-text.html | Full | PDF semantic limitations、scanned PDF/OCR requirement、layout approximation | no project corpus benchmark |
| S19 | Playwright Python intro/network docs | https://playwright.dev/python/docs/intro；https://playwright.dev/docs/network | Full | JS/browser support；route scopes；service-worker request caveat | routing not isolation; browser revision not pinned |
| S20 | Playwright downloads docs | https://playwright.dev/docs/downloads | Full | download event/URL/stream/saveAs and temp lifecycle | no file semantics/completeness claim |
| S21 | Tesseract repository/CLI docs | https://github.com/tesseract-ocr/tesseract；https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html | Full | TSV/hOCR geometry/confidence；formats/languages/Windows docs | confidence is recognition signal; no target-machine benchmark |
| S22 | IETF RFC 3986, URI Generic Syntax | https://www.rfc-editor.org/rfc/rfc3986 | Full | URI equivalence is application-dependent；query semantics; normalization levels | does not provide ownership algorithm |
| S23 | WHATWG HTML Standard, link type canonical | https://html.spec.whatwg.org/multipage/links.html#link-type-canonical | Full | `rel=canonical` is preferred URL/duplicate-content hint | not generic equivalence or ownership proof |
| S24 | Carbonell & Goldstein MMR; Santos et al. xQuAD | https://doi.org/10.1145/290941.291025；https://www.cs.cmu.edu/afs/cs/Web/People/jgc/publication/MMR_DiversityBased_Reranking_SIGIR_1998.pdf；https://terrierteam.dcs.gla.ac.uk/publications/ecir2010_rodrygo_div.pdf | Binary/unreadable PDFs; ACM DOI 403 | only conservative relevance + novelty/redundancy + aspects abstraction | no formula/parameter/experiment claim |

## 14. Final position

对本项目，最稳妥的 Search promise 是 **observable coverage and failure**, not “a sufficient report in one call”:

1. Search records query, route/backend, engine, rank/position, requested/effective filters, upstream state and partial failure.
2. caller agent owns claim decomposition, query families, source role selection, counterevidence, independence hypotheses and stop/continue.
3. `web_read` independently provides original content, bounded preview, structured locator and continuation across HTML/JS/PDF/OCR/image modalities.
4. evidence matrix stores support/contradiction, provenance, directness, access completeness and unresolved gaps without numeric truth score.
5. report stops only when material claims are explainable within scope, or explicitly labels `unresolved`/`unavailable`/`coverage_gap`.

这套策略与 ADR-0001/0002/0003/0004 兼容：不实现 server-side `deep_search`，不引入 paid API，query disclosure 由 caller 负责，v1 采用显式 SearXNG/Google route、默认不 retry、按 query 保留 partial。它不宣称 #6 已 resolved，也不将任何新字段、数字、benchmark 或 component choice 写成已实现或已批准。
