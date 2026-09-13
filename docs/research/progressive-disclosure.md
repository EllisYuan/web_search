---
title: Progressive Disclosure：Research agent 的可复核内容导航
status: researched
research_date: 2026-09-10
implementation_status: research only; no runtime experiments performed
scope: HTML、JavaScript-rendered pages、text/mixed/scanned PDF、网页文字图片、独立 image URL；Windows、CPU-only、free/open-source self-managed
---

# Progressive Disclosure：Research agent 的可复核内容导航

> 本报告是 Q3 的独立 deep research。它研究 Progressive Disclosure 是否以及如何成为本项目的主要 differentiator，而不是把正文切成普通 pagination。报告中的新字段、schema、操作、budget、阈值、组件顺序和验收标准均为 **Proposed / recommendation / unvalidated**；不等于已接受 contract、已实现行为或 SLA。日期为 2026-09-10。本轮没有运行新的 browser、OCR、PDF、Search 或 MCP host conformance experiment；项目已有的受限 CPU functional smoke 仅作为已有 evidence 说明，不能升级为本轮 benchmark。

## 1. 结论摘要

### 1.1 核心判断

**Progressive Disclosure 的可行 differentiator 不是“返回更少 token”，而是让 caller agent 在同一份可复核 source representation 上，逐步获得刚好足以做下一步判断的原文、定位、上下文和失败状态。** 这和普通 output pagination 的区别在于：pagination 只回答“下一段在哪里”，Progressive Disclosure 还回答“当前看到的是什么 representation、为什么这段值得继续读、哪些限定条件必须一起读、继续读取是否仍针对同一 snapshot，以及缺口是否来自 source、extraction 还是 output budget”。

建议把研究结论收敛为以下六点：

1. **证据强度有限但方向一致。** NN/g 的 human HCI guidance 支持“先展示少量核心选项、按需提供 specialized options、保持入口可发现”；ReAct、SWE-agent、ToolSandbox 与 Lost in the Middle 分别提供 observation loop、interface shape、stateful trajectory 和 context-position 的间接 agent evidence。它们不能证明本项目的 `preview -> find -> evidence window` 一定优于 full Markdown 或 fixed chunks，直接 A/B 仍是 open validation。[S1–S8]
2. **关键对象应是 source snapshot 与 extraction representation，而不是 URL、Markdown 行号或 cursor。** W3C selector/state、MCP pagination 的 opaque cursor 语义、RFC 3986/3629、Unicode UAX #29 支持明确 representation、normalization、offset unit 和 state；MCP Tools 页关于 stateful tools 的内容只是 non-normative guidance，不能据此把 statelessness 写成协议要求。完整 `source_snapshot_id`/`representation_id`/`cursor` schema 是项目 proposal，不是外部标准规定。[S7][S9][S10][S11][S12][S13]
3. **capture、extraction coverage、rendered output truncation 必须分开。** 页面成功下载不表示正文语义已抽取；抽取了 80% 页面不表示本次 response 输出了 80% 的结果；OCR 有文字不表示 figure、table 或 reading order 正确。三者必须有不同状态和恢复动作。
4. **需要分层 portfolio，不存在一个 universal converter。** HTTP/raw evidence、static HTML extraction、browser fallback、native PDF text/layout、selective OCR、advanced layout backend 和 Markdown/HTML projection 各自承担不同角色。官方资料支持候选能力边界，却没有证明目标 Windows CPU corpus 上的 fidelity、RAM、latency 或 license fit。[F18–F32]
5. **No-LLM structured extraction 应保持 v1 baseline。** `preview`、`find`、`read`、`expand` 都应返回 deterministic metadata、structure、verbatim text、locators、coverage 和 warnings，不把模型生成 summary 混进正文。未来 summary 只能是显式 caller-selected optional route，并带 generated/provenance 标记；它不属于 accepted baseline。
6. **Caller 必须拥有导航、reference following、query reformulation 与 synthesis。** `web_search` 只发现候选 URL/SERP metadata，`web_read` 独立读取 caller 提供的 URL；MCP Resources 是 application-driven，不能假设每个 host 有 picker 或自动注入。因此 Progressive Disclosure 必须在 plain tool result 上成立，Resources 只能是 optional transport/view。

### 1.2 目前可以说什么，不能说什么

| 层级 | 可以说 | 不能说 |
|---|---|---|
| 已核验 Fact | 外部论文、规范和 maintainer docs 的有限语义；例如 MCP cursor opaque、W3C position selector brittle、pypdf 对 PDF semantic layout 的限制 | 外部论文已经证明本项目的 default window、token saving 或 research quality |
| Interpretation | 同一 snapshot 的 bounded views 更容易审计；context closure 比裸字符切片更可能保住表头/脚注等解释前提 | 这是普遍优于 fixed chunks 的定律 |
| Proposed design | `preview/find/read/expand`、typed IR、snapshot/representation lineage、file-backed snapshot store、failure taxonomy | 字段已经是最终 schema、数字已经是批准 budget |
| Existing project evidence | pinned `4c210d1` 的受控 smoke 曾运行静态/JS HTML、text/scanned/mixed PDF、网页文字图片、独立 image URL 和逐页 continuation | 真实互联网 coverage、公开 corpus fidelity、performance benchmark、SLA 或 research-agent A/B |
| Open validation | Windows clean-machine、CPU/RAM、table/reading order、OCR alignment、host conformance、license/retention | “文档写了支持”即“目标系统完成验证” |

## 2. 产品边界与研究问题

### 2.1 Accepted requirements（不由本报告重新决定）

以下是仓库已有的 accepted boundary，本报告把它作为输入而不是重新批准：

- Deep Research 的 planning、query planning、source selection、counterevidence、继续研究和最终 synthesis 由 caller agent 负责。
- v1 提供可组合的 `web_search` 与 `web_read`，不增加 server-side `deep_search` facade。
- `web_search` 返回候选 URL 与 SERP metadata，不自动读取正文或生成综合答案；route/backend 由 caller 显式选择，v1 的 SearXNG route 只启用 Google engine，不做隐式 fallback，默认不 automatic retry，retry 由 caller 显式发起新的可审计 attempt。
- `web_read` 独立接受 caller 直接提供的 URL；首次响应包括 metadata、outline（若可得）和限长正文；可按 section、位置或页内关键词继续读取；正文尽量是原文抽取，不依赖模型 summary。
- v1 必须覆盖普通 HTML、JavaScript 页面、PDF，以及 OCR 的扫描 PDF、网页文字图片和独立 image URL。
- 自建组件必须免费、开源、Windows 可开发部署、CPU-only 可运行；不因此承诺任意页面无损或任意 source 都能完成。
- 页面、PDF、image、HTML comment、`alt`、OCR text 和 embedded metadata 均是 untrusted data，不得改变 tool policy、query、credential、budget、retention 或 reference-following policy。

### 2.2 本报告回答的独立问题

1. “渐进式”究竟比 output pagination 多出什么可验证价值？
2. 如何在 HTML、JS、text/mixed/scanned PDF、网页文字图片和独立 image URL 之间保留可恢复证据？
3. 如何同时服务默认初读、targeted find、section/page read、context expansion 和后续 continuation，而不让 server 代替 caller 做 research planning？
4. 哪些设计是外部规范支持的约束，哪些只是本项目应测的 proposal？
5. 如何用 paired baseline/ablation 测“固定 quality 下 useful evidence per token”，避免只优化短输出而牺牲 caveat、table header、footnote、source locator？

