# 渐进式披露的表示、一致性与证据契约

> 研究日期：2026-09-10
>
> 本 memo 研究 `web_read` 如何把同一份公开来源逐步交付给 agent，同时保持可续读、可引用、可复核。文中的 schema、状态机、字段名、存储路线、测试矩阵和阈值全部是 **Proposed / recommendation / unvalidated**，不是已实现或已批准的 product contract。除 MCP 规范、CommonMark/GFM、W3C Web Annotation、RFC 与 Unicode 规范所明确规定的内容外，不把候选设计写成事实。

## 1. 结论摘要

建议把 Progressive Disclosure 定位为 **同一份 immutable source snapshot 上的多个 bounded views**，而不是“每次请求重新抓取 URL 并截取更多 Markdown”。核心链路建议是：

```text
source URL
  -> source snapshot（抓取 bytes 与 retrieval identity）
  -> extraction representation（HTML DOM / PDF text-layout / OCR / normalized text）
  -> structural document（document / section / block / page / table / figure ...）
  -> bounded view（preview / section / range / find-window）
  -> citation / annotation（绑定 snapshot + representation + locator）
```

建议坚持以下边界：

1. **引用的稳定对象是 snapshot 内的 representation，不是 URL、Markdown 行号或一次响应的 cursor。** URL 只表示检索入口；citation 必须能指出使用了哪一份 bytes、哪一种 extraction revision 和哪一个 locator。
2. **Markdown 是 view format，不是唯一 canonical representation。** CommonMark 规定 block/inline 语法，GFM 增加 table、task-list 等扩展，但这些规范不提供 figure、视觉 layout、source offset、provenance 或表格注释的统一模型。因此应保留结构化 sidecar 与原始资产，再投影成 Markdown。
3. **offset 必须声明 representation、normalization 和 unit。** raw bytes、rendered DOM、extraction text、generated Markdown 和 bounded view 的 offset 不能互换；不允许为了“方便引用”而静默做 Unicode normalization、换行折叠或 offset unit 转换。
4. **continuation 必须绑定显式 state。** MCP 2026-07-28 是 stateless protocol：跨请求 state 必须通过显式 identifier 传回，不能依赖 connection/process。分页 cursor 是 opaque，且 MCP 标准分页只覆盖 list operations；`web_read` 的正文续读必须由应用 contract 自己定义。
5. **旧 citation 不随 OCR、browser extraction 或 parser 升级而原地改写。** extraction 改变就产生新的 `representation_id`；旧 citation 仍指向旧 representation。跨 representation 的 rehydration 只能生成带状态的映射结果，不能悄悄保留原 citation ID。
6. **必须区分四类状态：** extraction failure、output truncation、cursor/snapshot expiry、source changed。它们的恢复动作不同，不能都返回 `partial` 或重新抓取后伪装成 continuation。

## 2. 已核验事实与适用范围

### 2.1 MCP core 只提供容器，不提供正文渐进式披露语义

**事实。** MCP 2026-07-28 要求 tool result 有 `resultType`；`complete` 表示请求已完成，extension 可以增加其它 result type。tool result 可以包含多个 text/image/audio/resource-link/embedded-resource content block，也可以在 `structuredContent` 中返回任意 JSON value；如果声明 `outputSchema`，server 生成的 structured result 必须符合 schema，client SHOULD 验证。`isError: true` 是 tool execution error，不等同 JSON-RPC protocol error。[MCP-T]

**事实。** MCP resource 的 `resources/read` 返回 `contents`，每项是 text 或 base64 `blob`，带 `uri` 和可选 `mimeType`；resource 可以通过 `resource_link` 或 embedded resource 从 tool result 暴露。resource 是 application-driven，host 决定如何选择或注入 context。[MCP-R]

**事实。** MCP 2026-07-28 的 cursor pagination 只列出 `resources/list`、`resources/templates/list`、`prompts/list`、`tools/list` 四类 operations。cursor 是 opaque string，client MUST NOT 解析、修改或根据其格式推断结果；server 决定 page size。这个规范没有给任意 `tools/call` result 定义 `nextCursor` 的通用语义。[MCP-P]

**事实。** MCP 2026-07-28 明确称 protocol 是 stateless：每个 request 自带处理所需信息，server 不得依赖同一 connection 上的先前 request；跨请求 state 必须由 client 在后续 request 中传回 explicit identifier。tools 文档对 stateful tool 的**非规范性 guidance**建议 handle 保持 opaque、每次调用检查 authorization、说明 lifetime；过期 handle 应返回可恢复的 execution error。[MCP-B][MCP-T]

**设计含义。** `web_read` 可以使用 MCP tool 的 `structuredContent` 返回 `source_snapshot_id`、`representation_id`、`next_cursor` 等应用字段，也可以返回 resource link；但这些字段属于本项目的 application protocol，不是 MCP core 的正文分页保证。不能因为 MCP 有 `resources/read` 或 list cursor，就宣称所有 host 都自动理解 section continuation、snapshot pinning 或 citation rehydration。

### 2.2 Markdown 规范证明了结构化文本的边界，而不是完整来源模型

**事实。** CommonMark 0.31.2 将文档解析为 block 与 inline 结构，包含 heading、paragraph、list、block quote、fenced code、link、image 等语法。它规定“不能解释为其它 block 类型的一组非空行形成 paragraph”，并规定 fenced code 的内容按 literal text 处理。[CM]

**事实。** GFM 增加 table extension：table 有 header row、delimiter row 和可选 body rows；cell 内允许 inline Markdown，但 block-level elements 不能插入 table。GFM 目录还列出 task list items extension；本次 primary retrieval 未取得该 section 正文，因此本 memo 不把 task-list 语法或 checkbox rendering 作为已核验事实。[GFM]

