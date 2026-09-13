---
title: Progressive Disclosure Architecture Proposal
status: proposed
proposal_date: 2026-09-10
implementation_status: proposed only; no runtime experiments performed
related_research: ../research/progressive-disclosure.md
---

# Progressive Disclosure Architecture Proposal

> 本文是 `web_read` 的 Proposed architecture，不是已接受的 product contract，也不是实现记录。日期为 2026-09-10；本轮没有运行新的 browser、OCR、PDF、Search 或 MCP host conformance experiment。研究依据见 [`progressive-disclosure.md`](../research/progressive-disclosure.md)。字段、状态、操作、budget、cursor policy、组件路线和 acceptance gates 均需后续 contract review、Windows/CPU validation、license review 与 target-host integration test。

## 1. Design thesis

把 Progressive Disclosure 设计成：

> **对同一份 `SourceSnapshot` 的同一或明确版本化 `ExtractionRepresentation`，提供 caller 可选择、可继续、可引用的多个 bounded views；每个 view 都公开 coverage、lineage、context closure 和恢复状态。**

它不是：

- 把全文盲切成固定页后加一个 `next_cursor`；
- 用模型 summary 代替原文抽取；
- server-side Deep Research 或自动 source synthesis；
- 强制所有 host 使用 MCP Resources；
- 用 URL、Markdown 行号或缓存 freshness 伪装成 immutable evidence identity。

### 1.1 Differentiator hypothesis

在相同 source snapshot、相同 extraction representation、相同 agent/model、相同总 byte/token budget 和相同 task quality floor 下，下面的 loop 可能比 bounded full/fixed chunks 更有用：

```text
bounded initial read
  -> deterministic find / outline navigation
  -> target section/page/block read
  -> context closure / evidence expansion
  -> caller decides whether to follow reference or search counterevidence
```

“可能”是关键字。现有 ReAct、SWE-agent、ToolSandbox、Lost in the Middle 证据只能支持 observation/interface/context shape 值得测，不能证明这条 loop 已优于 alternatives。不得把本 proposal 的任何数字写成 SLA 或默认值。

## 2. Scope and decision boundary

### 2.1 Accepted requirements

下表来自仓库已有 ADR、scope 和用户确认；本设计不重新批准它们：

| Accepted requirement | 本设计如何继承 |
|---|---|
| caller agent owns Deep Research planning/synthesis | server 只 acquisition、extraction、navigation、continuation、evidence state；不做 research plan 或 final synthesis |
| `web_search` 只发现 candidate URL/SERP metadata | `web_read` 可直接接受 caller URL，不要求来自 Search；不自动把 Search 结果变成 read |
| v1 无 server-side `deep_search` | 不新增 facade；`find/read/expand` 只针对一个 caller-selected source/representation |
| 首次 `web_read` 返回 metadata、outline（若可得）和限长正文 | `initial` proposal 默认兼容该边界；metadata-only 只能作为显式 experimental mode，不静默替换 |
| section/position continuation 与 page keyword location | 提供 structure/page/block/quote locator 和 opaque continuation；最终字段需 review |
| 支持 HTML、JavaScript page、PDF、扫描 PDF、网页文字图片、独立 image URL OCR | 路由 portfolio 必须保留这些输入；阶段性实验可以隔离 route，但不能从 v1 scope 删除 |
| free/open-source self-managed、Windows、CPU-only | component adoption 必须做 license/model/dependency/Windows CPU review；不能从文档能力推出目标环境 validation |
| default no retry 属于 Search route boundary | `web_read` 的 browser/OCR escalation 应有显式 policy/representation state；不把失败悄悄改写成另一种成功 |
| page content is untrusted data | extraction output、HTML comments、OCR text、PDF metadata、alt/code block 都不能改变 policy、credentials、budget、retention 或 tool calls |

### 2.2 Non-goals

- 不在 `web_read` 中判断 source authority、independence、truth、claim support 或最终 evidence sufficiency。
- 不自动跟随全部 references、cited URLs、internal links 或 citation graph。
- 不承诺任意 JS 页面、infinite scroll、personalized branch、复杂 PDF table、图表语义或 OCR 都能无损恢复。
- 不把 `complete_as_fetched` 解释成 semantic correctness。
- 不在 v1 默认启用 model-generated summary 或 LLM-based reordering。
- 不将 MCP Resources 当作 host 的共同最低能力。

## 3. Proposed architecture layers

```text
┌────────────────────────────────────────────────────────────┐
│ caller-controlled web_read action                          │
│ initial / preview / find / read / expand / asset           │
├────────────────────────────────────────────────────────────┤
│ bounded view + context closure + Markdown/typed projection │
├────────────────────────────────────────────────────────────┤
│ structural IR + navigation index                           │
│ document/section/block/page/table/figure/footnote          │
├────────────────────────────────────────────────────────────┤
│ extraction representations                                  │
│ static DOM | rendered DOM | PDF native/layout | OCR | image │
├────────────────────────────────────────────────────────────┤
│ source snapshot                                             │
│ raw bytes/download | redirects | retrieval metadata        │
├────────────────────────────────────────────────────────────┤
│ policy-controlled acquisition                               │
│ SSRF | DNS | robots | auth/paywall | browser egress        │
└────────────────────────────────────────────────────────────┘
```

### 3.1 Layer contracts

1. **Policy/acquisition layer**：验证 scheme、hostname、A/AAAA、redirect hop、response/decompressed size、robots/access policy；取得 HTTP bytes、browser rendered DOM、download、PDF/image asset。它只声称 capture 状态。
2. **Source snapshot layer**：把一次 retrieval 的 requested/final URL、redirect chain、retrieved time、response status/media type、raw digest、retention state 和 source policy revision 固定为 snapshot identity。
3. **Extraction representation layer**：每一种 static DOM、rendered DOM、native PDF text/layout、OCR page/region、image asset 和 normalized text 都有独立 representation lineage、extractor/config revision、normalization 和 coverage。
4. **Structural IR layer**：把 text、heading、paragraph、list、code、page、table、cell、figure、caption、footnote、reference、OCR region 等变成 typed nodes。IR 必须保留 inferred/warning/source locator，不把 Markdown 视为 source of truth。
5. **Navigation index**：对 outline、page inventory、deterministic find、table/figure/footnote markers、related references 建索引；index miss 只能说明 searched representation 未命中，不说明 source absence。
6. **Bounded view layer**：按 initial/preview/find window/section/page/range/evidence window/asset 生成 deterministic output；同时给 typed blocks 和 Markdown projection（若可表达）。
7. **Continuation/citation layer**：以 snapshot + representation + structure revision + query/selection + budget compatibility 约束 cursor；citation 保存 locator state，不把 cursor 当 citation identity。

## 4. Identity and evidence model

以下字段是概念 schema，所有名字都为 proposal。

### 4.1 `SourceSnapshot`

```text
SourceSnapshot {
  source_snapshot_id: opaque immutable id
  requested_url: string
  final_url: string?
  redirect_chain: RedirectHop[]
  retrieved_at: timestamp
  retrieval_status: fetched | partial_bytes | unavailable | policy_refused | failed
  response_status: integer?
  response_headers_summary: object
  raw_media_type: string?
  raw_charset: string?
  raw_byte_length: integer?
  raw_sha256: string?
  validators: {etag?, last_modified?}
  source_policy_revision: string
  retention_class: raw_allowed | metadata_only | deleted | unknown
}
```