## 3. Evidence base：方向证据而非本项目效果证明

### 3.1 Human progressive disclosure：有用的原则，证据迁移弱

NN/g 将 progressive disclosure 定义为“Initially, show users only a few of the most important options”，并在需要时提供 specialized options；同时警告入口不可发现、层级过深和额外交互会增加成本。[S1] 这直接支持三个界面原则：默认 observation 不应要求 agent 先理解全部字段；高级内容应可按需展开；展开入口必须知道将获得什么。

但人类用户能够利用视觉布局、空间位置和熟悉控件推断 affordance，agent 更依赖 schema、locator、coverage、cursor 和明确的下一步动作。因而这是 interaction analogy，不是本项目 agent quality evidence。Carroll/Carrithers 的 `Training Wheels in a User Interface` 在本轮仅读取 Crossref 摘要/metadata，不能据此报告实验细节。[S2]

### 3.2 Agent evidence：Observation 形状重要，但任务不等价

- **ReAct。** 原论文展示 Thought/Action/Observation 交错，在 HotpotQA 示例中先 search、检查结果、改写 query、再读取；FEVER 中可以明确 `NOT ENOUGH INFO`。[S3, §2, Appendix C.1–C.2] WebShop/ALFWorld 的数字是特定任务、模型和 prompt 的结果，不是 `web_read` SLA。
- **SWE-agent。** 论文把 ACI 视为 agent 的操作界面，并提出 feedback 应 “informative but concise”。其 ablation 改变 edit/search/window/history shape 会改变成功率，但这些数值来自 code repair，不能直接成为 web page 的 char/page default。[S4, §2, §5.1, Table 3]
- **ToolSandbox。** 其 benchmark 强调 stateful、conversational、interactive trajectory，以及 milestones/minefields，而不是只看 final answer；正文/表格可读部分报告 1,032 scenarios、34 tools、11 domains 等 task-specific figures。[S5, §1–3, Table 4] 这支持把 stale cursor、补读脚注、错误后的恢复纳入 evaluation，不证明 Progressive Disclosure 的净收益。
- **Lost in the Middle。** 论文在 multi-document QA 和 key-value retrieval 中报告相关信息在开头/结尾通常更容易被利用，且 “extended-context models are not necessarily better”。[S6, §1–4, Figures 1/5/7/9] 这支持把 query-targeted evidence 放在可见位置、避免默认把无关长文倒入 observation；不能外推为任何 large-context、任何文档任务都失败。

**Evidence judgement：** 这些来源对“observation/interface/context shape 会影响 agent 行为”的支持为中等强度、跨任务间接；对本项目的 `preview -> find -> evidence window` 是否优于 alternatives 的支持为低，必须做 frozen-corpus paired experiment。

### 3.3 MCP：提供容器与能力，不提供本项目正文 pagination contract

MCP 2026-07-28 Tools specification 将 Tools 定义为 model-controlled；tool result 可以有 `content`、`structuredContent`、resource link、embedded resource，execution error 可以用 `isError: true` 表达。[S7] Resources specification 将 Resources 定义为 application-driven：host 可以用 UI、filter 或 heuristics 纳入 context，协议不规定一个共同 picker 或自动注入行为。[S8] Pagination specification 规定 cursor 是 opaque，server 决定 page size，client 不得解析/修改；标准 list pagination 覆盖 `resources/list`、`resources/templates/list`、`prompts/list`、`tools/list`，不自动定义 `tools/call` 的正文 continuation。[S9]

因此：

- `web_read` 可以在 `structuredContent` 中返回项目自己的 `source_snapshot_id`、`representation_id`、`coverage` 和 `next_cursor`；这些是 application protocol。
- Resources 可以承载 snapshot 或 evidence artifact，但不能作为所有 host 的最低入口。
- `isError` 应区分 protocol failure 和 execution/content state；例如 `output_truncated`、`extraction_partial` 可有结构化 content，不能都丢成 generic error。
- Stateful handle 的 opaque/lifetime/authorization 方向在 Tools 页属于 non-normative guidance，不应误写成 MCP MUST。[S7]

### 3.4 Representation evidence：可恢复性需要多层 lineage

W3C Web Annotation 规定 `TextQuoteSelector` 的 `exact`、可选 `prefix/suffix`，以及 `TextPositionSelector` 的 zero-based start、exclusive end；同时指出 position 对 source change 很脆弱，建议配合 State。[S10] RFC 3986 说明 fragment semantics 由 representation/media type 定义，不等于 immutable snapshot。[S11] RFC 3629 区分 UTF-8 byte unit 与 code point，Unicode UAX #29 说明 grapheme cluster 近似 user-perceived character，并提醒 storage offsets 可能不同。[S12][S13]

这些规范支持的最小结论是：locator 必须携带 representation、normalization 和 offset unit；URL fragment、Markdown line number、byte offset、code-point offset、UTF-16 code unit 不能互相冒充；source change 后旧 citation 不能静默指向新内容。`source_snapshot_id`、`representation_id`、node identity 和 cursor binding 的具体字段仍是 proposed。

## 4. 为什么 Progressive Disclosure 不是“更多 pagination”

### 4.1 四个对象要分开

1. **Source capture。** 是否取得了 response bytes、redirect hops、final URL、headers summary、PDF/image payload 或 rendered DOM。capture 可能失败、被 policy 拒绝、只取得 partial bytes。
2. **Extraction coverage。** 在已捕获 representation 中，哪些 page、DOM region、block、table、figure、OCR region 成功解析；JS shell、collapsed tab、infinite scroll、image-only region、encrypted PDF、OCR failure 都会造成 coverage gap。
3. **Rendered output truncation。** 本次 response 因 max bytes/code points/blocks/pages 截止，但相同 representation 仍可能有可继续读取的 blocks。它不是 source 不完整，也不是 extraction failure。
4. **Semantic adequacy。** 即使 capture/extraction/output 都标为 complete，reading order、table reconstruction、footnote association、figure semantics 仍可能是 inferred 或 uncertain；`complete_as_fetched` 不等于 semantic truth。

建议至少保持下列正交字段（名称为 proposal）：

```text
capture_status: fetched | partial_bytes | unavailable | policy_refused | failed
extraction_status: complete | partial | failed | unsupported
coverage_scope: pages / DOM regions / blocks / OCR regions actually processed
output_status: complete | truncated
semantic_warnings: reading_order_inferred | table_uncertain | ocr_approximate | figure_not_interpreted ...
```

### 4.2 Progressive Disclosure 的差异化行为

普通 pagination 通常只提供 `cursor -> next slice`。本项目的 proposal 应提供：

