---
title: Source Disclosure Completeness Audit
status: addressed-see-followup
audit_date: 2026-09-10
scope: Q1 source strategy、Q3 progressive disclosure、accepted ADR/scope、topic verification notes
verdict: pass with blockers for implementation acceptance
followup: ./correction-verification.md
---

# Source Disclosure Completeness Audit

> 2026-09-10 后续：本审查提出的文档级问题（HIGH-01、HIGH-03、HIGH-04 以及复核者提出的 required-format gate、instance/upstream 观测层级、增量 OCR `advance` 机制、identity 字段、context closure 边界、baseline 继承、database 措辞）已在四份综合文档中修正；逐项复核见 [correction-verification.md](correction-verification.md)。BLOCKER-01（differentiator 尚无 A/B 证据）与 BLOCKER-02（required formats 尚未 release-complete）需要 runtime 验证才能关闭，文档修正不能替代；HIGH-02、HIGH-05 与 MEDIUM 项同样保持 open。以下原始 findings 保留为历史记录。

## 1. Verdict

**总体判断：研究结论和设计方向可继续；不能把 Q3 differentiator 或 v1 format coverage 写成已验证结果。**

本次没有发现推翻整体架构的 P0 contradiction。四份 synthesis 保留了用户要求的职责边界、Google-only Search、standalone `web_read`、HTML/JS/PDF/OCR/image 全部 required formats、no-LLM baseline、no `deep_search` 和 caller-owned research planning。

但有两个必须明确的 blocker：

1. **Progressive Disclosure 作为主要 differentiator 尚无直接 research-agent A/B 证据。** 目前只能称为 proposed hypothesis，不能称为已证明的默认优势。
2. **所有 required formats 的 runtime quality、lossiness 和 citation reattachment 尚未完成验证。** 既有 `4c210d1` CPU functional smoke 是有价值的受限证据，但不是公开互联网 quality benchmark、research-agent A/B、performance SLA 或最终 contract conformance。

此外，发现一处 accepted scope 的 retry wording 残留、一个 Q3 source citation precision gap、一个可能被误读为缩小 image scope 的 `asset` wording，以及若干 implementation gate 尚未落地。

## 2. Completeness matrix

| 审计项 | 状态 | 依据与判断 |
|---|---|---|
| Q1 研究 report source needs，而非只列 library | **Pass** | `docs/research/research-source-strategy.md:69-125` 的 report-type matrix、claim-level worksheet、source role、directness、provenance、counterevidence 和 access state；`docs/design/research-source-strategy.md:64-130` 转成 caller-owned query strategy。 |
| Q3 是独立 deep research，不是 cursor-only | **Pass as research direction** | `docs/research/progressive-disclosure.md:13-37, 60-124` 讨论 human/agent evidence、representation、context closure、alternatives 和 paired evaluation；`docs/design/progressive-disclosure.md:13-39` 明确 differentiator hypothesis。 |
| 普通 HTML | **Retained; unvalidated** | `docs/research/progressive-disclosure.md:40-50, 128-150`；`docs/design/progressive-disclosure.md:529-543`。 |
| JavaScript-rendered pages | **Retained; unvalidated** | browser acquisition、rendered DOM、download 和 JS scope warning；同上。 |
| born-digital / mixed / scanned PDF | **Retained; unvalidated** | `docs/research/progressive-disclosure.md:151-160`；route matrix 明确 native/OCR lineage。 |
| 网页文字图片、standalone image URL OCR | **Retained; unvalidated** | `docs/research/progressive-disclosure.md:161-170, 481-487`；`docs/design/progressive-disclosure.md:529-543`。 |
| Google-only v1 | **Pass** | ADR-0004:12-17；`docs/design/research-source-strategy.md:132-181` 明确 `route=searxng`, `backend=google`, `engine=google`。 |
| 不把 SearXNG 与 Google 当独立 engines | **Pass** | `docs/research/research-source-strategy.md:20-23, 150-161`；`docs/research/2026-09-10-source-disclosure/search-coverage-verification.md:36-47`。 |
| retry / fallback explicit | **Pass with wording defect** | ADR-0004 明确 default no retry；design 明确 no implicit fallback。但 `docs/design/search-mcp-scope.md:37` 仍留有较早的“只做有限自动重试”。 |
| no LLM synthesis | **Pass** | `docs/research/progressive-disclosure.md:23-26, 349-372`；`docs/design/progressive-disclosure.md:59-66, 349-372`。 |
| no server-side `deep_search` | **Pass** | ADR-0001；`docs/research/research-source-strategy.md:10-12, 476-486`；`docs/design/research-source-strategy.md:534-536`。 |
| no paid / GPU dependency smuggling | **Pass as documentation; gate open** | PyMuPDF、Docling、PaddleOCR、Tesseract、RapidOCR/ONNX Runtime 等均被标为 candidate、optional 或需 license/CPU validation；没有被写成 approved dependency。 |
| truth independent from URL/score | **Pass** | `docs/research/research-source-strategy.md:16-23, 35-52, 232`；`docs/design/research-source-strategy.md:48-62, 183-193, 335-373`。 |
| accepted vs proposed separation | **Mostly pass** | 四份文档均有 front matter、Accepted requirements、Proposed / unvalidated 和 Open validation；仍需在最终 tool schema 中保留同样区分。 |
| cursor identity/lifecycle | **Proposed and well scoped; unvalidated** | `docs/research/progressive-disclosure.md:88-124, 193-198`；`docs/design/progressive-disclosure.md:461-527`。涵盖 snapshot/representation/config/expiry，但没有 target host、restart、TTL 和 concurrency 实测。 |
| format quality/lossiness | **Proposed and well scoped; unvalidated** | capture、extraction、output 和 semantic warnings 分轴；`docs/design/progressive-disclosure.md:217-267`。尚无 frozen corpus quality result。 |
| completeness/citation tests | **Proposed acceptance gates** | `docs/research/progressive-disclosure.md:374-444, 497-512`；`docs/design/progressive-disclosure.md:675-741`。测试设计齐全，但没有已通过的结果。 |

