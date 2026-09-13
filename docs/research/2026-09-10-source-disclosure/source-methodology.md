---
title: 研究型报告的 Source 与证据充分性
status: research-memo
research_date: 2026-09-10
scope: factual/technical investigation、comparative evaluation、current events/policy、academic/systematic review
implementation_status: proposed / unvalidated
---

# 研究型报告的 Source 与证据充分性

> 本 memo 研究“什么样的 Source 组合足以支撑不同类型的研究报告”，并把结论映射到本项目的 `web_search` / `web_read` 边界。它不是 systematic review，也不是 production contract。文中的新机制、字段、stop signal、阈值和 benchmark 均为 **proposed / unvalidated**。

## 1. 结论摘要

### Facts（由一手方法来源支持）

1. **证据充分性不是 URL 数量。** Cochrane Chapter 4 的可见正文反对把单一 database 当作充分检索；它讨论按题目组合多个 databases、registries、grey literature、reference/citation checking 等来源，并提醒不存在一种简单可靠的方法能找到所有未发表研究。[S1] 这说明“充分”至少要同时考虑 source 的覆盖范围和检索过程，而不是达到任意的 `N` 个结果。本轮没有把“作者或组织联系”写成已独立核实的必备项，因为读取结果在相关段落处受截断限制。
2. **Search 的透明性与 Search 的好坏是两件事。** PRISMA-S 提供 16 个 reporting items，要求报告每个 source 的 database/platform、完整 search strategy、limits、日期、peer review、retrieved records 和 deduplication；它明确说是引导 reporting，而不是指导执行或评估 Search 质量。[S2]
3. **Authority 依赖 context。** ACRL 将 “Authority Is Constructed and Contextual” 作为 information-literacy frame：不同 community 可承认不同 authority，适当的 authority 取决于 information need 与使用场景。[S3] 因此“官方”“论文”“博客”不能脱离 claim 类型直接排成固定可信度顺序。
4. **证据质量/确定性应拆解为不同判断。** GRADE 2004 原文使用 `quality of evidence`，把 `study design`、`study quality`、`consistency`、`directness` 分开，并把 `quality of evidence` 与 `strength of recommendations` 分开。[S4] 这是一个可借用的判断结构；原框架围绕 healthcare intervention，不应直接变成所有 agent report 的 checklist。
5. **Provenance 是可复核性的一部分。** W3C PROV-DM 用 `Entity`、`Activity`、`Agent`、generation、usage、derivation、attribution 表示对象、处理活动、责任主体和 lineage。[S6] W3C Web Annotation 定义了 `TextQuoteSelector` 与 `TextPositionSelector`，可将 claim 连接到可复核的原文位置。[S7]
6. **独立复核不能由域名数量推出。** 不同页面可能转发同一 wire、press release、dataset 或 quote-chain；它们是不同 URL，但不一定是独立 evidence。独立性必须根据 provenance 和 evidence-generation path 判断。这是本 memo 的解释性结论，不是 Search engine 提供的事实字段。

### Interpretation（本 memo 的综合判断）

“充分”应定义为：**对报告中所有 material claims，已有与 claim 类型匹配的 direct evidence、足够的 provenance 和可复核 locator，并且已主动寻找 counterevidence；剩余的 recency、version、language、geography、access 或 modality gaps 已被显式标记。** 这是一种 claim-level closure，而不是 source-count threshold。

### Proposed design（未验证）

- 由 agent 持有 claim decomposition、source selection、冲突处理和 stop/continue 判断；server 只提供可观测的 Search candidate、读取内容、定位和失败状态。
- 为每个 material claim 建立 evidence matrix；不要产生一个伪装成事实的总 `truth_score`。
- 将“source 有多权威”“此 source 是否直接支持该 claim”“多个 source 是否独立”“内容是否完整可访问”分开记录。
- 以 `supports` / `contradicts` / `context` / `unresolved` 表示 evidence 关系；保留冲突，不在 server 侧悄悄选一个“最佳答案”。
- stop signal 由 agent 按 report type 与 claim consequence 决定；系统只提供已搜索 queries、候选、读取状态、`truncated` / `next_cursor`、失败原因和 evidence metadata。

## 2. “Source 足够”到底包含哪些维度

下表是建议的判断维度，不是 universal weights。不同 report type 可改变优先级，但必须记录理由。

