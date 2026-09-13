# Retrieval 与可追溯 evidence 路线调研

> 对应 ticket：[调研网页读取、抓取与可追溯 evidence 的实现路线](https://github.com/EllisYuan/web_search/issues/3)  
> 调研日期：2026-09-08。本文是候选路线与验证计划，不是已批准的架构决定；厂商能力、价格和 hosted 条款需在上线前复核。

## 结论摘要

建议采用三层 pipeline，而不是把每个 search result 都送进 browser 或 hosted crawler：

1. **HTTP fetch + extraction（默认）**：只允许 `http/https`，用 `httpx`/Node `fetch` 取得原始 bytes，再用 Trafilatura 或 Mozilla Readability 提取 HTML 正文。通常比默认 browser 少一层资源开销，易缓存、易保存 raw evidence；JS shell 可按策略升级到 browser，下载与 PDF 进入受限 parser。遇到未授权登录态、paywall 或访问拒绝则返回明确状态，不通过 fallback 绕过限制，也不要假装正文完整。
2. **按需 browser fallback**：以“正文为空、明显 hydration、需要等待 selector、必须点击展开、下载附件”等可观测条件触发 Playwright。为每个 page/context 设置时间、字节、请求数、页面和并发预算，并在 browser 网络层执行 egress allowlist。
3. **高召回/文档专用的可选服务**：自托管 Crawl4AI，或经过数据分级与合规批准后使用 Firecrawl/Jina Reader。它们适合 PDF/OCR、复杂动态页、批量 crawl 或低运维场景，但会引入浏览器资源、第三方数据流、供应商缓存/计费和版本行为差异。

证据对象必须同时保留“抓到的东西”和“抽取后给模型的东西”：`source_url`、`final_url`、redirect chain、retrieved_at、status、headers/content-type/charset、fetcher/extractor/version/config、raw bytes SHA-256、canonical extracted text SHA-256，以及 section-level anchors。只保存 Markdown 会失去复核原页面的能力。原始内容保存受 provider terms、版权、访问授权和 retention policy 约束；无权保存时只保留允许的 metadata/引用，并明确无法保留完整 snapshot 的审计限制。

## 路线比较

| 路线 | 能力边界 | 证据与正文保真 | hosted / self-hosted、license | 适用判断 |
|---|---|---|---|---|
| **HTTPX + Trafilatura** | HTTPX 提供 sync/async、timeout、streaming；默认不跟随 redirect。Trafilatura 以 HTML 为主，支持正文、title/author/date/site name、links/images/tables/comments，以及 TXT/Markdown/JSON/XML/HTML 等输出；不应视为 PDF/OCR 方案。 | 可保存精确 response bytes，再保存 extractor output；metadata 与结构保留好，但受静态 HTML 质量影响。 | 本地 Python；HTTPX 为 BSD-3-Clause，Trafilatura 当前版本为 Apache-2.0（1.8.0 以前为 GPLv3+）。<https://www.python-httpx.org/quickstart/> <https://github.com/adbar/trafilatura> | 候选默认层，避免常驻 browser 开销；实际吞吐和成本未 benchmark，JS-rendered 页面不完整时按策略升级。 |
| **fetch + Readability（TS）** | `fetch` 取静态响应；Readability 需要 DOM，Node 场景通常配 `jsdom`。返回 `title/content/textContent/length/excerpt/byline/siteName/lang/publishedTime`；不负责 JS 执行、PDF 或 OCR。官方明确提醒它不负责清理不可信 HTML，应配 DOMPurify/CSP。 | `content` 是清理后的 HTML，适合作为正文 evidence，但 raw response、DOM 版本和 sanitizer 版本仍需另存。对复杂动态页只能先由 browser 生成 DOM。 | 本地 runtime；Readability 为 Apache-2.0，`fetch`/`jsdom` 的依赖条款需分别审查。<https://github.com/mozilla/readability> | TS 服务已有 DOM 处理栈时很合适；不要把 Readability 当 crawler 或 sanitizer。 |
| **Playwright** | Chromium/Firefox/WebKit，能运行 JS、监听 XHR/fetch、等待 selector、点击、下载和截取页面；`BrowserContext.route()` 可拦截 context 内请求。route 会关闭 HTTP cache，且 service worker 请求默认可能绕过 route，官方建议需要完整拦截时设 `serviceWorkers: 'block'`。 | 能保存 rendered DOM、截图、下载物和 response；但 browser DOM 不是原始 response，须同时记录 URL、DOM snapshot/hash、资源边界和触发动作。`page.pdf()`主要是生成打印 PDF；PDF 读取/OCR仍需独立 parser。 | 本地浏览器自动化，Apache-2.0；没有必须外传内容的服务依赖，代价转为浏览器 CPU/RAM/运维。<https://playwright.dev/docs/network> <https://playwright.dev/docs/api/class-browsercontext> <https://playwright.dev/docs/downloads> | 作为第二层 fallback，而非默认 fetch；适合 JS、交互和下载。 |
| **Crawl4AI** | Python async crawler，底层使用 Playwright；支持动态页、profiles/cookies/proxy、sitemap、多 URL BFS/DFS/Best-First、Markdown、links/citations、screenshots、PDF scraping。PDF 可逐页取 text/metadata/images，但官方 PDF 文档明确 OCR 不内置，扫描件需外接 OCR；复杂 layout、加密和 forms 需实测。 | Markdown 结构和 page-numbered PDF 输出对 LLM 友好；应额外保存 raw HTML/PDF、page number、block/order 和 extractor config，不能把 Markdown 当不可变原件。 | Apache-2.0；可 pip 或 Docker 自托管，官方 Docker API 默认 loopback/auth 等安全默认随版本变化，约需至少 4GB RAM（以 pinned release 文档为准）。文档所称 Cloud 是独立 hosted 路线，具体可用性/价格需确认。<https://github.com/unclecode/crawl4ai> <https://docs.crawl4ai.com/core/self-hosting/> <https://docs.crawl4ai.com/advanced/pdf-parsing/> | 需要批量 crawl、统一 Markdown 或 browser profile 时，比直接维护 Playwright 高阶封装省事；不是免费的 OCR 或 SSRF 防护替代品。 |
| **Firecrawl** | hosted API 与可自托管 open-source repo 并存；提供 scrape/crawl/map/actions、raw HTML/Markdown/screenshot/JSON，能处理 JS 页和 PDF。官方文档的 PDF parser 有 `fast/auto/ocr`，支持逐页 Markdown、layout blocks/bounding boxes、reading order/confidence；PDF 以每页 1 credit 计。 | 输出适合 agent，但仍应请求/保存 `rawHtml` 或原始文件及 page markers/blocks；screenshot/audio/video URL 有过期时间。`storeInCache` 默认 true，`maxAge` 默认约 2 天；`zeroDataRetention` 默认 false，需开通；`lockdown` 只读其 cache、不访问目标站点。 | 主 repo 为 AGPL-3.0；SDK/部分组件可为 MIT，需按目录核对。self-host 仍需数据库/queue/browser/运维，hosted 会把 URL/内容送至 Firecrawl 及其可选 proxy/LLM。文档还列出 `skipTlsVerification` 默认 true，生产应显式改为 false，并不能把其 Threat Protection 当成本地 egress policy。<https://github.com/firecrawl/firecrawl> <https://docs.firecrawl.dev/api-reference/endpoint/scrape> <https://docs.firecrawl.dev/features/document-parsing> | 适合低运维、动态页与文档处理候选；hosted 配置、费用和 self-host 功能差异应分别核验。 |
| **Jina Reader** | `https://r.jina.ai/<URL>` 提供 URL-to-Markdown；官方称支持 JS rendering、selectors、cookies、iframe/Shadow DOM、custom JS、PDF 和 image caption。也有 JSON/search 形态；不声称绕过 anti-bot 或 access control，cookie 只是复用既有 session。 | 快速得到 LLM-oriented Markdown，但 token budget 和服务端抽取会影响完整性；应把响应中 URL/title/timestamp 与本地 raw fetch/hash 一并记录。官方页面称通常 cache 约 5 分钟，`X-No-Cache` 绕过，DNT 请求不 cache/log；这些是服务控制，需合同/隐私审查。 | 主要是 hosted。官方页面将 ReaderLM-v2/jina-vlm 标为 CC BY-NC 4.0，并把商业 on-prem 描述为单独许可；不能据此假设可自由商用 self-host。<https://jina.ai/reader/> <https://jina.ai/en-US/api-dashboard/> | 低运维、复杂页/PDF 的 opt-in adapter；对敏感内容、强审计和严格 raw provenance 不应作为默认层。 |

## evidence、citation 与 hash 设计

- 每次 fetch 记录 `requested_url` 与每一跳 `redirect`；记录最终 URL、status、response headers、content length、媒体类型、解码方式、robots/ToS 决策、fetcher/extractor/browser 版本和配置。不要只记录搜索结果中的 URL。
- `raw_sha256` 对实际 response bytes 做 SHA-256；`extracted_sha256` 对规定 canonicalization 后的 UTF-8 正文做 SHA-256。canonicalization 要固定 Unicode normalization、换行和空白策略，否则同页不同 extractor 结果不应误认为相同。hash 用于发现变化，不是来源真实性或签名证明；若响应已有 HTTP `Content-Digest`/`Repr-Digest`，也应保留 header。
- 以 heading path + sibling index + normalized text 建立 HTML section；PDF 用 `page_number`、block/order、文本 offset。引用对象建议采用 W3C Web Annotation 的 `TextQuoteSelector`（`exact/prefix/suffix`）和 `TextPositionSelector`（`start/end`）组合，并把 `source`、representation/raw hash 和 retrieved_at 作为 state。quote 用于抗插入变化，position 用于快速定位，二者都需要重连失败标记。
- 给模型的 chunk 带上系统生成的内部 `evidence_id`，输出引用必须在受信任的 evidence 表中查验该 ID，并校验 quote/locator 对应关系；ID 本身不证明 claim 为真，也不能单独阻止 prompt injection。网页正文、HTML comments、alt text、OCR text 都标记为 **untrusted data**，不能混入 system/developer instruction。

## 安全与合规边界

1. **SSRF、redirect 与 DNS rebinding**：入口只接受 `http/https`，拒绝 `file:`, `data:`, `javascript:`、localhost、link-local、RFC1918、IPv4/IPv6 multicast、cloud metadata 地址。解析 hostname 的全部 A/AAAA，校验每个地址；每个 redirect hop 重新校验并限制次数。HTTPX 默认不跟随 redirect 是有利起点；browser 方案必须在代理/网络 namespace/firewall 处再做 egress allowlist，因为 page route 不是隔离边界，service worker 还可能绕过它。参考 OWASP SSRF 指南的 redirect、DNS rebinding/TOCTOU 和 egress controls。
2. **浏览器子资源**：默认 abort image/video/font/第三方 analytics，按需 allowlist 主域及必要 CDN；设 `serviceWorkers: 'block'`，限制 popup、WebSocket、下载大小、页面数和总 wall time。下载后以 MIME、magic bytes、大小和 decompressor limits 检查，不信任扩展名。
3. **robots 与 ToS**：遵守目标站点 robots policy 和声明的 user-agent；RFC 9309 明确 robots.txt 不是 access authorization，不能代替 auth，也不代表允许违反 ToS。robots 不可达时采用保守 fail-closed，并把决定写入 evidence；登录、paywall、MFA、反爬和版权限制不绕过。
4. **prompt injection**：OWASP LLM01:2025 把网页/文件中的 indirect prompt injection 作为重点风险。抓取内容仅是数据；不要让模型执行其中的指令、访问 credentials 或自行发起新网络请求。采用 schema validation、最小 tool privilege、敏感动作人工确认和 adversarial samples；Firecrawl 的 prompt-injection detection 可作信号，不能作为唯一防线。
5. **第三方数据流**：self-host 只减少 crawler provider 的外传，不会消除对目标网站、proxy、配置的 LLM、webhook、telemetry 的 outbound。Firecrawl/Jina 的 cache、DNT/ZDR 和区域选项是服务行为而非本地保证；敏感 URL 默认禁用 hosted adapter，必要时先脱敏并做供应商/合同审查。

## 验证样本、指标与成本变量

至少建立固定 corpus：静态正文与 malformed HTML；JS shell + delayed hydration + infinite scroll；cookie banner 与 selector 点击；redirect 到私网/IPv6/link-local、`file:`/`data:`、恶意下载和 service-worker 子资源；text PDF、多栏/表格/加密 PDF、扫描 PDF/OCR；robots disallow、登录/MFA/paywall；在正文、HTML comment、图片 alt 和 OCR 中放 indirect-injection marker；同一页面前后两次改写用于 anchor reattach。

每条样本比较：正文 precision/recall、heading/table/link 保真、PDF page/block 对齐、引用重连率、raw/extracted hash 稳定性、cache hit、首字节/总 latency、status/error 分类、CPU/RAM/browser concurrency、外连域名与 bytes。成本变量包括 browser RAM/并发、OCR/LLM token、hosted request/page/credit、proxy/anti-bot 附加费、raw/screenshot/PDF 存储、egress、SLA 与运维时间；本文不把任何当前价格当固定预算。

## Sources（primary docs）

- HTTPX redirects/timeouts/streaming：<https://www.python-httpx.org/quickstart/> · <https://github.com/encode/httpx/blob/master/docs/advanced/timeouts.md>
- Trafilatura：<https://github.com/adbar/trafilatura> · <https://github.com/adbar/trafilatura/blob/master/docs/corefunctions.md>
- Mozilla Readability：<https://github.com/mozilla/readability> · <https://github.com/mozilla/readability/blob/main/LICENSE.md>
- Playwright：<https://playwright.dev/docs/network> · <https://playwright.dev/docs/api/class-browsercontext> · <https://playwright.dev/docs/downloads>
- Crawl4AI：<https://github.com/unclecode/crawl4ai> · <https://docs.crawl4ai.com/core/self-hosting/> · <https://docs.crawl4ai.com/advanced/pdf-parsing/>
- Firecrawl：<https://github.com/firecrawl/firecrawl> · <https://docs.firecrawl.dev/api-reference/endpoint/scrape> · <https://docs.firecrawl.dev/features/document-parsing> · <https://docs.firecrawl.dev/contributing/self-host>
- Jina Reader：<https://jina.ai/reader/> · <https://jina.ai/en-US/api-dashboard/>
- robots：<https://www.rfc-editor.org/rfc/rfc9309>
- SSRF：<https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html>
- Prompt injection：<https://genai.owasp.org/llmrisk/llm01-prompt-injection/>
- Citation selectors：<https://www.w3.org/TR/annotation-model/>
- Digest/hash：<https://www.rfc-editor.org/rfc/rfc9530.html> · <https://docs.python.org/3/library/hashlib.html>