## 3. Findings, severity and corrections

### BLOCKER-01 — Q3 differentiator 未经直接验证

**Severity：Blocker for claiming the differentiator; not a blocker for continuing the proposal.**

**Exact locations**

- `docs/research/progressive-disclosure.md:21-26, 73-75, 124`
- `docs/research/progressive-disclosure.md:374-404, 497-512`
- `docs/design/progressive-disclosure.md:27-39, 677-741`
- `docs/research/2026-09-10-source-disclosure/disclosure-interaction-verification.md:51-63`

**Missing evidence**

No direct frozen-corpus paired experiment compares bounded full Markdown、fixed chunks、structure-aware blocks、`preview -> find -> read/expand`、evidence window 和 all-at-once under equal source snapshot、representation、agent/model、quality floor and total budget. Existing ReAct、SWE-agent、ToolSandbox、Lost in the Middle evidence is indirect and task-specific.

**Actionable correction**

Keep the wording as **proposed differentiator hypothesis**. Do not make it the accepted default or claim token/quality superiority until the proposed paired evaluation reports material-claim recall、quote fidelity、caveat preservation、negative-result honesty、tool-call burden and evidence bytes/tokens at a fixed quality floor. The existing `4c210d1` smoke should be inherited as a functional baseline, not treated as this A/B evidence.

### BLOCKER-02 — Required formats are retained but not yet release-complete

**Severity：Blocker for declaring v1 format-complete; not a contradiction in the research.**

**Exact locations**

- `docs/research/progressive-disclosure.md:40-50, 128-170`
- `docs/research/progressive-disclosure.md:473-512`
- `docs/design/progressive-disclosure.md:529-558, 743-765`
- `docs/research/2026-09-10-source-disclosure/format-fidelity-verification.md:62-75, 108-110`
- `docs/research/2026-09-10-source-disclosure/disclosure-interaction-verification.md:16-24, 51-59`

**Missing evidence**

No new clean-machine Windows CPU run, public corpus fidelity study, OCR alignment test, table/reading-order audit, JS completeness test, browser download semantics test, or source locator reattachment test was executed in this audit. The pinned smoke covers constrained functional paths only.

**Actionable correction**

Before v1 acceptance, require fixtures for static HTML、JS hydration/collapsed content、native/mixed/scanned PDF、web text image、standalone image、table/footnote、partial OCR and source mutation. Each fixture must record capture status、extraction coverage、output truncation、semantic warnings、locator reattachment and honest `partial/unsupported/refused` state. Do not remove a required format from the contract while a route is incomplete.