`raw_sha256` 是 `SourceSnapshot` 原始字节（raw bytes）的 identity/change-detection 摘要，用于判断两次 retrieval 是否取得同一 raw payload；它不是 authenticity proof，也不等同于某个 `ExtractionRepresentation` 的 `content_digest`（见 4.2）——后者是对该 representation 内容的摘要，两者分属不同层级，不能互相替代或合并成一个笼统的“hash”。HTTP validator/freshness 也不能代替 snapshot identity。若 raw 不可保留，snapshot 必须显式反映 limitation；后续不能从新抓取 URL 伪装恢复旧 raw。

同一 `raw_sha256` 并不保证下游 OCR 输出或 reading order 一致：确定性要求同时锁定 extractor/OCR engine 版本、`extraction_config_hash`、渲染/解码 pipeline，并通过独立的 determinism test（同一 raw bytes + 同一 config 重复抽取，比较 `content_digest`/node digest）来验证，不能从“raw bytes 相同”直接推断“输出相同”。

### 4.2 `ExtractionRepresentation`

```text
ExtractionRepresentation {
  representation_id: opaque immutable id
  source_snapshot_id: string
  parent_representation_id: string?
  representation_kind:
    raw_bytes | static_dom | rendered_dom | pdf_native_text |
    pdf_layout | ocr_text | image_asset | normalized_text | markdown_projection
  extractor_name: string
  extractor_version: string
  extraction_config_hash: string
  text_encoding: string?
  unicode_normalization: none | NFC | NFKC | named_form
  newline_policy: string
  layout_metadata_policy: string
  capture_scope: object
  extraction_status: complete | partial | failed | unsupported
  coverage: object
  warnings: Warning[]
  content_digest: string?
}
```

关键 invariant：

- raw bytes、rendered DOM、extracted text、OCR、Markdown 都是不同 representation；
- extractor/OCR/browser config 改变即新 representation，不覆盖旧 representation；
- OCR expansion 是 child representation，不直接修改旧 text offsets；
- representation digest 不证明 semantic truth；
- `unicode_normalization`、newline、whitespace、HTML entity handling 必须显式，否则 quote/offset 无法复核；
- rendered DOM、network/download asset 都只是 capture artifacts，不是语义完整性证明；raw HTML digest 不代表 JS 执行后的完整状态，因为同一 raw bytes 在不同时间/环境执行 JS 可能产生不同 DOM；
- 一旦某个 representation 生成并对外发布（被某次 view/citation 引用过），即视为 frozen（immutable）：其内容、`content_digest`、`extraction_config_hash` 不再原地修改；新的抽取/OCR/渲染只能产生新的 child representation（见 6.6 `advance`），不得覆盖或“长大”旧 representation。

### 4.3 `DocumentNode`

```text
DocumentNode {
  node_id: opaque, unique within representation
  parent_id: string?
  kind: document | section | heading | paragraph | list | list_item |
        quote | code_block | link | image | figure | caption |
        page | text_block | table | table_row | table_cell | table_note |
        footnote_marker | footnote_definition | reference | ocr_region | unknown
  structural_path: string[]
  text: string?
  source_locators: Locator[]
  source_method: native_text | static_html | rendered_dom | pdf_geometry |
                 ocr | inferred_structure | markdown_projection
  coverage: complete | partial | omitted | unknown
  warnings: Warning[]
  children: string[]
}
```

`node_id` 不跨 snapshot/representation 复用；同文重复 paragraph 不得因为 text 相同而 collision。`content_hash` 只能是 change detection，不是 node identity。

### 4.4 `Locator` and citation

```text
Locator {
  representation_id: string
  kind: structural_path | text_position | text_quote | dom_path |
        pdf_region | ocr_region | asset_region | page_block
  normalization: string
  offset_unit: byte | unicode_code_point | grapheme_cluster | utf16_code_unit
  start?: integer
  end?: integer
  quote?: string
  prefix?: string
  suffix?: string
  page_number?: integer
  bbox?: [number, number, number, number]
  node_id?: string
}

Citation {
  citation_id: opaque id
  source_snapshot_id: string
  representation_id: string
  locator: Locator
  source_state: {retrieved_at, content_digest, extraction_config_hash}
  rehydration_status: direct | view_reprojected | rehydrated | ambiguous | failed | unavailable
  retention_status: string
}
```

推荐同时保存 structural/page locator、quote selector 和 position selector（若 retention 允许）。如果只能保存 digest/position，必须说明无法回到 raw bytes。跨 representation 的 rehydration 需要新的 citation 或 mapping record，不应静默复用旧 ID。

## 5. Capture、extraction、coverage 与 output state

### 5.1 三条独立状态轴

```text
capture_status:
  fetched | partial_bytes | unavailable | policy_refused | failed

extraction_status:
  complete | partial | failed | unsupported

output_status:
  complete | truncated
```

附加 `semantic_warnings`：

```text
reading_order_inferred
merged_cells_uncertain
footnote_unresolved
ocr_approximate
image_text_only
figure_not_interpreted
javascript_scope_limited
service_worker_visibility_limited
```

示例：

- PDF bytes capture 成功、native text extraction 只覆盖 7/10 pages、response 只输出其中两个 pages：`capture=fetched`, `extraction=partial`, `output=complete`（若没有达到 output cap）。
- extraction 已完成整个 representation，但 response 因 max output 截断：`extraction=complete`, `output=truncated`, 可给 same-representation cursor。
- JS shell 下载成功但 tab 未加载：`capture=fetched`, `extraction=partial`, `coverage_scope=initial_dom_only`，不是 `not_found`。
- OCR page 没识别出字：`extraction=partial/failed` 或 `ocr_low_signal`，不能写成 image 没有文字。

### 5.2 Failure taxonomy

```text
policy_refused          # SSRF/unsupported scheme/auth/paywall/robots policy
acquisition_failed      # network/DNS/redirect/HTTP/download failure
unsupported_format      # route unavailable for recognized representation
extraction_failed       # parser/OCR/browser processing failure
extraction_partial      # some pages/regions processed, some missing
output_truncated        # same representation has more output under continuation
source_changed          # new retrieval is not old snapshot
snapshot_expired        # old snapshot was evicted/deleted/unavailable
cursor_expired          # cursor invalid, snapshot may remain
representation_missing  # requested child representation not available
```

建议 execution error 与 structured content 并存：有 partial evidence 的 extraction failure 不应丢弃已取得 blocks；不可恢复的 policy/acquisition error 不应生成 empty Markdown。具体 MCP `isError` mapping 需 target host test，不从 spec 推断 host rendering。

## 6. Proposed operations

以下可作为一个 `web_read(action=...)` tool 的 `action` enum，也可拆成多个 tools；两者未收敛。

### 6.1 `initial` / `preview`

`initial` 是与 accepted first-read boundary 兼容的候选：metadata + outline（若可得）+ bounded lead/body + coverage/warnings。`preview` 是明确要求只要 navigation view 时的候选。

以下示例为 **hypothetical fictitious document**，不是已实现行为或已运行结果，仅用来说明字段含义。

```json
{
  "url": "https://example.invalid/neutral-report",
  "action": "initial",
  "budget": {"max_code_points": 320}
}
```

