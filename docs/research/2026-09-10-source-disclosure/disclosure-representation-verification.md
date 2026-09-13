# 渐进式披露表示、一致性与证据契约：独立核验

> 核验日期：2026-09-10
>
> 对象：`disclosure-representation.md`
>
> 本文件是一次 adversarial evidence verification，不是实现报告，也不把本 memo 中的 schema、状态机、存储路线、测试矩阵或阈值变成已批准 contract。除下文标为 Confirmed 的规范事实外，设计结论仍是 Proposed / recommendation / unvalidated。

## 1. 核验范围与方法

本次完整阅读目标 memo，并重新打开其设计驱动的 public primary sources，重点核对：

- MCP 2026-07-28 的 `resultType`、`structuredContent`、tool execution error、resources、pagination、statelessness 与 explicit handle 行为；
- CommonMark 0.31.2 的 block/inline、paragraph、fenced code 语义；
- GFM table 与 task-list 规范可访问程度；
- W3C Web Annotation 的 `TextQuoteSelector`、`TextPositionSelector`、State；
- RFC 3986 fragment、RFC 3629 UTF-8、Unicode UAX #29 grapheme cluster、RFC 9111 cache freshness。

MCP 文档通过官方页面重新取得，并用 Context7 的官方文档索引作交叉定位；Context7 不是本次证据的 owning source。CommonMark、GFM、W3C、IETF 和 Unicode 只以各自官方页面作为证据。没有使用 vendor blog、搜索摘要或 DeepWiki 作为规范事实依据。

本次没有验证：目标 MCP host 的实际互操作、browser/PDF/OCR extractor parity、CPU/RAM、公开互联网质量、文件存储恢复、版权/PII retention policy、任何 benchmark 或 schema implementation。目标 memo 中这些项目已正确标成 open validation 或 Proposed；本文件不把它们重新解释为事实。

## 2. 总体结论

**总体 verdict：核心定位得到支持，但有三处证据契约需要收紧。**

1. 把 progressive disclosure 建模为同一份 pinned snapshot 上的多个 bounded views，是与 MCP 的 statelessness、W3C State/selector 约束和 RFC freshness 语义相容的 **project design recommendation**；它不是这些规范共同强制的架构。
2. `source_snapshot_id + representation_id + locator`、offset unit 显式声明、旧 citation 不因 extractor/OCR 升级而原地改写，属于合理且可审计的 Proposed design；规范支持约束和失败模式，但没有规定这些字段名或完整 schema。
3. MCP stateful-tools guidance 被目标 memo 原先写成“要求”过强。官方 tools 页面明确称该节为 non-normative guidance，并使用 “should consider”。已在目标 memo 中改为“非规范性 guidance 建议”。
4. GFM table 的关键断言已核对；GFM 页面本次只取得 task-list section 的目录标题，未取得正文。因此不能把 task-list 语法、checkbox rendering 或兼容规则写成已核验事实。已在目标 memo 正文和 citation ledger 中标明限制。
5. RFC 9111 支持 freshness/revalidation 的缓存语义，但不直接提供 source identity 或 origin-change proof。目标 memo 已将原先容易读成绝对事实的表述改为更窄的“不能替代 identity/state”。

## 3. Claim ledger