- **导航线索：** metadata、heading outline、page map、table/figure inventory、exact find matches；不生成事实性摘要。
- **目标选择：** caller 用 query、section、page、block、table、figure、footnote 或 evidence locator 选择下一步。
- **context closure：** 自动确定性补上会改变 interpretation 的 header、unit、caption、footnote、definition、time range、exception 和 section ancestry，并标出 target/context boundary。
- **representation awareness：** 明确当前是 static HTML、rendered DOM、native PDF text、PDF layout、OCR text、image asset 还是 Markdown projection。
- **recoverability：** continuation 绑定固定 snapshot/representation/config/query，source changed、cursor expired、snapshot expired、representation missing 和 output truncated 分开恢复。
- **caller control：** 不自动跟随所有 references，不自动跨 source synthesis，不用 server-side summary 代替 evidence。

由此，differentiator 的假设可写成可测命题：在相同 source snapshot、相同 extraction representation、相同总 byte/token budget 和相同 agent/model 下，结构化导航和 context closure 是否提高 material claim recall、quote fidelity 和 caveat preservation，同时降低无效 observation；这不是当前已证实结果。

## 5. 必须覆盖的内容形态与保真边界

### 5.1 HTML、Markdown、纯文本

Trafilatura 官方 README 将其定位为 main text/metadata/comments extraction，可选 links、images、tables，并输出 TXT/Markdown/JSON/HTML/XML 等；当前 README 写 Apache-2.0，但未据此证明目标 Windows runtime。[F18] Mozilla Readability 的 `parse()` 返回 title/content/textContent 等 article-oriented fields，官方明确 `isProbablyReaderable()` 有 false positives/negatives，且 parser 不负责 sanitization。[F19]

建议的事实边界：

- raw HTML/response bytes 必须先保留或按 retention policy 明确不能保留；content view 不是 raw page。
- headings、`pre/code`、figure/alt/figcaption、links、tables、comments 和 DOM lineage 不应被 main-text extractor 静默销毁。
- CommonMark core 不含 tables/footnotes；GFM table cell 允许 inline content、不允许 block-level elements。[F20] 复杂 table、nested block、footnote relation 和 page locator 应留在 typed IR/HTML/sidecar，不强行压成 GFM。

### 5.2 JavaScript-rendered pages

Playwright Python 官方文档列出 Windows/macOS/Linux、Chromium/Firefox/WebKit 和 sync/async API。[F21] Network docs 支持 page/context routing、request observation，并提醒 service-worker requests 可能不出现在通常 routing/events；download docs 支持 download event、URL、suggested filename、stream 和 `saveAs`。[F22][F23]

不能把“执行 JavaScript 成功”写成“语义内容完整”。以下内容仍可能缺失：

- delayed hydration、collapsed tabs、普通 interaction 后才出现的 content；
- infinite scroll 的未滚动部分、pagination fragments、personalized/A-B branches；
- service-worker-handled requests、third-party iframe、downloaded artifact 的真实 MIME/magic bytes；
- DOM order 与视觉阅读顺序之间的差异。

因此 browser 是 acquisition/extraction route，不是 completeness proof。应记录 rendered method、triggering action、scroll/page budget、loaded scope 和未加载 scope。

### 5.3 Text PDF、mixed PDF、scanned PDF

pypdf 官方文档指出 PDF 通常缺少 paragraph/header/footer/table/caption 的 semantic layer，reading order 可能不明确，scanned PDF 需要 OCR；`layout` mode 和 visitor callbacks 只是 approximation。[F24] pypdf LICENSE 为 BSD-3-Clause。[F25]

PyMuPDF 文档支持 pages → blocks → lines → spans → characters、words、DICT/RAWDICT、image/render/OCR/table API，但 default order 可能是 creator order，`sort=True` 是 top-left approximation；其 AGPL/commercial license 必须先解决，不能仅因为 capability 强就默认采用。[F26][F27]

Docling 文档描述 structured `DoclingDocument`、body/furniture、reading order、tables、pictures、formulas、provenance/layout，以及 PDF/HTML/images/OCR/Markdown/JSON 方向；官方安装页同时列 Windows support 与 Linux-oriented CPU-only example，不能把前者推导成 native Windows CPU validation。[F28][F29]

建议的 per-page classification（proposal）：`native_text`、`ocr_text_layer`、`image_only`、`mixed`、`uncertain`。native text 与 OCR 必须是不同 representation lineage；mixed PDF 的 overlap conflict 不静默选择，保留 native/OCR 两份和 bbox/source method。

### 5.4 OCR、网页文字图片、独立 image URL

Tesseract 官方 repo/docs 支持 Apache-2.0、Windows 10/11、100+ languages，以及 hOCR/TSV/ALTO/PAGE/PDF 等 output；官方示例可提供 bbox/confidence，4 CPU cores 的文字是 build/documentation fact，不是目标机器 benchmark。[F30][F31] PaddleOCR FAQ 提到 Windows/macOS adaptation，repository 为 Apache-2.0，但当前资料不提供完整 CPU inference matrix 或 performance evidence；model/weights/runtime licenses 仍需 inventory。[F32]

独立 image 与网页 `<img>` 不能只转成 OCR text：

- 保存原始 asset、MIME、dimensions、hash/final URL（受 retention policy 约束）；
- 关联 `alt`、`figure`、`figcaption`、nearby heading/paragraph；WHATWG 区分 alt 的 textual replacement 与 figcaption 的 supplementary caption，不能把 caption 重复写进 alt。[F33]
- 保存 OCR boxes/confidence/engine/version/language 和 page/region lineage；
- chart axes、legend color、箭头/拓扑、formula layout 和视觉 emphasis 不由 OCR 自动恢复；无法支持时标记 `figure_not_interpreted`，不猜测图义。

## 6. Layer roles：从 capture 到可复核 bounded view

建议把实现理解成七层；这是 architecture proposal，不是现有实现：

```text
1. Policy + acquisition
   URL validation, SSRF/robots/access policy, raw response/download
2. Source snapshot
   bytes/redirect/retrieval identity/retention state
3. Extraction representations
   static DOM, rendered DOM, native PDF text/layout, OCR, image asset
4. Structural IR
   document/section/block/page/table/figure/caption/footnote/locator
5. Navigation index
   outline, deterministic find, page/block inventory, reference links
6. Bounded views
   preview, find_window, section/page/range, evidence window, asset
7. Citation/continuation
   snapshot + representation + locator + opaque cursor + lifecycle state
```

### 6.1 Portability与可恢复证据

- **Portability：** 依赖 MCP `structuredContent` + TextContent 同源回退，不依赖 Resources picker；caller 直接传 URL、snapshot ID、representation ID 或 opaque cursor。Resources 可选暴露 artifact，但无 resource support 的 host 仍能使用同步 bounded tool result。
- **Recoverability：** raw/source snapshot、extraction artifact、typed IR、view 和 citation ledger 分开保存；新增 extractor 产生 child representation，不覆盖旧 representation。若不能保存 raw bytes，必须明确 `retention_status=metadata_only`，不要声称可恢复原始页面。
- **审计性：** citation 绑定 `source_snapshot_id + representation_id + locator + normalization + offset_unit + digest/retrieved_at`；`raw_sha256`（source snapshot 原始字节的 identity/change-detection 摘要）与某个 representation 自身的 content digest 是两个不同层级的东西，不应混成同一个笼统的“hash”概念——两者都只用于 identity/change detection，都不证明 publisher authenticity，也都不能保证同一 raw bytes 在不同 extractor/OCR config 下产生相同输出或 reading order；确定性需要额外锁定 extractor/OCR 版本与 config，并通过 determinism test（同 raw + 同 config 复算 digest）验证。
- **Restart：** continuation 不能隐式依赖 process/connection；process restart 后若 snapshot 不可恢复，应返回 `snapshot_expired`，让 caller 新起 read，而不是按 URL silently refetch 并伪装继续。
- **Representation frozen 与 capture artifact：** rendered DOM、network/download asset 只是 capture 阶段的产物，不是语义完整性证明；raw HTML digest 不代表 JS 执行后的完整状态（同一 raw bytes 在不同时间/环境执行 JS 可能得到不同 DOM）。一旦某个 representation 被生成并对外返回过（进入过某个 view/citation），就应视为 frozen：后续新的抽取/渲染/OCR 只产生新的 child representation，不得原地修改或“长大”已发布的 representation。

