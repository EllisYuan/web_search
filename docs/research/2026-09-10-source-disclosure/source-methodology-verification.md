---
title: Source methodology verification
status: independent-evidence-verification
verification_date: 2026-09-10
scope: source sufficiency for factual/technical investigation, comparative evaluation, current events/policy, academic/systematic review
implementation_status: verification record only; no production implementation
---

# Source methodology 独立核验

> 本文件以 adversarial evidence verification 方式复核 `source-methodology.md`。目标不是重复 memo，而是检查其 design-driving facts 是否确实来自 owning primary source、是否把摘要/搜索结果当成全文、是否把方法框架不当迁移成通用真理，以及是否把 proposed recommendation 写成已验证事实。

## 1. 核验范围与方法

### 1.1 本轮重新打开的来源

本轮直接重新读取或尝试读取了 `source-methodology.md` 的主要依据：

- S1 Cochrane Handbook Chapter 4：重新读取官方 chapter page；核对 version、更新时间、单一 database、多个信息源、grey literature、reference/citation checking、未发表研究和 language/limit 相关段落。
- S2 PRISMA-S：重新读取 PMC 上的开放全文；核对 16 个 reporting items、platform/source、完整 search strategy、limits、日期、peer review、records、deduplication，以及 reporting-not-conduct 表述。
- S3 ACRL Framework：重新读取 ACRL/ALA 官方页面；核对 “Authority Is Constructed and Contextual” 的定义、frame 日期和原文。
- S4 GRADE 2004：重新读取 PMC 上的开放全文；核对原始术语、四个 evidence components 和 quality/recommendation distinction。
- S5 IPCC AR6 WGI Chapter 1：尝试读取官方 HTML/PDF；只能得到 official-domain Search result，直接 HTML/PDF 在本轮不可用。
- S6 National Academies Chapter 7：重新读取官方章节页面；核对 source/date/eligibility/appraisal/synthesis/limitation/funder reporting 要求，但页面内容带截断限制。
- S7 W3C PROV-DM：重新读取官方 Recommendation；核对 Entity、Activity、Agent、Generation、Usage、Derivation、Attribution 的模型角色。
- S8 W3C Web Annotation Data Model：重新读取官方 Recommendation；核对 `TextQuoteSelector`、`TextPositionSelector` 和 `TimeState`。

S9 Reuters Agency standards 仍只有 Search result summary，且没有支撑本 memo 的核心 design-driving claim；本轮不把它升级为已验证证据。

### 1.2 读取状态口径

- **Full**：本轮拿到来源主体或规范相关章节，且可核对目标 claim。
- **Partial**：拿到官方正文的一部分，但存在截断或页面访问限制；只能确认可见范围。
- **Search-only / unavailable**：只有搜索结果或链接元信息，不能声称已读正文。
- **Confirmed** 仅表示该 claim 在列明的 source 和 scope 内得到支持，不表示该 source 证明了本项目的最终方案、质量、truth 或 benchmark。

### 1.3 不在本轮声称的事项

- 没有运行 Search、OCR、browser、MCP host conformance 或 performance benchmark。
- 没有把 Cochrane、PRISMA-S、GRADE、IPCC 或 National Academies 的方法原样批准为所有 report type 的 checklist。
- `source-methodology.md` 没有引入一个外部 library 的 pinned version/license/CPU benchmark/protocol compatibility claim；SearXNG/Google-only、caller-owned planning、`web_search`/`web_read` boundary 是仓库已接受的项目背景或 proposed mapping，不是本轮用外部文献证明的事实。
- Evidence matrix、`source_role`、`provenance_cluster`、stop/continue signal、字段、阈值和 schema 仍是 **proposed / unvalidated**。

## 2. 总体 verdict