| ID | 目标 memo 的主张 | Verdict | 核验结论与限制 |
|---|---|---|---|
| C1 | MCP 2026-07-28 的 result response 有 `resultType`；`complete` 表示完成，extension 可增加类型 | **Confirmed** | 官方 Basic 页面明确要求 result 包含 `resultType`，并定义 `complete`；工具页面示例与其一致。 |
| C2 | tool result 可含 `content`、resource link、embedded resource、`structuredContent`；`outputSchema` 要求 server 符合、client SHOULD validate；`isError` 是 execution error | **Confirmed** | 官方 Tools `Tool Result`、`Structured Content`、`Output Schema`、`Error Handling` 直接支持。注意“同一 result 生成两份兼容输出”是项目推荐，不是 MCP 强制。 |
| C3 | stateful tool handle 要 opaque、检查 authorization、声明 lifetime、过期报可恢复错误 | **Corrected** | 行为方向正确，但规范强度过高。官方页面写明该节是 “non-normative guidance”，并说服务器 “should consider”；目标 memo 已改为非规范性建议并补 `[MCP-T]`。 |
| C4 | MCP 是 stateless；跨请求 state 必须由 client 每次传 explicit identifier | **Confirmed** | 官方 Basic `Statelessness` 原文明确要求 server 不依赖同 connection 的先前 request，跨请求 state 由 explicit identifier 引用。 |
| C5 | MCP pagination 只规范 `resources/list`、`resources/templates/list`、`prompts/list`、`tools/list`；cursor opaque，page size 由 server 决定 | **Confirmed** | 官方 Pagination 页面逐项列出四类 operation，并规定 cursor opaque、client 不得解析/修改、page size 由 server 决定；无 `tools/call` 正文分页语义。 |
| C6 | MCP resources 是 application-driven；`resources/read` 返回 text 或 base64 `blob`；`https` 仅在 client 可直接 fetch 时适用 | **Confirmed** | 官方 Resources 页面直接定义 application-driven、`contents`、text/blob 及 `https://` guidance。自定义 `snapshot://` 的 continuation semantics 仍属本项目 protocol。 |
| C7 | CommonMark 0.31.2 以 block/inline 解析；paragraph 由 non-blank lines 组成；fenced code literal、同字符 closing fence | **Confirmed** | 官方直接 anchor `#paragraphs` 与 `#fenced-code-blocks` 可取得相关正文。landing page 的大段全文提取会截断，但本次使用的 section 已可见。 |
| C8 | GFM table 有 header/delimiter/body rows，cell 可有 inline Markdown，不能放 block-level elements | **Confirmed** | GFM `Tables (extension)` 正文可取得，原文明确 “Block-level elements cannot be inserted in a table.” |
| C9 | GFM task-list 是独立 extension | **Partially verified** | 官方 GFM 页面目录能看到 `Task list items (extension)` 标题，但本次 retrieval 在 `5.2 List items` 后截断，未取得 `5.3` 正文。目标 memo 已明确不把具体 task-list syntax/rendering 当作事实。 |
| C10 | W3C `TextQuoteSelector` 要求 normalized text、Unicode code points、grapheme-safe boundary，并支持 exact/prefix/suffix 与多匹配处理 | **Confirmed** | W3C §4.2.4 可访问；原文含 “The text MUST be normalized...” 和 “in terms of unicode code points”。目标 memo 将其用于 locator recommendation，而非声称 client 自动支持。 |
| C11 | `TextPositionSelector` 是 zero-based inclusive/exclusive，位置脆弱，建议附 State | **Confirmed** | W3C §4.2.5 原文为 “first character ... position 0”、end exclusive，并称 “very brittle with regards to changes to the resource”；建议添加 State。 |
| C12 | W3C State 在 Selector/Style 之前处理，可记录 time/request-header representation state | **Confirmed** | W3C §4.3、§4.3.1、§4.3.2 相关段落可见；原文为 “States MUST be processed before processing Selector or Style information.” |
| C13 | URI fragment 的 semantics 由 representation/media type 定义，dereference 前分离；fragment syntax 允许 `pchar`、`/`、`?` | **Confirmed** | RFC 3986 §3.5 可取得 ABNF `fragment = *( pchar / "/" / "?" )` 及分离语义。fragment 本身不等于 immutable snapshot。 |
| C14 | UTF-8 byte offset 与 code-point/character offset 是不同坐标系 | **Confirmed** | RFC 3629 §1、§3 明确 one-octet encoding unit 与 1–4 octets；由此区分 byte 与 code-point coordinate。 |
| C15 | UAX #29 将 grapheme cluster 作为 user-perceived character 的近似，extended cluster 与 canonical-equivalent text 可有不同 storage offsets | **Confirmed with version caveat** | canonical latest URL 与 fixed `tr29-47.html` 均核对；固定页标示 Unicode 17.0.0 / Revision 47。目标 memo 使用的是 general rule，不应把 latest URL 与固定版本混写成永久版本。 |
| C16 | RFC 9111 freshness 不能替代 `raw_sha256`、`retrieved_at` 或 representation state | **Confirmed after wording correction** | RFC §4 定义 fresh/stale、freshness lifetime 和 revalidation；§4.3 讨论 ETag/Last-Modified。它没有把 freshness 规定成 source identity，因此目标 memo 已改为不宣称 freshness 证明 origin 是否改变。 |
| C17 | snapshot/representation/node/view/citation 分层、cursor scope、failure taxonomy、context closure、file-backed store | **Proposed / unvalidated** | 这些是目标项目的 design recommendations，不是 CommonMark、W3C、RFC 或 MCP 规定的 schema。规范只能约束部分边界，不能验证具体 field names、TTL、budget 或存储路线。 |