### 6.2 Reading order

- HTML：DOM heading path 是 structure cue，但 visually styled non-heading、shadow DOM、rendered DOM 和 static DOM 要标记区别。
- PDF：如有 tagged/structured data 优先使用；否则 geometry inference，标记 `reading_order_inferred`。header/footer/furniture 不默认销毁，应可在 view policy 中隐藏但保留 lineage。
- OCR：engine line order 与 bbox grouping 只是 extraction signal，不等于 semantic order。
- 多栏文档：错误 reading order 可能比固定 chunks 更危险；结构化 view 必须保留 page/column/block locators 和 warning。

### 6.3 Tables

- HTML table 保留 `thead/tbody/tfoot`、caption、row/col span、cell header relationships。
- PDF table 多数只有 absolute-positioned text；geometry/table model 是 inference，应带 cell lineage、merged-cell uncertainty 和 page bbox。
- GFM table 仅适合简单 rectangular table；merged cells、nested blocks、table notes 用 HTML/typed sidecar。
- OCR table 要结合 boxes 与 grid/layout signals；plain OCR text 不足以重建 rows/columns。
- `find` 命中一个数字时，evidence window 应带 caption、header、unit、row/column labels 和 notes，而不是只返回数字。

### 6.4 Footnotes、captions、figures、references

Context closure 只能确定性补齐**结构或 index 中可发现的链接**：

- section ancestry；
- table caption/header/unit/table note；
- figure caption/alt/legend/asset status；
- footnote marker + definition（通过 marker 显式链接的部分）；
- reference label/anchor，但不自动 fetch cited source。

`definition`、`sample/time-range qualifier`、`exception/limitation` **只有在它们通过上述某种确定性链接（例如同一 table note、同一 footnote definition）与 target 相连时**才属于 closure 的职责；如果它们只是散落在正文别处、没有结构/index 链接，closure 不会、也不应该去发现——这类未链接的远距限定语和语义例外，只能由 caller 自行阅读周边正文或整份 source 判断，closure 不能替代这一步。

每个 context block 都应携带 `closure_basis`（凭哪种确定性链接被补入）；响应应携带 `unknown_context`/`unresolved_context` 和恒为 `unknown` 的 `semantic_completeness` 字段，提醒 caller：**空的 `unknown_context` 列表从不意味着语义完整**。如果 closure 超出 budget，应显式返回 `omitted_context` 或 `unresolved_reference`，而不是把 target 伪装成 self-contained fact；通过 inference 而非显式链接得到的关联，必须标注为推断。完整字段设计见 [`../design/progressive-disclosure.md`](../design/progressive-disclosure.md) 第 7.2 节。

## 7. Caller-driven navigation model

### 7.1 Candidate operations（proposal）

可做一个 `web_read` tool 的 `action` 字段，也可拆成多个小 tool；本轮不锁定暴露方式。概念动作：

- `preview`：metadata、representation status、outline/page map、inventory、warnings、bounded lead；不是 summary。
- `find`：在 pinned representation 上做 deterministic exact/normalized/structure-aware matching，返回 verbatim match、locator、representation scope 和 negative-result meaning。
- `read`：按 section/page/block/table/figure/footnote/range 读取 bounded structured Markdown/typed blocks。
- `expand`：围绕 match/evidence 加 context closure，优先补 prerequisites，而不是无条件扩大全文。
- `asset`（可选的暴露方式，不是可选的能力）：取 image/page crop/PDF asset metadata 或 policy 允许的 bytes。图片获取与 OCR 覆盖是 accepted scope 的必需能力，必须通过 `initial`/`find`/`read` 或另一显式动作可达；`asset` 只是把 image/page bytes 交给 caller 的一种额外操作，是否单独提供不影响必需的 image OCR 支持。

### 7.2 默认初读与“metadata+outline”选项的 ADR tension

已有 ADR-0001/0004 和 scope 明确要求首次 response 包含 metadata、outline（若有）和限长正文，并支持 section/位置 continuation 与关键词定位。这是 accepted boundary，不应被本报告静默改成纯 metadata-only。

研究上存在三种**待验证 mode**：

| Mode | 优点 | 风险/冲突 | 研究处理 |
|---|---|---|---|
| `metadata + outline + bounded lead` | 继承 accepted first-read；调用方马上得到少量原文 | lead 可能不是 query-relevant；长 outline 本身消耗 budget | 作为现行边界兼容候选，不宣称最终 default 参数 |
| `metadata + outline only` | navigation cost 最低；适合超长/高成本 OCR | 与“首次含限长正文”的 accepted wording 有张力；agent 可能多一次无效 call | 作为显式 mode/ablation，不替换 accepted boundary |
| bounded full/projection on short docs | 小文档调用少；便于 baseline | 长文档中间 context/noise、table/footnote separation | 作为短文档候选和 paired baseline |

推荐研究实验同时比较三者，但任何 default、outline cap、lead selection、自动 preview 是否触发，都必须在后续 contract review 和真实 corpus 后决定。

### 7.3 Sequential continuation 与 targeted continuation

- **Sequential：** 从当前 view 的 opaque cursor 继续读取同一 representation 的下一个 structure/page/block；适合 caller 想完整核对长 section。
- **Targeted：** 用 `find` 命中、section ID、page、table/figure/footnote locator、query constraint 直接取得目标 view；适合 research agent 先定位再扩展。
- 两者都不应自动重新 fetch URL；若 source snapshot 不存在、representation/config 不匹配或 source changed，返回显式 error/state。
- Caller 决定是否重复 query、读取 counterevidence、追随 reference、换 representation（例如从 native text 请求 OCR page image）；server 不把一次 `expand` 变成 Deep Research loop。

### 7.4 Hypothetical canonical sequence

以下是一个 **hypothetical**（非已实现、非已运行实验）的中性 fictitious document 交互序列，用来说明 `initial`/output continuation/`advance`/targeted read 四者如何配合，不重复完整 JSON——完整字段级示例见 [`../design/progressive-disclosure.md`](../design/progressive-disclosure.md) 第 6.1、6.6、6.7 节：