```json
{
  "source": {
    "source_snapshot_id": "opaque-snap-1",
    "representation_id": "opaque-rep-1",
    "representation_kind": "static_dom",
    "requested_url": "https://example.invalid/neutral-report",
    "final_url": "https://example.invalid/neutral-report"
  },
  "view": {
    "view_kind": "initial",
    "outline": ["Scope", "Observations", "Limitations"],
    "target_blocks": [
      {"kind": "heading", "text": "Scope", "node_id": "opaque-node-1"},
      {
        "kind": "paragraph",
        "text": "This fictitious field survey covers three sample plots recorded between March and April. Instruments were calibrated once before deployment.",
        "node_id": "opaque-node-2"
      }
    ],
    "markdown_projection": "# Scope\n\nThis fictitious field survey covers three sample plots recorded between March and April. Instruments were calibrated once before deployment."
  },
  "coverage": {
    "capture": "fetched",
    "extraction": "complete",
    "searched_scope": "static_dom_text_and_headings"
  },
  "output": {
    "status": "truncated",
    "truncation_reason": "max_code_points reached before end of selection"
  },
  "next_cursor": "opaque-cursor-1",
  "warnings": ["image_regions_not_ocr_searched"]
}
```

`output.status` 描述的是**本次 declared selection**（这里是 `initial` 的 bounded lead）是否已读完，不是整份文档是否读完，也不是 `extraction_status` 的替代：即使 `extraction=complete`（representation 已全部抽取），`output` 仍可能因为 `budget` 而 `truncated`；反过来 `extraction=partial` 时，`output` 也可能对已抽取部分显示 `complete`。两者必须分开判断。

`next_cursor` 只读取当前 representation 里已经**发布**（已抽取完成）的内容，不触发新的网络请求、渲染或 OCR——它单纯是“这份 representation 里还有更多已发布正文可以继续读”。如果本次 capture 还留有**尚未处理**（尚未抽取/尚未 OCR）的已捕获 pages/regions，响应会额外携带 `processing_continuation`（见 6.6 `advance`），与 `next_cursor` 分开表示“还有未处理的原始素材，需要显式发起有限处理”，而不是“还有可以直接读的正文”；二者可以同时出现，也可以只出现一个。

`metadata-only` 可以作为显式 experimental request，但不应覆盖当前 accepted “首次包含限长正文”边界。

### 6.2 `find`

目标是 deterministic, representation-scoped search，不是 summary。

```json
{
  "url": "https://example.invalid/neutral-report",
  "action": "find",
  "source_snapshot_id": "opaque-snap-1",
  "representation_id": "opaque-rep-1",
  "query": "sampling interval",
  "scope": "document",
  "limit": 8,
  "include": ["heading", "table", "caption", "footnote"]
}
```

匹配顺序（proposal）：exact phrase → case/Unicode/hyphen normalization → heading/table/caption/footnote scan → paragraph/block scan。后续 semantic retrieval 只能作为额外 route，仍需返回 verbatim text、match type、representation scope 和 locator。

空结果必须说明：

```json
{
  "matches": [],
  "negative_result": {
    "meaning": "not_found_in_searched_representation",
    "searched_scope": "static_dom_text",
    "omitted_scope": ["image_text", "unloaded_tab"]
  },
  "coverage": {"extraction": "partial"}
}
```

不得把空结果写成 source 没有该概念。

### 6.3 `read`

定位输入可选一个或多个：

```json
{
  "url": "https://example.invalid/neutral-report",
  "action": "read",
  "source_snapshot_id": "opaque-snap-1",
  "representation_id": "opaque-rep-1",
  "locator": {
    "kind": "structural_path",
    "node_id": "opaque-node-14"
  },
  "include": ["body", "tables", "captions", "footnotes"],
  "budget": {"max_blocks": 24, "max_code_points": 8000}
}
```

应返回 target blocks、context blocks、omitted context、typed structure 和 Markdown projection。仅按 local Markdown character range 不足以成为唯一 locator。

### 6.4 `expand`

`expand` 不等于“多给一些前后文字”，而是 context closure：

```json
{
  "url": "https://example.invalid/neutral-report",
  "action": "expand",
  "source_snapshot_id": "opaque-snap-1",
  "representation_id": "opaque-rep-1",
  "match_id": "opaque-match-2",
  "include_prerequisites": [
    "section_ancestry",
    "table_caption",
    "table_header",
    "unit",
    "footnote",
    "limitation"
  ],
  "direction": "both"
}
```

如果 prerequisite 受 budget 或 retention 限制无法提供，应返回 `omitted_context`/`unresolved_reference`，不能静默删掉 qualifier。

### 6.5 `asset`

用于 caller 明确要求 image/page crop/PDF asset metadata 或 policy 允许的 bytes。image view 应保留 asset lineage、alt/caption、OCR region、confidence 和 `figure_not_interpreted` 状态；不默认把 figure 生成 caption。

图片获取与 OCR 覆盖是 accepted scope 的必需能力：网页文字图片和独立 image URL 的 OCR 必须通过 `initial`/`find`/`read` 或另一显式动作可达。`asset` 只是把 image/page bytes 或 crop 交给 caller 的一种可选操作；即使最终 contract 不单独暴露 `asset`，必需的 image OCR 支持也不能因此缺失。OCR 失败时保留原始 asset 并报告 `ocr_low_signal`/partial，不得写成 image 没有文字。

### 6.6 `advance`（bounded incremental processing）

`advance` 是本 proposal 为“增量 OCR / 增量处理”选定的**唯一**默认机制：一个 synchronous、bounded、由 caller 显式发起的动作，只对已经 capture 的 source pages/regions 做新的有限抽取。它不是 background job，不产生 queued/server-side pending state，也不是 `next_cursor` 的隐式延伸——`next_cursor` 只读已发布内容，`advance` 才会做新的处理。

```json
{
  "url": "https://example.invalid/neutral-report",
  "action": "advance",
  "source_snapshot_id": "opaque-snap-1",
  "parent_representation_id": "opaque-rep-1",
  "selection": {"pages": [3, 4], "regions": ["opaque-region-9"]},
  "processing_budget": {"max_ocr_seconds": 20, "max_pages": 2}
}
```

行为约束：

- 输入必须包含 `source_snapshot_id`、要处理的 `parent_representation_id`、page/region selection 和一个 bounded `processing_budget`；
- 只在已经 capture 的 asset（page image、PDF page、DOM region 等）上运行新的有限抽取/OCR，不重新 acquisition、不重新 render；若目标 page/region 从未被 capture，`advance` 必须返回明确的 `need_new_acquisition`，而不是试图通过 cursor 静默取数据；
- 成功时返回一个新的 **immutable representation revision**，其 `parent_representation_id` 指向被处理的旧 representation，新 revision 引用可复用的旧 immutable blocks（未处理部分不复制、不重写）并携带 lineage；
- 响应必须列出 `processed_ranges`、`pending_ranges`、`failed_ranges` 和 `alignment_status`（新旧 block 能否确定性对齐，或 `ambiguous`）；`pending_ranges` 既不是 “missing”（capture 缺失），也不是 “no_match”（find 未命中），必须用独立状态表示；
- 不做失败的自动重试；某个 range 处理失败就保留在 `failed_ranges` 中，需要 caller 再次显式调用 `advance`；
- 旧的 cursor 和 citation 在 `advance` 之后继续对旧 representation 有效，**不会**被静默重新解析到新 revision；新 revision 产生新的 citation，且新 citation 必须区分“locator 因新抽取而 rebase”（同一段内容，位置随新 representation 重新编号）与“origin lineage”（该内容最初来自哪个 representation/OCR pass），不得混同；
- 当新旧内容的对齐关系无法确定性判断时，返回 `alignment_status: ambiguous` 并保留旧 citation 不失效，不能靠猜测把旧 locator 映射到新内容。

