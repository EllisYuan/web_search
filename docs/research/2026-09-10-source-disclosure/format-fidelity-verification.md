---
title: HTML、JS、PDF 与 OCR 内容保真核验
status: independent-verification
verification_date: 2026-09-10
scope: primary-source recheck of format-fidelity.md; Windows CPU-only public-content acquisition/extraction
---

# HTML、JS、PDF 与 OCR 内容保真核验

> 本文件是对 `format-fidelity.md` 的 adversarial evidence verification，不是实现方案、benchmark 或组件批准。核验重点是：原始文档是否真的支持 memo 中的 capability、license、platform、CPU 与 protocol/format assertions，以及这些事实能否直接迁移到本项目。

## 1. 核验范围与方法

本轮重新打开并读取了以下 public primary sources（均于 2026-09-10 访问）：

- Trafilatura、Mozilla Readability、Playwright、pypdf、PyMuPDF、Docling、Tesseract、PaddleOCR 的官方 repository/docs/license；
- CommonMark、GFM、WHATWG HTML images、W3C Web Annotation、OWASP SSRF、RFC 9309；
- 使用 WebFetch 读取 official page/source；Docling 的官方文档另以 Context7 作为导航交叉核对。没有安装 package、执行 browser/OCR/PDF inference、运行 benchmark 或做 MCP conformance test。

**证据口径：** `confirmed` 只表示 primary source 明确支持该有限事实；不表示本项目 pipeline 已运行或质量已证明。`corrected` 表示原文档中的表述需要收窄，相关文字已在 `format-fidelity.md` 原位置修改。`unverified` 表示当前 primary source 不足以支持该更强 claim，或本轮没有做目标环境验证。

## 2. Verdict

### 2.1 保留的核心结论

- 分层 portfolio（HTTP/raw evidence、static extractor、browser fallback、native PDF、selective OCR、advanced layout backend）仍是与 source limitations 相符的 **proposed** 方向。
- `raw first, Markdown last`、保留 block/page/bbox/lineage、native text 与 OCR 分开、把 JS 执行成功与完整语义区分、把 coverage/truncation/failure 分开，均没有被本轮 primary-source recheck 推翻。
- `PyMuPDF` 的 extraction capability 与 AGPL/commercial gating 事实成立，但不等于本项目可以采用它。
- `Docling Windows compatibility` 与 `Docling CPU-only installation example` 是两个不同事实；memo 保留了这一差别。

### 2.2 已修正的高影响表述

1. **Tesseract 的 4 CPU cores**：官方编译文档支持“默认一次 OCR 使用 4 CPU cores”的说明；它不是目标 Windows 机器 benchmark。bulk processing 的官方建议是关闭 OpenMP、运行多个独立 single-threaded instances，不应泛称为已验证的“多进程性能路径”。
2. **Tesseract TSV `-1`**：官方命令行页面的示例中非 word-level 结构行出现 `-1`，但页面没有给出可推广到所有版本/输出的通用语义。memo 已改为只把它描述为可观察的缺少 word-level confidence 值，不能把 `-1` 当作完整、版本无关的定义。
3. **Playwright routing**：`page.route()` / `browserContext.route()` 是请求拦截与观测 API；官方文档没有把 routing 说成 isolation boundary。memo 的 browser egress isolation 仍明确标为 proposed engineering control，而不是 Playwright 保证。
4. **PaddleOCR Windows**：FAQ 明确写有 Windows/macOS adaptation，但同时没有 CPU inference support matrix 或性能证据。memo 未把 Windows adaptation 外推成 Windows CPU readiness。

## 3. Claim ledger