1. **`initial`**：caller 用 URL 发起首次读取，得到 `source_snapshot_id`、`representation_id`、outline、一段 bounded 的 verbatim 正文，以及相对于本次 selection 的 `output.status`（可能是 `truncated`，因为还有未展示的已发布正文）。
2. **output continuation（同一 identifiers）**：caller 用上一步返回的 `next_cursor`（绑定同一 `source_snapshot_id`/`representation_id`）继续读取同一 representation 里已经发布的后续正文；这一步不发起网络请求、不做新的渲染或 OCR，只读已有内容。
3. **`advance`（新 representation，parent 指向旧 representation）**：如果响应带了 `processing_continuation`（说明还有已 capture 但未处理的 pages，例如某些扫描页尚未 OCR），caller 显式调用 `advance` 对这些 pages 做有限处理；成功后得到一个新的 representation revision，其 `parent_representation_id` 指向第 1 步的旧 representation，旧的 cursor/citation 仍然只指向旧 representation，不会被静默改指到新 revision。
4. **在新 representation 上做 targeted read**：caller 用新 representation 的 `representation_id` 加上 section/table/footnote locator 做一次 `find`/`read`，取得原文命中、section path、table caption/header/unit、footnote，以及必要的 `ocr_not_searched`/`alignment_status` warning；不返回“该报告的结论是……”这类生成式摘要。

这四步只是概念序列，具体字段、错误分支和 JSON 形态以设计文档为准，本报告不重复维护第二份 schema 副本。

## 8. Alternatives comparison

| Strategy | 证据/强项 | 失败模式与 counterexample | 建议定位 |
|---|---|---|---|
| Bounded full Markdown | 调用少，短文档可读；是必要 baseline | 长报告中间 evidence 被淹没；多栏/表格/footnote 被重排；输出 limit 可能切开 code/table | short docs / explicit final review / baseline |
| Fixed chunks | 无 heading/OCR 时仍能工作，cursor 简单 | 切断 heading、table header、caption、footnote、definition；chunk boundary 不等于 semantic boundary | structure failure fallback |
| Structure-aware blocks | 可保留 section/page/table/figure lineage；支持 context closure | inferred heading/table/reading order 错误可能造成更强误导；parser complexity | 长文档 preferred candidate，必须 adversarial test |
| `preview -> find -> read/expand` | caller 先导航、再取得证据；可减少无关 observation；支持 query reformulation | outline/find 质量不足会迷路；调用次数增加；错误 negative result 会造成 false absence | 核心 differentiator hypothesis |
| Evidence window | quote-ready；把 qualifier 放在 target 附近 | closure 太小会漏 exception；closure 太大退化成 full read | research/policy/science candidate |
| Model-generated summary | 可能压缩 token，人工浏览快 | hallucination、unsupported abstraction、caveat loss、无法替代 source locator；与 no-LLM baseline 冲突 | v1 禁用；未来 explicit optional route |
| Large-context all-at-once | 逻辑简单，一次有全局输入 | cost/latency、middle-position use、agent 不知道下一步；大 context 不是安全网 | explicit final review, not default navigation |
| Automatic reference following | graph coverage 可能更快扩展 | 无限 crawl、scope drift、caller 失去 source selection、跨 source synthesis hidden | 禁止默认；caller explicit follow |

**关键 counterexample：** 如果材料是一张关键信息仅在 image chart 的短 PDF，metadata+outline 或 text-only `find` 可能比 bounded full image view 更差；若材料是带跨页 footnote 的长法规，bounded full Markdown 可能 token 充足但 caveat 错位。因而 Progressive Disclosure 不是“永远少读”，而是根据 representation 与 task 选择 target view，同时保留 raw/asset fallback。

## 9. Candidate extraction portfolio 与选择边界

### 9.1 推荐作为 proposal 的 route order

**第一步：复现已有 baseline，而不是重新挑选组件。** 已有 pinned `4c210d1` CPU functional smoke 已经跑通 Trafilatura（static HTML）、Playwright/Chromium（JS render/download fallback）、pypdfium2（native text PDF baseline）、RapidOCR + ONNX Runtime CPU（OCR）这条覆盖 HTML/JS/PDF/OCR/image 的路径。后续 prototype 的第一优先级是在同一/相近 corpus 上复现这条路径本身，作为唯一 baseline，而不是从候选清单里另挑一套组件：

1. Hardened HTTP/raw evidence manifest；
2. static HTML content view（Trafilatura，既有 baseline）；
3. native text PDF baseline（pypdfium2，既有 baseline）；
4. RapidOCR + ONNX Runtime CPU OCR（既有 baseline）；
5. Playwright rendered DOM/download fallback（既有 baseline）。

**第二步：只有在同一 corpus 上发现具体、可复现的 gap 时**，才逐一评估以下比较对象，且每次只针对暴露出 gap 的那类输入做对比，不做整体替换：

6. pypdf 或 PyMuPDF 与 pypdfium2 的 native PDF 抽取对比（仅当 pypdfium2 在某类 PDF 上有具体缺陷时）；
7. Tesseract 与 RapidOCR 的 OCR 对比（仅当 RapidOCR 在某类图像/语言上有具体缺陷时）；
8. Docling 作为 advanced layout/scanned PDF backend 的对比（仅当既有 PDF/OCR baseline 在复杂 layout/table 上有具体缺陷时）；
9. PaddleOCR 作为 targeted OCR/layout escalation 的对比（仅当 RapidOCR 在特定语言/场景上有具体缺陷时）；
10. Mozilla Readability 作为 static HTML 抽取的 comparison/fallback（仅当 Trafilatura 主内容抽取有具体缺陷时）。

这不是质量排名或 benchmark 排名，第 6–10 项也不是默认要采用的组件，而是“复现 baseline 之后，按需触发的同 corpus 对比”清单；不应无反证地用第二步的候选替换第一步已经跑通的 baseline，版本、license 和最终采用仍未锁定。

### 9.2 License、Windows 与 CPU 不能合并成一个 claim

- library 的 open-source license 不等于 models、weights、browser binaries、traineddata 和 transitive dependencies 都可按同一 terms 发布。
- “Windows support”不等于“native Windows CPU-only validated”；Docling 官方列 Windows，但 CPU-only example 主要 Linux-oriented；PaddleOCR FAQ 的 Windows adaptation 不等于 CPU matrix。[F28][F29][F32]
- PyMuPDF capability 强，但 AGPL/commercial gating 是 adoption input，不能在 license review 前成为默认依赖。[F26]
- Tesseract official 4-core wording 不是目标 machine benchmark；不能写成 throughput/RAM SLA。[F30]
- Playwright routing 不是 process/network isolation boundary；browser egress、credential isolation、DNS/redirect policy 需要独立控制和验证。[F22]

## 10. Proposed no-LLM baseline 与 optional summary 边界

### 10.1 v1 baseline

`web_read` 的 baseline 应是 deterministic structured extraction：

- capture raw response/download/page asset（受 retention policy 约束）；
- 生成 representation metadata、outline、block/page/table/figure/footnote inventory；
- deterministic `find`，返回 verbatim text、match type、representation scope、locator；
- `read/expand` 返回 typed blocks + structured Markdown projection；
- 自动 context closure 只按规则补齐 section ancestry、header/unit/caption/footnote/definition/exception；
- 返回 coverage、warnings、omissions、output truncation 和 opaque continuation；
- 不调用 LLM 进行 extraction、reordering、summary 或 source-quality judgement。

### 10.2 Future optional summary（不属于 accepted baseline）

若未来实验显示某些 task 有净收益，可以另加 caller-selected summary route，必须：