**解释。** 这些规范能支持一个对 agent 友好的 textual projection，但并不构成 page-layout、figure-caption、PDF page、OCR bounding box、footnote provenance 或 source-offset contract。规范没有为 `figure`、视觉位置、原始 bytes、提取器版本或 citation state 提供统一字段。故“把所有输入先转成 Markdown，再以 Markdown 行号作引用”会在下列场景丢失信息：

- HTML figure 与 caption、图片 URL、alt text、图片 OCR 文本之间的关系；
- PDF page、column、table region、reading order 与坐标；
- 表格 header、cell span、caption、table note、footnote 定义与正文 marker 的关系；
- browser-rendered DOM 与原始 HTML bytes 的差异；
- OCR confidence、text region、旋转方向和页面内位置；
- 由不同 extractor 或 normalization 生成的两个 Markdown 版本是否真的对应同一 source。

因此 Markdown 应是可展示、可供 LLM 消费的 `view`，不是唯一证据层。

### 2.3 W3C selectors 给出引用的有用约束，但不能替代 snapshot identity

**事实。** W3C Web Annotation Data Model 的 `TextQuoteSelector` 用 `exact` 以及可选 `prefix` / `suffix` 描述一段文字；文本在记录 selector 前必须 normalized（包括移除 markup、展开 character entities），selection 以 Unicode code points 计数而不是 code units，并且 SHOULD NOT 在 grapheme cluster 内开始或结束。[WA-Q]

**事实。** `TextPositionSelector` 的 `start` 是 zero-based、inclusive，`end` 是 exclusive；位置也必须在同样的 normalized text 上计数。W3C 称 position selector “very brittle”，因为 source 被编辑或动态插入内容后位置会移动，并 RECOMMENDS 附加 `State` 以识别 intended representation。[WA-P]

**事实。** W3C State 可以描述资源的 version、format 或其它 representation；States MUST 在 selector 之前处理。Time State 可指定 source 适用的时间，Request Header State 可记录取得目标 representation 所需的请求头。[WA-S]

**设计含义。** 建议 citation 同时保存 quote selector 与 position selector（若保存 quote 符合 retention/版权政策），并把 snapshot、representation、normalization、offset unit 和 extraction revision 放在 citation state 中。W3C selector 的 `exact` 或 `start/end` 不是稳定 ID；它们只是针对指定 representation 的 locator。

### 2.4 URI fragment 与 Unicode offset 不能被当作跨表示层的通用 ID

**事实。** RFC 3986 §3.5 规定 fragment identifier 的 semantics 由 retrieval 后得到的 representation 的 media type 定义；fragment 在 dereference 前从 URI 中分离，不随 request 发送。fragment syntax 允许 `pchar`、`/`、`?`，更具体的解释由 media type 决定。[RFC3986]

**事实。** RFC 3629 说明 UTF-8 使用 one-octet encoding unit，U+0000..U+10FFFF 的 code point 用 1 到 4 octets 编码；byte offset 与 character/code-point offset 因而是不同坐标系。[RFC3629]

**事实。** Unicode UAX #29 将 grapheme cluster 作为近似的 “user-perceived character”，推荐 extended grapheme clusters；一个可见字符可以由多个 code points 构成，规范还指出 canonical equivalent text 的 segmentation 结果可以保持一致而 storage offsets 不同。[UAX29]

**设计含义。** 可以用 custom URI 或 fragment 表示可分享 locator，但 URI fragment 不能独自代表 immutable snapshot，也不能把 `#L10-L20` 当作所有 representation 通用的行号。每个 locator 应至少声明：

```text
representation_id
locator_kind: byte_range | text_position | text_quote | dom_path | pdf_region | ocr_region | structural_path
normalization
offset_unit: byte | unicode_code_point | grapheme_cluster | utf16_code_unit
start / end              # 对 position range 建议 start inclusive, end exclusive
quote / prefix / suffix  # 可选，受 retention policy 限制
```

## 3. Proposed representation model

以下 schema 只用于收敛概念和测试边界，全部为 Proposed / unvalidated。

### 3.1 `SourceSnapshot`：抓取结果的不可变身份

建议把 URL 作为获取入口，而不作为证据身份：

```text
SourceSnapshot {
  source_snapshot_id       # opaque, immutable
  requested_url
  final_url
  redirect_chain[]
  retrieved_at
  retrieval_status         # fetched | unavailable | policy_rejected | partial_bytes
  response_status
  response_headers_summary
  raw_media_type
  raw_charset
  raw_byte_length
  raw_sha256
  source_policy_revision
  retention_class
}
```

`source_snapshot_id` 应绑定实际取得的 response bytes（或在不允许保存 raw bytes 时绑定合规允许的 digest/metadata），而不是只绑定 `canonical_url`。同一 URL 在不同时间、不同 redirect、不同 content negotiation、不同 region 或不同 upstream 上可能得到不同 representation；如果服务器没有保存 raw bytes，至少要明确 `snapshot_unavailable` 会让历史 citation 无法重新验证，而不是假装可以恢复。

建议把 HTTP validator（例如 `ETag` / `Last-Modified`）作为 retrieval metadata，而不是 snapshot identity。RFC 9111 的 freshness 定义缓存响应何时可复用及何时需要验证；它不提供 source identity 或 origin-change proof。因此 cache freshness 不能替代 `raw_sha256`、`retrieved_at` 或 representation state。[RFC9111]

### 3.2 `ExtractionRepresentation`：一种明确版本的抽取结果

同一个 snapshot 可以有多种 representation，且 representation 的变更必须可见：