### 6.7 Canonical hypothetical sequence

以下四步串起 6.1 与 6.6 的示例，仍是 **hypothetical fictitious document**，不是已运行结果。文档假设为一份 5 页的 mixed PDF：第 1–2 页有 native text layer，第 3–5 页是扫描图像。

**Step 1 — `initial`（见 6.1）** 返回 `source_snapshot_id: opaque-snap-1`、`representation_id: opaque-rep-1`、bounded body、`output.status: truncated`、`next_cursor: opaque-cursor-1`；因为第 3–5 页尚未 OCR，同时返回：

```json
{
  "processing_continuation": {
    "pending_ranges": [{"kind": "page", "from": 3, "to": 5, "reason": "image_only_not_ocr_processed"}],
    "advance_hint": {"parent_representation_id": "opaque-rep-1", "selection": {"pages": [3, 4, 5]}}
  }
}
```

**Step 2 — output continuation（同一 identifiers，不做任何处理）**

```json
{
  "url": "https://example.invalid/neutral-report",
  "action": "read",
  "source_snapshot_id": "opaque-snap-1",
  "representation_id": "opaque-rep-1",
  "cursor": "opaque-cursor-1",
  "budget": {"max_code_points": 3000}
}
```

```json
{
  "source": {"source_snapshot_id": "opaque-snap-1", "representation_id": "opaque-rep-1"},
  "view": {
    "view_kind": "range",
    "target_blocks": [
      {"kind": "heading", "text": "Observations", "node_id": "opaque-node-3"},
      {"kind": "paragraph", "text": "Plot B recorded the highest reading on the second visit; see Table 1 for the per-plot values.", "node_id": "opaque-node-4"}
    ],
    "markdown_projection": "# Observations\n\nPlot B recorded the highest reading on the second visit; see Table 1 for the per-plot values."
  },
  "coverage": {"capture": "fetched", "extraction": "partial", "searched_scope": "pdf_native_text_pages_1_2"},
  "output": {"status": "complete"},
  "next_cursor": null,
  "processing_continuation": {
    "pending_ranges": [{"kind": "page", "from": 3, "to": 5, "reason": "image_only_not_ocr_processed"}],
    "advance_hint": {"parent_representation_id": "opaque-rep-1", "selection": {"pages": [3, 4, 5]}}
  },
  "warnings": []
}
```

`output.status: complete` 表示 `opaque-rep-1` 已发布的正文（第 1–2 页）已读完，`extraction: partial` 与 `processing_continuation` 说明第 3–5 页仍未处理；这一步没有网络请求、渲染或 OCR。

**Step 3 — `advance`（新 representation，parent 指向旧 representation）**

```json
{
  "url": "https://example.invalid/neutral-report",
  "action": "advance",
  "source_snapshot_id": "opaque-snap-1",
  "parent_representation_id": "opaque-rep-1",
  "selection": {"pages": [3, 4]},
  "processing_budget": {"max_ocr_seconds": 20, "max_pages": 2}
}
```

```json
{
  "source": {"source_snapshot_id": "opaque-snap-1"},
  "representation": {
    "representation_id": "opaque-rep-2",
    "parent_representation_id": "opaque-rep-1",
    "representation_kind": "ocr_text",
    "reused_block_ranges": [{"kind": "page", "from": 1, "to": 2, "from_representation_id": "opaque-rep-1"}]
  },
  "processed_ranges": [{"kind": "page", "from": 3, "to": 4}],
  "pending_ranges": [{"kind": "page", "from": 5, "to": 5, "reason": "not_selected_in_this_advance"}],
  "failed_ranges": [],
  "alignment_status": "deterministic",
  "old_citations": "remain_bound_to_opaque-rep-1",
  "warnings": ["ocr_approximate"]
}
```

第 5 页仍在 `pending_ranges`：它既不是 missing，也不是 no-match，只是本次 `advance` 没有选择它。旧的 `opaque-cursor-1` 和任何基于 `opaque-rep-1` 的 citation 继续有效，且仍指向 `opaque-rep-1`。

**Step 4 — 在新 representation 上做 targeted read**

```json
{
  "url": "https://example.invalid/neutral-report",
  "action": "find",
  "source_snapshot_id": "opaque-snap-1",
  "representation_id": "opaque-rep-2",
  "query": "Table 1",
  "scope": "document",
  "limit": 4
}
```

```json
{
  "source": {"source_snapshot_id": "opaque-snap-1", "representation_id": "opaque-rep-2"},
  "matches": [
    {
      "match_id": "opaque-match-7",
      "match_type": "exact",
      "text": "Table 1. Per-plot readings (unit: mm)",
      "locator": {"kind": "ocr_region", "page_number": 3, "bbox": [72, 640, 520, 660], "representation_id": "opaque-rep-2"},
      "source_method": "ocr",
      "origin_lineage": {"first_extracted_in": "opaque-rep-2"}
    }
  ],
  "negative_result": null,
  "coverage": {"capture": "fetched", "extraction": "partial", "searched_scope": "pages_1_4_native_and_ocr", "omitted_scope": ["page_5_not_processed"]},
  "warnings": ["ocr_approximate"]
}
```

随后的 `expand` 会按 7.2 的确定性规则补入 table caption、header、unit 与已链接的 table note，并标出 `closure_basis`。四步中 `source_snapshot_id` 始终不变；只有 `advance` 产生了新的 `representation_id`。

## 7. Bounded views 与 context closure

### 7.1 `BoundedView`

```text
BoundedView {
  view_id: opaque id
  source_snapshot_id: string
  representation_id: string
  structure_revision: string
  view_kind: initial | preview | find_window | section | range | page | evidence_window | asset
  target_blocks: string[]
  context_blocks: string[]
  context_closure_basis: { [node_id: string]: "heading_ancestry" | "table_structure_link" | "linked_footnote" | "other_deterministic_link" }
  omitted_context: OmittedContext[]
  unknown_context: string[]
  unresolved_context: string[]
  semantic_completeness: "unknown"
  budget: {
    max_bytes?: integer
    max_code_points?: integer
    max_blocks?: integer
    max_pages?: integer
    max_occurrences?: integer
  }
  content_parts: TypedBlock[]
  markdown_projection?: string
  coverage: object
  output_status: complete | truncated
  truncation_reason?: string
  continuation_scope: object
  next_cursor?: string
  processing_continuation?: {
    pending_ranges: object[]
    advance_hint: object
  }
  warnings: Warning[]
}
```

### 7.2 Context closure rules

Context closure 的能力边界必须明确：它只能补齐**结构或 index 中可确定性找到的链接**——heading ancestry、table header/unit/caption、通过 marker 显式链接的 footnote 等；它**不能**发现散落在别处、未被结构或 index 链接的限定语，也不能替 caller 判断某个 semantic exception 是否适用。每个 `context_blocks` 条目都在 `context_closure_basis` 中标注凭什么规则被补入；不属于这些确定性链接的内容不会被 closure 自动补入。

按目标 block 确定性补齐（均对应一种 `closure_basis`）：