### HIGH-01 — Accepted scope retains stale retry wording

**Severity：P1 implementation ambiguity.**

**Exact locations**

- `docs/design/search-mcp-scope.md:14` correctly says the earlier wording must not override ADR-0004.
- `docs/design/search-mcp-scope.md:37` still says “只做有限自动重试”。
- `docs/adr/0004-v1-search-read-boundary.md:12-18` says default no retry and caller-issued new attempt.
- `docs/design/research-source-strategy.md:530-532` also records the chronology, but an implementer may still read the old line as scope.

**Missing evidence**

The issue is not primary-source evidence; it is an unresolved document-level contradiction in the accepted scope page.

**Actionable correction**

Replace the stale line with one canonical statement:

> Search v1 默认不 automatic retry，也不做 implicit backend fallback。Retry 或 extraction escalation 必须由 caller/policy 显式发起、可审计并保留原失败状态。

Clarify that browser/OCR escalation is a new representation/route decision, not an implicit Search retry.

### HIGH-02 — Cursor identity/lifecycle is proposed, but host and persistence evidence is absent

**Severity：P1 contract readiness.**

**Exact locations**

- `docs/research/progressive-disclosure.md:88-124, 193-198`
- `docs/design/progressive-disclosure.md:461-527, 576-596`
- `docs/research/2026-09-10-source-disclosure/disclosure-representation-verification.md:84-92`
- `docs/research/2026-09-10-source-disclosure/disclosure-interaction-verification.md:51-59`

**Missing evidence**

No target MCP host conformance test for `structuredContent`/TextContent parity、resource links、custom URI、embedded resources or tool execution errors. No test covers restart、TTL/eviction、concurrent continuation、source mutation、cursor replay or raw-retention deletion.

**Actionable correction**

Keep `source_snapshot_id`、`representation_id`、structure/config binding、opaque cursor and explicit expiry as proposed contract elements. Add failure fixtures for `source_changed`、`snapshot_expired`、`cursor_expired`、`representation_missing` and `output_truncated`. Require no silent refetch and verify that old citation remains attached to old representation. Do not infer host behavior from MCP specification alone.

### HIGH-03 — One consequential MCP statelessness claim has imprecise inline citation

**Severity：P1 evidence traceability, not architecture correctness.**

**Exact locations**

- `docs/research/progressive-disclosure.md:22` attributes MCP statelessness/pagination in citation range `[S9-S17]`.
- `docs/research/progressive-disclosure.md:527-545` lists S7 Tools、S8 Resources、S9 Pagination, but does not list the MCP Basic statelessness page.
- `docs/design/progressive-disclosure.md:782-793` does list MCP Basic, so the design document is stronger than the research report here.

**Missing evidence**

The underlying claim is supported by the MCP Tools stateful-tools section and/or MCP Basic statelessness page, but the research report's inline range does not clearly point to the relevant entry. The source ledger should not make a reader infer that S9 Pagination proves statelessness.

**Actionable correction**

Add the owning MCP Basic statelessness URL to the Q3 research ledger and cite it directly at the statelessness sentence. Keep the existing warning that stateful-tools guidance is non-normative; do not turn it into a protocol MUST.

### HIGH-04 — `asset` marked optional could be misread as dropping required image support

**Severity：P1 scope wording.**

**Exact locations**

- `docs/research/progressive-disclosure.md:230-239` labels `asset` optional.
- `docs/design/progressive-disclosure.md:398-400` repeats optional `asset` while standalone image URL and OCR remain required in `:529-543`.
- `docs/research/progressive-disclosure.md:473-487` correctly says phases must not remove HTML/JS/PDF/OCR/image scope.

**Missing evidence**

No explicit contract sentence says whether image acquisition/OCR is mandatory while an `asset` action is merely one optional exposure mechanism.

**Actionable correction**

Change wording to:

> Image acquisition and OCR coverage are required by the accepted scope. `asset` is only an optional caller-facing operation for returning image/page bytes or crops; required image OCR must remain reachable through `initial`/`find`/`read` or another explicit action.

Add a standalone image fixture and a test that OCR failure preserves the raw asset and reports `ocr_low_signal`/partial rather than no text.

### HIGH-05 — Candidate dependencies are correctly unapproved, but no final approval gate exists

**Severity：P1 before dependency adoption.**

**Exact locations**