```text
ExtractionRepresentation {
  representation_id       # immutable; includes source_snapshot lineage
  source_snapshot_id
  representation_kind     # raw_bytes | parsed_dom | rendered_dom | pdf_layout | ocr | normalized_text | markdown_projection
  extractor_name
  extractor_version
  extraction_config_hash
  parent_representation_id?
  text_encoding
  unicode_normalization   # none | NFC | NFKC | other explicitly named form
  newline_policy
  layout_metadata_policy
  extraction_status        # complete | partial | failed
  coverage                 # pages / regions / blocks actually covered
  warnings[]
  content_digest
}
```

原则：

- **raw bytes** 是输入事实；**rendered DOM** 是执行 JavaScript、等待或交互后的观察结果；**extraction text** 是 parser 的输出；**Markdown** 是另一次 projection。它们都可以有 digest，但 digest 不表示 source truth 或 publisher authenticity。
- `unicode_normalization`、newline policy、HTML entity handling 和 whitespace policy 必须显式。不能一边返回 code-point offsets，一边在服务端无记录地把 NFC、CRLF、HTML whitespace 或 Markdown hard break 折叠掉。
- `representation_id` 不能只由 URL 或抽取后全文 hash 组成。全文相同的两个 extraction run 可能有不同的 page/DOM/locator metadata；建议把 source lineage、representation kind、extractor/config revision 纳入 identity。
- OCR 是 representation，不是“给原 representation 补几个字符”。扫描 PDF 的 OCR 结果、网页图片 OCR、独立 image URL OCR 都应记录覆盖范围与 extraction revision。

### 3.3 `DocumentStructure`：稳定引用应落在结构节点，不落在 Markdown 行

建议用 typed tree 表达抽取后的结构。最小节点类型可包括：

```text
document
section
paragraph
heading
list / list_item
quote
code_block
link
image / figure / caption
 table / table_row / table_cell / table_note
footnote_marker / footnote_definition
page
text_block
ocr_region
```

推荐的 node identity 原则：

1. `node_id` 至少绑定 `representation_id`；同一 URL 的新 snapshot 或新 extraction 不复用旧 node ID。
2. node ID 应来自 deterministic structural path 加 disambiguator，例如 section ancestry、sibling ordinal、node kind；不要只用全文 hash，因为相同段落可以重复出现。
3. content hash 适合 detection/change checking，不适合单独作 identity。两个相同段落可能属于不同 section、不同 page 或不同 figure caption。
4. page number、DOM path、PDF block order、OCR bounding box 都是 locator 维度，不自动等于永久 identity。parser 或 browser 行为改变时，应生成新 representation。
5. `view_id` 是一次投影的 identity，不能作为 citation 的唯一 identity；一个 section 可以在 preview、section view、find window 中多次出现。

### 3.4 `BoundedView`：渐进式披露的可审计输出

建议把每次输出建模为对一个 representation 的 bounded projection：

```text
BoundedView {
  view_id
  source_snapshot_id
  representation_id
  structure_revision
  view_kind                 # preview | section | range | find_window | page | asset
  selection                 # node IDs and/or explicit locators
  context_closure
  budget {
    max_bytes?
    max_code_points?
    max_blocks?
    max_pages?
    max_occurrences?
  }
  content_parts[]           # typed blocks, not only one Markdown string
  markdown_projection?
  coverage
  truncated
  truncation_reason?
  continuation_scope
  next_cursor?
  warnings[]
}
```

首次 `preview` 建议包含 metadata、heading outline（若可得）、lead/first useful blocks、page/figure/table inventory、extraction warnings 和明确 coverage，而不是承诺“摘要完整”。若 heading outline 本身超过预算，应返回 bounded outline 与 `outline_truncated`，不能把缺失的 headings 当成不存在。

后续 view 建议至少支持：

- `section`: 以 immutable `node_id` 或 structural path 读取一个 section；
- `range`: 在指定 representation 上使用显式 locator；
- `page`: PDF/OCR 按 page 读取，并保留 page identity；
- `find_window`: 在同一个 snapshot/representation 上寻找 occurrence，返回 occurrence locator 与前后 context；
- `asset`: 需要时单独取 figure/image/PDF asset metadata 或受限 bytes。

每个 view 都应同时返回 typed structure 与 Markdown projection（若该 projection 可用）。这样 host 可以选择消费结构化字段、Markdown 文本或 resource link，而不需要从 Markdown 反向猜 table/figure/page 结构。

## 4. Stable ID、locator 与 offset contract

### 4.1 ID 的职责分离

建议明确区分五种 ID：

| ID | Proposed 所指对象 | 能否跨 snapshot 复用 |
|---|---|---|
| `source_snapshot_id` | 一次实际 retrieval 的来源快照 | 否；新 retrieval 生成新 ID |
| `representation_id` | snapshot 上某种 extraction/config/version | 否；representation 改变生成新 ID |
| `node_id` | representation 内的结构节点 | 否；只在该 representation 内稳定 |
| `view_id` | 对节点/locator 的一次 bounded projection | 否；可重复生成 |
| `citation_id` | 对 snapshot + representation + locator 的证据引用 | 不应静默复用；跨 representation 要新建或显式 rehydrate |

`cursor` 不列入稳定 ID。它是 server 生成的 opaque continuation handle，必须绑定 scope，可能过期，也不能出现在 citation 中。MCP specification 对 stateful handles 的 guidance 支持这一方向：handle 是普通字符串，不是隐式 session，服务端应校验 authorization 与 lifetime。[MCP-T]

### 4.2 Offset matrix