| 维度 | 要问的问题 | 常见误判 | 建议记录 |
|---|---|---|---|
| Relevance | Source 是否回答当前 claim，而不是只讨论相邻主题？ | 主题相近就当作支持 | `claim_id`、scope match、直接引用 |
| Epistemic authority | 该 source 对这类 claim 是否拥有合适的能力、责任或方法位置？ | “官方”对所有事实都优先；名校/大媒体自动代表正确 | authority basis、发布机构/作者、适用 context |
| Original evidence | 是否接近原始记录、原始数据、实验、代码、法规文本、访谈或现场观察？ | 二手总结被当成原始事实 | `source_role`、原始材料链接、引用链 |
| Provenance | 谁产生、何时产生、经过什么处理、当前页面是否是版本/转载？ | 只保存裸 URL，丢失版本与 redirect | `published_at`、`updated_at`、`retrieved_at`、version、redirect、hash |
| Independence | 两条证据是否独立收集或独立分析？ | 不同 domain = 独立；同一 press release 的十篇稿件 = 十条证据 | `provenance_cluster`、共同上游、共同 dataset/funder/quote |
| Directness | source 的 population、setting、version、outcome 是否与 claim 对齐？ | 一般趋势被外推到具体产品/地区/版本 | population/setting/version/outcome notes |
| Method quality | 数据、方法、执行、样本和不确定性是否可检查？ | 有 DOI 或漂亮图表就视为高质量 | methods availability、limitations、replication status |
| Controversy / counterevidence | 是否主动找了反例、批评、失败结果、限制条件？ | 只搜支持初始假设的 query | contradiction search、negative/critical sources |
| Recency / version fit | claim 是否与发布日期、当前版本、政策生效期匹配？ | 旧 release note 支撑新 API；新闻初报支撑最终事实 | `as_of`、version、superseded status |
| Language / geography | 是否遗漏不同语言、地区、司法辖区、当地记录？ | English-only 或单一国家 source 被当成全球情况 | language、country/region、locale gap |
| Conflict of interest | funding、ownership、incentive、sponsorship 是否影响解释？ | 有 conflict 就全盘排除，或完全不披露 | author/org、funding、sponsor role、COI note |
| Access completeness | 是全文、摘要、SERP snippet、不可访问、OCR partial 还是截断？ | 不能打开被当成不存在；snippet 被当成全文 | `access_status`、modality、`truncated`、unavailable reason |

### Primary source 不是永远最佳

Primary source 的优点是接近原始事实或原始操作，但它并不自动解决所有问题：

- 官方 regulation 是判断“文本写了什么、何时生效”的 primary authority，却未必能单独证明政策的实际效果。
- Maintainer release note 是 version fact 的 primary source，却可能没有独立性能测量；性能 claim 还需要可重复 workload 和独立 benchmark。
- Eyewitness 或现场帖可能是事件的 direct lead，却可能时间早、视角窄、不可复核；需要与原始记录和独立 corroboration 配对。
- A systematic review 或方法论文是二级 synthesis，但对“已有研究整体如何”“某方法的已知 bias”可能比单篇 primary study 更合适。它的搜索范围、纳入标准和 conflicts 仍需核查。

因此建议使用 **source role**，而不是 `primary = trustworthy / secondary = untrustworthy` 的二元规则：`primary-record`、`primary-data`、`primary-method`、`independent-replication`、`methodological-synthesis`、`commentary/context`、`counterevidence`。

## 3. 按 report type 定义 Source 组合

### 3.1 Factual / technical investigation

**典型问题**：某个 API、协议、release、实现限制或性能 claim 是否成立？

**核心 Source 组合（proposed）**：

1. **版本/规范 primary**：maintainer docs、specification、release note、issue/PR、source code 或官方 data record；用于回答“定义是什么、在哪个 version/commit、谁负责发布”。
2. **直接行为证据**：可复现的 command、test、benchmark、trace、response 或原始样本；用于回答“实际做了什么”。
3. **独立复核**：不同作者、不同 workload 或不同环境的 reproduction；用于避免把 maintainer claim 当作 observed behavior。
4. **反例与边界**：已知 issue、negative result、unsupported platform、failure mode、license/terms 限制。