- **section**（`heading_ancestry`）：heading ancestry 和 current section path；
- **table**（`table_structure_link`）：caption、header row、units、target row labels、table notes、merged-cell warning；
- **figure/image**（`table_structure_link` 或等价结构链接）：figure ID、caption、alt、legend/asset/OCR status；
- **footnote**（`linked_footnote`）：marker + definition；definition 超 budget 时显式列入 `unresolved_context`；
- **list**：list type、nesting level、task-state（若 parser 已验证支持）；
- **code**：language/info string，fence 成对；无法成对时降为 plain-text typed block；
- **PDF/OCR**：page、block index、bbox、reading-order status、native/OCR source method。

`sample`、`date range`、`population`、`exception`、`limitation` 等 qualifier **只有在它们通过以上某种确定性链接（例如同一 table note、同一 footnote definition）与 target 相连时**才会被 closure 补入；如果它们只是在正文其他位置以自然语言出现、没有结构/index 链接，closure 不会、也不应该去发现它们——这类未链接的远距限定语和语义例外，只能由 caller 自行阅读周边正文或整份 source 来判断。

`target_blocks` 与 `context_blocks` 必须可区分，避免 caller 把 closure 当作 query hit 或把 page furniture 当作正文。context closure 规则先于 token optimization；如果确定性 closure 造成超 budget，应报告原因而不是无声删除。

响应必须携带 `unknown_context`（本次未尝试或未能确认的潜在上下文线索）、`unresolved_context`（已发现链接但因 budget/retention 无法展开）和恒为 `"unknown"` 的 `semantic_completeness`——**空的 `unknown_context` 列表从不意味着语义完整**，closure 只覆盖它能确定性发现的链接，任何“语义上是否完整”的判断都必须由 caller 结合任务自行决定。通过 inference（而非显式结构/index 链接）得到的关联，必须在对应 block 的 `warnings` 中标注为推断，不能和确定性链接混同。

### 7.3 Oversized block splitting

proposal invariants：

1. 不在 UTF-8 byte sequence 或 Unicode code point 中间截断；
2. user-facing selection 尽量不跨 grapheme cluster；
3. 保存 `parent_block_id`、`segment_index`、`segment_count` 与 source locator；
4. code fence 要么完整，要么明确 plain-text fragment；
5. table row/cell 的拆分必须标为 `cell_segment`，不能让后续 caller 以为是新 row；
6. segment local offset 不取代 source locator；
7. hard cap 同时支持 bytes 与 code points，必要时 pages/blocks 也参与 cap。

## 8. Continuation、state lifecycle 与 cursor policy

### 8.1 State lifecycle

```text
NEW_REQUEST
  -> ACQUIRING
  -> SNAPSHOT_CREATED
  -> EXTRACTING
  -> REPRESENTATION_READY | REPRESENTATION_PARTIAL | FAILED
  -> VIEW_CREATED
  -> CURSOR_ISSUED (only if output has more same-representation, already-published view)
  -> CONTINUING
  -> VIEW_CREATED
  -> EXPIRED / REVOKED / DELETED

REPRESENTATION_PARTIAL
  -> (caller calls `advance` with a bounded processing_budget)
  -> ADVANCING (bounded, synchronous, no background job / queued state)
  -> CHILD_REPRESENTATION_READY | CHILD_REPRESENTATION_PARTIAL | ADVANCE_FAILED
     (parent_representation_id = old representation; old cursors/citations stay bound to the old representation)
```

每次 continuation 都必须显式带 caller-supplied opaque state；不能依赖 process、connection 或隐式 session。MCP pagination 的 opaque cursor 语义可作为协议方向参考，但 custom `web_read` cursor 的 scope/expiry 是应用 contract。

### 8.2 Cursor binding

建议 cursor 逻辑绑定：

```text
source_snapshot_id
representation_id
structure_revision
extraction_config_hash
view_kind
selection / section / locator
find query + normalization
offset policy
compatible budget policy
cursor issuance / expiry metadata
```

两种待选 policy：

- **strict config hash：** 任何 view config/budget change 都要求新 cursor，简单但调用较多；
- **monotonic budget policy：** 允许缩小 budget，不允许改变 selection/config；复杂但可能减少重复。

本设计推荐先实现 strict config hash 作为 prototype 可审计 baseline，但这不是已接受选择；后续需用 continuation tests 验证。

### 8.3 Expiry/change rules

- `output_truncated`：representation pinned，允许 same-scope cursor；
- `source_changed`：新 retrieval 是新 snapshot；旧 cursor 不得继续到新 bytes；
- `snapshot_expired`：snapshot 曾存在但被 retention/TTL 清理；不得隐式 refetch；
- `cursor_expired`：snapshot 可能还在，但 cursor 无效；可从 snapshot 新建 view；
- `representation_missing`：snapshot 在，但请求的 OCR/browser/layout child representation 不在；caller 可请求另一 representation；
- `extraction_partial`：representation 内已经**发布**（已完成抽取）的 blocks/regions 仍可用 `next_cursor` 继续读——这只是读取已发布内容，不做新处理；尚未处理（尚未抽取/OCR）的 captured pages/regions 不通过 `next_cursor` 暴露，而是在响应中以 `processing_continuation` 提示 caller 可显式调用 `advance`（6.6）对它们做新的有限处理并产生新的 representation revision；`next_cursor` 本身不会因为背后还有更多待处理素材而自动“长大”或指向未来才存在的内容；
- `extraction_failed`：不提供伪造 cursor，可返回另一明确标注 representation。

### 8.4 File-backed snapshot proposal

推荐把 file-backed content-addressed store + small metadata index 作为**第一个要验证的实验**——这是“从简单开始，先用能满足需求的最小方案”的工程判断，不是“永久排除数据库”的产品决策；用户没有禁止数据库，如果 file-backed 方案在 retention/TTL/并发/查询场景上暴露出具体不足，评估数据库方案是合理的下一步，而不是被本 proposal 排除的选项。file-backed 方案本身：

```text
snapshots/<source_snapshot_id>/raw.*
representations/<representation_id>/manifest.json
representations/<representation_id>/blocks.jsonl
representations/<representation_id>/assets/*
views/<view_id>/manifest.json
citations/<citation_id>.json
```

这是 portability/restart/reproducibility proposal，不是实施决定。raw、extraction artifact、view、citation ledger 应有分离 retention；crash-safe writes、cleanup、locking、ACL/encryption、TTL 和 multi-process behavior 需要实验。只保存 Markdown 不足以恢复 PDF bbox、OCR image region、DOM lineage、table model 和原始 asset。

## 9. Format-specific route portfolio

### 9.1 Route matrix

| 输入 | capture | primary representation | fallback/escalation | 必须披露的 limitation |
|---|---|---|---|---|
| `text/plain` | raw bytes + charset | normalized text + raw | decode diagnostic | decode/replacement policy；不重排原文 |
| Markdown | raw source | AST/blocks + raw | raw-only if extension unsupported | CommonMark core 不含 tables/footnotes；dialect explicit |
| static HTML | HTTP raw + DOM | static DOM/content view | Readability comparison | main-content heuristic 不等于 full page；comments/figure/links 可被过滤 |
| JS HTML | HTTP raw + browser context | rendered DOM + network/download artifacts | explicit caller request | JS success 不等于 complete；tab/scroll/service-worker scope |
| born-digital PDF | PDF bytes | native text/layout/page blocks | geometry backend | PDF semantic layer、reading order、table/footnote 可能不完整 |
| mixed PDF | PDF bytes | per-page native + OCR child representation | layout backend | overlap conflict、source_method、per-page coverage |
| scanned PDF | PDF bytes + rendered pages | OCR blocks/page image | targeted OCR/layout backend | OCR confidence 不是 truth；未识别 page 不是 no text |
| webpage text image | page raw + image asset | image OCR + DOM context | targeted OCR | alt/caption/OCR/asset 需分开；图形 semantics 不自动恢复 |
| standalone image URL | image bytes | asset + OCR regions（OCR 为必需能力，不是可选） | targeted OCR/layout escalation | SVG/animated/large image handling；chart/formula semantics uncertain |