| 范围 | Verdict | 结论 |
|---|---|---|
| S1 Cochrane search breadth | **confirmed with scope / corrected** | 核心检索原则被官方 Chapter 4 支持；本轮不能把作者/组织联系写成已完整核验的必备项，且 Cochrane 语境主要是 intervention reviews。 |
| S2 PRISMA-S reporting transparency | **confirmed** | 16 items 及其具体 reporting fields 和 “guide reporting, not conduct” 得到全文支持；它不是 overall evidence-quality score。 |
| S3 ACRL contextual authority | **confirmed with scope** | frame 定义准确；它是 information-literacy framework，不是 empirical source-ranking 或 truth guarantee。 |
| S4 GRADE dimensions | **confirmed / terminology corrected** | 原始 2004 文章使用 `quality of evidence`，而非后续文献可能使用的 `certainty`；四个 components 及与 `strength of recommendations` 的区分得到支持。 |
| S5 IPCC uncertainty language | **unverified in this pass** | official Search result 暴露相关入口和概念，但直接 HTML/PDF 未读到，不能把细粒度 confidence/likelihood 规则当作已核验事实。 |
| S6 National Academies reporting standards | **confirmed with scope** | 可见正文支持 source/date/eligibility/appraisal/synthesis/limitations/funder reporting；页面截断，且语境是 systematic review reporting。 |
| S7 PROV-DM | **confirmed with scope** | W3C Recommendation 支持 provenance vocabulary；它不自动给 source quality、independence 或 truth score。 |
| S8 Web Annotation | **confirmed with scope** | selector、offset 和 TimeState 语义得到规范支持；它们是 locator/state primitives，不是 immutable source identity 或 authenticity proof。 |
| S9 Reuters | **unverified / not design-driving** | 仅有 Search result summary，本 memo 不依赖它作为硬证据。 |

## 3. Claim ledger