| ID | 主题与 memo claim | 状态 | Primary-source 核验与迁移限制 |
|---|---|---|---|
| F1 | Trafilatura 可抽取 main text/metadata/comments，过滤 boilerplate，可选 links/images/tables，输出多种 text/markup formats，Apache-2.0；README 未明确 Windows support。 | **confirmed** | [Trafilatura README](https://github.com/adbar/trafilatura)：README 写有 “main texts, metadata and comments”、optional “links, images, tables”，输出 TXT/Markdown/CSV/JSON/HTML/XML/XML-TEI，并写明 Apache 2.0、v1.8.0 以前 GPLv3+。当前 README 未给 Windows/platform guarantee；不能用它证明目标环境可用。 |
| F2 | Mozilla Readability `parse()` 返回 title/content/textContent 等字段；会修改 DOM；`isProbablyReaderable()` 有 false positives/negatives；不做 sanitization，建议 DOMPurify/CSP；Apache-2.0。 | **confirmed** | [Readability README](https://github.com/mozilla/readability/blob/main/README.md)：以上各点均由 README 明确支持。它仍是 article-centric heuristic，不是 lossless parser、JS executor 或 sanitizer；必须保存原始 DOM/bytes 后再生成 view。 |
| F3 | Playwright Python 支持 Chromium/WebKit/Firefox、sync/async API、Windows/macOS/Linux；Python 3.8+；可做 browser automation。 | **confirmed with version caveat** | [Playwright Python intro](https://playwright.dev/python/docs/intro) 明确列 Python 3.8+、Chromium/WebKit/Firefox、sync/async，并列 Windows 11+/Server 2019+、macOS 14+ 与若干 Linux distributions。页面未提供 pinned package/browser revision；不能把“docs currently lists OS”当作目标机器 smoke-test 结果。 |
| F4 | Playwright `page.route()` 是单 page，`browserContext.route()` 是 context scope；context route 覆盖 popups/opened links；service-worker requests 可能不出现在通常 route/events，必要时 block service workers。 | **confirmed; design wording narrowed** | [Playwright network](https://playwright.dev/docs/network) 支持这些范围和 service-worker caveat。该页没有声称 routing 是 process/network isolation；因此 egress allowlist、credential isolation、resource budgets 必须继续作为本项目 proposed controls。 |
| F5 | Playwright download 事件提供 URL、suggested filename、content stream；可 `saveAs`；context 关闭时临时下载删除。 | **confirmed** | [Playwright downloads](https://playwright.dev/docs/downloads) 明确写 `page.on('download')`、Download object、URL/filename/content stream、`download.saveAs()`，并说明 context close 时下载文件会删除。仍需项目自己校验 MIME、magic bytes、decompressed size 和 PDF route。 |
| F6 | pypdf 不能从 PDF 可靠恢复 semantic paragraph/header/footer/table/caption/reading order；扫描 PDF 需要 OCR；`extraction_mode="layout"` 和 visitor callbacks 只是 approximation。 | **confirmed** | [pypdf Extract Text](https://pypdf.readthedocs.io/en/stable/user/extract-text.html) 明确说 PDF 没有 semantic layer、tables 常为 absolute-positioned text、scanned PDF 需要 OCR，并提供 layout/visitor APIs。页面中的个别绝对化文字（例如 “will never confuse characters”）不能转译为项目的 universal fidelity guarantee。 |
| F7 | pypdf 是 BSD-3-Clause。 | **confirmed** | [pypdf LICENSE](https://github.com/py-pdf/pypdf/blob/main/LICENSE) 的条款匹配 BSD 3-Clause；[pyproject metadata](https://github.com/py-pdf/pypdf/blob/main/pyproject.toml) 只暴露 `license = "BSD-3-Clause"` 和 Python `>=3.9`，版本字段是 dynamic，未据此声称当前 release。 |
| F8 | PyMuPDF 提供 TextPage blocks/lines/spans/characters、words、DICT/JSON、RAWDICT/RAWJSON；默认顺序可能是 creator order，`sort=True` 是 top-left geometric approximation；支持 image/render/OCR/table API。 | **confirmed with semantic limitation** | [PyMuPDF Appendix 1](https://pymupdf.readthedocs.io/en/latest/app1.html) 支持层级、字段与 default creator order / `sort=True` 说明；[PyMuPDF about](https://pymupdf.readthedocs.io/en/latest/about.html) 列出 image rendering、OCR API、table extraction。官方文档明确不足以证明 multi-column 或复杂页面的 semantic reading order。 |
| F9 | PyMuPDF/MuPDF 以 AGPL 或 commercial license 提供。 | **confirmed; adoption unverified** | [PyMuPDF about/licensing](https://pymupdf.readthedocs.io/en/latest/about.html) 明确写 “AGPL and commercial license agreements”，并建议不适用 AGPL 时联系 Artifex。是否符合本项目最终 distribution model、是否需要 commercial license，仍未决定；memo 不应把 capability 当作 adoption approval。 |
| F10 | DoclingDocument 是 structured/Pydantic-based model，可表达 text、tables、pictures、key-value，body/furniture、reading order、provenance/layout/bounding boxes；Docling 支持 PDF/HTML/images、layout/reading order/table/formula/OCR、Markdown/HTML/JSON 等，项目页标 MIT。 | **confirmed as documentation claim** | [DoclingDocument](https://docling-project.github.io/docling/concepts/docling_document/) 支持文档模型、body/furniture、children order、provenance/layout；[Docling overview](https://docling-project.github.io/docling/) 支持输入/能力/输出与 local/air-gapped wording，并以 MIT badge 标示项目 license。它不提供本项目 corpus 的质量或 semantic completeness 证据。 |
| F11 | Docling lists Windows/macOS/Linux 与 x86_64/arm64；CPU-only setup 的官方示例明确以 Linux 为主，部分 OCR/model paths 有平台约束。 | **confirmed; important boundary** | [Docling installation](https://docling-project.github.io/docling/getting_started/installation/) 写 “Works on macOS, Linux, and Windows” 与架构支持；CPU-only PyTorch 示例明确是 Linux 场景；Nemotron OCR 例子还要求 Linux x86_64/Python 3.12/CUDA 13.x。故 `Windows supported` 不能推出 `native Windows CPU-only pipeline validated`；memo 的 open validation 保留。 |
| F12 | Tesseract repository Apache-2.0，支持 PNG/JPEG/TIFF、100+ languages，输出 plain text/hOCR/PDF/TSV/ALTO/PAGE；Windows 10/11 docs；TSV/hOCR 有 geometry/confidence。 | **confirmed with two qualifications** | [Tesseract repository](https://github.com/tesseract-ocr/tesseract) 明确 license、formats、`more than 100 languages` 和 output formats；[supported OS](https://tesseract-ocr.github.io/tessdoc/supported-operating-systems.html) 列 Windows 10/11；[CLI usage](https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html) 支持 hOCR `bbox`/`x_wconf`、TSV hierarchy 与 `left/top/width/height/conf`。README 没有 current CPU performance matrix；confidence 仍是 recognition signal，不是 semantic truth。 |
| F13 | Tesseract 默认构建的一次 OCR 使用 4 CPU cores；bulk processing 建议关闭 OpenMP、运行独立 single-threaded instances。 | **confirmed; not a benchmark** | [Tesseract compiling/OpenMP](https://tesseract-ocr.github.io/tessdoc/Compiling-%E2%80%93-GitInstallation.html) 明确写默认一次 OCR 使用 4 CPU cores，并给出 bulk processing 的 OpenMP/独立实例策略。不能把该文档句子转成目标 Windows CPU throughput/RAM 结论；memo 已收窄原文。 |
| F14 | PaddleOCR FAQ 说明已适配 Windows/macOS；Windows model download/setup 有说明；repository Apache-2.0；不能据此证明 CPU inference matrix/performance。 | **confirmed with limitation** | [PaddleOCR FAQ](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/FAQ.en.md) 在 “How to run on Windows or Mac?”（亦出现在 Legacy Issues）写 adaptation，并给出 Windows 下手动模型下载/解压注意事项；FAQ 没有 CPU support matrix 或性能数据。[PaddleOCR LICENSE](https://github.com/PaddlePaddle/PaddleOCR/blob/main/LICENSE) 是 Apache 2.0，但模型/weights/runtime dependencies 仍需独立 inventory。 |
| F15 | CommonMark 0.31.2 core 不包含 tables/footnotes；GFM tables 允许 inline content，不允许 block-level elements。 | **confirmed** | [CommonMark 0.31.2](https://spec.commonmark.org/0.31.2/)（2024-01-28）将 tables/footnotes 作为 implementations 的 extensions；[GFM](https://github.github.com/gfm/) 明确 table header/delimiter/body 和 “Block-level elements cannot be inserted in a table.” 这支持 complex table 使用 sidecar/HTML/IR，但不证明任何 renderer 的互操作质量。 |
| F16 | WHATWG `alt` 是 image 的 textual replacement，`figcaption` 是补充 caption，不能把 caption 重复写入 alt。 | **confirmed** | [WHATWG images](https://html.spec.whatwg.org/dev/images.html) 明确区分 alternative text 与 figure caption，并说明 caption 不应复制到 `alt`。OCR 仍不能从 standalone image 恢复 chart/diagram 的完整 visual semantics；这是工程解释，不是 HTML standard guarantee。 |
| F17 | W3C `TextQuoteSelector` 使用 normalized text 与 Unicode code points，避免 grapheme cluster 中间边界；`TextPositionSelector` 是 zero-based、start-inclusive/end-exclusive 且 brittle；State 先于 selector 处理。 | **confirmed** | [W3C Web Annotation Data Model](https://www.w3.org/TR/annotation-model/) 的 TextQuoteSelector、TextPositionSelector、States sections 明确支持这些语义。它不自动提供 snapshot store、PDF/OCR mapping 或本项目 citation rehydration；这些仍是 proposed engineering design。 |
| F18 | OWASP SSRF guidance 支持禁止自动 redirect、检查 A/AAAA 与 private/non-public ranges、考虑 DNS pinning；也明确不应接受未经验证的完整 user URL。 | **confirmed as security guidance** | [OWASP SSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html) 明确写 “Do not accept complete URLs from the user”、prefer allow-list、disable redirects、validate A/AAAA and internal ranges，并讨论 DNS pinning。具体部署控制、browser egress 与 DNS race 仍需本项目安全验证。 |
| F19 | RFC 9309 把 robots rules 定义为 crawler policy，不是 access authorization；涉及 redirect/error/cache behavior。 | **confirmed; transfer narrowed** | [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html) 明确 “not a form of access authorization”，并规定至少 five consecutive redirects、4xx/5xx 与 cache behavior 的 crawler semantics。项目的“默认尊重 robots”是 proposed product policy；robots 不能代替 auth/SSRF/egress controls，也不能据 RFC 单独推出 copyright/retention permission。 |

## 4. 未能由本轮 primary sources 证明的 claims

以下事项仍保持 `Open validation`，不能写成已验证事实：

1. 任一 extractor 在本项目 corpus 上的 reading order、table reconstruction、caption/footnote/formula preservation、OCR quality、locator reattach rate 或 completeness。
2. Docling 在目标 native Windows、CPU-only、offline model cache、长 PDF、scanned/mixed PDF 上的 import、runtime、RAM、稳定性和模型下载路径。
3. PaddleOCR 的 Windows CPU inference path、模型与 runtime dependency license inventory、真实质量/资源开销。
4. Tesseract 在目标 Windows machine 的 language data、Chinese/English mixed layout、低清/旋转/表格 OCR quality、wall-clock/RAM；官方“4 cores”只是一条 build/documentation fact。
5. Playwright browser binary/revision pinning、browser context 的实际 subresource isolation、service-worker blocking 对目标页面的影响、无限 scroll 或个性化内容的 completeness。
6. PyMuPDF AGPL/commercial license 对最终 packaging/distribution model 的法律适用；pypdf 的依赖树及所有 transitive license。
7. Trafilatura 当前 pinned package release、Windows wheel/runtime support；Readability 的实际 article extraction quality；Markdown renderer 之间的互操作。
8. 任意固定的 `deadline_ms`、page/byte/scroll/OCR budgets、raw retention TTL、output thresholds；memo 中这些都是 proposed configuration inputs。
9. `coverage` 状态词、`next_cursor` scope、snapshot persistence、citation rehydration 与 target MCP host 的真实互操作；规范和 library docs 不替代 integration tests。
10. robots、版权、ToS、raw HTML/PDF/image/OCR retention 的项目-specific permission。software license 不等于内容保存或再分发授权。

## 5. 对原 memo 的审阅结论

- **没有发现足以推翻分层 portfolio 的 primary-source contradiction。** 但没有任何一个官方页面支持“单一 converter 对 HTML、JS、PDF、OCR 全部无损”的更强结论。
- **已 demonstrably corrected 的内容** 已在 `format-fidelity.md` 原位置完成：Tesseract 4-core wording、Tesseract TSV `-1` semantics；相关 ledger 也同步收窄。
- **必须继续保留的 caution**：Docling Windows compatibility 不等于 Windows CPU validation；PaddleOCR Windows adaptation 不等于 CPU readiness；Playwright network routing 不等于 isolation；PyMuPDF capability 不等于 license approval；OCR confidence 不等于 semantic truth。
- **研究结论仍应按 Facts / Interpretation / Proposed / Open validation 解释。** 本文件确认的是 source-to-claim fidelity，不是产品实现、最终 schema、性能 SLA 或 library selection approval。

## 6. Verified source ledger（访问限制摘要）

| Source | Owning institution / authors | 本轮读取结果与限制 |
|---|---|---|
| [Trafilatura README](https://github.com/adbar/trafilatura) | adbar / contributors | README 主体可读；当前 repository/main 的 exact release 未 pin，README 未明确 Windows support。 |
| [Mozilla Readability README](https://github.com/mozilla/readability/blob/main/README.md) | Mozilla / Arc90 contributors | README 主体可读；验证 API/security/license，但没有运行 DOM parser。 |
| [Playwright Python intro](https://playwright.dev/python/docs/intro) | Microsoft Playwright project | 官方 intro 可读；具体 package/browser revision 未 pin。 |
| [Playwright network](https://playwright.dev/docs/network) | Microsoft Playwright project | network routing/service-worker caveat 可读；未把 route 当 isolation。 |
| [Playwright downloads](https://playwright.dev/docs/downloads) | Microsoft Playwright project | download lifecycle 可读；未运行 download test。 |
| [pypdf Extract Text](https://pypdf.readthedocs.io/en/stable/user/extract-text.html) | py-pdf/pypdf contributors | stable docs 可读；exact installed release 未验证；未运行 extraction。 |
| [pypdf LICENSE](https://github.com/py-pdf/pypdf/blob/main/LICENSE) | py-pdf contributors | license 条款可读；pyproject 暴露 BSD-3-Clause/Python >=3.9，但 version dynamic。 |
| [PyMuPDF Appendix 1](https://pymupdf.readthedocs.io/en/latest/app1.html) | Artifex / PyMuPDF maintainers | structured extraction sections 可读；未做 complex-PDF quality test。 |
| [PyMuPDF about](https://pymupdf.readthedocs.io/en/latest/about.html) | Artifex / MuPDF maintainers | capability/license sections 可读；页面标注覆盖至 PyMuPDF 1.28.2，但未核验 distribution legal fit。 |
| [Docling overview](https://docling-project.github.io/docling/) / [DoclingDocument](https://docling-project.github.io/docling/concepts/docling_document/) | Docling Project / contributors | official docs 可读；未验证 model/runtime/dependency licenses 或 output quality。 |
| [Docling installation](https://docling-project.github.io/docling/getting_started/installation/) | Docling Project | OS/architecture 与 Linux CPU-only example 可读；Windows CPU clean-machine run 未做。 |
| [Tesseract repository](https://github.com/tesseract-ocr/tesseract) / [supported OS](https://tesseract-ocr.github.io/tessdoc/supported-operating-systems.html) | tesseract-ocr maintainers | license/formats/languages/Windows docs 可读；README 无完整 current CPU matrix。 |
| [Tesseract CLI usage](https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html) / [compiling/OpenMP](https://tesseract-ocr.github.io/tessdoc/Compiling-%E2%80%93-GitInstallation.html) | tesseract-ocr documentation | geometry/confidence/4-core wording 可读；未运行 target-machine OCR。 |
| [PaddleOCR FAQ](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/FAQ.en.md) / [LICENSE](https://github.com/PaddlePaddle/PaddleOCR/blob/main/LICENSE) | PaddlePaddle / PaddleOCR contributors | Windows adaptation/model setup and Apache-2.0 repo license 可读；FAQ 无 CPU matrix，models/dependencies 未 inventory。 |
| [CommonMark 0.31.2](https://spec.commonmark.org/0.31.2/) / [GFM](https://github.github.com/gfm/) | CommonMark Project / GitHub | syntax/table limits 可读；未比较 renderer interoperability。 |
| [WHATWG images](https://html.spec.whatwg.org/dev/images.html) | WHATWG | alt/figcaption semantics 可读；未判断 source page semantics 是否正确。 |
| [W3C Web Annotation Data Model](https://www.w3.org/TR/annotation-model/) | W3C | selectors/state sections 可读；project-specific rehydration 未测试。 |
| [OWASP SSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html) | OWASP Foundation | URL/redirect/A-AAAA/DNS pinning guidance 可读；未验证 deployment network controls。 |
| [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html) | IETF / Robots Exclusion Protocol authors | robots redirect/error/cache semantics 可读；未把 robots 当作 authorization。 |

## 7. Final concise verdict

`format-fidelity.md` 的主要事实基础在本轮 2026-09-10 primary-source recheck 后仍可用，但只能作为 **proposed, unvalidated design memo**。两处具体 overstatement 已修正：Tesseract 4-core/bulk wording 与 TSV `-1` semantics。高影响未知仍集中在目标 Windows CPU reality、Docling/PaddleOCR models and dependencies、PyMuPDF license fit、真实 corpus 的 extraction fidelity、resource isolation、retention/ToS 与 MCP host continuation behavior；这些不能由官方 capability pages 或 README 推出，必须通过后续 clean-machine、adversarial corpus、license inventory 和 integration validation 单独验证。