**充分性判断**：若只有官方文档，没有实际行为证据，能支持 definition/availability，不能自动支持 latency、quality、coverage 或长期稳定性。若只有一次本地 run，能支持该 run 的 observation，不能外推全局 benchmark。

**不应默认的做法**：把 GitHub stars、搜索排名、供应商 marketing、一个成功样本或一个版本的结果外推为普遍事实。

### 3.2 Comparative evaluation

**典型问题**：在 Windows、CPU-only、指定 corpus 与约束下，Route A 是否比 Route B 更适合？

**核心 Source 组合（proposed）**：

- 每个候选的 official docs/source/release/license，确认能力和版本边界。
- 同一 corpus、同一 hardware、同一 configuration、同一 stopping rule 的 controlled measurement。
- independent benchmark 或公开 dataset/paper，检查结果是否只对自造样本成立。
- failure corpus：低清、multicolumn、JS shell、OCR、timeout、access denied、language/region edge case。
- 适用性分析：maintenance、privacy、license、CPU/RAM、raw evidence、可定位性；这些不是单一质量分数。

**充分性判断**：comparison 的 minimum unit 不是“每个候选各一个 URL”，而是一个可审计的 **同条件对照**。不同实验设置不能直接用一张排名表合并；若结果冲突，应保留差异和 workload，而不是平均成一个总分。

### 3.3 Current events / policy

**典型问题**：某 jurisdiction 在某 `as_of` date 的政策、事件状态或监管要求是什么？

**核心 Source 组合（proposed）**：

1. **原始记录**：gazette / consolidated legal text、official filing、agency notice、transcript、court document、发布会原文或带 timestamp 的数据。
2. **执行/影响证据**：实施 guidance、预算/统计、现场记录、直接受影响方材料；明确它回答的是 implementation/effect，而不是法律文本本身。
3. **独立 corroboration**：不同 provenance 的报道、数据或当事方记录；识别 wire copy、共同 press release 和同一匿名 source 的 syndication cluster。
4. **反方/争议**：法律异议、审计、反驳、地理差异、尚未确认的早期信息。

**充分性判断**：必须固定 jurisdiction、时间截点和状态词（proposed、enacted、effective、reported、confirmed）。对于 unfolding event，应明确“截至检索时间的可证实状态”，而不是把第一条报道写成最终结论。对政策解释，commentary 可帮助理解但不能替代原始文本。

### 3.4 Academic / systematic review

**典型问题**：一组研究对某方法或干预的整体 evidence 是什么？

**核心 Source 组合（proposed）**：

- protocol / research question / eligibility criteria / analytic plan；
- 多个适合问题的 bibliographic databases、registry、grey literature、citation chaining 和其他 supplementary sources；
- 对每个 source 的完整 query、platform、日期、limits、records 与 deduplication 记录；
- 纳入研究的 primary data、risk-of-bias / limitations、heterogeneity、publication bias 与 synthesis method；
- 更新日期、未发表/预印本/语言与 geography 覆盖说明。

Cochrane 与 PRISMA-S 可作为 search breadth 与 reporting transparency 的方法参考，但不应把 healthcare systematic-review checklist 原样强加给技术调查、新闻事实核查或工程 comparison。[S1][S2] 例如，技术评估可能需要 code/issue/reproduction，而不是 clinical trial registry；current-events report 需要 timestamp、jurisdiction 和 direct record，而不是强行套 PICO。

**充分性判断**：不是“找到很多 paper”就足够；要能够解释哪些研究被找到、哪些被排除、哪些证据质量/直接性不足、不同结果为何不能或可以合并。

## 4. Concrete Search strategy（proposed）

此方案遵守已接受边界：`web_search` 只获取候选 URL 和 SERP metadata，`web_read` 读取指定 URL；Deep Research 的规划、source selection、冲突判断和 synthesis 由 agent 执行。v1 使用调用方显式选择的 route/backend；当前约束下 SearXNG 只启用 Google engine，不把多 engine 数量当作 source breadth；不做隐式 fallback，默认不 retry。

### Step 1：先建 Claim Map，不先定 URL 配额

把问题拆成 `claim_id`，为每个 claim 标记：

- `claim_type`：definition、historical fact、measurement、causal/impact、comparison、legal/policy status、uncertainty；
- `decision_consequence`：若错了会改变什么结论或行动；
- `as_of` / version / geography / language；
- preferred source role；
- required directness 与 possible counterevidence。