### 9.2 Candidate selection caveats

**第一优先级：复现已有 baseline。** 已有 pinned `4c210d1` CPU functional smoke 已经跑通 Trafilatura（static HTML）、Playwright/Chromium（JS render/download）、pypdfium2（native PDF text）、RapidOCR + ONNX Runtime CPU（OCR）这条覆盖 HTML/JS/PDF/OCR/image 的路径。后续 prototype 的第一步是在同一/相近 corpus 上**复现这条已验证路径**，而不是从候选列表里另选组件——“已经跑通过”本身就是证据，不应无反证地被替换：

- Trafilatura（baseline，复现优先）：static HTML main-content extraction；官方 repo 描述 metadata、links/images/tables 和多种 output，Apache-2.0；当前 README 未独立保证目标 Windows runtime，仍需在本项目 corpus 上复现。
- Playwright/Chromium（baseline，复现优先）：JS render/download；官方列 Windows 和多 browser；routing 不等于 process/network isolation，browser binary revision 需 pin。
- pypdfium2（baseline，复现优先）：既有 smoke 使用的 native PDF text 路径；具体 capability 引用见既有 smoke 记录，本轮不重复背书。
- RapidOCR + ONNX Runtime CPU（baseline，复现优先）：既有 smoke 使用的本地 CPU OCR 路径；同上，先复现，再谈是否比较其他组件。

**第二优先级：只有在复现 baseline 后、在同一 corpus 上发现具体、可复现的 gap 时**，才逐一评估以下比较对象，且每次只针对暴露出 gap 的那类输入做对比，不做整体替换：

- pypdf 或 PyMuPDF 作为 pypdfium2 的 native PDF 抽取对比：pypdf 是 lightweight/BSD-3-Clause candidate，官方明确 semantic/table/scanned limits；PyMuPDF capability 更丰富但 AGPL/commercial license 是 adoption gate；两者都只在 pypdfium2 对某类 PDF 出现具体缺陷时才拿来同 corpus 对比，不因为“功能更强”就默认替换 baseline。
- Tesseract 作为 RapidOCR 的 OCR 对比：Windows/Apache-2.0/local CPU candidate，TSV/hOCR lineage 可用，官方 4-core 文档不是 target benchmark；只有当 RapidOCR 在某类图像/语言上出现具体缺陷时才对比。
- Docling 作为 advanced layout/scanned PDF backend 的对比：官方列 Windows 与 rich document model，但 native Windows CPU/model/dependency validation 未完成；仅在既有 PDF/OCR baseline 对复杂 layout/table 有具体、可复现缺陷时才评估。
- PaddleOCR 作为 targeted OCR/layout escalation 的对比：official FAQ 的 Windows adaptation 不等于完整 CPU readiness，models/dependencies license 需单独 inventory；仅在 RapidOCR 对特定语言/场景有具体缺陷时才评估，不作为默认 OCR。
- Mozilla Readability 作为 Trafilatura 的 comparison/fallback：API 会修改 DOM，不做 sanitization，保留 raw/clone DOM，Apache-2.0；仅在 Trafilatura 主内容抽取出现具体缺陷时对比。

组件版本、最终 default route、license fit、CPU/RAM 和 quality 仍 open；“候选能力看起来更强”本身不构成替换 baseline 的理由，必须先有同 corpus 上的具体、可复现 gap。

## 10. Markdown/output projection policy

Markdown 是 agent-friendly projection，不是 canonical evidence layer。

- headings、paragraphs、lists、quotes、code：GFM-compatible Markdown；
- simple rectangular table：GFM table candidate；
- merged cells、row/col spans、nested blocks、table notes：raw HTML table 或 typed sidecar；
- image：asset reference + separate `alt` + separate `figcaption` + OCR/semantic status；
- formula：original text/image/uncertainty；无法证明时不自动改写为 LaTeX；
- footnotes：marker/body relation + renderer-aware projection；
- references：保留 original order/labels/links，不自动 deduplicate/collapse editions；
- page breaks/locators：comments/attributes/sidecar manifest，不能污染正文语义；
- code fences：不返回跨-view 无闭合 fence；必要时 plain-text typed block。

同一 result 中的 `structuredContent` 与 TextContent 必须由同一 `BoundedView` 生成。不能让结构化字段是 preview、TextContent 却是全文，否则 caller 的 citation/offset 会漂移。具体 host 是否保留两者需 integration test。

**Engineering proposal，非 required MCP change：** 同一个 `BoundedView` 内应避免把同一段正文同时完整塞进 `content_parts`（typed blocks）和 `markdown_projection` 两份——推荐做法是 `content_parts`/locators 只携带结构化 metadata 和定位信息，`markdown_projection` 承担一次 body 投影，两者引用同一份底层文本而不是各自重复整份正文；`structuredContent` 与 TextContent 都要序列化时，也应从同一个 `BoundedView` 取数，而不是分别渲染两份独立正文。budget 计算必须把这种重复计入总量，否则会看似“没超预算”，实际已把同一内容占用了两倍空间。这是本项目的工程实现建议，不是对 MCP 协议本身提出的必需变更。

## 11. Resources and host portability

### 11.1 Baseline without Resources

目标 host 可能不支持 Resource picker、`resources/list`、custom URI、resource link display 或 embedded resource roundtrip。因此最低可用路径应是：

```text
caller -> web_read tool -> structuredContent + same-source TextContent
```

tool result 可以 optional 返回 `resource_link`，但主导航、continuation、coverage 和 evidence 必须在 tool result 内可读。caller 直接给 URL；不要求先列 Resources。

### 11.2 Optional Resources use

若 host capability matrix 证明可行，server 可以把 source snapshot、representation manifest、large asset 或 evidence ledger 暴露为 resource link，例如：

```text
snapshot://opaque-snap-1/representation/opaque-rep-1/view/opaque-view-3
```

该 URI 仍只是应用层 locator。MCP `resources/read` 不自动理解本项目 section/cursor semantics；custom URI 的 authorization、lifetime、retention 和 expiry 仍由 server 定义。不要把 Resources 当作 continuation 的唯一通道。

## 12. Security and untrusted content

### 12.1 Acquisition controls

Proposed safeguards：

- scheme allowlist 仅 `http`/`https`；拒绝 `file:`、`data:`、`javascript:`、`gopher:`；
- A/AAAA 全解析，拒绝 loopback、RFC1918、link-local、multicast、metadata ranges；
- 禁用自动 redirect，每个 hop 重新 canonicalize/resolve/validate；
- browser context 不继承 caller/host cookies、Authorization、tokens；
- service worker、third-party iframe、analytics、WebSocket、video、font、popup 默认受 policy/allowlist 控制；
- download 校验 MIME、magic bytes、decompressed size，不信 extension；
- auth、MFA、paywall、captcha、anti-bot、robots refusal 不 bypass；RFC 9309 的 robots rules 不视为 authorization。

