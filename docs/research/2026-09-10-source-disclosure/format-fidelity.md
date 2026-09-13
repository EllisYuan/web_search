# HTML、JS、PDF 与 OCR 的内容保真研究备忘录

> **研究日期：2026-09-10**  
> **状态：研究建议，未实现、未 benchmark、未构成已批准选型**  
> **范围：** Windows 本机、CPU-only、免费/开源、自建 pipeline；公开 HTML、Markdown、纯文本、JavaScript-rendered pages、born-digital PDF、multi-column PDF、scanned/mixed PDF、网页文字图片和 standalone image URL。  
> **重要边界：** 不绕过 auth、paywall、MFA、robots policy 或 anti-bot/access control；不把 OCR confidence 当成语义正确性；不把 Markdown 当成原始证据。

## 1. 摘要与建议

### 1.1 核心判断

**建议采用分层 portfolio，而不是一个 universal converter。** 这是基于一手文档支持的能力边界和工程解释，不是实测结论：

1. **HTTP-first**：先获取原始 response bytes，记录 redirect、headers、content-type、hash 和 policy decision；对静态 HTML、Markdown、纯文本和公开图片优先走此路径。
2. **Static HTML extraction**：以 Trafilatura 作为候选主路径，以 Mozilla Readability 作为 article-like 页面比较/回退路径；两者都不能替代原始 DOM 和资源清单。
3. **Browser fallback**：只有检测到 JS shell、hydration、普通交互后才出现的公开内容、分页/`load more` 或 browser-triggered download 时才启用 Playwright。它可以执行 JavaScript，但不证明页面的无限滚动、个性化分支或任意 side effect 已经完整覆盖。
4. **Native PDF first**：先检测 page-level text layer。简单 born-digital PDF 可用 pypdf；若需要 blocks、words、coordinates、image extraction、table detection，PyMuPDF 是较强候选，但其 AGPL/commercial licensing 必须先解决。
5. **Layout-heavy/scanned PDF**：Docling 是候选 advanced backend，可提供 layout、reading order、tables、formulas、pictures、OCR 和结构化 document model；官方文档明确 Windows support，但 CPU-only 说明主要明确覆盖 Linux，native Windows CPU 仍需验证。
6. **OCR**：Tesseract 作为候选默认 local CPU OCR；保留 TSV/hOCR 的 boxes 与 confidence，而不是只存 plain text。PaddleOCR 可作为可选 escalation，但当前官方核对明确了 Windows adaptation，未在同一资料中独立证明所有 CPU 路径和性能。
7. **Canonical IR before Markdown**：先保留 block/table/figure/formula/footnote/reference、coordinates、lineage、confidence 和 warnings，再渲染为 GFM/HTML hybrid Markdown。Markdown 是 presentation view，不是唯一 source of truth。

### 1.2 适用于本项目的结论

这份 memo 支持下列**拟议**方向：

- `web_search` 只发现 URL；`web_read` 对指定 URL/file 做 acquisition、extraction 和 progressive disclosure，不生成最终综合答案。这与已接受的 v1 boundary 一致。
- `web_read` 的返回应能区分：policy refused、unsupported format、encrypted/unreadable、acquisition failed、parse failed、OCR partial、output truncated、complete-as-fetched。`complete` 只表示在当前 representation 和 budget 下没有继续可读的输出，不表示恢复了原始语义。
- 每个 page/block 应携带 coverage 和 lineage；对超长正文返回 bounded output 与 opaque `next_cursor`，而不是把截断伪装成完整成功。
- 对 PDF 与 OCR，应同时保留 raw representation 和 extracted representation；仅保存 Markdown 会失去复核和重抽取能力。
- 浏览器、PDF parser、OCR 应在 worker/process 和资源 budget 上隔离；页面内容、HTML comments、`alt`、OCR text 和 PDF embedded text 都是不可信 data，不得改变 tool policy。

### 1.3 尚未验证的高影响问题

- 在目标 Windows 机器上，Docling 的 native Windows CPU 依赖、模型下载、RAM、实际可用速度和长 PDF 稳定性没有验证。
- PaddleOCR 的 basic Windows/CPU path 与 high-performance path 不能仅由当前官方 FAQ 推出；需要 clean-machine smoke test 和 license inventory。
- PyMuPDF 是否符合最终 distribution model 的 AGPL/commercial licensing 尚未决定。
- 任一 extractor 的阅读顺序、table reconstruction、OCR 质量和 citations locator 尚无本项目 benchmark；下文只给测试设计，不声称结果。
- 常见网页的 JS shell / infinite scroll 检测阈值、page/byte/time budgets、raw retention TTL 和 `next_cursor` schema 需要实测收敛。

## 2. 事实、解释、拟议设计的分层

本 memo 使用以下标签：

- **Fact**：可由一手官方 docs/source/spec 直接支持的事实；引用 source ledger。
- **Interpretation**：对事实的工程含义，不是 library 保证。
- **Proposed**：为本项目提出的机制、schema、threshold 或 route；未实现、未验证、不是用户已批准的 numeric contract。
- **Open validation**：必须通过 clean-machine、adversarial corpus 或真实 MCP integration 验证的项目。

特别注意：`Windows support`、`CPU inference available`、`GPU optional`、`performance acceptable` 是四个不同 claim；不能从其中一个推出另外三个。

## 3. 一手资料支持的事实

### 3.1 Static HTML、Markdown 和纯文本