先找决定性 claims，再处理背景 claims。高 consequence claim 可要求更严格的 primary record、独立 corroboration 或 reproduction，但不把“严格”编码成固定 universal weight。

### Step 2：按 intent 形成 query families

对每个 material claim，至少考虑以下 query family；不是每题都必须执行所有 family，但跳过必须记录理由。

| Query family | 目的 | 例子（抽象模板） |
|---|---|---|
| Definition / primary record | 找 owning source | `site:official-domain exact term specification/release/notice` |
| Direct evidence | 找 data、test、code、document | `exact version + benchmark/dataset/filing/transcript` |
| Counterevidence | 找 critique、failure、negative result、amendment | `term + limitation/issue/critique/failure/retraction` |
| Independent corroboration | 找不同 provenance 的记录 | `event/claim + second institution/region/dataset` |
| Version / recency | 查 superseded、effective、updated 状态 | `term + version/date/effective/amended` |
| Language / geography | 查本地/非 English 记录 | `native-language term + country/region` |
| Modality | 查 PDF、image、registry、source archive | `title/identifier + PDF/registry/archive` |

Search queries 要服务于 evidence gap，不要只为增加结果数。Query、route、backend、engine、执行时间和返回状态应被记录；SERP `rank` / `score` 只帮助 triage，不是 authority 或 truth score。

### Step 3：Candidate triage 后再 `web_read`

对候选先聚类再阅读：

- 合并 canonical URL、redirect 与明显 mirror；
- 标记共同 press release、wire、dataset、funder、author、quote；
- 给候选分配 `source_role` 和 `provenance_cluster`；
- 先读取能直接改变 claim 判断的 primary sources，再读取 synthesis/context；
- 读取长内容时使用 `web_read` 的 section/position continuation，记录 `truncated`、`next_cursor`、无法访问的 modality 和 OCR/JS 状态。

同一 syndication cluster 的十个页面不能作为十次独立 corroboration；它们仍可能有价值，因为可以暴露传播时间或不同版本，但不应增加“独立证据”计数。

### Step 4：建立 claim-level Evidence Matrix