| 层 | 典型 locator | 优点 | 主要失败方式 |
|---|---|---|---|
| original bytes | `byte_start/end` | 可回到 raw payload；适合 audit | 不等于 decoded text；UTF-8 variable length，可能落在 code point 中间 |
| parsed DOM | DOM node path + text offset | 能保留 HTML 结构 | parser/browser 执行、动态插入、sanitization 会改变路径 |
| rendered DOM | DOM path + rendered text | 覆盖 JS 页面 | 页面时序、广告、locale、A/B 与用户状态造成变化 |
| extraction text | code-point `start/end` + quote | 适合 evidence 与 W3C selectors | normalization/extractor revision 改变 offset |
| PDF layout/OCR | page + block/region + bbox + text offset | 保留版面、页码、坐标 | OCR/parser 重跑会重分块、重排 reading order |
| Markdown projection | Markdown code-point/byte offset + node ID | agent 读取方便 | 是 projection；换 renderer 或 context closure 后行号会漂移 |
| bounded view | `view_id` + local offset + source locator | 可说明本次输出中的位置 | local offset 只能在该 view 中使用，不是 source identity |

所有 locator 都应携带 `representation_id`、`normalization`、`offset_unit`。如果 consumer 需要 UTF-16 code unit（例如某些 runtime），必须显式声明 `utf16_code_unit`，不能把它冒充 Unicode code-point offset。对 user-facing selection，建议另存 grapheme-cluster-safe 边界；对 evidence 对齐，W3C 的 code-point 规则与 quote selector 更适合作为 baseline。[WA-Q][UAX29]

### 4.3 Citation contract

建议的 Proposed citation：

```text
Citation {
  citation_id
  source_snapshot_id
  representation_id
  locator {
    kind
    structural_path?
    start?
    end?
    offset_unit?
    quote?
    prefix?
    suffix?
    page_number?
    bbox?
  }
  source_state {
    retrieved_at
    content_digest
    extraction_config_hash
    normalization
  }
  rehydration_status   # direct | rehydrated | ambiguous | failed | unavailable
  retention_status
}
```

`quote` 可以为空：受版权、隐私或 retention policy 限制时，保留 position、digest 和 source state，但必须诚实返回“无法保存 quote”。W3C 已指出 quote 可能复制超出预期的受限文本；因此 quote length 与 raw snapshot retention 必须由项目 policy 决定，而不是为方便引用无限保存。[WA-Q]

## 5. Continuation 一致性与 cursor 作用域

### 5.1 continuation 的必要 invariant

建议续读请求至少逻辑上受以下条件约束：

```text
same source_snapshot_id
same representation_id
same structure_revision
same extraction_config_hash
same selection / find query
same normalization + offset policy
compatible budget / view_kind
cursor not expired or revoked
```

`page_size` 或 `max_bytes` 是否允许变化，应在 contract 中明确：一种较安全的 Proposed 方案是允许缩小 budget，不允许扩大到会改变 cursor 的 selection/config；另一种更简单方案是把完整 view configuration hash 绑定 cursor，任何 config 变化都要求新 view。无论选哪一种，都不能让 cursor 表面上继续、实际上在另一 representation 上输出。

MCP 的 list pagination 要求 cursor opaque、server 决定 page size，并把缺失 `nextCursor` 视为结束；但它没有为自定义 `web_read` 内容分页规定 cursor scope/expiry。因此项目需要自行定义 `continuation_scope`、过期错误和 invalidation 行为。[MCP-P]

### 5.2 changed page、cache expiry 与 restart

**Proposed rule：continuation never re-fetches by URL.** 如果 `cursor` 对应的 snapshot 已经被清理、未能复原或 representation 不可用，返回 `snapshot_expired` / `cursor_expired` / `representation_unavailable`；让 caller 发起新的 `web_read(url)`，得到新的 `source_snapshot_id`。如果系统为了满足新请求重新抓取，必须标为新 snapshot，而不是在旧 cursor 下“继续”。

这条规则避免三种误导：

- 内容已变化但旧 citation 看起来仍指向相同位置；
- server 因 restart 丢失旧 snapshot，却把重新抓取的数据当成续读；
- cache stale 被隐藏成成功 continuation。

建议区分：

```text
source_changed        # 新 retrieval 与原 snapshot 不同；旧 citation 仍有效但只针对旧 snapshot
snapshot_expired      # 原 snapshot 曾存在，因 retention/TTL 被清理
cursor_expired        # snapshot 仍可能存在，但 cursor 本身失效
representation_missing# snapshot 存在，要求的 extraction variant 不存在
```

若保留 `ETag`、`Last-Modified` 或其它 HTTP validator，可用于 retrieval comparison 与 conditional request，但不能把 validator 当作 source identity；RFC 9111 的 cache expiry 只约束缓存复用时间，不证明源站是否已经改动。[RFC9111]

### 5.3 failure state 不应合并

| 状态 | 是否有可用 representation | 是否应给 `next_cursor` | caller 的合理动作 |
|---|---:|---:|---|
| `extraction_failed` | 否或仅有另一种明确标注的 representation | 否 | 改用可用 media/extractor 或报告失败 |
| `extraction_partial` | 是，coverage 有缺口 | 仅在同一 representation 可继续时 | 请求缺失 page/region，不能假定全文完整 |
| `output_truncated` | 是 | 是，若 snapshot/representation 可 pin | 用相同 scope continuation |
| `source_changed` | 是另一新 snapshot | 否（旧 cursor） | 显式开始新 read 并新建引用 |
| `snapshot_expired` | 否 | 否 | 重新 read；旧 citation 标记 unavailable |
| `cursor_expired` | snapshot 可能仍有 | 否 | 从 snapshot 的新 view 起点恢复，或重新 read |
| `representation_unavailable` | 其它 representation 可能有 | 否或针对其它 representation 新 cursor | 明确请求 OCR/browser/HTML 等 variant |