- 明确 `generated=true`；
- 标记 model/provider/prompt/config provenance（若项目之后允许）；
- 保留 source coverage、quotes/locators 和 caveats；
- 不替换 evidence window，不改变 old citation；
- 单独做 raw-evidence + optional-summary ablation；
- 不得因为加入 summary 而把 structured extraction 变成黑盒。

## 11. Stress tests 与 paired evaluation

### 11.1 Paired variants

在相同 frozen source snapshots、相同 extraction representation、相同 agent/model、相同 upstream/host adapter、相同总 byte/token budget 和相同 task set 下，至少比较：

A. bounded full Markdown；
B. fixed chunks；
C. structure-aware blocks；
D. `preview -> find -> read/expand`；
E. D + evidence-window/context-closure；
F. large-context all-at-once；
G. raw evidence + optional summary（单独 exploratory arm，不与 baseline 混合）。

不能让 Progressive variant 偷换成更好的 OCR、更多 source crawl、更多 reference follow 或额外 retry。应冻结 URL content/hash、rendered/parsed representation、OCR engine/config、extractor version 和 source snapshot。

### 11.2 “Useful evidence per token” 的可测定义

不要用 output token 越少越好。建议以固定 quality floor 比较：

- `material_claim_recall`：gold claim 中有多少能回到 source locator；
- `quote_fidelity`：quote 与 frozen representation 的 exact/normalized match 和 locator reattach；
- `caveat_preservation`：unit、sample/time range、exception、uncertainty、footnote、scope 是否保留；
- `structure_coverage`：命中相关 section/table/figure/footnote 的比例；
- `negative_result_honesty`：no-match 是否正确标为 searched representation 的 not found，而非 source absence；
- `tool_call_burden`：总 calls、重复 calls、无效 continuation；
- `evidence_bytes/tokens`：达到 quality floor 所需的 caller-visible evidence；
- `correction_quality`：收到 JS/OCR/partial/stale warning 后能否选择正确 next action；
- `coverage_honesty`：capture/extraction/output 三种 gap 是否被正确披露。

可报告 `useful evidence per token` 作为分析指标，但不能抹平质量 floor 失败；一份极短但漏掉 footnote 的输出不是更高效的 evidence。

### 11.3 Stress corpus 与 expected assertions

| Stress case | Expected assertion（proposal） |
|---|---|
| HTML comments 含 prompt-like text | content 只进入 untrusted data，不改变 policy/query/budget；raw lineage 保留 |
| `figure + img alt + figcaption` | alt、caption、OCR text 分开；caption 不重复写进 alt |
| malformed HTML、nested list、`pre/code` | raw 保留；code whitespace 不被 prose cleanup；warning 可追溯 |
| JS shell + delayed hydration + collapsed tab | static 与 rendered representation 分开；未加载 tab 不产生 global negative result |
| infinite scroll with duplicate items | budget 停止为 partial/truncated；去重不丢 lineage；不宣称 complete |
| browser download redirect | download bytes 做 MIME/magic-byte validation，再走 PDF/image route；redirect hops 可审计 |
| native single-column PDF | native text 优先，page/block locators 保留 |
| two-column PDF + header/footer | reading order inferred warning；furniture 可隐藏但不销毁；column/page locator 可回溯 |
| table with merged cells/notes | 不强转 GFM；HTML/IR + merged-cell uncertainty；caption/header/unit/notes 可 closure |
| scanned PDF with one OCR-failed page | per-page coverage partial；失败页不等于 no text；可继续请求 page/image/OCR variant |
| mixed PDF native/OCR overlap | native/OCR source_method 分开；overlap conflict 保留而非静默 merge |
| low-resolution Chinese/English OCR | boxes/confidence/engine/language 保留；低 confidence 不是 semantic verdict |
| standalone chart/formula image | raw asset + OCR regions；figure semantics `not_interpreted` unless supported |
| repeated exact phrase | multiple/ambiguous occurrences；不静默选第一处 |
| table value with footnote changing meaning | evidence window must include footnote or return omitted/unresolved context |
| source changes between calls | old cursor stays on old snapshot; new read creates new snapshot/representation |
| process restart / TTL expiry | distinct `snapshot_expired`/`cursor_expired`; no silent refetch continuation |
| SSRF localhost/private IP/IPv6/link-local/DNS change | reject before fetch and each redirect hop; log policy decision, no content leakage |
| retention forbids raw bytes | metadata/hash-only citation marked unavailable for raw rehydration; no fabricated quote |
| auth/paywall/captcha/anti-bot | explicit refused/auth_required; no bypass |

### 11.4 Ablations

至少做以下 ablation，数字和默认 mode 均待验证：

- 去掉 `outline`；
- 去掉 `find`，只保留 fixed chunks；
- 去掉 context closure 的 caption/header/footnote/prerequisite；
- 同总 budget 比较 bounded full、structure-aware 和 evidence window；
- 去掉 warnings/coverage，观察 agent 是否把 partial/empty 当作 negative fact；
- `resource/list` discovery-only 对比 direct URL tool entry；
- caller-controlled reference follow 对比 automatic follow（后者只作 failure baseline，不是 proposed behavior）；
- stable snapshot/representation/node/locator 字段对比 URL + local offset；
- sequential continuation 对比 targeted continuation；
- raw evidence baseline 对比 optional generated summary。

## 12. Security、access-control 与 retention

### 12.1 SSRF、redirect、DNS 与 browser egress

OWASP SSRF guidance 建议不要直接接受未经验证的完整 user URL，禁用自动 redirects，解析 A/AAAA 并拒绝 private/non-public ranges，考虑 DNS rebinding/pinning。[F34] RFC 9309 明确 robots rules 是 crawler policy、不是 access authorization。[F35]

Proposed controls：

- scheme allowlist 仅 `http`/`https`；拒绝 `file:`、`data:`、`javascript:`、`gopher:` 等；
- 每个 redirect hop 重新 canonicalize、resolve、validate A/AAAA；限制 hop/response/decompressed size；
- browser context 不继承 host cookies/tokens/credentials；service worker、third-party iframe、analytics、WebSocket、video、font 按 allowlist/policy 控制；
- Playwright route 只用于 observation/control，不当作 network isolation；需要 process/network boundary 时另行实现和验证；
- download 用 MIME + magic bytes + decompressed size 复核，不信 extension/filename；
- robots decision、auth/paywall/captcha/anti-bot refusal 单独记录，不绕过。

### 12.2 Raw retention 与 PII/版权边界

software license 不等于 source content 的保存或再分发许可。raw HTML/PDF/image/OCR 可能包含 PII、版权内容或 embedded token；日志默认只记 opaque IDs、status、digest、locator，不写完整正文。若 retention policy 只允许 metadata/hash，必须让 citation/retrieval status 反映 raw unavailable；不能重新抓取新页面冒充旧 snapshot，也不能伪造 quote。

### 12.3 Prompt injection boundary

页面正文、HTML comments、alt、OCR、PDF metadata、code blocks 和 search snippet 都进入 untrusted data channel。它们不能：

- 修改 system/tool description、route/backend、query privacy policy、credentials、SSRF allowlist、budget、retention 或 retry policy；
- 自动触发新的 URL fetch、reference follow、browser interaction 或 model summary；
- 让 caller 把 source content 当作 server instruction。