**Fact — Trafilatura。** Trafilatura 官方 repository 将其描述为把 raw HTML 转成 structured content 的 Python package/CLI，重点是 main text 并过滤 headers、footers 和 boilerplate；可选包含 comments、links、images、tables，输出 TXT、Markdown、CSV、JSON、HTML、XML、XML-TEI；当前 repository 的 license 是 Apache-2.0，同时注明早于 1.8.0 的版本曾为 GPLv3+。[Trafilatura README](https://github.com/adbar/trafilatura)

**Interpretation。** Trafilatura 适合普通 article/static HTML 的 first-pass，但“main content”本身就是一种有损目标：侧栏、导航、related content、脚注和页面级 figure 可能被过滤。若产品承诺 content fidelity，就必须同时保留 raw HTML/DOM-derived representation，而不能只保留 Trafilatura 输出。

**Fact — Mozilla Readability。** Readability 的 API 接受 DOM `document`，`parse()` 返回 `title`、`content`、`textContent`、`length`、`excerpt`、`byline`、`dir`、`siteName`、`lang`、`publishedTime` 等；它会修改传入 DOM，调用方若要保留原 DOM 应 clone。`isProbablyReaderable()` 是近似预判，官方明确提示会产生 false positives 和 false negatives。Readability 不负责 sanitization，对 untrusted HTML 推荐 DOMPurify 和 CSP；license 是 Apache-2.0。[Readability README](https://github.com/mozilla/readability/blob/main/README.md)

**Interpretation。** Readability 适合作为 article-like 页面第二意见或 fallback，不是 lossless page parser，也不是 security sanitizer。用它前应保存未修改 DOM 或 raw bytes，并把 `content` 视为一个 extraction view。

**Fact — Markdown dialect。** CommonMark 定义核心 Markdown parsing syntax，但官方说明 tables、footnotes 等属于 implementations 的 extensions，不是 core；GFM 增加 tables、task-list、strikethrough、autolinks 和 raw-HTML restrictions，但 GFM table cell 只允许 inline content，不能表达任意 nested block structure。[CommonMark spec](https://spec.commonmark.org/0.31.2/) · [GFM spec](https://github.github.com/gfm/)

**Interpretation。** GFM 可作为 practical output profile，但不能承诺保留 PDF 的 merged cells、row/column spans、复杂 table notes、footnote relationships、formula semantics 或 arbitrary layout。复杂 table 应保留 HTML 或 sidecar structured object；formula 应保留原始 asset/文本和 warning，而不是未经依据地改写成 LaTeX。

### 3.2 JavaScript-rendered pages 与 browser acquisition

**Fact — Playwright Python。** 官方 Python docs 说明 Playwright 提供 sync/async APIs，支持 Chromium、Firefox、WebKit，以及 Windows、macOS、Linux 等平台；它可以自动化现代 web applications。[Playwright Python introduction](https://playwright.dev/python/docs/intro)

**Fact — network control。** Playwright 的 `page.route()` 可拦截单 page 请求，`browserContext.route()` 覆盖整个 context（包括 popups/opened links）；可以继续、取消、修改或 mock 请求，并观察 responses。官方 network docs 警告 service worker 处理的请求可能不出现在通常 routing/network events 中，必要时应 block service workers 以恢复可见性。[Playwright network](https://playwright.dev/docs/network)

**Fact — downloads。** 页面触发下载会产生 `download` event；`Download` 可提供 URL、suggested filename、payload stream，使用 `saveAs(path)` 保存。默认下载是临时的，creating browser context 关闭时会被删除，除非明确保存。[Playwright downloads](https://playwright.dev/docs/downloads)

**Interpretation。** Browser acquisition 可以让页面脚本运行并抓取公开 rendered DOM、XHR/fetch responses 和 downloads，但不能把“脚本执行成功”解释成“语义内容完整”。DOM order 可能仍是应用实现顺序，不一定是视觉阅读顺序；network responses 可能是 pagination fragments，不能自动合并成完整 page。

**Proposed — browser escalation。** 先 static HTTP fetch，再按可观测信号升级 browser：

- response body 很小但预期页面类型应有正文；
- visible text 明显少于 DOM/script shell；
- static extraction 无 headings/paragraphs 但 DOM 有 hydration markers；
- content 需普通公开 `load more`/pagination interaction；
- 公开页面触发 PDF/CSV/Office download；
- caller 明确要求 rendered view。

**Proposed — infinite scroll honesty。** 对无限滚动只记录实际滚动和取得的 items。达到 scroll/time/bytes/page budget 后返回 `partial` 或 `truncated`，说明“在 budget 内取得的 rendered content”，不返回 `complete`。任意无限 scroll、个性化内容、时间触发内容和需要登录的 continuation 都应标记 coverage gap，不尝试绕过 auth/paywall/anti-bot。

### 3.3 PDF：text、multi-column、mixed 和 scanned

**Fact — pypdf limitations。** pypdf 官方 extraction guide 说明 PDF 主要面向视觉呈现而不是 semantic meaning；通常没有 paragraph、header、footer、page number、table、caption 的语义标记。文本元素可被独立定位，reading order 可能有歧义；tables 常常只是绝对定位的文字，不能可靠恢复 rows/columns；scanned PDF 可能只有 images，pypdf 不能 OCR。[pypdf Extract Text](https://pypdf.readthedocs.io/en/stable/user/extract-text.html)

官方同时说明 `extract_text(extraction_mode="layout")` 尝试产生接近页面视觉布局的 fixed-width output，可通过 orientation/filter/visitor callbacks 观察或筛选 fragments；这仍是 approximation，不是 semantic guarantee。[pypdf Extract Text](https://pypdf.readthedocs.io/en/stable/user/extract-text.html)

**Fact — pypdf license。** 官方 LICENSE 是 BSD-3-Clause。[pypdf LICENSE](https://github.com/py-pdf/pypdf/blob/main/LICENSE)

**Interpretation。** pypdf 是 license 简洁、适合 lightweight native text/metadata 和 diagnostic path 的候选，但不应承担本项目全部 PDF fidelity。born-digital PDF 应优先 native text，避免对已存在的 glyph/encoding/font information 再做 OCR；multi-column/table/footnote 需要 geometry-aware route 和 warning。

**Fact — PyMuPDF structured extraction。** PyMuPDF 的官方文档描述 `TextPage` 层级为 pages → blocks → lines → spans → characters，并支持 `blocks`（bbox/text/type）、`words`（bbox/text/block/line/word indices）、`DICT/JSON`（结构、font、bbox、image bytes/base64）和 `RAWDICT/RAWJSON`（per-character text/origin/bbox）。默认 extraction order 通常遵循 PDF creator order，`sort=True` 可近似按 top-left 到 bottom-right 重排；该排序不是通用 semantic reading-order proof。[PyMuPDF Appendix 1](https://pymupdf.readthedocs.io/en/latest/app1.html)

PyMuPDF 官方文档还提供 embedded image extraction、page rendering、`get_textpage_ocr()` 和 `page.find_tables()` 等能力示例。[PyMuPDF about](https://pymupdf.readthedocs.io/en/latest/about.html) · [PyMuPDF functions](https://pymupdf.readthedocs.io/en/latest/functions.html)

**Fact — PyMuPDF license。** PyMuPDF/MuPDF 以 AGPL 和 commercial license 两种方式提供；官方建议若 AGPL 条件不适用，联系 Artifex 获取 commercial license。[PyMuPDF about/licensing](https://pymupdf.readthedocs.io/en/latest/about.html)

**Interpretation。** PyMuPDF 是较强的 native PDF/layout candidate，但其 license 是架构输入，不是事后 legal cleanup。若 distribution model 不能接受 AGPL 或 commercial license，不能把它作为默认依赖；可改用 pypdf 加 Docling/其他经过 license review 的 route。

**Fact — Docling representation。** Docling 官方文档描述 `DoclingDocument` 为 Pydantic-based structured model，能够区分 text、tables、pictures、key-value items；text 可包含 paragraphs、section headings、equations/formulas；`body` 和 `furniture` 分开组织 main body 与 headers/footers 等 document furniture；reading order 由 body tree 和 child sequence 表达；items 可保留 provenance/layout/bounding boxes。官方项目页列出 PDF、HTML、images 等输入以及 layout、reading order、table structure、formula extraction、OCR 和 Markdown/HTML/JSON/DocTags/DocLang 输出。[DoclingDocument](https://docling-project.github.io/docling/concepts/docling_document/) · [Docling overview](https://docling-project.github.io/docling/)

**Fact — Docling Windows/CPU nuance。** 官方 installation docs 写明 Docling 支持 Windows、macOS、Linux，x86_64 和 arm64；同页的 CPU-only setup 说明明确以 Linux 为例，OCR choices 包括 Tesseract bindings/CLI、RapidOCR/ONNX Runtime、EasyOCR 等，部分 OCR/模型路径有明确的 Linux/CUDA constraints。[Docling installation](https://docling-project.github.io/docling/getting_started/installation/)

**Interpretation。** Docling 是 advanced document path 的候选，不应把 “Windows supported” 等同于 “native Windows CPU pipeline 已经验证”。在本项目 clean Windows machine 上必须分别验证 import、model acquisition、offline cache、CPU-only run、scanned PDF、table/formula outputs 和 memory behavior。

**Proposed — PDF classification。** 每页独立判定：`native_text`、`ocr_text_layer`、`image_only`、`mixed`、`uncertain`。classification 输入可包括 native text count、image-block coverage、font presence、text entropy、page dimensions 和 parser warnings；这些字段/阈值均是 proposed，尚未 benchmark。

**Proposed — mixed PDF merge。** native blocks 和 OCR blocks 不应简单拼接。以 page+bbox overlap、source method 和 confidence 建立 merge decision：同区域已有可靠 native text 时保留 native；image-only region 才追加 OCR；冲突时保留两份 representation 并标记 `overlap_conflict`，不要静默选择一个。

### 3.4 OCR、网页文字图片与 standalone image URL

**Fact — Tesseract。** Tesseract 官方 repository 采用 Apache-2.0；输入示例包括 PNG/JPEG/TIFF；支持 100+ languages，并可输出 plain text、hOCR、PDF、TSV、ALTO、PAGE 等。官方 supported operating systems page 列出 Windows 10/11；编译文档说明默认构建的一次 OCR 会使用 4 个 CPU cores，并建议 bulk processing 时关闭 OpenMP、运行多个独立的单线程实例；这不是本项目目标机器上的性能 benchmark。[Tesseract repository](https://github.com/tesseract-ocr/tesseract) · [supported operating systems](https://tesseract-ocr.github.io/tessdoc/supported-operating-systems.html) · [compiling/OpenMP](https://tesseract-ocr.github.io/tessdoc/Compiling-%E2%80%93-GitInstallation.html)

**Fact — OCR geometry/confidence。** Tesseract 的 hOCR 输出有 page/block/paragraph/line/word hierarchy、word `bbox` 和 `x_wconf`；TSV 输出包含 page/block/paragraph/line/word hierarchy、`left/top/width/height` 和 `conf`。官方示例中非 word-level 的结构行出现 `-1`，但该页面没有给出可推广到所有版本/输出的通用定义；因此本项目只能把它当作“该记录没有 word-level confidence” 的可观察值，不能据此推断更强语义。word-level confidence 仍只是 numeric recognition signal。[Tesseract command-line usage](https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html)

**Interpretation。** OCR confidence 只反映 engine 对 recognition 的内部信号，不是 semantic truth、table correctness、reading order 或 figure meaning。必须保存 OCR text 与 source image/region 的关系，并给下游 agent 显示 `ocr_approximate`、engine/language/version、bbox 和 confidence，而不是把结果伪装成 native text。

**Fact — PaddleOCR。** PaddleOCR 官方 FAQ 说明已适配 Windows 和 macOS；基础使用说明中明确 Windows 的 model download/setup 注意事项。当前核对的官方 FAQ 没有为 CPU inference 给出独立性能或完整 hardware matrix；高性能部署页面不应被基本 Windows compatibility 直接替代。[PaddleOCR FAQ](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/FAQ.en.md) · [PaddleOCR repository](https://github.com/PaddlePaddle/PaddleOCR)

**Fact — PaddleOCR license。** repository LICENSE 是 Apache-2.0；模型、weights、runtime dependencies 的具体 license 仍需单独 inventory，不从 repository license 自动推出。[PaddleOCR LICENSE](https://github.com/PaddlePaddle/PaddleOCR/blob/main/LICENSE)

**Interpretation。** PaddleOCR 可以作为候选 escalation，尤其是复杂 text detection/layout/table workload，但在 Windows CPU-only v1 中不应无验证地替换 Tesseract；先做 targeted smoke test，不承诺性能或质量。

**Proposed — standalone image route。** 对 `image/*` URL 或 HTML `<img>`：

1. 保存原始 image bytes、MIME、dimensions、hash 和 final URL；
2. 对 SVG/animated/very large image 分开分类，禁止只看 extension；
3. 抽取 OCR text/boxes/confidence（若允许且在 budget 内）；
4. 关联 page DOM context、`alt`、`figure`、`figcaption`、nearby heading/paragraph；
5. 输出 image asset + OCR blocks + warning，不能只输出 OCR text。

**Fact — HTML image semantics。** WHATWG HTML Standard 区分 `img alt` 与 `figure/figcaption`：`alt` 应提供 image 的 textual replacement/substantive information，caption 是补充性的 visible caption/title，caption 不应复制进 `alt`。缺失 `alt` 的例外很窄。[WHATWG embedded content/images](https://html.spec.whatwg.org/dev/images.html)

**Interpretation。** 只有 OCR 不能恢复 chart axes 的关系、图例颜色语义、箭头/拓扑、公式图形和视觉 emphasis。figure 应保留原 image 和 caption/alt lineage；若无法解释图形，输出“figure retained”比猜测图义更保真。

## 4. Coverage contract：什么是完整、部分和失败

### 4.1 Proposed status vocabulary

下列字段是**拟议 schema，不是已实现 contract**：

```json
{
  "coverage": "complete_as_fetched",
  "content_status": "ok",
  "representation": "native_pdf_text",
  "truncated": false,
  "next_cursor": null,
  "warnings": [],
  "omissions": []
}
```

`coverage` 建议使用：

- `complete_as_fetched`：当前 representation 已读取完，未触发 output/page/byte budget；不表示语义无误。
- `partial`：只覆盖可取得的一部分，例如多 query batch 的部分 URL、部分 scroll、部分 pages 或部分 OCR regions。
- `truncated`：主要正文仍可继续读取，但本次因 hard output limit 停止；必须返回 `next_cursor` 或明确不可继续。
- `unavailable`：URL/file 当前无法取得或正文未公开，不声称内容缺失于源站。
- `refused`：policy 明确拒绝，如 SSRF、robots policy、unsupported scheme、auth/paywall/no-bypass policy。
- `unsupported`：识别为格式/encoding/encryption/feature，但当前 portfolio 没有可用 route。
- `failed`：取得或解析发生未归类错误；保留 phase、exception class、request id 和已取得 partial evidence。

`content_status` 建议独立表示：

- `ok`、`empty`、`parse_failed`、`ocr_low_signal`、`encrypted`、`auth_required`、`size_limit`、`time_limit`、`network_error`、`policy_denied`。

**关键区分：** `truncated` 是 server output limit；`partial` 是 coverage 状态；`failed` 是执行失败；`refused` 是 policy decision。不能把它们合并成空正文或 generic error。

### 4.2 Block-level coverage

顶层 `complete_as_fetched` 不应覆盖所有 block。每个 block 应有：

```json
{
  "block_id": "b-0007",
  "kind": "table",
  "coverage": "partial",
  "source_method": "pdf_geometry_inference",
  "confidence": null,
  "warnings": ["merged_cells_uncertain"],
  "lineage": ["page-004:box-12", "raw:sha256:..."]
}
```

拟议 `kind`：`heading`、`paragraph`、`list`、`quote`、`code`、`table`、`figure`、`caption`、`formula`、`footnote_ref`、`footnote_body`、`reference`、`header`、`footer`、`page_break`、`unknown`。

### 4.3 Output truncation and continuation

`web_read` 首次 response 应包含 metadata、coverage summary、outline（如果能得到）和 bounded preview；后续以 `section_hint` 或 opaque `next_cursor` 继续。cursor 必须绑定 source representation、query constraints、retrieved snapshot/hash 和 extraction config；若原文已变化，续读应返回 `stale_cursor` 或新 snapshot，而不是静默把旧 offset 指向新内容。

## 5. Proposed adaptive portfolio

### 5.1 Acquisition layer

**Proposed route selection：**

| 输入 | 首选 route | 升级条件 | 不应承诺 |
|---|---|---|---|
| `text/plain` | 保存 raw bytes，按 charset 解码 | decode error 时保留 bytes + replacement warning | 不重新排版原文 |
| Markdown | 保存 raw source，解析为 AST/blocks | parser 不支持 extension 时保留 raw + warning | 不假设 CommonMark 支持 tables/footnotes |
| Static HTML | raw HTML → DOM → Trafilatura/Readability views | content sparse、JS shell、explicit rendered request | main-content view 等于完整页面 |
| JS-rendered HTML | Playwright context → DOM/network/downloads | interaction/page/bytes/time budget | 任意 infinite scroll 完整 |
| `application/pdf` | page classification → pypdf/PyMuPDF native | low text/image-only/complex layout → OCR/Docling | native text reading order 完美 |
| scanned/mixed PDF | native per page + selective OCR | low confidence/overlap conflict | OCR confidence 是 truth |
| standalone image | raw asset + OCR boxes + context | difficult text/layout → optional PaddleOCR | OCR 恢复 figure semantics |

### 5.2 HTML representation

保存三种 view（均是 proposed）：

1. `raw_response`：实际 HTTP bytes、response metadata、redirect chain。
2. `dom_snapshot`：静态 parser 或 browser 生成的 normalized DOM；记录是否 rendered。
3. `content_view`：Trafilatura/Readability 输出和 custom block map。

不要在 browser 中默认加载第三方 analytics、video、font、popup、WebSocket；必要 subresources 使用 allowlist。普通公开 UI interaction 可在 caller policy 允许时执行，但遇到 login/paywall/verification/anti-bot 必须返回 refusal，不进行 bypass。

### 5.3 PDF representation

保存：

- original PDF bytes 或明确记录 retention restriction；
- page count、media boxes、encryption/enabled flags；
- native text blocks/words/spans；
- rendered page images（仅在 OCR/diagnostic 必需且 policy 允许时）；
- OCR hOCR/TSV；
- table model output；
- page/block `bbox` 和 source method。

Born-digital native text 与 OCR output 需要不同 `source_method`，否则下游无法评估其可复核性。

### 5.4 Markdown serializer

**Proposed output profile：**

- headings、paragraphs、lists、quotes、code 用 GFM-compatible Markdown；
- simple rectangular table 可用 GFM table；
- merged cells、row/col spans、nested blocks、table notes 使用 raw HTML `<table>` 或 sidecar JSON；
- image 用 asset path，`alt` 与 `<figcaption>` 分开；
- formula 保留 original text/image/uncertainty，不未经 evidence 改写；
- footnotes 以 sidecar relation 和 renderer-specific extension 表示；
- references 保持原 section/order，不自动 deduplicate 或 claim merge；
- page breaks/locators 用 comments/attributes/sidecar manifest，不污染正文语义。

## 6. Lineage、coverage 和 progressive disclosure

### 6.1 Proposed source/block schema

以下是**设计草案，未实现**：

```json
{
  "source": {
    "source_id": "src-01",
    "requested_url": "https://example.org/a",
    "final_url": "https://example.org/article",
    "redirects": [],
    "retrieved_at": "2026-09-10T00:00:00Z",
    "http_status": 200,
    "content_type": "text/html",
    "charset": "utf-8",
    "raw_sha256": "...",
    "representation_id": "rep-01",
    "retention": "metadata_only"
  },
  "block": {
    "block_id": "b-12",
    "parent_id": "section-3",
    "kind": "paragraph",
    "text": "...",
    "source_method": "static_html_trafilatura",
    "coverage": "complete_as_fetched",
    "locators": [],
    "lineage": ["rep-01"],
    "warnings": []
  }
}
```

`raw_sha256` / `extracted_sha256` 只用于 representation identity/change detection，不是 source authenticity proof；canonicalization 规则需要固定并记录。

### 6.2 Stable locators

W3C Web Annotation Data Model 定义：

- `TextQuoteSelector` 用 selected passage 加 prefix/suffix，较能抵抗小范围插入/改写，但会复制文本；
- `TextPositionSelector` 用 zero-based `start/end` offsets，不复制 quote，但对内容变化很脆弱；规范建议结合 `State` 表示 intended representation。[W3C Web Annotation Data Model](https://www.w3.org/TR/annotation-model/)

**Proposed locator portfolio：**

- HTML：heading path + normalized text offset + `TextQuoteSelector` + `TextPositionSelector`；不要把 CSS selector 单独当稳定引用。
- Browser DOM：rendered snapshot hash + DOM path/role + quote/offset；标记 `rendered` 和 triggering action。
- PDF：`page_number` + `bbox` + block/word index + normalized text offset；对 page image/OCR 另存 image region hash。
- OCR：page/image hash + hOCR/TSV line/word ids + bbox + quote；confidence 不进入 locator correctness。
- Table：table id + row/column/cell ids + page bbox；merged cell inference 需 warning。

Progressive disclosure 读取必须带 representation id/hash，否则同一个 URL 的更新页面可能让旧 cursor/offset 指向错误文本。

## 7. HTML/PDF/OCR fidelity 细则

### 7.1 Headings、headers、footers 和 reading order

- HTML heading hierarchy 应来自 DOM headings，同时保留 skipped levels 和 visually styled-but-not-heading 的 warning。
- PDF `header/footer` 不应默认丢弃；Docling 可把 furniture 与 body 分开，建议保留 furniture blocks，并在 Markdown view 中按 policy 隐藏而非销毁。
- PDF multi-column reading order 应优先使用 tagged/structured data（如果存在），否则使用 geometry inference 并标记 `reading_order_inferred`。
- OCR line order 由 engine 输出与 bbox grouping 共同决定；不能因为 TSV 行号存在就认为 semantic order 正确。
- figure caption 不能被当成正文 paragraph 的无来源拼接。

### 7.2 Tables

- HTML table 解析应保留 `thead/tbody/tfoot`、row/col span、cell header relationships 和 captions。
- PDF table 常无 row/column semantics；geometry/table model output 是 inference，必须带 warning 和 cell lineage。
- GFM table 不支持 nested block contents；complex table 使用 HTML/IR。
- OCR table 需同时看 text boxes 和 line/grid/layout signals；plain OCR text 不足以 reconstruct table。

### 7.3 Code、formulas、footnotes、references

- `pre/code` 原文应优先保留 whitespace、language hint、line breaks；不要先通过 prose cleanup。
- Formula 可能是 PDF glyph、image 或 MathML/LaTeX source；无法证明时保存 visual asset + extracted text + `formula_uncertain`。
- Footnote reference/body 建 relation，不把 footnote body 无条件移入 main paragraph。
- References section 保留原顺序、label、链接和 page/DOM locator；不要未经 agent 判断合并不同 editions。

### 7.4 Images and figure semantics

HTML standard 将 `alt` 视为 image 的 textual replacement，把 `figcaption` 视为补充 caption；PDF/standalone image 没有同样可靠的 semantic source。OCR 可读出文字，但不能可靠恢复 chart/diagram 的 spatial semantics、颜色编码或公式含义。因此 output 必须保留：

- original asset or page crop；
- `alt` / caption / nearby context separately；
- OCR blocks and confidence；
- semantic interpretation status (`not_interpreted` unless supported by evidence)。

## 8. Security、resource isolation 和 retention

### 8.1 SSRF、redirect 和 DNS

OWASP SSRF guidance 建议：不要直接接受未经验证的完整 user URL；禁用自动 redirects 以避免 validation bypass；同时解析 A 和 AAAA 并对每个结果检查 private/non-public ranges；DNS rebinding/pinning 需要避免只依赖 initial resolution。[OWASP SSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)

**Proposed controls：**

- scheme allowlist 只允许 `http`/`https`；拒绝 `file:`、`data:`、`javascript:`、`gopher:` 等；
- 解析 hostname 的全部 A/AAAA，拒绝 loopback、RFC1918、link-local、multicast、metadata-service 等；
- 每个 redirect hop 重新 canonicalize、resolve、validate，限制 hop 数；
- 禁止 HTTP client 自动 redirect，改为 application-controlled redirect；
- 记录 `requested_url`、每个 hop、最终 URL、policy decision；
- browser egress 在 network/process boundary 再做 allowlist，不能把 Playwright route 当 isolation boundary。

### 8.2 Browser subresources

**Proposed default：**

- 只允许 main origin 和明确必要 CDN；
- 默认 abort analytics、video、font、popup、WebSocket、第三方 iframe；
- 对 `serviceWorkers` 设 policy（若需要完整 request visibility，考虑 block）；
- 限制下载 MIME、magic bytes、decompressed size；
- 不继承 host cookies、tokens、credentials；
- 每个 browser context 独立 temp profile，job 结束销毁；
- 页面 content 进入 untrusted-data channel，不执行页面文字中的 instructions。

### 8.3 Parser isolation

**Proposed per-job budgets（数值仅为待验证配置项，不是已批准约束）：**

- `deadline_ms`：总 wall-clock hard cap；
- `connect/read/idle timeout`：HTTP 分项 timeout；
- `max_redirects`、`max_response_bytes`、`max_decompressed_bytes`；
- `max_browser_pages`、`max_scroll_steps`、`max_download_bytes`、`max_subresource_bytes`；
- `max_pdf_pages`、`max_render_pixels_per_page`、`max_ocr_seconds_per_page`；
- per-job `max_memory`、CPU worker count、temporary disk quota；
- `max_output_bytes/chars`，触发 `truncated` 而非 `failed`。

所有 parser/OCR/browser 应在低权限 worker 中运行；成功、失败、timeout、cancel 都执行 cleanup；startup scavenger 清理 crash 留下的 temp directories。

### 8.4 Robots、auth/paywall 和 retention

RFC 9309 规定 robots.txt 的 matching、redirect、error、cache behavior，并明确 robots rules “not a form of access authorization”。[RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html)

**Proposed policy：**

- 记录 user-agent 与 robots decision；默认尊重 disallow；
- robots 不可达时按项目 policy 明确选择保守拒绝或有限读取，不能伪装成 auth decision；
- login、MFA、paywall、captcha、anti-bot/access refusal 明确返回 `refused`/`auth_required`，不进行 bypass；
- raw HTML/PDF/images/OCR artifacts 的 retention 受 source terms、版权、用户 policy 和存储预算共同约束；
- 若不允许保存全文，保留允许的 metadata、hash、locator、error/coverage ledger，并把“无法保留 raw snapshot”写入 provenance；
- 默认只为 progressive disclosure 需要保留 representation，TTL/删除策略待 validation，不在本 memo 固化数字。

## 9. 代表性 failure cases 与测试设计

以下是**拟议测试样本**，不是已运行结果，也不是 benchmark：

| 类别 | 样本 | 期望行为 |
|---|---|---|
| Static HTML | malformed tags、nested lists、`pre/code`、HTML comments 中 injection marker | 保留 raw；正文 view 不执行 comments；code whitespace 保留；warning 可追溯 |
| HTML semantics | `figure` + `img alt` + `figcaption`、image-only link、lazy `srcset` | alt/caption 分离；解析 absolute URL；image asset 独立记录 |
| JS shell | initial HTML 只有 root div，hydration 后出现 headings/table | static route partial/upgrade signal；Playwright capture rendered DOM 和 triggering method |
| Infinite scroll | scroll 后重复 items、cursor API、永不结束的 observer | 以 scroll/page/byte/time budget 停止；去重但保留 source lineage；返回 partial/truncated |
| Download | click 触发 PDF，download URL redirect 到 file | 等待 download event；保存 bytes；验证 MIME/magic bytes；另走 PDF route |
| Browser egress | service worker、third-party iframe、analytics、WebSocket | 记录/阻断策略；service worker visibility 不被误报为完整网络捕获 |
| PDF native | single-column、multi-column、headers/footers、footnotes、references | blocks/words/bbox 保留；reading_order_inferred 与 furniture 不静默删除 |
| PDF table | merged cells、nested line breaks、table caption/notes | 不强转 GFM；table IR/HTML + uncertainty warning |
| PDF scanned | image-only page、多页 mixed native/OCR | per-page classification；OCR only where needed；native/OCR overlap 保留冲突 |
| PDF encrypted | password-required/encryption metadata | `encrypted`/`refused`，不重复 retry，不伪造 empty content |
| OCR | rotated text、low-resolution scan、Chinese/English mixed、tables | TSV/hOCR boxes/confidence 保留；low confidence 不是 semantic verdict |
| Image | standalone PNG/JPEG/SVG、large image、chart/diagram/formula | raw asset + OCR region；figure semantics `not_interpreted`，不 hallucinate |
| SSRF | localhost、RFC1918、IPv6 loopback/link-local、DNS changing A/AAAA、redirect chain | reject before/after each hop；记录 policy refusal |
| Retention | source forbids raw persistence / source changes before continuation | metadata/hash-only mode；stale cursor；不把 old locator 指向新 snapshot |

**拟议指标：** 不是性能 benchmark，而是 correctness/coverage ledger：block coverage recall、heading/table/caption preservation、page/block locator reattach rate、native-vs-OCR source attribution、partial/truncated classification precision、SSRF refusal coverage、cancel 后 no-new-request、retention-policy compliance。具体 acceptance numbers 待 corpus 和 clean-machine validation 后决定。

## 10. 候选组件比较

| 组件 | 适合的层 | 一手资料支持的能力 | 明确限制/风险 | license/platform 结论 |
|---|---|---|---|---|
| **Trafilatura** | static HTML main-content view | metadata、links/images/tables 可选；TXT/Markdown/JSON/HTML/XML 等输出 | main-content heuristic 有损；images/links 不应替代 DOM inventory | 当前 repo Apache-2.0；历史版本 license 需按 pinned version 核对；Windows support 在当前 README 未明确 |
| **Mozilla Readability** | article-like HTML second opinion | DOM → title/content/textContent/byline/lang/publishedTime；Firefox Reader View lineage | article-centric；mutates DOM；false positive/negative；不做 sanitization/JS/PDF/OCR | Apache-2.0；Node/DOM runtime 依赖另审 |
| **Playwright Python** | JS render、interaction、download、network observation | Windows；Chromium/Firefox/WebKit；sync/async；route/response/download | browser binaries、side effects、service-worker route caveat；无限 scroll 无完成保证 | Apache-2.0；浏览器 revision 和 runtime 需 pin |
| **pypdf** | simple native PDF / diagnostic | native text、layout mode、visitor callbacks；BSD-3-Clause | 不 OCR；PDF semantic/reading order/table limits | BSD-3-Clause；适合作为轻量 baseline，但非 full fidelity |
| **PyMuPDF** | rich native PDF/layout | blocks/words/dict/rawdict、images、rendering、OCR、table API | reading order 仍需判断；license 是 AGPL/commercial gating | AGPL 或 Artifex commercial；是否可用未决定 |
| **Docling** | advanced layout/scanned/mixed PDF | layout、reading order、tables、formulas、pictures、OCR、structured DoclingDocument、Markdown/JSON | model/runtime heavier；Windows support 明确，native Windows CPU 未充分验证；models license 另审 | code MIT；模型/依赖 license inventory 必需 |
| **Tesseract** | default local CPU OCR | Windows 10/11 docs；TSV/hOCR/ALTO/PAGE/PDF；boxes/confidence | OCR recognition 不等于 semantics；layout/table/figure 需上层 reconstruction | Apache-2.0；Leptonica/dependency inventory 仍需保留 |
| **PaddleOCR** | optional OCR/layout escalation | Windows adaptation；Apache-2.0 repository | current official FAQ 未独立证明 CPU matrix/performance；model/runtime inventory | Apache-2.0 repo；models/dependencies 另审 |

### 10.1 Proposed portfolio choice

如果必须先做一个小而可信的 portfolio，建议按下列顺序实现（均为 proposal）：

1. hardened HTTP + raw evidence manifest；
2. Trafilatura static HTML view；
3. pypdf native PDF route（或在 license approval 后启用 PyMuPDF）；
4. Tesseract OCR with TSV/hOCR lineage；
5. Playwright Python fallback；
6. Docling advanced PDF backend；
7. Readability comparison/fallback；
8. PaddleOCR targeted escalation。

这不是按“质量排名”排序，而是按 baseline 可解释性、资源/依赖风险和 required coverage 的递增路径提出的 implementation order；没有实测 benchmark 支持性能排序。

## 11. 对 progressive disclosure 的具体含义

progressive disclosure 在本项目不只是把字符串切成 chunks，而是让 agent 能在不丢失 lineage 的情况下逐步从：

1. source metadata / content-type / policy status；
2. coverage summary / outline / page map；
3. bounded preview；
4. section/page/block；
5. quote/locator；
6. raw asset/OCR evidence

继续读取。

**Proposed read response：**

```json
{
  "source": {"source_id": "src-01", "representation_id": "rep-03"},
  "coverage": {"status": "partial", "truncated": true, "omissions": []},
  "outline": [],
  "blocks": [],
  "warnings": [],
  "next_cursor": "opaque",
  "continuation": {
    "same_representation_required": true,
    "content_hash": "..."
  }
}
```

如果 source URL、snapshot、extractor config 或 canonicalization 改变，continuation 不应默认为安全；应要求新读取或返回 stale status。locator 应尽量同时提供 quote 和 position；W3C 规范明确指出 quote 更容易恢复、position 更容易避免复制文本但更易因内容变化失效。

## 12. 结论与 next validation

### 12.1 建议保留的设计原则

- **Raw first, Markdown last.**
- **Native text before OCR; OCR per page/region, not blindly per document.**
- **Browser only on observable need; arbitrary JS is not completeness.**
- **Source method and coverage are first-class fields.**
- **GFM is output convenience, not semantic storage.**
- **Images/figures remain assets plus context; OCR does not recover visual semantics.**
- **AGPL/model/dependency licenses are route-selection inputs.**
- **No bypass of auth/paywall/robots/anti-bot.**
- **Budget and parser isolation are correctness controls, not only operations concerns.**

### 12.2 下一轮必须验证

1. Windows clean machine：Playwright browser install/render/download、Tesseract Windows binary and language data、Docling import/offline model cache、PaddleOCR basic CPU path。
2. Fixed corpus：static HTML、JS shell、infinite scroll、multi-column PDF、table/formula PDF、scanned/mixed PDF、web image、standalone image、encrypted PDF。
3. Per-type output：block coverage、reading order、table/caption/footnote/formula preservation、OCR source lineage、locator continuation。
4. Security corpus：redirect-to-private、A/AAAA changes、service-worker subresources、large compressed PDF/image、malicious file types、robots/auth/paywall refusal。
5. License inventory：pinned package/binary/model versions，尤其 PyMuPDF AGPL/commercial、Docling model dependencies、PaddleOCR model files、Tesseract traineddata。
6. Resource measurements：CPU/RAM/disk/time per route，作为未来阈值输入；本 memo 不提供或声称任何 performance number。

## 13. Citation ledger

> **读取状态约定：** 本表只收录本轮通过 WebFetch/Context7 读取到的 official primary page/source；WebSearch 只用于发现入口，不作为“已读取全文”的证据。访问日期统一为 2026-09-10。`Full` 表示本轮拿到页面主体或 source 内容；某些 living docs/repository `main` 的确切 package release 尚未 pin。

| Source | Owning institution/authors | Version/publication | Exact supporting section/short quote | Access limitation |
|---|---|---|---|---|
| [Trafilatura repository](https://github.com/adbar/trafilatura) | adbar / Trafilatura contributors | repository `main`, accessed 2026-09-10 | README: “focuses on the actual content”; optional “links, images, tables”; TXT/Markdown/JSON/HTML/XML outputs; Apache-2.0; pre-1.8.0 historical GPLv3+ note | Full README/source page fetched；exact pinned release and Windows classifier not established here |
| [Mozilla Readability README](https://github.com/mozilla/readability/blob/main/README.md) | Mozilla / Arc90 contributors | repository `main`, accessed 2026-09-10 | `new Readability(document, options)`; `parse()` fields; “likely to produce both false positives and false negatives”; “strongly recommend you use a sanitizer library”; Apache-2.0 | Full README fetched；article quality is heuristic，not a general fidelity guarantee |
| [Playwright Python intro](https://playwright.dev/python/docs/intro) | Microsoft Playwright project | current official docs, accessed 2026-09-10 | Python 3.8+；Windows 11+/Server 2019+ listed；Chromium/WebKit/Firefox；sync and async APIs | Full docs fetched；exact browser revision is not pinned |
| [Playwright network](https://playwright.dev/docs/network) | Microsoft Playwright project | current official docs, accessed 2026-09-10 | `page.route()` vs `browserContext.route()`；service-worker requests may not appear in normal routing/events；block service workers for visibility | Full docs fetched；routing is not a network isolation boundary |
| [Playwright downloads](https://playwright.dev/docs/downloads) | Microsoft Playwright project | current official docs, accessed 2026-09-10 | `download` event；`download.saveAs(path)`；temporary files removed when context closes | Full docs fetched；does not validate downloaded file semantics |
| [pypdf Extract Text](https://pypdf.readthedocs.io/en/stable/user/extract-text.html) | py-pdf/pypdf contributors | stable docs page, accessed 2026-09-10 | PDF lacks semantic distinctions；tables may be absolutely positioned text；scanned PDF needs OCR；`extraction_mode="layout"` and visitor callbacks | Full docs fetched；exact package lock/version remains open |
| [pypdf LICENSE](https://github.com/py-pdf/pypdf/blob/main/LICENSE) | py-pdf contributors | repository `main`, accessed 2026-09-10 | BSD-style redistribution conditions and disclaimer | Full license fetched；license compliance still needs dependency inventory |
| [PyMuPDF Appendix 1](https://pymupdf.readthedocs.io/en/latest/app1.html) | Artifex / PyMuPDF maintainers | docs covering current line, accessed 2026-09-10 | TextPage pages→blocks→lines→spans→characters；`blocks`/`words`/`DICT`/`RAWDICT`; default creator order；`sort=True` top-left approximation | Full docs fetched；no quality benchmark；reading order remains inference |
| [PyMuPDF about/licensing](https://pymupdf.readthedocs.io/en/latest/about.html) | Artifex / MuPDF maintainers | docs through current line, accessed 2026-09-10 | “available under both, open-source AGPL and commercial license agreements” | Full page fetched；legal applicability depends on distribution model |
| [Docling overview](https://docling-project.github.io/docling/) | Docling Project / contributors | current docs, accessed 2026-09-10 | supported PDF/HTML/images；advanced PDF layout, reading order, table structure, formula extraction；local/air-gapped operation；Markdown/JSON outputs | Full docs fetched；model/runtime performance not benchmarked |
| [DoclingDocument](https://docling-project.github.io/docling/concepts/docling_document/) | Docling Project | current docs, accessed 2026-09-10 | Pydantic-based document format；text/tables/pictures/key-value；body/furniture；reading order by tree sequence；provenance/layout | Full docs fetched；exact model versions and licenses not resolved |
| [Docling installation](https://docling-project.github.io/docling/getting_started/installation/) | Docling Project | current docs, accessed 2026-09-10 | Windows/macOS/Linux and x86_64/arm64；CPU-only discussion explicitly Linux-oriented；OCR backends and CUDA/platform restrictions | Full docs fetched；native Windows CPU path remains open validation |
| [Tesseract repository](https://github.com/tesseract-ocr/tesseract) | tesseract-ocr maintainers | repository `main`, accessed 2026-09-10 | Apache-2.0；PNG/JPEG/TIFF；100+ languages；hOCR/TSV/ALTO/PAGE/PDF outputs | Full README fetched；README does not provide complete current CPU/platform matrix |
| [Tesseract supported OS](https://tesseract-ocr.github.io/tessdoc/supported-operating-systems.html) | tesseract-ocr documentation | current docs, accessed 2026-09-10 | Windows 10/11 listed；older versions unsupported | Full page fetched；no performance claim |
| [Tesseract compiling/OpenMP](https://tesseract-ocr.github.io/tessdoc/Compiling-%E2%80%93-GitInstallation.html) | tesseract-ocr documentation | current docs, accessed 2026-09-10 | default OCR run uses 4 CPU cores；bulk processing guidance disables OpenMP and runs separate single-threaded instances | Full page fetched；这是文档对默认构建/批处理策略的说明，不是目标机器 benchmark |
| [Tesseract command-line usage](https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html) | tesseract-ocr documentation | current docs, accessed 2026-09-10 | hOCR `bbox`/`x_wconf`；TSV hierarchy, geometry, `conf`; examples show `-1` on non-word-level rows without defining a universal meaning | Full page fetched；confidence meaning is engine signal, not semantic truth；不要把 `-1` 推广为版本无关的完整定义 |
| [PaddleOCR FAQ](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/FAQ.en.md) | PaddlePaddle / PaddleOCR contributors | repository `main`, accessed 2026-09-10 | “adapted to Windows and MAC systems”; Windows model download/setup notes | Full page fetched；CPU matrix/performance not established |
| [PaddleOCR LICENSE](https://github.com/PaddlePaddle/PaddleOCR/blob/main/LICENSE) | PaddlePaddle Authors | Apache-2.0, accessed 2026-09-10 | Apache-2.0 terms | Full license fetched；models/dependencies may have separate terms |
| [CommonMark 0.31.2](https://spec.commonmark.org/0.31.2/) | John MacFarlane / CommonMark | 0.31.2, Jan. 28, 2024 | core syntax；tables/footnotes called extensions of implementations | Full spec fetched；does not describe arbitrary document layout |
| [GFM spec](https://github.github.com/gfm/) | GitHub | current hosted spec, accessed 2026-09-10 | tables/task lists/strikethrough/autolinks/raw HTML rules；table cells inline-only | Full spec fetched；renderer interoperability varies |
| [WHATWG HTML images](https://html.spec.whatwg.org/dev/images.html) | WHATWG | living standard, accessed 2026-09-10 | `alt` as textual replacement；`figcaption` supplements image；do not duplicate caption in alt | Full section fetched；source pages may misuse semantics |
| [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html) | IETF; Robots Exclusion Protocol authors | RFC 9309, Sep. 2022 | redirect/error/cache behavior；“not a form of access authorization” | Full RFC fetched；robots remains policy input, not security control |
| [OWASP SSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html) | OWASP Foundation | current cheat sheet, accessed 2026-09-10 | disable redirects；resolve A/AAAA；validate private/non-public addresses；DNS rebinding/pinning | Full page fetched；controls must match deployment network |
| [W3C Web Annotation Data Model](https://www.w3.org/TR/annotation-model/) | W3C | Recommendation/current TR, accessed 2026-09-10 | TextQuoteSelector stores quote + prefix/suffix；TextPositionSelector uses start/end and is brittle to changes；pair with State | Full section fetched；selectors identify representations, not source truth |

## 14. 最终建议（简版）

**Proposed baseline：** `HTTP fetch + Trafilatura + pypdf + Tesseract`；`Playwright` 作为 observable JS/download fallback；`Docling` 作为 advanced layout/scanned PDF backend；`PyMuPDF` 只有在 AGPL/commercial license 通过后启用；`Mozilla Readability` 用于 article-like comparison；`PaddleOCR` 暂作为 targeted escalation。

这个组合的关键不在于宣称某个 extractor“最好”，而在于：

- 任何 route 都输出 coverage、source method、warnings 和 lineage；
- native、rendered、OCR、inferred 四种 representation 不混写；
- 超长内容可继续读取，不能把 output truncation 伪装成 source completeness；
- table/caption/figure/formula/footnote/reference 不因 Markdown 不足而静默丢弃；
- Windows/CPU/license/资源预算在实现前分别验证；
- 公开页面是 untrusted data，拒绝 auth/paywall/robots/SSRF bypass。