- `docs/research/progressive-disclosure.md:151-170, 327-347`
- `docs/design/progressive-disclosure.md:529-558, 743-765`
- `docs/design/research-source-strategy.md:516-525`
- `docs/research/2026-09-10-source-disclosure/format-fidelity-verification.md:62-75, 108-110`

**Missing evidence**

Exact package versions、transitive licenses、traineddata/model/weights terms、Windows CPU clean-machine path、RAM/latency、browser binary version and distribution model remain open. Existing smoke execution does not approve RapidOCR/ONNX Runtime/pypdfium2/Trafilatura/Playwright or any replacement.

**Actionable correction**

Create a dependency ledger with package/version/license/direct-or-transitive/CPU-GPU/network/runtime cost/approval/fallback. Keep PyMuPDF AGPL/commercial、Docling platform/model caveats、PaddleOCR model/runtime terms and SearXNG target release as explicit gates.

### MEDIUM-01 — Healthcare frameworks are used carefully, but transfer validation remains absent

**Severity：P2 scope/transfer limitation.**

**Exact locations**

- `docs/research/research-source-strategy.md:16-20, 27-39, 423-443`
- `docs/research/2026-09-10-source-disclosure/source-methodology-verification.md:44-56, 122-162`
- `docs/design/research-source-strategy.md:562-570`

**Missing evidence**

Cochrane、PRISMA-S、GRADE、National Academies主要来自 healthcare/systematic-review context。文件已经明确它们不是 technical/current-events universal checklist，但没有真实四类 claim set 的 transfer review。

**Actionable correction**

Keep the role-based concepts as interpretation/proposal. Before turning the worksheet into a universal rubric, review representative factual/technical、comparative、policy/current-events and academic claims; record where a framework over-requires sources or creates false confidence.

### MEDIUM-02 — Source identity/provenance grouping is explicitly hypothetical, but acceptance criteria must prevent false independence

**Severity：P2.**

**Exact locations**

- `docs/research/research-source-strategy.md:20, 43-52, 273-284`
- `docs/design/research-source-strategy.md:335-373`
- `docs/research/2026-09-10-source-disclosure/search-coverage-verification.md:60-68`

**Missing evidence**

No cross-domain labeled set for syndicated pages、press-release copies、mirrors、quote chains or hosted platforms; no validated clustering algorithm or threshold.

**Actionable correction**

Keep `provenance_cluster`/`ownership_group_id` as hypothesis with `unknown` state. Add adversarial fixtures and human adjudication before exposing any numeric independence or source-count acceptance rule. Domain count, URL count, `rel=canonical`, hash or score must not be sufficient evidence.

### MEDIUM-03 — Search coverage and filter semantics remain unvalidated

**Severity：P2.**

**Exact locations**

- `docs/research/research-source-strategy.md:53-61, 267-271`
- `docs/design/research-source-strategy.md:132-181, 375-412`
- `docs/research/2026-09-10-source-disclosure/search-coverage-verification.md:60-78`

**Missing evidence**

No live target SearXNG instance test for locale/language/time filters、page overlap/skip、CAPTCHA/429 rate、Google coverage、filter precision or target release variance.

**Actionable correction**

Keep requested/configured/effective filter states separate. Treat `pageno`/opaque continuation as best-effort, not immutable snapshot. Run bounded capability and drift experiments before setting any page/result/deadline defaults. Do not claim Web-wide recall.

## 4. Primary-source spot checks

The following high-consequence claims were rechecked against owning sources on 2026-09-10. These checks support the narrow facts only; they do not validate this project's runtime behavior.