## 6. Context closure 与 bounded view 算法

### 6.1 最小 useful evidence 不是任意字符切片

单纯按 byte/character hard cap 切割容易丢失语义。建议每个 view 先选择目标 blocks，再做 deterministic context closure：

- section ancestry：附带当前 block 的 heading path；
- table：附带 caption（若有）、header row、当前 row 的 cell labels、table note；
- figure/image：附带 figure ID、caption、alt text、asset URL 或明确的 OCR status；
- footnote：附带 marker 与 definition，若 definition 超出预算则返回 unresolved reference；
- list：附带 list type、nesting level 和 task state；
- code block：附带 language/info string，并保持 fence 成对或改为 `text/plain` fragment；
- PDF/OCR：附带 page number、reading-order block index 与 region status；
- preceding/following context：仅在 budget 允许时增加，且标出它是 context 而不是 target evidence。

建议 view 明确 `target_blocks`、`context_blocks`、`omitted_context[]`，避免 agent 把为闭合语义补充的 header/note 误认为命中 query 的正文。

### 6.2 oversized block 的拆分

建议 block splitter 的不变量：

1. 不在 UTF-8 byte sequence 中间截断；
2. 不在 Unicode code point 中间截断；
3. user-facing text selection 不跨 grapheme cluster boundary；
4. 记录 `parent_block_id`、`segment_index`、`segment_count` 与 source locator；
5. Markdown fence 要么完整保留，要么该 segment 明确改用 plain-text representation；
6. table row/cell 不应被无标记地拼接到下一页；若 cell 必须拆分，应返回 `cell_segment` 与 continuation relation；
7. 每个 segment 仍可以回到同一 source locator，不用 segment 的 local offset 代替 source offset。

Hard cap 建议同时按 bytes 与 code points（必要时再按 pages/blocks）表达，因为仅有字符上限无法限制多字节 payload，仅有 byte 上限又可能截断过短的 visible text。具体数字必须通过真实 corpus 评测后再选，本文不提出已验证阈值。

### 6.3 find occurrence windows

`find_window` 建议只在 pinned representation 上执行，返回：

```text
Occurrence {
  occurrence_id       # 仅在当前 request/view 中标识
  node_id
  locator
  exact / prefix / suffix?
  window_content
  window_truncated
  match_count_capped?
}
```

对于重复 exact text，prefix/suffix、structural path、page 或 sibling ordinal 用于区分；不要返回“第 3 段”这种无法复核的 ordinal。W3C 对 quote selector 明确要求考虑多个匹配结果；若 selector 仍匹配多处，应标记 `ambiguous` 或列出所有 capped matches，而不是静默选择第一处。[WA-Q]

## 7. PDF/OCR 与 progressive expansion

PDF/OCR 需要比 HTML Markdown 多一层 lineage：

```text
PDF bytes snapshot
  -> page inventory
  -> text extraction representation
  -> layout blocks / table regions
  -> OCR representation per page/region
  -> Markdown / text views
```

**Proposed invariant：OCR expansion never mutates old representation.** 初次读取可能只有 PDF metadata、page inventory 和已有 text extraction；之后按需 OCR 某页会产生新的 `representation_id` 或明确的 child representation。旧的 `citation_id` 仍指向旧 representation，即使新 OCR 发现了更好的文字。新 representation 可以保存 `parent_representation_id` 与 page/region alignment map，但 alignment 失败必须公开。

建议 per-page/per-region 状态至少分开：

```text
not_requested | queued | running | complete | failed | unsupported
```

这不等于 MCP Tasks 必须实现。MCP tasks 是 capability-gated extension；本项目即使不使用 Tasks，也可以用同步 bounded call + explicit handle，或在 caller 侧管理 job。MCP core 不会替项目定义 OCR progress、page continuation 或 alignment semantics。[MCP-B][MCP-T]

OCR 视图建议保留：page number、region/bbox、reading order、OCR engine/version、language/model configuration（若适用）、confidence 作为 extractor metadata，以及原始 image/PDF lineage。不要把 OCR text 直接混入 HTML representation；否则一条 citation 无法说明它来自网页正文、图片、扫描页还是人工生成 caption。

## 8. Annotation、rehydration 与 citation 不变性

### 8.1 允许的 rehydration 层级

建议把 rehydration 分为可审计状态，而不是 universal trust score：

1. `direct`：同一 `source_snapshot_id` + `representation_id`，locator 直接命中；
2. `view_reprojected`：同一 representation，换了 Markdown projection 或 view budget，source locator 未变；
3. `rehydrated`：representation 改变，但通过 quote/position/structural/page mapping 找到唯一新目标；必须生成新 citation 或新 mapping record；
4. `ambiguous`：多个候选，不能自动选择；
5. `failed`：无法匹配；
6. `unavailable`：原 snapshot/representation 已因 retention 或访问状态不可取。

只有 `direct` / `view_reprojected` 可以在不新建 citation 的情况下保持原 citation identity。`rehydrated` 即使匹配成功，也建议产生 `new_citation_id`，并保留 `supersedes` 或 `derived_from` 关系。

### 8.2 citation 验证步骤

一个 Proposed deterministic verifier 可按以下顺序工作：

```text
1. 找到 source_snapshot_id
2. 校验 representation_id 与 content/extraction digest
3. 校验 locator 的 normalization 与 offset_unit
4. 先用 structural/page locator 缩小范围
5. 用 position selector 检查 start/end
6. 用 exact + prefix + suffix 检查内容
7. 若多个匹配，返回 ambiguous，不选第一项
8. 输出 rehydration_status 与 failure reason
```