| Claim ID | `source-methodology.md` 中的主张 | Owning primary source / 实际访问链接 | 状态 | 支持范围与原文 | Transfer / adversarial check | Remaining limitation |
|---|---|---|---|---|---|---|
| C1 | 证据充分性不是 URL 数量；单一 database 不足；应按问题组合 databases、registries、grey literature、reference/citation checking，并注意未发表研究。 | Cochrane, *Cochrane Handbook for Systematic Reviews of Interventions*, Chapter 4, v6.5.1, March 2025。<https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-04> | **confirmed with correction** | 官方页面可见 “A search of MEDLINE alone is not considered adequate.”、 “Searches should aim for high sensitivity, which may result in relatively low precision.”、 “There is no easy and reliable single way to obtain information about studies that have been completed or terminated but never published.”；可见 sections 4.2–4.5 及多个 source type。 | 支持“不要用固定 URL count 代替 search coverage”的方法性解释；不支持把 Cochrane 的 review workflow 直接当作 technical/current-events 的完整 checklist。 | 当前 extraction 有截断标记；作者/组织联系在本轮没有作为已完整核验项保留。Cochrane 主要面向 healthcare intervention reviews。 |
| C2 | PRISMA-S 规定 16 个 reporting items，要求报告 source/platform、完整 query、limits、日期、peer review、records、deduplication，并明确只指导 reporting 而非 conduct。 | Rethlefsen et al., *PRISMA-S*, *Systematic Reviews* 10:39 (2021), PMC full text。<https://pmc.ncbi.nlm.nih.gov/articles/PMC7839230/>；DOI <https://doi.org/10.1186/s13643-020-01542-z> | **confirmed** | Abstract/Results 明确 “The final checklist includes 16 reporting items”；Table 1 Items 1–2、8、9、13–16 分别覆盖 database/platform、完整 strategy、limits、date、peer review、records、deduplication；Checklist 开头原文 “It is intended to guide reporting, not conduct, of the search.” | 可支持本项目保存 query/route/backend/time/status 的 transparency recommendation；不能由 PRISMA-S 推出 Search quality、recall 或 evidence truth。 | 本轮依赖开放 PMC HTML；publisher/BMJ-style interface 未作为证据入口。全文用于核心 claim，但不意味着核验了 PRISMA-S 的全部应用争议。 |
| C3 | Authority 依赖 context；不同 communities 可能承认不同 authority。 | ACRL/ALA, *Framework for Information Literacy for Higher Education*, frame “Authority Is Constructed and Contextual”。<https://www.ala.org/acrl/standards/ilframework> | **confirmed with scope** | 官方页面原文：“Authority is constructed in that various communities may recognize different types of authority. It is contextual in that the information need may help to determine the level of authority required.” 页面还说明 information resource 的 expertise/credibility 需按 information need 和 context 评估。 | 支持按 claim type/context 记录 authority basis，而非固定“官方 > 论文 > 博客”排序；不支持“contextual”被解释成任何 source 都同样可信。 | 页面底部内容在 extraction 中截断；PDF 未作为独立证据读取。该 frame 是 information-literacy guidance，不是 calibrated evidence grade。 |
| C4 | 证据质量应拆解为 study design、study quality、consistency、directness，并与 recommendation strength 分开。 | GRADE Working Group, *Grading quality of evidence and strength of recommendations*, *BMJ* 328(7454):1490 (2004), PMC full text。<https://pmc.ncbi.nlm.nih.gov/articles/PMC428525/>；DOI <https://doi.org/10.1136/bmj.328.7454.1490> | **confirmed / terminology corrected** | 原文明确使用 `quality of evidence`；正文列出 “study design, study quality, consistency, and directness”，并区分 “quality of evidence” 与 “strength of recommendations”。同时讨论 indirectness、imprecision、reporting bias、conflicts 等。 | 可借用“拆分判断维度、不压成单一分数”的结构；不能把 healthcare intervention 的 GRADE levels、downgrade/upgrade 规则直接迁移到 technical report。 | 原始 BMJ HTML 在本轮不可访问，依据 PMC 全文；source-methodology 已把 “certainty” 改为更忠实的原始术语 “quality of evidence”。 |
| C5 | Provenance 可用 Entity、Activity、Agent、generation、usage、derivation、attribution 表示 lineage。 | W3C, *PROV-DM: The PROV Data Model*, W3C Recommendation, 2013-04-30。<https://www.w3.org/TR/prov-dm/> | **confirmed with scope** | W3C sections 2/5 对 Entity、Activity、Agent 及 generation、usage、derivation、attribution 提供规范定义；例如 Activity 是 “something that occurs over a period of time”，Agent 关联 responsibility。 | 支持把 source/evidence processing lineage 作为可解释 metadata；不支持由 PROV 自动计算 authority、independence、quality 或 truth。 | W3C 模型是 generic provenance model；如何映射到本项目的 source/evidence record 仍是 proposed，未做 schema conformance 或 storage test。 |
| C6 | `TextQuoteSelector` 的 `exact/prefix/suffix`、`TextPositionSelector` 的 `start/end` 可用于 claim locator；source state/version 应显式记录。 | W3C, *Web Annotation Data Model*, Recommendation。<https://www.w3.org/TR/annotation-model/> | **confirmed with scope** | §4.2.4 支持 `exact` 与可选 `prefix`/`suffix`；§4.2.5 支持 zero-based `start`、exclusive `end`；§4.3 的 TimeState 记录 source/time state。规范还说明 position selector 对内容变化较脆弱。 | 支持 quote/position/representation state 组合的 proposed locator；不支持把 selector 当作 snapshot identity、publisher authenticity 或跨 extractor 的稳定 ID。 | selector reattachment、OCR/PDF normalization、changed-page handling 和 retention policy 需要项目测试。source-methodology 已移除把 `content_hash` 归因给 W3C 的表述，改为项目 proposed identity/change-detection 字段。 |
| C7 | Systematic review reporting 应列出 all sources、dates、eligibility、appraisal、synthesis、limitations、funding/sponsor role。 | National Academies, *Finding What Works in Health Care: Standards for Systematic Reviews*, Chapter 7。<https://www.nationalacademies.org/read/13059/chapter/7> | **confirmed with scope** | 官方章节可见 “All sources of information about potentially eligible articles”、 “Date of last search”、eligibility criteria、risk-of-bias assessment、qualitative/quantitative synthesis、strengths/limitations、以及 “the role of the funder”。 | 支持透明记录 source boundary、selection、appraisal、synthesis 和 sponsor role；不能把 health-care review standard 变成每一种 engineering investigation 的必填字段集合。 | 官方页面在末尾带 “Content truncated”；只能确认可见章节和表格范围，不能声称穷尽整章。 |
| C8 | IPCC 的 confidence 可与 evidence/agreement 区分，likelihood 是另一种不确定性表达，evidence type/amount/quality/consistency 可作为概念参考。 | IPCC AR6 WGI Chapter 1, Box 1.1。<https://www.ipcc.ch/report/ar6/wg1/chapter/chapter-1/>；PDF <https://www.ipcc.ch/report/ar6/wg1/downloads/report/IPCC_AR6_WGI_Chapter01.pdf> | **unverified in this pass** | official-domain Search result 暴露 Chapter 1/PDF 入口，以及 “type, amount, quality and consistency of evidence” 与 evidence/agreement、confidence/likelihood 的摘要性描述。 | 该概念可能适合作为“证据基础、agreement、uncertainty 不混为一项”的 analogy，但当前不能用于声称 IPCC 的细粒度 calibrated language 已被读取或适用于本项目。 | 直接 HTML/PDF 在本轮 WebFetch 不可用；source-methodology 已将其降级为 provisional conceptual analogy，不复制 numerical likelihood table/terms。 |
| C9 | Reuters standards 可支持 cross-checking、named sources、seeking comment、independence。 | Reuters Agency, Journalistic Standards。<https://reutersagency.com/about/standards-values/> | **unverified / not used** | 本轮只有 Search result summary，没有直接正文。 | 不把 vendor/journalism policy 的摘要当作本项目 evidence sufficiency 的 primary proof。当前 memo 的 current-events guidance 主要是 proposed synthesis。 | 需要直接可读的 owning page 才能做 claim-level verification；本轮没有依赖该来源作设计依据。 |