## 13. Phased prototype experiments（不删除 v1 required formats）

可以分阶段隔离故障，但每阶段都要保留 required format 的 coverage contract 和 honest failure，不得为了简化 MVP 静默移除 HTML/JS/PDF/OCR/image scope。

### Phase A：representation/citation core

实现或验证 raw snapshot、representation lineage、typed block/page/locator、bounded full/fixed baseline、output truncation 与 explicit continuation。用 text/static HTML 和小型 PDF 建立 invariant，不宣称完整 fidelity。

### Phase B：HTML/JS/image

加入 static HTML extraction、rendered DOM fallback、download handling、网页文字图片和 standalone image asset/OCR；测 capture vs extraction vs output state、image context closure、JS shell/infinite scroll partial semantics。

### Phase C：PDF/OCR

按 page classification 接入 native text、mixed/scanned OCR、table/footnote/reading-order warnings；优先复测已有 CPU smoke 路径，再比较候选 backend；完成 licenses/models/dependencies inventory。

### Phase D：agent paired evaluation

冻结 multi-format corpus 与 task set，比较 alternatives/ablations；以 fixed quality floor 衡量 evidence per token，而不是单一 latency/token；建立 target MCP host capability/conformance matrix。

### Phase E：policy/retention/restart hardening

验证 file-backed snapshot/artifact store、restart/TTL/eviction、multi-process locking、raw deletion、authorization re-check、SSRF/DNS/redirect/browser egress 和 prompt-injection corpus。

## 14. Acceptance gates（proposed, not approved）

只有在以下 gates 通过后，才建议把具体 mechanism 或默认 mode 提交为 contract review：

1. 每一种 required format（静态 HTML、JS 页面、text/mixed/scanned PDF、网页文字图片、独立 image URL）都有**可运行的 acquisition/extraction route**，并通过代表性的成功 fixture（范围内的中文与英文）和失败 fixture；`unsupported/partial/refused` 只能是针对单个输入的诚实结果，不能替代某种 required format 的实现。单个 fixture 通过不等于质量保证：release coverage 与真实 corpus fidelity 是另外的、更高的 gate；
2. capture、extraction coverage、output truncation 三类状态可由 agent 区分并选择恢复动作；
3. 同一 snapshot 上 continuation 不重新 fetch URL，representation/config/query 不匹配会失败；
4. old citation 在 extractor/OCR upgrade 后仍指向 old representation，rehydration 有明确状态；
5. table/header/unit/caption/footnote/exception 的 context closure 经过 adversarial corpus audit；
6. static/JS/PDF/OCR/image 的 locator 可回到其 declared representation，无法回到 raw 时显示 limitation；
7. fixed quality floor 下 Progressive route 在至少一组 material research tasks 上显示净收益，或被明确降级为 optional mode；
8. target host 能消费 structuredContent 或兼容 TextContent，不依赖 Resources picker；
9. license/CPU/Windows/model/runtime/retention/SSRF controls 完成独立 verification；
10. 页面 instruction 不改变 policy、fetch scope、credentials、budget、retention 或 synthesis。

这些 gate 是建议的 evidence bar，不是本轮声称已经通过的结果。

## 15. 未解决的高影响问题

1. `preview` 是否采用 accepted 的 metadata+outline+bounded lead，还是增加显式 metadata-only mode；默认 budget、lead selection 和 auto-render 条件未收敛。
2. `preview/find/read/expand` 是一个 `web_read(action=...)` 还是多个 tools；需要 target host smoke test 比较 tool discoverability、schema size、error handling。
3. structure-aware parser 的错误 reading order/table reconstruction 是否比 fixed chunks 更危险；需要人工标注和 quote/locator audit。
4. HTML/JS/PDF/OCR/image 的 representation scope 如何统一表达，尤其无 heading、collapsed content、OCR-only search 和 figure semantics。
5. snapshot 的 file-backed retention、TTL、restart recovery、eviction、locking、privacy/版权边界未验证。
6. cursor 是否允许缩小 budget、是否绑定完整 view config、如何在 partial failure 中恢复，尚无最终 policy。
7. target MCP host 是否保留 `structuredContent`、resource links、custom URI、embedded resources 和 tool execution error，不能从 spec 推出。
8. Docling、PaddleOCR、PyMuPDF、Tesseract traineddata、browser binary 与 transitive dependencies 的 pinned versions/license/Windows CPU matrix 未完成。
9. optional summary 是否带来净收益未知；summary 可能减少首读成本，也可能漏 caveat 或生成 unsupported claim。
10. 没有直接的 research-agent A/B 证明 `preview -> find -> evidence window` 优于 bounded full/fixed chunks/all-at-once；这是最重要的未解决问题。

## 16. Primary source ledger

访问日期为 2026-09-10。`Full` 表示本轮取得相关正文/规范章节；`Partial`/`abstract-only`/`dynamic` 表示仅使用可见的有限内容。以下 URLs 是 owning primary sources；内部 research memo 只用于工作范围和项目背景，不替代这些来源。