OWASP 的 URL/redirect/A-AAAA/DNS guidance 是 security guidance；这些 controls 的 deployment effectiveness 未在本轮验证。Playwright `route()` 是 interception/observation API，不是 network boundary。

### 12.2 Prompt-injection boundary

所有 source text 进入 untrusted data channel。提取器和 tool executor 必须保证 page content 不能修改：

- caller query/privacy policy；
- URL allowlist、redirect/SSRF policy；
- retry、browser action、reference-following 和 budget；
- credentials/cookies/tokens；
- raw retention/deletion；
- model system instructions 或 final synthesis。

对 HTML comments、Markdown code、OCR text、PDF metadata、alt text 和 SERP snippets 采用同一边界；不要因“看起来像 instruction”而执行，也不要把其内容写进 server policy。

## 13. Proposed budgets and errors

### 13.1 Budget dimensions

不提出已验证数值；建议 contract 允许 caller/server policy 表达：

```text
max_response_bytes
max_code_points
max_blocks
max_pages
max_occurrences
max_redirects
max_response_bytes / max_decompressed_bytes
max_browser_pages / max_scroll_steps / max_download_bytes
max_pdf_pages / max_render_pixels_per_page
max_ocr_seconds_per_page
max_memory / cpu_worker_count / temp_disk_quota
deadline_ms / connect_timeout / read_timeout / idle_timeout
```

默认值必须在 frozen corpus + Windows CPU measurements 后决定。`max_code_points` 不能替代 byte cap；UTF-8 variable width 与 image/PDF decompression 需要单独限制。

### 13.2 Error response shape（proposal）

```json
{
  "error": {
    "category": "cursor_expired",
    "retryable": false,
    "recover_action": "start_new_view_from_snapshot",
    "message": "The continuation is no longer valid for this representation."
  },
  "source": {
    "source_snapshot_id": "opaque-snap-1",
    "representation_id": "opaque-rep-1"
  },
  "coverage": {
    "capture": "fetched",
    "extraction": "complete",
    "output": "not_returned"
  },
  "warnings": []
}
```

`retryable` 只是建议字段，不应按 generic network retry 逻辑处理 `source_changed`/`snapshot_expired`。Search route 的 default no retry boundary 仍不应被 `web_read` 误读为自动 retry policy。

## 14. Validation plan and acceptance gates

### 14.1 Paired evaluation

冻结 source snapshots（bytes/hash、rendered DOM、PDF/OCR representation、extractor/config），使用同一 agent/model、同一 task、同一 host adapter 和同一总 budget，比较：

1. bounded full Markdown；
2. fixed chunks；
3. structure-aware blocks；
4. `initial -> find -> read/expand`；
5. evidence-window closure；
6. large-context all-at-once；
7. raw evidence + optional summary（独立 exploratory arm）。

禁止某个 variant 偷换更好的 OCR、额外 reference crawl、不同 source snapshot、不同 retry 数或不等量总 budget。

### 14.2 Quality and efficiency measures

必须同时测：

- material claim recall；
- source-locator reattach / quote fidelity；
- caveat preservation（unit、scope、time range、exception、uncertainty、footnote）；
- section/table/figure/page coverage；
- negative-result honesty；
- OCR/native source attribution；
- tool-call burden、重复 calls、stale continuation；
- first useful preview、first evidence、final answer wall time；
- evidence bytes/tokens 达到 fixed quality floor 的成本；
- coverage/refusal/partial/truncation 分类正确性；
- correction after JS/OCR/parse warning。

不允许只用 token count 或 call count 宣称 Progressive Disclosure 成功。小 output 但丢掉 table header/footnote 的 variant 应判为 quality-floor failure。

### 14.3 Adversarial test assertions

- same raw bytes + same extractor/config 产生 stable representation/node digest/path；
- same URL + different bytes 产生 different snapshot IDs；
- new extractor/OCR 不覆盖 old representation/citation；
- byte/code-point/grapheme/UTF-16 offset 不混淆；
- repeated exact match 返回 multiple/ambiguous，不静默选首项；
- table target 必须能 closure 到 caption/header/unit/note，不能只给数值；
- footnote 改变语义时，漏读 footnote 必须标 unresolved/omitted；
- JS shell、unloaded tab、image-only page 不产生 global `not_found`；
- output truncation 才能给 same-representation cursor；extraction failure 不给伪造 cursor；
- process restart、TTL expiry、cursor revoke、representation missing 返回 distinct state；
- continuation 不触发 network fetch（mock network counter）；
- source changed 不让 old cursor 指向 new content；
- SSRF redirect/DNS change/private IP 在每 hop 拒绝；
- raw deletion 后 citation verifier 返回 unavailable，不重新抓取替代；
- malicious source instruction 不改变 policy、credentials、budget、retention、reference follow 或 tool choice；
- target host 在没有 Resources capability 时仍能完成 initial/find/read/expand 的同步 tool path；
- `advance` 只在已 capture 的 asset 上运行，不发起新的网络请求；若目标 page/region 未曾被 capture，返回 `need_new_acquisition`，不通过 cursor 静默抓取；
- `advance` 产生的新 representation revision 的 `parent_representation_id` 指向旧 representation；旧 cursor/citation 在 `advance` 之后继续解析到旧 representation，不会被静默重定向到新 revision；
- 无法确定性对齐新旧内容时，`advance` 返回 `alignment_status: ambiguous`，不得靠猜测把旧 locator 映射到新 revision；
- `next_cursor` 与 `processing_continuation` 各自的存在与否互不隐含：只有已发布内容剩余才给 `next_cursor`；只有已 capture 但未处理的素材才给 `processing_continuation`；
- context closure 只依据 `context_closure_basis` 中列出的确定性链接类型工作；对未被结构/index 链接的 qualifier，closure 不得声称发现，`unknown_context` 为空也不能被解释为语义完整。

### 14.4 Acceptance gates（proposed）

只有在以下结果可复核后，才建议把具体 default 提交为 contract：

1. 每个 required format（HTML、JS-rendered page、born-digital/mixed/scanned PDF、网页文字图片、独立 image URL）都有一条**可运行**的 acquisition/extraction route，并配有该类型的代表性成功 fixture（中文/英文均在 scope 内的类型下，两种语言都要有 fixture）和失败 fixture；`unsupported`/`partial`/`refused` 只是某个具体 input 的诚实结果，不能替代“实现了这个 required format”——只靠总是返回 `unsupported` 通过验收视为未满足本 gate。单个 fixture 跑通不构成质量保证，只是“route 存在且可运行”的最低证据；release-level coverage 与 real-corpus fidelity 是两个更高、独立的 gate（见 14.1–14.2），不得把本 gate 的通过等同于它们已经通过；
2. capture/extraction/output 三种状态可以分别驱动恢复；
3. continuation 不 silent refetch，state binding 可审计；
4. old citation 在 extractor upgrade 后保持 old representation identity；
5. table/figure/footnote/reading order 的 limitation 有 locator/warning；
6. target host 能消费 structuredContent 或同源 TextContent，不依赖 Resources picker；
7. Windows CPU clean-machine、license/model/dependency inventory 完成；
8. SSRF/access-control/raw-retention/prompt-injection tests 通过；
9. paired evaluation 在 fixed quality floor 下显示 net benefit，或 Progressive route 被降级为 explicit optional mode；
10. 没有把本 proposal 的数字、组件或 default 误写成 accepted product decision。