## 4. 被 refute 或修正的地方

### 4.1 Cochrane claim 收窄

原 memo 把“作者或组织联系”列入本轮已核验的 Cochrane source 组合。由于当前官方页面 extraction 在相关内容处存在截断，无法在本轮把该项作为完整核验结果。已在 `source-methodology.md` 改为：核心可见正文支持多个 databases、registries、grey literature、reference/citation checking 和未发表研究问题；作者/组织联系不再写成已独立核实的必备项。

这不是否认 Cochrane 其他版本或补充材料可能讨论 contact；只是拒绝把本轮没有完整读取的细节写成已验证事实。

### 4.2 GRADE 术语纠正

原 memo 用“证据 certainty”概括 2004 原文。原文标题与正文主要使用 `quality of evidence`，并另行讨论 `strength of recommendations`。已改为“证据质量/确定性”，在事实陈述中优先保留原文 `quality of evidence`。后续 literature 的 terminology 不能反向覆盖原始文章。

### 4.3 W3C locator 与 hash 的边界纠正

W3C Web Annotation 定义 selector 和 TimeState，但没有规定本项目的 `content_hash`、snapshot identity 或 source authenticity。已把 `content_hash` 明确标为本项目 proposed 的 representation identity/change-detection 字段，并把 source representation/time 的记录归入 TimeState 能表达的范围。W3C selector 不应被写成 truth proof。

### 4.4 IPCC claim 降级

IPCC official Search result 能证明入口存在，不能证明已经读取官方 Box 1.1 的完整上下文。已把 S5 的 access status 记为 `Search-only / unavailable`，并限制其用途为 provisional conceptual analogy。

## 5. 对“source 足够”方法的 adversarial transfer review

### 5.1 Primary source 不是自动的充分证据

- 官方 regulation 可直接支持文本、版本和生效日期，却不单独证明 implementation/effect。
- Maintainer docs 可直接支持 API definition 或 stated support，却不单独证明 latency、quality、coverage 或长期稳定性。
- 一次本地 run 可支持该 run 的 observation，却不能外推为 universal benchmark。
- 一篇 primary study 可直接支持其 sample、method 和 reported outcome，却不自动支持 broader causal claim。
- Systematic review 可更适合回答已有研究的整体 pattern，但仍要检查其 search boundary、eligibility、risk-of-bias、funding 和更新状态。