如果只保留 quote，不保留原始 bytes，应把验证能力描述为“对 extraction representation 的复核”，不要宣称“可回到原网页 bytes”。如果 snapshot 已删除，citation ledger 可以保留 citation metadata，但内容必须标为 `unavailable`，不能生成新的 quote 伪造可复核性。

## 9. Stateful complexity、storage 与 security

### 9.1 三种路线比较

| 路线 | 复杂度 | 一致性 | 适用判断 |
|---|---:|---|---|
| 每次按 URL 重新抓取并切片 | 低 | 弱；页面变化、redirect、JS 时序会漂移 | 仅适合明确声明 non-repeatable、无稳定 citation 的简单 preview；不建议作为本项目 progressive disclosure baseline |
| process 内 bounded snapshot store | 中 | 在 TTL 与同一 process 内较好；restart 丢失 | 可作为本机 prototype 的 Proposed 起点；必须把 restart 变成显式 `snapshot_expired` |
| file-backed content-addressed store + metadata index | 中高 | 可跨请求/restart 复核，仍可不引入 database | 更符合 local Windows/CPU 与 evidence retention 目标；需要清理、权限、加密/隐私 policy 验证 |
| database + object store | 高 | 多用户、并发、检索与审计更强 | 只有在实测需要并发/跨进程查询后再考虑；不是本 memo 的默认前提 |

建议优先验证 **file-backed snapshot/artifact store + 小型 metadata index**，但这只是 recommendation，不等于实现决定。存储层应把 raw bytes、extraction artifact、views、citation ledger 分开设 retention；任何“只保存 Markdown”路线都无法完整满足原始 asset、OCR region、layout 与 rehydration 要求。

### 9.2 handle 与 cursor 的安全约束

- `source_snapshot_id`、`representation_id`、`cursor` 应是 opaque，避免在 token 中直接放 URL、query、authorization、filesystem path 或 PII；
- 每次 continuation 重新检查 caller authorization 与 retention scope；MCP 的 handle guidance 不把 handle 本身视为 authorization capability；
- cursor 要绑定 source/representation/config/query，过期后不可通过猜测或修改恢复；
- page content、HTML comments、alt text、OCR text、PDF metadata 都是不可信 data，不得改变 tool policy、egress allowlist 或 retention policy；
- raw bytes 与 extracted text 可能包含个人信息、版权内容或第三方 tokens，日志默认只记 IDs、状态和 digest，不记完整正文；
- 删除 snapshot 后保留 citation ledger 时，必须保留 `retention_status` 与 unavailable reason，避免下游误以为 citation 仍可验证；
- `https` resource URI 只有在 client 能自行 fetch 时才适合直接使用；若必须经 MCP server 读取，应使用明确的 custom URI 或 tool input，并记录 server-side snapshot state。[MCP-R]

## 10. MCP tool/resource contract 的 Proposed 形态

下面只给出概念字段，所有字段名、错误码与 view type 仍需 schema review：

```text
web_read({
  url,
  snapshot_id?,
  representation_id?,
  view_kind?,
  section_id?,
  locator?,
  find?,
  cursor?,
  budget?,
  extraction_policy?
}) -> {
  resultType: "complete",
  source_snapshot,
  representation,
  view,
  citations?,
  next_cursor?,
  state,
  warnings[]
}
```

推荐把 application state 放进 `structuredContent`，同时给兼容 host 一个内容清晰、与 structured result 同源的 TextContent。MCP tool docs 明确建议 structured result 同时带 serialized TextContent 以兼容旧 client；两份内容必须由同一个 result 生成，不能一份是 preview、另一份是全文，否则 citation 会漂移。[MCP-T]

如果使用 MCP resource link，可让 `resource_link.uri` 指向 `snapshot://.../representation/.../view/...` 之类的 custom scheme；URI 只做资源定位，真正的 continuation scope 仍在 application schema。`resources/read` 不能被假定为带有项目自定义 `cursor` 或 section semantics。

## 11. Deterministic validation plan

下列是 Proposed tests，不是已运行 benchmark；验收应优先检查 invariant 而不是平均 latency。

### 11.1 Representation 与 ID

- 同一 raw snapshot、同一 extractor/version/config、同一输入多次运行，输出 structure path、node identity 和 content digest 一致；
- duplicate paragraphs、duplicate headings、相同 table cell text 不发生 node ID collision；
- 相同 URL 的两个不同 bytes 生成不同 `source_snapshot_id`；
- 同一 snapshot 用不同 extractor 或不同 normalization 生成不同 `representation_id`；
- Markdown projection 改变不改变 source node/citation locator，但会改变 view-local offsets。

### 11.2 Offset 与 Unicode

- UTF-8 中文、emoji ZWJ、combining mark、regional indicator、CRLF 与 HTML entity；
- raw byte offset 落在 multibyte sequence 中间时被拒绝，不转换成“最近字符”；
- TextPositionSelector 使用 zero-based inclusive/exclusive；TextQuoteSelector 不在 grapheme cluster 中间切开；
- NFC/NFD 或 NFKC 选择变化时，representation/config hash 和 locator state 变化；
- UTF-16 consumer 明确请求时，返回 `offset_unit=utf16_code_unit`，不与 code-point offset 混淆。

### 11.3 Context closure 与 Markdown hygiene