## 15. Phased implementation experiment order

阶段化只隔离风险，不减少 accepted content scope：

### Phase A — identity and bounded output

先验证 source snapshot、representation lineage、typed blocks、locators、coverage/output state、bounded full/fixed baseline、file-backed persistence 和 cursor invariant。使用 text/static HTML/小型 PDF 建立可复核基础。

### Phase B — HTML/JS/image

加入 static HTML、rendered DOM、download、网页文字图片、standalone image asset/OCR。针对 JS shell、delayed hydration、infinite scroll、service-worker visibility 和 image context closure 建 adversarial fixtures。

### Phase C — PDF/OCR

按 page classification 加 native text、mixed/scanned OCR、table/footnote/reading-order warnings。优先复测已有 RapidOCR/ONNX Runtime/pypdfium2/Playwright smoke，再比较 pypdf/PyMuPDF/Docling/Tesseract/PaddleOCR candidate；不能用阶段性失败删除 PDF/OCR/image requirement。

### Phase D — Progressive loop A/B

冻结 cross-format corpus 和 research tasks，比较 full/fixed/structure/progressive/evidence-window/all-at-once；评估 evidence per token、caveat preservation、quote fidelity 和 correction，而不是只看 latency。

### Phase E — host, restart, policy

做 target MCP host capability matrix、structuredContent/TextContent parity、optional Resources、restart/TTL/eviction/locking、raw deletion、authorization re-check、SSRF/DNS/redirect/browser egress 和 injection corpus。

## 16. Unresolved design choices

1. 一个 `web_read(action=...)` 还是多个 tools；需用 target host 的 tool discovery 和 error UX 测量。
2. `initial` 是否固定为 metadata+outline+bounded lead，还是允许 metadata-only experimental mode；不应静默违背现有 ADR。
3. outline、lead、find-window、context closure 的具体 budget；禁止从 SWE-agent 的 line numbers 直接复制。
4. strict cursor config hash 与 monotonic budget policy 的取舍。
5. file-backed store 的 raw retention/TTL、restart recovery、eviction、locking、encryption/ACL、multi-user boundary。
6. static HTML/JS representation 如何复用同一 structural node lineage；rendered DOM 是否每次 interaction 都生成新 representation。
7. PDF reading order、table inference、footnote mapping 的错误如何标注、何时降级为 fixed blocks。
8. OCR engine/backend、models/weights/traineddata/runtime dependencies 的 license 与 Windows CPU path。
9. `structuredContent`、TextContent、resource link、embedded resource 在目标 host 的保留、展示和 roundtrip 行为。
10. raw quote length、PII/copyright retention 与 W3C quote selector 的组合 policy。
11. optional summary 是否有净收益；若未来引入，是否由 caller 外部执行或单独 tool 执行。
12. whether `asset` is an action or a separate tool；是否允许 caller 请求 page crop/region bytes。
13. `advance` 产生的新 representation revision 与旧 representation 之间，除 `parent_representation_id` 外是否还需要跨 revision 的 diff/mapping 结构；`alignment_status: ambiguous` 的具体判定规则待定。

## 17. Source references

本设计的外部事实只依赖以下 primary sources；研究报告提供完整 ledger、access limitations 和 evidence strength：

- MCP Tools 2026-07-28：<https://modelcontextprotocol.io/specification/2026-07-28/server/tools.md>
- MCP Resources 2026-07-28：<https://modelcontextprotocol.io/specification/2026-07-28/server/resources.md>
- MCP Pagination 2026-07-28：<https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/pagination.md>
- MCP Basic 2026-07-28：<https://modelcontextprotocol.io/specification/2026-07-28/basic/index.md>
- W3C Web Annotation Data Model：<https://www.w3.org/TR/annotation-model/>
- RFC 3986 §3.5：<https://www.rfc-editor.org/rfc/rfc3986#section-3.5>
- RFC 3629：<https://www.rfc-editor.org/rfc/rfc3629>
- Unicode UAX #29：<https://www.unicode.org/reports/tr29/>；fixed Unicode 17.0 Revision 47：<https://www.unicode.org/reports/tr29/tr29-47.html>
- CommonMark 0.31.2：<https://spec.commonmark.org/0.31.2/>
- GitHub Flavored Markdown：<https://github.github.com/gfm/>
- ReAct：<https://arxiv.org/html/2210.03629>
- SWE-agent：<https://arxiv.org/html/2405.15793v3>
- ToolSandbox：<https://arxiv.org/html/2408.04682>
- Lost in the Middle：<https://arxiv.org/html/2307.03172>
- Nielsen Norman Group Progressive Disclosure：<https://www.nngroup.com/articles/progressive-disclosure/>
- Trafilatura：<https://github.com/adbar/trafilatura>
- Mozilla Readability：<https://github.com/mozilla/readability/blob/main/README.md>
- Playwright Python intro：<https://playwright.dev/python/docs/intro>
- Playwright network：<https://playwright.dev/docs/network>
- Playwright downloads：<https://playwright.dev/docs/downloads>
- pypdf extraction：<https://pypdf.readthedocs.io/en/stable/user/extract-text.html>
- pypdf license：<https://github.com/py-pdf/pypdf/blob/main/LICENSE>
- PyMuPDF Appendix 1：<https://pymupdf.readthedocs.io/en/latest/app1.html>
- PyMuPDF licensing/about：<https://pymupdf.readthedocs.io/en/latest/about.html>
- Docling overview：<https://docling-project.github.io/docling/>
- DoclingDocument：<https://docling-project.github.io/docling/concepts/docling_document/>
- Docling installation：<https://docling-project.github.io/docling/getting_started/installation/>
- Tesseract：<https://github.com/tesseract-ocr/tesseract>
- Tesseract supported OS：<https://tesseract-ocr.github.io/tessdoc/supported-operating-systems.html>
- Tesseract CLI/OpenMP：<https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html> · <https://tesseract-ocr.github.io/tessdoc/Compiling-%E2%80%93-GitInstallation.html>
- PaddleOCR FAQ/license：<https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/FAQ.en.md> · <https://github.com/PaddlePaddle/PaddleOCR/blob/main/LICENSE>
- WHATWG HTML images：<https://html.spec.whatwg.org/dev/images.html>
- OWASP SSRF Prevention Cheat Sheet：<https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html>
- RFC 9309 Robots Exclusion Protocol：<https://www.rfc-editor.org/rfc/rfc9309.html>

## 18. Final proposal

先实现并验证最小可审计 vertical slice：

```text
raw/snapshot identity
  -> one or more immutable representations
  -> typed structure + deterministic find
  -> accepted-compatible initial view
  -> section/page/evidence read with context closure
  -> opaque, state-bound continuation
  -> explicit coverage/failure/citation state
```

该 slice 必须从第一轮设计起保留 HTML、JS、text/mixed/scanned PDF、网页文字图片和独立 image URL 的 route/state vocabulary；可以按阶段实现和测量，不能把未完成的 route 静默当作“不在 v1”。Progressive Disclosure 是否成为默认 differentiator，取决于后续 frozen-corpus paired evaluation 是否在固定 quality bar 下证明 evidence coverage、quote fidelity 和 caveat preservation 的净收益。