因此 `source_role` 的设计是合理的 proposed abstraction，但 role 本身不产生 quality judgment；claim-level directness、provenance、counterevidence 和 uncertainty 仍需 agent 判断。

### 5.2 多个 domain 不等于独立 corroboration

这一点是方法性 interpretation，而不是任何 Search engine 字段保证。不同页面可能共同复制 press release、wire、dataset、匿名 source 或同一 quote chain。要声称 independent corroboration，必须追 provenance/evidence-generation path；`domain_count` 不能代替 `provenance_cluster`。

本轮没有找到一个通用、已验证、适用于新闻/technical docs/academic papers 的 provenance clustering algorithm。因此 memo 中 cluster 字段、识别规则和 stop signal 必须继续保持 proposed/unvalidated。

### 5.3 缺失不是随机缺失

`paywall`、regional block、JS-only、scanned PDF、image-only、OCR failure、language barrier 和 deleted/updated page 会系统性影响某些主题、地区、机构或证据类型。source-methodology 要求区分 `not found`、`not indexed`、`access denied`、`parse failed`、`ocr partial`、`truncated`，这一要求是谨慎的设计 recommendation；本轮没有对这些 missingness mechanism 做定量 bias study。

不能将以下转换视为合法推理：

- “Search 没找到” → “没有该事实/反例”；
- “页面不可读” → “source 不存在”；
- “SERP snippet” → “完整正文/方法”；
- “OCR 没识别到文字” → “图片没有文字”；
- “Google-only candidate set” → “全网 recall 足够”。

### 5.4 Framework transfer 的边界

| Framework | 适合借用的最小概念 | 不应直接迁移的部分 |
|---|---|---|
| Cochrane Chapter 4 | 不依赖单一 source；按问题增加 source type；主动处理 unpublished/grey evidence | healthcare intervention review 的具体 search workflow 当作所有 report type 的硬 checklist |
| PRISMA-S | query、platform、date、limits、records、dedupe 的 reporting transparency | 把 reporting completeness 当成 retrieval quality 或 evidence truth |
| ACRL | authority 随 context 和 information need 变化 | 把 authority contextual 化解释为没有相对权威差异 |
| GRADE 2004 | 把 design/quality/consistency/directness 拆开；不混淆 evidence quality 与 recommendation | healthcare 的 level、downgrade/upgrade、clinical decision rule |
| National Academies | source、eligibility、appraisal、synthesis、limitations、sponsor role 的报告 | 以 systematic-review reporting chapter 证明 technical/current-events 的结果为真 |
| W3C PROV / Annotation | provenance relation、quote/position/state locator | 自动给 evidence truth、independence、authenticity 或跨 representation 永久稳定性 |
| IPCC | evidence、agreement、confidence/likelihood 作为分离不确定性概念的候选启发 | 在未直接读取本轮官方文本的情况下复制 calibrated scale 或数值 likelihood |

## 6. 对 `source-methodology.md` 的剩余结论

### 6.1 可以保留的核心结论

1. **不使用 universal source-count threshold。** 来源是否足够应按 material claim、claim consequence、source role、directness、provenance、counterevidence、recency/version、language/geography 和 access completeness 判断。
2. **Search transparency 与 evidence sufficiency 分开。** PRISMA-S 只能支撑记录检索过程的透明性；它不替 agent 判断 claim 是否被证据支持。
3. **Primary/secondary 采用 role-based 判断。** “primary” 对定义、法律文本、版本事实或原始记录通常有优势，但对 effect、quality、generalization 可能仍需独立 reproduction 或 synthesis。
4. **Evidence matrix、`supports`/`contradicts`/`context`/`unresolved`、provenance cluster 和 stop/continue 仍是 agent-owned proposed mechanisms。** server 提供 observable metadata 和 coverage/failure state，不返回 numeric truth score。
5. **Google-only 不能从本 memo 推出 coverage sufficiency。** 多轮 query 和多 domain reading 可以是 agent 的 proposed strategy，但实际 domain/language/geography coverage、重复率、freshness 和 blocking 仍需真实 corpus 验证。

### 6.2 仍不能写成已验证事实的内容