建议的结构（**proposed schema，未验证**）：

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
  content_hash
}
```

`authority_basis`、`independence_notes` 和 `source_reliability_notes` 是可解释的 notes，不应被 server 计算成虚假的 numeric truth score。`locator` 可采用 W3C `TextQuoteSelector`（`exact`/`prefix`/`suffix`）和 `TextPositionSelector`（`start`/`end`）；W3C `TimeState` 可记录 intended source representation/time。`content_hash` 是本项目 proposed 的 representation identity/change-detection 字段，不是 W3C selector 对真实性的证明。[S8]

### Step 5：Agent-owned stop / continue signals

**Continue research（proposed）**，当满足任一条件：

- material claim 只有 commentary、SERP snippet 或不可复核的 summary，没有合适的 direct source；
- supporting sources 属于同一 provenance cluster，独立 corroboration 尚未形成；
- 存在实质 contradiction，且未定位到 version、population、date、jurisdiction 或 measurement difference；
- source 不是当前 version / effective date，或 page 可能已 superseded；
- language/geography coverage 与问题不匹配；
- technical modality（JS、PDF、scanned image、OCR）未读取或读取被截断，且该内容可能改变结论；
- pivotal claim 只有一次不可复现 measurement，或只有 vendor/maintainer 自述而无边界与失败样本；
- conflict of interest、funding、sponsor role 或 data provenance 未能解释；
- query 已停止扩展，但还有明确的 high-impact evidence gap。

**Stop with explicit gap（proposed）**，当每个 material claim 都有适配的 evidence role，支持/反驳关系和 locator 已记录，已执行相应的 counterevidence 查询，且剩余缺口不能在当前 scope/access/时间预算内合理消除。此时报告“`unavailable` / `unresolved` / `coverage gap`”，不要将缺口改写成“没有反例”。

**Stop without more Search（proposed）**，当新增候选只重复已有 provenance cluster，或只增加背景 commentary 而不覆盖新的 material claim；这不是“证明为真”，只是相对于当前问题的边际收益下降。

## 5. 四个具体 query/report 例子

### Example A：Technical fact

**Query**：`Python 3.13 free-threaded build 在指定 CPU-bound workload 上是否提高吞吐？`

**Evidence plan**：

- Python/CPython official PEP、release note、build/documentation：确认 feature 的定义、supported version 和 caveat；
- benchmark source code、workload、hardware、compiler、run trace：支持“在该条件下观察到什么”；
- independent reproduction：检查是否只有 maintainer-selected workload；
- issue/negative result：查 race、extension compatibility、regression、setup limitation。

**Stop condition**：可以回答“官方定义/限制”和“该 workload 的 observed result”，但若没有跨环境 reproduction，不得写成普遍性能提升。版本和 compiler 必须进入 evidence metadata。

### Example B：Comparative evaluation

**Query**：`CPU-only、Windows、中文扫描 PDF：Tesseract 与基于 ONNX Runtime 的 OCR route 哪个更适合本项目？`

**Evidence plan**：

- 每个候选 official repo/docs/license/release：确认 OCR、language、CPU、PDF pipeline 的真实边界；
- 固定 corpus：清晰扫描、多栏、低清、表格、中文/英文、旋转页、图片文字；
- 固定 hardware/config/output target：记录 OCR text、page/block alignment、confidence、latency、RAM、失败类别；
- independent paper/dataset 或公开 evaluation：检查本地 corpus 是否过于有利；
- 记录 privacy、license、maintenance、可定位性与扫描 PDF 模态缺口。

**Stop condition**：不产出一个脱离 corpus/config 的 universal winner；报告 route × workload 的 trade-off，保留未测语言、layout、低清和版本差异。

### Example C：Current policy

**Query**：`截至 2026-09-10，某 jurisdiction 的 AI rule 对某类 deployer 的 effective obligation 是什么？`

**Evidence plan**：

- official gazette/consolidated legal text 与 amendment history：回答“法条写什么、何时生效”；
- regulator guidance、implementation notice、official FAQ：回答“主管机构如何解释/执行”；
- court/legislative/administrative record：查争议、延期和辖区差异；
- independent legal analysis 与 affected-party record：解释实际影响，但不能替代原文；
- query 需包含 jurisdiction、effective date、version、native-language terms。

**Stop condition**：把 enacted、effective、proposed、reported、challenged 分开；若只找到新闻稿或早期报道，状态为 `unresolved` 或 `as_of-limited`，不写成已确认的最终要求。

### Example D：Academic/systematic review

**Query**：`citation-aware retrieval 是否改善 factuality？`

**Evidence plan**：

- protocol、eligibility、outcomes 与预设 analysis；
- 多个适合的 databases/registries、citation chaining、grey literature；
- PRISMA-S search log：platform、完整 query、limits、日期、records、dedupe；
- 每项 primary study 的 data、model/version、dataset、evaluation metric、risk-of-bias；
- 处理 publication bias、preprint 与 published duplicate、language/geography、异质性和更新；
- 失败/negative result 与非显著结果不可因不符合初始假设而排除。

**Stop condition**：不是达到任意 paper 数，而是能解释搜索边界、纳入/排除、质量和 synthesis；若无法获得全文或方法细节，应把结论降级并记录 missing-not-at-random。

## 6. Missing-not-at-random 与 coverage honesty

不可访问内容不是随机缺失：paywall、robots、regional block、JS-only、扫描 PDF、图片文字、OCR failure、语言壁垒、搜索 index 的 locale 偏差和被删除/更新的页面，可能与 topic、机构、地区或结论方向相关。因而：

- `not found`、`not indexed`、`access denied`、`parse failed`、`ocr partial`、`truncated` 必须区分；
- 不能把“未找到”写成“没有”；
- 不能把 SERP snippet 当成正文或完整方法；
- 同一页面不能只因 `web_read` 先返回 preview 就被视为全文覆盖；要标记 continuation 是否完成；
- 语言/地区未覆盖时，报告应写 coverage gap，而不是把 English-only sample 当成全球样本；
- dynamic page 必须记录 retrieved time、rendering method 和可能变化的 version。

这是本项目尤其重要的边界：`web_search` 只提供 candidate/SERP，`web_read` 负责正文读取和 progressive disclosure；server 不能以 Search score、抓取成功或 OCR 有输出推断 evidence sufficiency。

## 7. 对 Search 与 evidence metadata 的 concrete implications

### 7.1 Search 侧（与已接受 v1 边界一致）

建议 `web_search` 至少让 agent 能观察到（**字段提案，未验证**）：

- `query`、`route`、`backend`、`engine`、`searched_at`；
- per-query `results[]`：`url`、`title`、`snippet`、`rank`、upstream status；
- `partial`、失败项、`warnings`、request/attempt identity；
- 可选的 domain/locale/date metadata，但不得把其语义写成已验证的 relevance 或 authority score。

同一 batch 的 query 结果要分组返回；部分失败保留成功结果。route/backend 由 caller 显式选择，不隐式 fallback；v1 只启用 SearXNG/Google route 中的 Google engine。**Google-only 不是“覆盖充分”的证明，SearXNG 也不会因套了一层 metasearch 就自动扩大 Google 的 index。** Source breadth 应按独立 provenance 和实际 domain/language/geography coverage 观察，而非按搜索引擎数量计算。

### 7.2 Web Read / evidence 侧

`web_read` 返回的 evidence metadata（**字段提案，未验证**）应能区分：

- `requested_url`、`final_url`、redirect chain、`retrieved_at`；
- `published_at`、`updated_at`、document version、publisher/author；
- `mime_type`、language、geography、rendering/extraction/OCR method；
- `access_status`、`truncated`、`next_cursor`、unavailable reason；
- `raw_hash` / `extracted_hash`（若保存策略允许）；
- heading/paragraph/page/block locator；
- `source_role`、`provenance_cluster` 与 untrusted-content marker。

正文仍是不可信 data，不可让页面内指令改变 tool policy、query、credential 或预算。`web_read` 负责尽量完整的主要正文和 continuation；claim 的 authority、independence、counterevidence 和最终 synthesis 仍由 agent 决定。

### 7.3 可审计的 run ledger（proposed）

每次研究建议保留：`run_id`、问题与 `as_of`、query plan、query attempts、候选与 selection reason、source/evidence records、unavailable/partial failures、agent stop reason、schema/extractor version。它是复盘和重新检索的 provenance，不是“truth database”。对于动态网页，旧 `content_hash` 和新版本要共存，不能覆盖历史证据。

## 8. Rubric：不用 universal weights 的判断表

对每个 material claim，以 `Pass / Gap / Conflict / Unavailable` 填写，而不是加权成一个数字：

| 检查项 | Pass 的含义 | Gap / Conflict 的含义 |
|---|---|---|
| Claim fit | 至少一个 source 直接回答 claim | 只有相邻主题或泛泛 commentary |
| Primary/role fit | source role 与 claim 类型匹配 | primary 记录缺失，或把 secondary 当 direct proof |
| Provenance | 发布者、时间、版本、处理链可追溯 | mirror/syndication/origin 不明 |
| Independence | corroboration 的共同上游已核查 | 多个 URL 实为同一 origin |
| Counterevidence | 执行过反例/限制/争议 query | 只有 confirmatory search |
| Directness | population/setting/version/outcome 对齐 | 发生外推或 scope mismatch |
| Recency/version | 与 `as_of` / version / effective date 对齐 | stale、superseded 或动态页面未固定 |
| Language/geography | 题目要求的 locale 与地区有覆盖说明 | 关键 locale/region 未覆盖 |
| Completeness | 全文/相关 section/locator 可复核 | snippet、摘要、OCR partial、truncated |
| Method/uncertainty | 方法、限制、precision/heterogeneity 等可说明 | 只有结论，没有方法或不确定性 |
| Conflict | funding/ownership/sponsor role 已披露并解释 | COI 未知或可能影响关键判断 |

**使用规则（proposed）**：

- 所有 material claims 至少不能留在未解释的 `Gap`；若不能补齐，结论必须降级并写明 gap。
- `Conflict` 不自动否定 source，但必须保留 competing evidence 或说明为何仍采用。
- `Unavailable` 是事实状态，不可被系统转成负面或正面证据。
- 一次 strong primary record 可以足以确认一项定义或官方状态；同样的一条 source 不一定足以确认 causal effect、quality、performance 或 broad generalization。
- 任何 numeric confidence 或 likelihood 若由 agent 使用，必须说明其含义、证据基础和适用范围；不能与 server 的 `score` 混用。

## 9. 高影响待验证项

1. **Google-only 的 coverage**：在中文、English、mixed-language、新闻、technical docs、policy、regional query 上的独立 domain coverage、重复率、freshness 和阻断率尚未系统测量；不能从本 memo 推出 Search 召回。
2. **Provenance clustering**：如何识别 wire/syndication、共同 press release、共同 dataset、转载改写和独立重述，尚无已验证算法或阈值。
3. **Evidence metadata 可获得性**：不同 HTML、JS、PDF、扫描 PDF、网页文字图片和独立图片 URL 能否稳定提供 version、publisher、page/block locator、OCR confidence，需要真实 corpus 验证。
4. **Agent stop signals**：上述 continue/stop 条件需要用人工标注 claim set 和失败样本校准；本 memo 没有声称它们能自动判断 truth 或 completeness。
5. **不完整访问的偏差**：paywall、地域限制、删除页面、robots、JS failure 和 OCR failure 对不同主题是否造成方向性缺失，需按 report type 建立记录与抽样检查。
6. **保存与复核边界**：raw bytes、截图、PDF、OCR text 和完整网页的 retention、copyright、ToS 与公开分享边界仍需独立确认；evidence hash 只能帮助发现变化，不是真实性签名。
7. **跨报告类型迁移**：Cochrane、PRISMA-S、GRADE、IPCC 的方法概念如何最小化地迁移到 technical/comparative/current-events report，需通过具体 case review 验证，不能直接宣称一个 universal rubric。

## 10. Citation ledger（primary sources）

> `access_status` 区分了全文读取、部分读取和只能从搜索结果看到。对未全文获取的来源，本 memo 只使用可见的有限内容，不把它们当作已完成的全面核验。

| ID | Owning source / publication | URL | Accessed 2026-09-10 / access status | 本 memo 使用的事实与 exact section/short quote | Limitation |
|---|---|---|---|---|---|
| S1 | Cochrane, *Cochrane Handbook for Systematic Reviews of Interventions*, Chapter 4 “Searching for and selecting studies”, version 6.5.1, last updated March 2025 | <https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-04> | Partial full-text page returned; page header confirmed version 6.5.1 and March 2025; the extracted response exposed the relevant sections but also contained truncation markers | Multiple sources, grey literature, citation/reference checking, registries, language restrictions and search sensitivity. Quotes: “A search of MEDLINE alone is not considered adequate.” “Searches should aim for high sensitivity, which may result in relatively low precision.” “There is no easy and reliable single way to obtain information about studies that have been completed or terminated but never published.” Sections 4.2–4.5 and related search guidance. | The current fetch did not provide a reliably complete reading of every subsection/supplement; this memo therefore does not treat author/organization contact as independently verified here. Cochrane focus is intervention reviews, mainly trials. |
| S2 | Rethlefsen et al., “PRISMA-S: an extension to the PRISMA Statement for Reporting Literature Searches in Systematic Reviews”, *Systematic Reviews* 10:39 (2021), DOI 10.1186/s13643-020-01542-z | <https://pmc.ncbi.nlm.nih.gov/articles/PMC7839230/> · <https://doi.org/10.1186/s13643-020-01542-z> | Full article text obtained through Europe PMC mirror; direct PMC page also exposed browser verification in one fetch | 16 reporting items; source/platform, exact strategies, limits, dates, peer review, records, deduplication and supplementary searches. Quote: “It is intended to guide reporting, not conduct, of the search.” Checklist section and explanations for items 1–16. | Publisher page redirected/403. Full text was read through the open mirror path; the direct publisher interface was not relied on. PRISMA-S reports search transparency, not overall evidence quality. |
| S3 | Association of College & Research Libraries, *Framework for Information Literacy for Higher Education*, frame “Authority Is Constructed and Contextual” | <https://www.ala.org/acrl/standards/ilframework> | Official page content partially fetched; authority frame and practices/dispositions were visible | Authority depends on community and context. Quote: “Authority is constructed in that various communities may recognize different types of authority.” Frame text and listed knowledge practices/dispositions. | PDF fetch was unreadable; this memo uses the accessible HTML frame content, not omitted PDF material. |
| S4 | GRADE Working Group, “Grading quality of evidence and strength of recommendations”, *BMJ* 328 (7454), 1490–1494 (2004), DOI 10.1136/bmj.328.7454.1490 | <https://pmc.ncbi.nlm.nih.gov/articles/PMC428525/> · <https://www.bmj.com/content/328/7454/1490> | Full-text content was available in the open PMC article; BMJ page itself returned 403 | The 2004 article uses the term “quality of evidence”; it separates “study design, study quality, consistency, and directness” and distinguishes quality of evidence from “strength of recommendations”. It also discusses indirectness, imprecision, reporting bias and conflicts as considerations. | Direct BMJ HTML could not be fetched. Do not silently substitute later “certainty” terminology for the article’s original wording. GRADE is healthcare-oriented; this memo uses it as an example of explicit dimensions, not a universal non-medical grading system. |
| S5 | IPCC, AR6 WGI, Chapter 1 “Framing, Context and Methods”, Box 1.1 | <https://www.ipcc.ch/report/ar6/wg1/chapter/chapter-1/> · <https://www.ipcc.ch/report/ar6/wg1/downloads/report/IPCC_AR6_WGI_Chapter01.pdf> | Official-domain Search result exposed the chapter/PDF links, but direct HTML/PDF retrieval was unavailable in this verification pass | Search-result text exposed the distinction between qualitative `confidence` based on evidence/agreement and probabilistic `likelihood`, plus the phrase “type, amount, quality and consistency of evidence”. This is retained only as a provisional conceptual analogy, not as a fully verified factual premise. | Not fully fetched; no numerical likelihood terms or table are copied into the proposed schema. Treat fine-grained IPCC claims as unverified until the official chapter/PDF is directly readable. |
| S6 | National Academies, *Finding What Works in Health Care: Standards for Systematic Reviews*, reporting standards chapter | <https://www.nationalacademies.org/read/13059/chapter/7> | Official page text available but truncated near end | Report all information sources, dates, eligibility, appraisal, synthesis, limitations, funding and sponsor role. Quote: “all sources of information about potentially eligible articles”. Used to support transparent source and sponsor reporting. | Health-care systematic-review standards; the memo adapts the reporting principle, not the clinical criteria. |
| S7 | W3C, *PROV-DM: The PROV Data Model*, W3C Recommendation (2013) | <https://www.w3.org/TR/prov-dm/> | Full normative text fetched | Entity, Activity, Agent, generation, usage, derivation and attribution for provenance. Quotes: “physical, digital, conceptual, or other kind of thing”; “something that occurs over a period of time”. Used for proposed evidence lineage metadata. | PROV-DM is a generic provenance model; mapping it to this project is proposed and unvalidated. |
| S8 | W3C, *Web Annotation Data Model*, Recommendation | <https://www.w3.org/TR/annotation-model/> | Full text fetched | `TextQuoteSelector` with `exact` and optional `prefix`/`suffix`; `TextPositionSelector` with zero-based `start`/`end`; `TimeState` for source version/time. Used for proposed claim-level locators. | Selector reattachment on changed pages and OCR/PDF mapping need project-specific tests. |
| S9 | Reuters Agency, Journalistic Standards | <https://reutersagency.com/about/standards-values/> | Search result summary only; direct fetch unavailable | Search result described named sources, cross-checking, seeking comment and independence. Not used as sole support for a design rule; current-events recommendations are primarily proposed synthesis. | No direct page text was fetched; do not treat this memo as a complete transcription of Reuters policy. |

## 11. Final position

对本项目，最稳妥的承诺不是“每次返回至少 X 个来源”，而是：

1. Search 明确记录 query、route/backend、engine、rank、upstream status 与 partial failure；
2. agent 围绕 claim map 主动搜索 primary、independent、counterevidence、recency/version、language/geography 和 modality gaps；
3. web_read 提供可继续读取的原文、结构化 locator、`truncated` / `next_cursor` 与 access status；
4. evidence matrix 显式保存 source role、provenance、independence、directness、conflict、uncertainty 和 unavailable gap；
5. 最终 report 只在 material claims 的证据状态可解释时停止，并对无法读取或尚未解决之处保持诚实。

这使系统提供 **observable coverage**，而不是伪造一个“真相分数”。Google-only 的 v1 route 仍可被 agent 通过多轮 query、独立网站、`web_read` 和 counterevidence 搜索使用，但它不自动承诺全网 recall，也不因 SearXNG 的外层存在而获得更多独立 search engine coverage。