- table header、caption、table note、footnote definition 与正文 target 分离标记；
- 跨 chunk 的 code fence 不产生无闭合的 Markdown，或者改用 plain-text typed block；
- oversized table cell、长 URL、长 unbroken code、image caption、OCR region 都能分段而不丢 source locator；
- preview 在 outline 超过 budget 时明确 `outline_truncated`，不会把遗漏 headings 当不存在；
- `find_window` 对相同 exact text 返回 multiple/ambiguous，而不是稳定地错误选择第一处。

### 11.4 Continuation 与失效

- continuation 请求不触发 network fetch；用 mock network counter 检验；
- page 在两次调用之间改变，旧 cursor 仍只针对旧 snapshot；新 read 生成新 snapshot 和新 citation；
- process restart、TTL expiry、cursor revoke、representation missing 分别返回不同状态；
- 改变 `find` query、normalization、extraction config 或 representation 后复用旧 cursor 必须失败；
- 缩小/改变 budget 的策略按 contract 一致执行，不允许同一个 cursor 有时重复返回、有时跳过 blocks；
- `extraction_failed` 没有 `next_cursor`；`output_truncated` 只有在 representation pin 成功时才有 `next_cursor`；
- partial PDF/OCR 页明确 coverage，不能把未 OCR page 误记为“无文字”。

### 11.5 Retention 与 privacy

- cursor、snapshot ID、citation ID 的日志不包含完整 URL query、Authorization、raw text 或 OCR payload；
- 删除 raw snapshot 后 citation ledger 的 verifier 返回 `unavailable`，不重新抓取替代；
- handle 过期或换 caller 后进行 authorization check；
-恶意 HTML/PDF/image 中的 prompt-like text 只进入 untrusted content，不会改变 extractor policy、tool allowlist 或存储 retention。

## 12. Open validations

1. **MCP host matrix：** 目标 host 是否保留 `structuredContent`、resource links、embedded resources、custom URI 与 tool execution error；需要真实 host conformance，而不是只读 specification。
2. **Representation retention：** 开源 self-managed 场景在版权、robots、privacy policy 下可保存 raw bytes、PDF、图片、OCR output 到什么程度；不能由 software license 推断 content retention authorization。
3. **Extraction parity：** HTML static、JS-rendered DOM、PDF text/layout、scanned PDF、网页文字图片和独立 image URL 的 representation coverage、CPU/RAM 与 failure rates 尚未测量。
4. **OCR alignment：** 不同 OCR engine/version 对 page/block/reading-order 的重现性与 citation rehydration rate 尚未测量；不能假设 OCR expansion 可以复用原 text offsets。
5. **Budget selection：** byte/code-point/page/block hard caps、context closure 的最小 useful evidence、find-window context 长度均需 corpus-based eval，本文未提出已验证数字。
6. **Cursor retention：** file-backed store 的 TTL、restart recovery、eviction、multi-process locking 和 interrupted write recovery 尚未验证。
7. **Failure taxonomy：** `source_changed`、`snapshot_expired`、`cursor_expired`、`representation_unavailable` 是否能被 target agent 正确理解，需要 tool description 与 adversarial tests 验证。
8. **Quote policy：** W3C quote selector 的 exact/prefix/suffix 与项目的版权、PII、retention 限制如何组合，需明确 policy；不能默认保存全文 quote。

## 13. 具体 implications

- `web_read` 的 differentiator 不是“把网页切成更多 Markdown”，而是 **对同一 source snapshot 提供可解释、可继续、可引用的 views**。
- 首次 response 应把 `coverage`、`representation_kind`、`truncated`、`next_cursor` 的 scope 和 warnings 讲清楚；没有这些字段，agent 很容易把 preview 当全文或把 OCR 空白当源站没有内容。
- stable citation 应落在 `source_snapshot_id + representation_id + locator`；Markdown line number、URL fragment、cursor、view-local offset 都只能是附加 locator 或 presentation hint。
- 应先实现一种可测、可持久化的 representation lineage，再增加 browser、PDF layout 和 OCR；新增 extractor 不能覆盖旧 representation。
- 推荐保留无 state host 的 baseline：如果 host 不支持 resource 或 extension，tool 仍能同步返回 bounded `structuredContent`；但 stateful continuation 仍需显式 handle，不能退回隐式 connection session。
- 不建议引入 universal trust/rank score。此层应返回 source/extraction/provenance facts、coverage 和 rehydration status，把 relevance、source quality 与最终 research judgment 留给 caller agent。

## Citation ledger

> 访问日期均为 2026-09-10。以下只列本 memo 实际使用的 public primary sources；“访问限制”说明 WebFetch 获取情况或规范本身未定义的部分。