| Claim checked | Owning primary source and observed evidence | Audit result / limit |
|---|---|---|
| SearXNG Search API exposes `q`, `language`, `pageno`, `time_range`, `format`, `safesearch`; some filter support is engine-dependent; disabled format can return 403 | SearXNG Search API: https://docs.searxng.org/dev/search_api.html. The page describes `q`, `language`, `pageno`, `time_range`, `format`, `safesearch`; says time-range/safesearch apply only to engines that support them and disabled format may return `403 Forbidden`. | **Confirmed within API-doc scope.** Does not prove target instance behavior or Google filter precision. |
| Google search result availability and ordering are context-sensitive | Google Search Central, https://developers.google.com/search/docs/fundamentals/how-search-works. Short quotes: “Relevancy is determined by hundreds of factors” including location/language/device; “Indexing isn't guaranteed.” | **Confirmed.** Does not provide this project's recall, drift or SLA. |
| SearXNG `score` is aggregation mechanics, not truth evidence | Pinned `results.py`: https://raw.githubusercontent.com/searxng/searxng/3fdc6d753a339b5f4a7dc5842c94c0d8324726f1/searx/results.py. `calculate_score()` uses engine weight/position/priority; duplicate merge appends positions; ordering first sorts score and then groups categories/templates/images. | **Confirmed for the pinned source snapshot.** Snapshot behavior is not the selected deployment release and does not prove score calibration. |
| MCP pagination cursor is opaque and page size is server-determined | MCP Pagination, https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/pagination. Short quote: “The cursor is an opaque string token”; page size is determined by server; client must not parse or modify cursor. | **Confirmed.** This does not define custom `web_read` continuation identity, persistence or source snapshot semantics. |
| MCP structured results, resource links, execution errors and stateful handle guidance | MCP Tools, https://modelcontextprotocol.io/specification/2026-07-28/server/tools. The page defines `structuredContent`, resource links and `isError`; stateful-tools section explicitly says “This section is non-normative guidance” and describes explicit handles. | **Confirmed with normative-strength caveat.** Project schema/state policy remains proposed and host behavior needs conformance tests. |
| W3C selectors require normalization and explicit state | W3C Web Annotation, https://www.w3.org/TR/annotation-model/. Short evidence: text must be normalized; position starts at 0 with exclusive end; position selectors are “very brittle” under source changes; States are processed before selectors. | **Confirmed.** Does not supply project snapshot storage, OCR/PDF mapping or authenticity proof. |
| PDF semantic layer and OCR limits | pypdf extraction docs, https://pypdf.readthedocs.io/en/stable/user/extract-text.html. Short evidence: “PDF files don’t contain a semantic layer”; image-only pages should consider OCR; visitor coordinates may be wrong. | **Confirmed.** Does not validate any chosen extractor on target corpus. |
| Tesseract 4-core wording is documentation, not benchmark | Tesseract compilation/OpenMP docs, https://tesseract-ocr.github.io/tessdoc/Compiling-%E2%80%93-GitInstallation.html. It describes default single-image OCR using 4 CPU cores and a bulk-processing strategy using independent single-threaded instances. | **Confirmed with limit.** Not a target Windows throughput/RAM result. |

## 5. Explicit scope limits

This audit does **not** establish:

- live Google/SearXNG coverage, recall, freshness, filter precision, CAPTCHA rate or pagination stability;
- target SearXNG release/instance behavior;
- public-internet HTML/JS/PDF/OCR/image fidelity;
- Windows CPU latency, RAM, throughput or clean-machine installability;
- OCR quality, reading order, table reconstruction, formula/chart semantics or citation reattachment;
- MCP client/host retention of `structuredContent`, TextContent, resource links, custom URI or tool errors;
- snapshot TTL, restart recovery, eviction, locking, concurrency or authorization behavior;
- universal source quotas, provenance-clustering precision, numeric truth score or report correctness;
- paid/GPU/license/ToS/retention permission for any candidate component or source content;
- benefit of Progressive Disclosure over bounded full/fixed/all-at-once variants;
- any runtime result not explicitly recorded in the existing pinned smoke reports.

The project evidence record must continue to distinguish:

- **Fact:** supported by an accessible owning source or existing recorded run;
- **Interpretation:** reasoned transfer with explicit limits;
- **Proposed design:** not accepted or implemented;
- **Open validation:** required experiment not yet run.

## 6. Final decision

**Approve the four synthesis documents as a proposed research/design baseline, not as a completed implementation contract.**

Before implementation acceptance, close HIGH-01 through HIGH-05 and run the format, citation, cursor lifecycle, dependency, and target-host tests. Before describing Progressive Disclosure as the project's demonstrated differentiator, close BLOCKER-01 with a frozen-corpus paired evaluation. Before declaring v1 format-complete, close BLOCKER-02 with required-format fixtures and honest partial/unsupported/refused behavior.

No required format was removed, no independent-engine claim was smuggled in, no LLM synthesis or `deep_search` facade was introduced, and no candidate paid/GPU dependency was silently approved. The remaining work is validation and contract hardening, not a change to the accepted research direction.