| ID | Owning source / publication | URL | Supporting section / short quote | Access limitation |
|---|---|---|---|---|
| S1 | Jakob Nielsen, Nielsen Norman Group, `Progressive Disclosure` (2006) | https://www.nngroup.com/articles/progressive-disclosure/ | 定义 “Initially, show users only a few of the most important options” 与按需提供 specialized options；全文可读 | Practitioner guidance，不是 research-agent experiment |
| S2 | John M. Carroll & Caroline Carrithers, `Training Wheels in a User Interface` (1984) | https://api.crossref.org/works/10.1145/358198.358218 | Crossref abstract/metadata：training interface 与学习、错误和 comprehension 的摘要描述 | 仅摘要/metadata，未读完整 paper |
| S3 | Shunyu Yao et al., `ReAct: Synergizing Reasoning and Acting in Language Models` (2022) | https://arxiv.org/html/2210.03629 | §2 Thought/Action/Observation；Appendix C query revision 与 `NOT ENOUGH INFO`；Tables 3–4 task results | 任务、model、prompt 与本项目不同 |
| S4 | John Yang et al., `SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering` (2024) | https://arxiv.org/html/2405.15793v3 | §2 “Environment feedback should be informative but concise”；§5.1/Table 3 observation/search/window ablations | Code repair domain；数字不能变成 web_read default |
| S5 | Jiarui Lu et al., `ToolSandbox: A Stateful, Conversational, Interactive Evaluation Benchmark for LLM Tool Use` (2025) | https://arxiv.org/html/2408.04682 | §1–3/Table 4 stateful trajectories、milestones/minefields、scenario/tool/domain figures | HTML 后段/附录不完整；非长文档 disclosure benchmark |
| S6 | Nelson F. Liu et al., `Lost in the Middle: How Language Models Use Long Contexts` (TACL 2024) | https://arxiv.org/html/2307.03172 | §1–4、Figures 1/5/7/9 的 U-shaped position effect 与 extended context caveat | 位置/任务实验，不是 web_read interface A/B |
| S7 | Model Context Protocol maintainers, MCP Specification 2026-07-28 Tools | https://modelcontextprotocol.io/specification/2026-07-28/server/tools.md | Tool Result、Structured Content、Output Schema、Error Handling、Stateful Tools guidance | Protocol primitives 不定义本项目 preview/read semantics；stateful section 是 non-normative guidance |
| S8 | Model Context Protocol maintainers, MCP Specification 2026-07-28 Resources | https://modelcontextprotocol.io/specification/2026-07-28/server/resources.md | Resources application-driven、`resources/read` text/blob、resource links/embedded resources | Host picker/auto-injection 未验证 |
| S9 | Model Context Protocol maintainers, MCP Specification 2026-07-28 Pagination | https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/pagination.md | cursor opaque、server controls page size、standard list operations | 自定义 `tools/call` continuation 需项目定义 |
| S10 | W3C, `Web Annotation Data Model` | https://www.w3.org/TR/annotation-model/ | `TextQuoteSelector` exact/prefix/suffix；`TextPositionSelector` zero-based inclusive/exclusive；State before selector | Selector 是 locator primitive，不是 source identity/authenticity proof |
| S11 | IETF, RFC 3986 §3.5 | https://www.rfc-editor.org/rfc/rfc3986#section-3.5 | fragment semantics 由 representation/media type 定义；fragment 在 dereference 前分离 | fragment 不等于 immutable snapshot |
| S12 | IETF, RFC 3629 | https://www.rfc-editor.org/rfc/rfc3629 | UTF-8 one-octet unit 与 1–4 octets；byte/code-point coordinate 区别 | 不提供项目 offset contract |
| S13 | Unicode Consortium, UAX #29; fixed Unicode 17.0 Revision 47 page | https://www.unicode.org/reports/tr29/ · https://www.unicode.org/reports/tr29/tr29-47.html | grapheme cluster 近似 user-perceived character；canonical equivalence 与 storage offsets | latest 与 fixed version 必须区分；不是所有 backend 的唯一 offset |
| F18 | Trafilatura maintainers, official repository README | https://github.com/adbar/trafilatura | main text/metadata/comments；optional links/images/tables；outputs；Apache-2.0 | Dynamic repository main；exact release/Windows runtime 未 pin |
| F19 | Mozilla/Arc90, Readability README | https://github.com/mozilla/readability/blob/main/README.md | parse fields；mutates DOM；false positives/negatives；not sanitization；Apache-2.0 | Dynamic repository main；未运行 parser |
| F20 | CommonMark 0.31.2 and GitHub Flavored Markdown | https://spec.commonmark.org/0.31.2/ · https://github.github.com/gfm/ | CommonMark tables/footnotes as extensions；GFM table cell inline-only、no block-level elements | 不提供 source lineage/layout model；task-list section access limited |
| F21 | Microsoft Playwright Python introduction | https://playwright.dev/python/docs/intro | sync/async、Chromium/WebKit/Firefox、Windows/macOS/Linux | Package/browser revision 未 pin；未做 target clean-machine run |
| F22 | Microsoft Playwright network docs | https://playwright.dev/docs/network | page/context route；service-worker routing caveat | route 不等于 network isolation；未做 egress validation |
| F23 | Microsoft Playwright downloads docs | https://playwright.dev/docs/downloads | download event、URL、suggested filename、stream、saveAs、context cleanup | 未验证下载文件 semantics |
| F24 | pypdf official Extract Text docs | https://pypdf.readthedocs.io/en/stable/user/extract-text.html | PDF semantic layer、table/reading-order limits、scanned PDF needs OCR、layout/visitor approximation | exact package version/quality 未测 |
| F25 | py-pdf/pypdf LICENSE | https://github.com/py-pdf/pypdf/blob/main/LICENSE | BSD-3-Clause | dependency inventory 仍需完成 |
| F26 | PyMuPDF Appendix 1 | https://pymupdf.readthedocs.io/en/latest/app1.html | TextPage hierarchy、blocks/words/DICT/RAWDICT、creator order 与 `sort=True` limitation | no corpus fidelity benchmark |
| F27 | PyMuPDF About/licensing | https://pymupdf.readthedocs.io/en/latest/about.html | AGPL and commercial license agreements；OCR/table/render capability | legal fit 未决定；不能视为 adoption approval |
| F28 | Docling overview/DoclingDocument | https://docling-project.github.io/docling/ · https://docling-project.github.io/docling/concepts/docling_document/ | structured document model、body/furniture、reading order、tables/pictures/formulas/provenance | docs capability claim；未测目标 corpus |
| F29 | Docling installation | https://docling-project.github.io/docling/getting_started/installation/ | Windows/macOS/Linux support；CPU-only example mainly Linux-oriented | native Windows CPU/model/cache 仍 open |
| F30 | Tesseract repository and OS docs | https://github.com/tesseract-ocr/tesseract · https://tesseract-ocr.github.io/tessdoc/supported-operating-systems.html | Apache-2.0、Windows 10/11、100+ languages、hOCR/TSV/ALTO/PAGE/PDF | no target-machine performance matrix |
| F31 | Tesseract CLI and OpenMP docs | https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html · https://tesseract-ocr.github.io/tessdoc/Compiling-%E2%80%93-GitInstallation.html | bbox/confidence output；default 4-core wording；bulk guidance | documentation fact，不是 benchmark；TSV `-1` semantics limited |
| F32 | PaddleOCR FAQ and LICENSE | https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/FAQ.en.md · https://github.com/PaddlePaddle/PaddleOCR/blob/main/LICENSE | Windows/macOS adaptation；repository Apache-2.0 | no complete CPU matrix；models/weights/runtime licenses open |
| F33 | WHATWG HTML images | https://html.spec.whatwg.org/dev/images.html | `alt` textual replacement 与 `figcaption` supplementary caption 的区别 | 不保证 source page 正确使用 semantics |
| F34 | OWASP SSRF Prevention Cheat Sheet | https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html | 不直接接受未经验证完整 URL；disable redirects；A/AAAA/private-range validation；DNS rebinding/pinning guidance | deployment-specific controls 未验证 |
| F35 | IETF RFC 9309 | https://www.rfc-editor.org/rfc/rfc9309.html | robots rules “not a form of access authorization” 与 redirect/error/cache behavior | robots 不是 SSRF/auth/retention control |

## 17. Final position

Progressive Disclosure 值得作为本项目的主要 differentiator proposal，但目前最诚实的表述是：它是一套**caller-controlled、snapshot-consistent、representation-aware、evidence-preserving 的 bounded navigation hypothesis**，不是已证明的 token optimization，也不是把全文换成 summary。研究支持把 `preview/find/read/expand`、context closure、locators、coverage/failure disclosure、snapshot lineage 和 optional Resources 设计成可测对象；不支持现在锁定默认 mode、budget、组件版本、MCP host behavior、性能或质量数字。

下一步应在已有 CPU functional-smoke baseline 上，冻结跨格式 source corpus，分别测 bounded full、fixed chunks、structure-aware、`preview -> find -> read/expand` 和 evidence-window variants；所有 required formats 继续纳入 scope，失败以 coverage/refusal/unsupported/partial 诚实呈现。只有当 paired evaluation 在固定 quality bar 下证明 material claim recall、quote fidelity 和 caveat preservation 的净收益，才应把 Progressive route 从 proposed differentiator 变成 accepted default。