| ID | URL；owning institution / authors；publication/version | 本 memo 使用的 supporting section / short quote | 访问限制 |
|---|---|---|---|
| `[MCP-T]` | <https://modelcontextprotocol.io/specification/2026-07-28/server/tools.md>；Model Context Protocol maintainers；MCP Specification 2026-07-28 | `Tool Result`、`Structured Content`、`Output Schema`、`Stateful Tools`、`Error Handling`。要点包括 “structured content is returned as a JSON value in `structuredContent`”、tool result 可含 resource links/embedded resources，以及 protocol has “no concept of a state handle”。 | 官方 specification page 已抓取相关全文；文档示例会省略 request `_meta`，不影响本 memo 的 result/state 结论。 |
| `[MCP-R]` | <https://modelcontextprotocol.io/specification/2026-07-28/server/resources.md>；Model Context Protocol maintainers；MCP Specification 2026-07-28 | `Resources`、`Reading Resources`、`Resource Contents`、`Common URI Schemes`。要点包括 resources application-driven、`resources/read` 返回 text/blob、`https://` 仅在 client 可自行 fetch 时 SHOULD 使用。 | 官方 page 已抓取；本 memo 不把 resource annotations 当成 snapshot/version contract。 |
| `[MCP-P]` | <https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/pagination.md>；Model Context Protocol maintainers；MCP Specification 2026-07-28 | `Pagination Model`、`Operations Supporting Pagination`、`Implementation Guidelines`。短句：“The cursor is an opaque string token”；支持的 operations 仅 resources/prompts/tools list。 | 官方 page 已抓取；自定义 `tools/call` result 的 `next_cursor` 需应用层定义。 |
| `[MCP-B]` | <https://modelcontextprotocol.io/specification/2026-07-28/basic/index.md>；Model Context Protocol maintainers；MCP Specification 2026-07-28 | `Statelessness`：server processes each request independently；跨请求 state MUST 由 explicit identifier 引用。 | 官方 page 已抓取；不等于所有 SDK/host 都完整实现每个 extension。 |
| `[CM]` | <https://spec.commonmark.org/0.31.2/>；CommonMark Project / John MacFarlane；CommonMark 0.31.2 | block/inline syntax、paragraph、fenced code。短句：“A sequence of non-blank lines that cannot be interpreted as other kinds of blocks forms a paragraph.”；“The content of a code fence is treated as literal text”。 | 规范页面可访问；本文只用其语法范围，不推导 Markdown parser 的具体 extractor 行为。 |
| `[GFM]` | <https://github.github.com/gfm/>；GitHub；GitHub Flavored Markdown specification（页面标示 0.29） | `Tables (extension)` 正文已核对；目录列出 `Task list items (extension)`，但本次 retrieval 未取得该 section 正文。短句：“GFM enables the `table` extension”；“Block-level elements cannot be inserted in a table.” | table 相关章节可访问；task-list 具体语法与 checkbox rendering 未核验。本文不把 GFM table 推广为完整 PDF/HTML table-layout 模型；source offsets/provenance 不在所核对的 GFM 数据模型内。 |
| `[WA-Q]` | <https://www.w3.org/TR/annotation-model/#text-quote-selector>；W3C；Web Annotation Data Model | §4.2.4 `TextQuoteSelector`。要点包括 normalized text、Unicode code points “not in terms of code units”、不在 grapheme cluster 内起止、exact/prefix/suffix 与多匹配。 | 官方 section 已抓取；本文把 selector 用作 locator 设计参考，不宣称所有 client 自动支持。 |
| `[WA-P]` | <https://www.w3.org/TR/annotation-model/#text-position-selector>；W3C；Web Annotation Data Model | §4.2.5 `TextPositionSelector`。要点包括 “character position 0”、start inclusive/end exclusive、position brittle。 | 官方 section 已抓取；position 的实际 code-point mapping 仍由本项目 representation 定义。 |
| `[WA-S]` | <https://www.w3.org/TR/annotation-model/#state>；W3C；Web Annotation Data Model | §4.3 `States`、§4.3.1 `Time State`、§4.3.2 `Request Header State`。短句：“States MUST be processed before processing Selector or Style information.” | 官方 section 已抓取；W3C State 不是本项目 retention/cache policy 的完整替代。 |
| `[RFC3986]` | <https://www.rfc-editor.org/rfc/rfc3986#section-3.5>；IETF / Tim Berners-Lee, Roy T. Fielding, Larry Masinter；RFC 3986 | §3.5 `Fragment`。短句：“The semantics of a fragment identifier are defined by the set of representations…”；“the fragment identifier is separated from the rest of the URI prior to a dereference”。 | RFC 全文公开；fragment 的具体语义仍由 representation/media type 或应用定义。 |
| `[RFC3629]` | <https://www.rfc-editor.org/rfc/rfc3629>；IETF / F. Yergeau；RFC 3629 | §1、§3。短句：“UTF-8 has a one-octet encoding unit”；U+0000..U+10FFFF 使用 1–4 octets。 | RFC 全文公开；本 memo 不把 UTF-8 byte boundary 当作 user-visible character boundary。 |
| `[UAX29]` | <https://www.unicode.org/reports/tr29/>；Unicode Consortium；Unicode Standard Annex #29；本次另核对固定版本 <https://www.unicode.org/reports/tr29/tr29-47.html>（Unicode 17.0.0, Revision 47） | §3、§3.1.1、§6.1。要点包括 grapheme clusters 近似 “user-perceived characters”、extended grapheme clusters、canonical equivalence 对 segmentation 与 storage offset 的区别。 | canonical URL 是 latest 入口；固定版本页面明确标示 Unicode 17.0.0 / Revision 47。本文不把 grapheme cluster 作为所有后端的唯一 storage offset。 |
| `[RFC9111]` | <https://www.rfc-editor.org/rfc/rfc9111#section-4>；IETF / R. Fielding et al.；RFC 9111 | §4 freshness。要点包括 fresh response 可在 freshness lifetime 内复用，过期只限制 cache reuse，不证明 origin 改变或 immutable。 | WebFetch 返回了相关 freshness 内容；本文未依赖未抓到的 ETag/If-None-Match 细则。 |

## 证据边界

- 本 memo 没有读取或声称读取任何需要登录、付费 API 或私有网页；没有运行 benchmark、OCR 实验、browser 实验或 MCP host conformance test。
- 现有 repository research docs 只作为项目背景，不作为本 memo 的外部事实来源；MCP、Markdown、Web Annotation、URI 与 Unicode 的关键事实均重新核对 public primary sources。
- 本 memo 不重新打开 agent-owned Deep Research、Search provider 选择或 `deep_search` tool；只把它们当作已给定的产品边界，并集中讨论 `web_read` 的 representation、continuation、citation 与 progressive disclosure contract。