- `provenance_cluster` 的识别精度或任何阈值；
- material claim 的最低 source 数或 universal stop rule；
- `authority_basis`、`directness_notes` 或 `source_reliability_notes` 的可比性；
- OCR/JS/PDF extraction 能提供哪些稳定 version/publisher/page/block locator；
- Google-only route 的 recall、freshness、regional coverage、阻断率；
- `content_hash` 或任何 hash 对 source authenticity 的证明能力；
- agent 按该 rubric 停止研究后，事实正确率、报告质量或用户决策质量会提高多少。

## 7. High-impact unresolved gaps

1. **S5 IPCC source remains unavailable.** 若继续引用，应保留 Search-only/unverified 标记，或之后直接读取 official Chapter 1/PDF 后再升级。
2. **Cochrane full section context remains partial.** 如需保留 author/contact 或更细的 language/format restriction claim，应重新获取完整 Chapter 4 或可读 supplement，逐段核对。
3. **Framework transfer needs case review.** 至少要用四类 report 的真实 claim set 做人工 review，检查 Cochrane/PRISMA-S/GRADE/IPCC concepts 是否导致过度要求、错误排除或虚假 confidence。
4. **Independence detection has no validated algorithm.** 需要 labeled syndication/press-release/dataset/quote-chain cases；不能从 domain 数或 URL 数推断。
5. **Missing-not-at-random needs sampling.** 需要记录 access failures by report type、language、geography、modality 和 source role，再决定 coverage disclosure 的最低字段。
6. **Evidence metadata availability is unverified.** HTML、JS-rendered page、born-digital/scanned PDF、网页文字图片和 standalone image URL 上的 publisher/version/locator/OCR state 需要真实 corpus 验证。
7. **No external library/CPU/license/protocol claim was validated here.** 若 source strategy 后续引用其他 memo 的 Trafilatura/Playwright/pypdf/Docling/Tesseract/PaddleOCR、MCP version 或 license/platform assertions，应对那些 memo 单独执行同等 primary-source ledger，不得把本文件的 S1–S8 核验当作覆盖证明。

## 8. Verified source URLs

- Cochrane Chapter 4: <https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-04>
- PRISMA-S full text: <https://pmc.ncbi.nlm.nih.gov/articles/PMC7839230/>
- PRISMA-S DOI: <https://doi.org/10.1186/s13643-020-01542-z>
- ACRL Framework: <https://www.ala.org/acrl/standards/ilframework>
- GRADE 2004 full text: <https://pmc.ncbi.nlm.nih.gov/articles/PMC428525/>
- GRADE DOI: <https://doi.org/10.1136/bmj.328.7454.1490>
- National Academies Chapter 7: <https://www.nationalacademies.org/read/13059/chapter/7>
- W3C PROV-DM: <https://www.w3.org/TR/prov-dm/>
- W3C Web Annotation Data Model: <https://www.w3.org/TR/annotation-model/>
- IPCC Chapter 1 (not directly verified in this pass): <https://www.ipcc.ch/report/ar6/wg1/chapter/chapter-1/>
- IPCC Chapter 1 PDF (not directly verified in this pass): <https://www.ipcc.ch/report/ar6/wg1/downloads/report/IPCC_AR6_WGI_Chapter01.pdf>
- Reuters standards (not directly verified and not used as hard evidence): <https://reutersagency.com/about/standards-values/>

## 9. Final verdict

`source-methodology.md` 的 design-driving primary claims大体有可靠来源支撑，但不是所有 citation ledger 条目都达到同一访问强度。S1、S4、S5 和 W3C locator 的边界已修正：Cochrane author/contact 细节收窄，GRADE 2004 术语回到 `quality of evidence`，IPCC 降级为未核验 conceptual analogy，`content_hash` 不再归因于 W3C selector。其余 core claims 以 source-specific scope 保留。

本 memo 足以支持继续把“claim-level evidence matrix + provenance/access/counterevidence metadata + agent-owned stop/continue”作为 **proposed research design**；不足以支持任何 universal source quota、truth score、Google coverage guarantee、provenance algorithm、benchmark、library/platform/license approval 或已实现 tool contract。