## 4. 已在目标 memo 中原地修正的内容

- **MCP stateful handles：** 将“guidance 还要求”改成“非规范性 guidance 建议”，并补上 `[MCP-T]`，避免把 `should consider` 误写成 MUST。
- **GFM task-list：** 保留“目录列出 extension”这一有限事实；同时说明 section 正文未取得，不再把 task-list 语法或 checkbox rendering 当作已核验事实。
- **RFC 9111：** 将“freshness 只决定何时无需联系 origin；过期/未过期分别不等于 changed/immutable”改成规范直接支持的窄结论：freshness 定义缓存可复用与验证条件，不提供 source identity 或 origin-change proof。
- **UAX #29 source ledger：** 补记 fixed `tr29-47.html` 的版本信息，并区分 canonical latest URL 与固定版本 URL。

未修改目标 memo 中的其他 schema、状态、数字、storage 或测试建议；它们已经被清楚标成 Proposed / unvalidated，擅自替换会越出本次 evidence verification 范围。

## 5. Primary source ledger

以下链接是本次实际访问的 owning sources；Context7 只用于定位官方 MCP 页面，不替代下面的 URL。

| ID | 实际访问链接与 owning institution | 支持的章节/短引文 | 访问限制 |
|---|---|---|---|
| `[MCP-T]` | [MCP Tools, 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/server/tools.md)；Model Context Protocol maintainers | `Tool Result`、`Structured Content`、`Output Schema`、`Stateful Tools`、`Error Handling`。关键句包括 “structured content is returned as a JSON value in `structuredContent`” 和 stateful tools section 的 “This section is non-normative guidance”。 | 相关章节可访问；本核验不把官方页面示例当作所有 host 的实现保证。 |
| `[MCP-R]` | [MCP Resources, 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/server/resources.md)；Model Context Protocol maintainers | `Resources`、`Reading Resources`、`Resource Contents`、`Common URI Schemes`。可见 application-driven、text/blob、`https://` guidance。 | 相关章节可访问；不提供本项目 snapshot/version/citation contract。 |
| `[MCP-P]` | [MCP Pagination, 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/pagination.md)；Model Context Protocol maintainers | `Pagination Model`、`Operations Supporting Pagination`、`Implementation Guidelines`。关键句 “The cursor is an opaque string token”。 | 相关章节可访问；只规范 list operations，不替自定义 `tools/call` content pagination 定义 semantics。 |
| `[MCP-B]` | [MCP Basic, 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/basic/index.md)；Model Context Protocol maintainers | `ResultType`、`Statelessness`。关键句 “A server processes each request independently” 及跨请求 state 使用 explicit identifier。 | 相关章节可访问；MCP version/protocol support 不等于目标 host 已实现全部能力。 |
| `[CM]` | [CommonMark 0.31.2](https://spec.commonmark.org/0.31.2/)；CommonMark Project / John MacFarlane | §4.5 fenced code、§4.8 paragraphs；关键句 “A sequence of non-blank lines...” 和 “The content of a code fence is treated as literal text”。 | landing page 的完整提取会截断；本次直接取得 `#fenced-code-blocks` 与 `#paragraphs`，足以核对所用断言。 |
| `[GFM]` | [GitHub Flavored Markdown](https://github.github.com/gfm/)；GitHub；页面标示 GFM 0.29 | `Tables (extension)` 正文；关键句 “GFM enables the `table` extension” 和 “Block-level elements cannot be inserted in a table.” 目录可见 `Task list items (extension)`。 | table section 可访问；task-list section 正文在本次 retrieval 中不可得，因此具体 task-list syntax/rendering 保持未核验。 |
| `[WA-Q]` | [W3C Web Annotation Data Model — TextQuoteSelector](https://www.w3.org/TR/annotation-model/#text-quote-selector)；W3C | §4.2.4；关键句 “The text MUST be normalized before recording...” 与 “in terms of unicode code points”。 | 所需 section 可访问；页面后续部分会截断，不影响本 section 核对。 |
| `[WA-P]` | [W3C Web Annotation Data Model — TextPositionSelector](https://www.w3.org/TR/annotation-model/#text-position-selector)；W3C | §4.2.5；`start` zero-based/inclusive、`end` exclusive、 “very brittle with regards to changes to the resource”，以及 State recommendation。 | 所需 section 可访问；本项目仍须定义 extraction representation 的 text mapping。 |
| `[WA-S]` | [W3C Web Annotation Data Model — State](https://www.w3.org/TR/annotation-model/#state)；W3C | §4.3、§4.3.1、§4.3.2；关键句 “States MUST be processed before processing Selector or Style information.” | 所需 section 可访问；W3C State 不是本项目 retention/cache policy 的完整替代。 |
| `[RFC3986]` | [RFC 3986 §3.5](https://www.rfc-editor.org/rfc/rfc3986#section-3.5)；IETF / Tim Berners-Lee, Roy T. Fielding, Larry Masinter | `fragment = *( pchar / "/" / "?" )`；关键句 “the fragment identifier is separated from the rest of the URI prior to a dereference”。 | 所需 section 可访问；fragment 的具体 semantics 仍由 representation/media type 或应用定义。 |
| `[RFC3629]` | [RFC 3629](https://www.rfc-editor.org/rfc/rfc3629)；IETF / F. Yergeau | §1、§3；关键句 “UTF-8 ... has a one-octet encoding unit” 和 1–4 octets。 | 所需章节可访问；不把 byte boundary 当作 user-visible character boundary。 |
| `[UAX29]` | [Unicode UAX #29 latest](https://www.unicode.org/reports/tr29/)；另核对 [Unicode 17.0.0 Revision 47 fixed page](https://www.unicode.org/reports/tr29/tr29-47.html)；Unicode Consortium | §3、§3.1.1、§6.1；grapheme cluster、extended grapheme cluster、canonical equivalence 与 “different offsets”。 | canonical URL 是 latest；fixed URL 是本次可复现的版本化证据。不同 Unicode version 的规则变化仍需在实现选定版本后锁定。 |
| `[RFC9111]` | [RFC 9111 §4](https://www.rfc-editor.org/rfc/rfc9111#section-4) 与 [§4.3](https://www.rfc-editor.org/rfc/rfc9111#section-4.3)；IETF / R. Fielding et al. | fresh/stale、freshness lifetime、revalidation、ETag/Last-Modified；关键句 “A \"fresh\" response is one whose age has not yet exceeded its freshness lifetime.” | 所需章节可访问；本文未依赖未取得的其它 cache corner cases，也不把 cache validator 当 immutable identity。 |

## 6. 未解决的高影响缺口

1. **MCP host conformance：** 规范允许 `structuredContent`、resource links 和 custom URI，但仍需真实目标 host 验证它们是否保留、展示和传回；不能只从 spec 推断客户端行为。
2. **Snapshot retention 与 privacy：** 是否可保存 raw bytes、PDF、图片和 OCR text 取决于内容 policy、版权与 PII 处理，不由软件 license 推出。当前 memo 没有宣称已获得 retention authorization。
3. **Representation parity：** static HTML、JS-rendered DOM、PDF layout、scanned PDF、网页文字图片和独立 image URL 的 extraction coverage、CPU/RAM、失败率和定位重现性均未测量。
4. **OCR rehydration：** OCR engine/version、page/block/reading-order alignment 不能假设稳定；需要 adversarial corpus 验证旧 citation 不会被新 representation 伪装为同一 citation。
5. **Budget 与 cursor：** byte/code-point/page/block caps、context closure 的最小 useful evidence、TTL、restart recovery、eviction、multi-process locking 都是待评估 Proposed numbers/behaviors。
6. **GFM task-list：** 若后续实现需要 task-list parsing，应重新取得官方 section 5.3 正文或官方 source，并单独核对语法；本 memo 当前只需要 table/Markdown boundary，未依赖 task-list 细节。
7. **License/CPU assertions：** 本 memo 没有用具体 library、license、CPU benchmark 作为证据；这些项目约束来自仓库已接受的 product boundary，若后续新增库或性能结论，必须另行以 maintainer source、license text 与实测记录核验。

## 7. 结论

目标 memo 的 differentiator 论证没有发现会推翻整体方向的 primary-source contradiction。最关键的证据契约应保持：同一 `source_snapshot_id` 上的 representation lineage、显式 normalization/offset unit、opaque continuation state、旧 citation 不随新 extraction 覆盖，以及把 extraction failure、output truncation、expiry 和 source change 分开。

但这些是本项目为可靠 progressive disclosure 提出的设计约束，不是 MCP、Markdown、W3C、URI、Unicode 或 HTTP freshness 规范直接规定的完整 schema。后续实现与验收必须继续把外部事实、设计推论和实测结果分栏，尤其不能把 GFM task-list 未取得的正文、目标 host 行为或 CPU/OCR 性能写成已证实事实。
