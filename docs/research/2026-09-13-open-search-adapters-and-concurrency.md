---
title: SearXNG、Whoogle、YaCy 与公开 Search API MCP adapter 的高并发边界
status: researched
research_date: 2026-09-13
implementation_status: proposed / unvalidated
runtime_experiments: none
scope: 仅合法公开 API、自托管索引、上游限流与反爬风险；不评估绕过 CAPTCHA/IP block 的方案
---

# SearXNG、Whoogle、YaCy 与公开 Search API MCP adapter 的高并发边界

> 本报告只使用 provider 官方文档、官方项目文档/源码、官方 API 页面和 GitHub 源码快照。没有调用收费 API、没有注册 credentials、没有运行高并发实验，也没有把 HTML scraping 当成合法 public API 接入。所谓“未见”只表示本次核查的指定文件/commit 没有观察到该机制，不证明整个项目或外部部署绝对不存在该能力。
>
> 查证日期：2026-09-13。项目当前还受 [ADR-0002](../adr/0002-free-open-source-solutions-only.md) 的免费、开源自建约束；本文记录 provider/API 与 adapter 事实，不改变该 ADR。

## 1. Executive conclusions

1. **高并发的首选是 provider 官方 API，而不是提高 HTML scraping 的并发。** Mojeek、Brave 都有明确的公开 Search API；Google Custom Search JSON API 仍可由既有客户使用到 2027-01-01，但已关闭新客户；Microsoft Bing Search APIs 已于 2025-08-11 完全退役。官方 API 提供 quota/rate-limit 语义，应用应按 plan、response headers 和 429 做 admission control，而不是用 proxy pool 隐藏真实流量。[Mojeek API quickstart](https://www.mojeek.com/support/api/search/quickstart.html)；[Mojeek API plans](https://www.mojeek.com/services/search/web-search-api/)；[Brave Web Search API](https://api-dashboard.search.brave.com/app/documentation/web-search/get-started)；[Brave rate limiting](https://api-dashboard.search.brave.com/documentation/guides/rate-limiting)；[Google Custom Search availability](https://developers.google.com/custom-search/v1/overview)；[Microsoft Bing retirement](https://learn.microsoft.com/en-us/lifecycle/announcements/bing-search-api-retirement)。
2. **YaCy 才是这组对象中真正能把查询从外部 SERP 转到自有索引的路线。** 它由自托管 search index、crawler 和 scheduler 组成；`resource=local` 只查本 peer，`verify=cacheonly` 可限制为已有缓存/索引结果。`resource=global` 则会把查询扩展到 YaCy peers，不能混同于本地-only。[YaCy 官方 repository](https://github.com/yacy/yacy_search_server)；[YaCy Search API](https://wiki.yacy.net/index.php/Dev%3AAPIyacysearch)；[YaCy Crawler API](https://yacy.net/api/crawler/)。
3. **SearXNG 是 metasearch，不是自己的 Web index。** 自建 SearXNG 可以控制入口 limiter、连接池、proxy、engine suspension 和日志，但 query 仍会发给配置的上游。官方 limiter 的目标之一正是防止实例因为机器人流量触发上游 CAPTCHA/block；它不能消除上游反爬。[SearXNG README](https://github.com/searxng/searxng)；[limiter](https://docs.searxng.org/admin/searx.limiter.html)；[outgoing settings](https://docs.searxng.org/admin/settings/settings_outgoing.html)。
4. **Whoogle 当前不应作为 Google 的合法 public API adapter。** 其源码请求 `https://www.google.com/search?gbv=1&q=` 的 Google HTML，并解析非 JS 结果；proxy/Tor 是单个出口配置与 Tor identity recovery，不是 provider-approved API quota。README 已说明 Google blocked no-JS route，Google Custom Search BYOK 也不再是可行 fallback，并宣布停止 active work。[Whoogle README commit](https://github.com/benbusby/whoogle-search/blob/0543f86528678ab60a20b3049483975add6b6e40/README.md#L9-L12)；[request.py](https://github.com/benbusby/whoogle-search/blob/0543f86528678ab60a20b3049483975add6b6e40/app/request.py#L219-L264)；[CSE client](https://github.com/benbusby/whoogle-search/blob/0543f86528678ab60a20b3049483975add6b6e40/app/services/cse_client.py#L15-L16)。
5. **官方维护的 MCP adapter 已确认有 Mojeek 与 Brave；Google、Bing 本轮只确认到 community-maintained adapters。** [Mojeek/mojeek-search-mcp](https://github.com/Mojeek/mojeek-search-mcp) 和 [brave/brave-search-mcp-server](https://github.com/brave/brave-search-mcp-server) 分别位于 provider 自己的 GitHub organization。Google 的 [adenot/mcp-google-search](https://github.com/adenot/mcp-google-search)、[fbettag/google-custom-search-mcp](https://github.com/fbettag/google-custom-search-mcp) 与 Bing 的 [leehanchung/bing-search-mcp](https://github.com/leehanchung/bing-search-mcp) 是第三方仓库；本轮没有在 Google/Microsoft provider 官方文档或官方 provider organization 中识别到 canonical MCP repo。这个“未识别到”不是全网不存在的证明。
6. **MCP adapter 的 `async` 不等于高并发治理。** 本轮核查的 Mojeek、Brave、Google、Bing adapter 都是单次异步 HTTP 或 MCP handler；除 Bing community adapter 的简单本地计数器、fbettag Google adapter 的进程内 query cache 外，指定源码中未见 durable queue、backpressure、provider-aware semaphore、通用 retry/backoff 或 response cache。高并发应在 MCP 前增加 gateway：per-provider rate limiter、bounded queue、deadline、jittered retry、cache policy、usage ledger 和 circuit breaker。
7. **Proxy pool 不能作为“绕过上游反爬”的默认答案。** SearXNG 支持多 proxy round-robin 和 retry 时换 proxy；Whoogle 支持一个 proxy/Tor path；但对官方 API 应优先遵守 key/account quota，不用 IP rotation 绕过 429、CAPTCHA、条款或计费。只在 provider 条款允许、出口属于组织且有审计时使用 proxy 作为网络可用性/隔离手段。

## 2. “合法公开 API”口径

本文把下面三类严格分开：

- **Official API**：provider 明确给出 API endpoint、authentication 和 usage/quota 文档。Mojeek、Brave 属于此类；Google CSE 对既有客户属于此类；Bing Search API 只属于历史事实，当前已退役。
- **Self-hosted index API**：YaCy 的本地 HTTP/JSON API 查询 operator 自己维护的 index；这是自托管路线，不是调用 Google/Bing/Mojeek 的 public SERP API。
- **HTML/非官方 scraping**：Whoogle、SearXNG 的 `google.py`、`bing.py`、`mojeek.py`、`brave.py` 和 SearXNG 的 `google_cse.py` 当前快照均不应被当作 provider official API adapter。这里不对特定部署是否获得许可作法律判断，只说明它们不是 provider documented API；本项目“只覆盖合法公开 API 接入”的范围内不推荐把它们当生产 API route。

## 3. Provider API 事实

| Provider | 一手事实 | 高并发相关限制 | 本报告的可用性判断 |
|---|---|---|---|
| **Mojeek** | 官方 quickstart 给出 `https://api.mojeek.com/search?q=...&api_key=...&fmt=json`；官方产品页列出 Startup 5 queries/sec、100,000/day、最多 10 results；Business 10/sec、400,000/day、最多 40；Enterprise custom。 | 官方明确按 QPS/day 管理；缓存权利也有 plan 语义：非 Business/Enterprise 结果只能保存 1 小时用于 caching，Business 可存储结果。[产品页](https://www.mojeek.com/services/search/web-search-api/) | **推荐评估**。按 account plan 做 token bucket/leaky bucket；不要通过 proxy pool 超过 QPS。 |
| **Brave** | 官方 endpoint `https://api.search.brave.com/res/v1/web/search`，key 放 `X-Subscription-Token`；`count` 最大 20，`offset` 最大 9，并应依据 `more_results_available` 决定是否继续翻页。[Web Search docs](https://api-dashboard.search.brave.com/app/documentation/web-search/get-started) | 官方 rate-limit 文档规定 1-second sliding window，超限返回 429；每个 response 给 `X-RateLimit-Limit/Policy/Remaining/Reset`。示例是 1 request/sec 与 15,000/month；实际值应读取 plan headers，不能把示例硬编码为所有 plan。[Rate limiting](https://api-dashboard.search.brave.com/documentation/guides/rate-limiting) | **推荐评估**。在 gateway 根据 headers 做动态 admission control；只在 `more_results_available=true` 时翻页以减少无效调用。 |
| **Google Custom Search JSON API** | 官方 REST endpoint `https://www.googleapis.com/customsearch/v1`，必需 `key`、`cx`、`q`；最多先返回 100 results。[REST](https://developers.google.com/custom-search/v1/using_rest) | 官方当前说明 closed to new customers；既有客户可用至 2027-01-01，免费 100 queries/day、每日最多 10,000 queries。[Overview](https://developers.google.com/custom-search/v1/overview) | **仅既有客户的过渡候选**。不要为新项目设计依赖；按剩余 quota 限制并尽快替换。 |
| **Bing Search API** | Microsoft 官方宣布 Bing Search APIs 于 2025-08-11 retired；existing instances completely decommissioned，产品不再可用或接受新 customer signup。[retirement notice](https://learn.microsoft.com/en-us/lifecycle/announcements/bing-search-api-retirement) | 不应再设计 Bing Search API 的新并发、proxy 或 quota 方案。 | **当前不可作为合法 public API route**。社区 adapter 即使源码仍指向 endpoint，也不能当作可用生产依赖。 |

## 4. SearXNG：自托管控制面不等于自有 index

### 4.1 上游与 API

SearXNG 官方 README 将自身定义为 “a metasearch engine”，聚合多个 search services 和 databases；其 HTTP API 是具体 instance 的 `/search` 或 `/`，JSON/CSV/RSS 是否开启由 `settings.yml` 决定。[README](https://github.com/searxng/searxng)；[Search API](https://docs.searxng.org/dev/search_api.html)。因此：

- 自建 instance 能控制自己的入口、日志、出口和配置；
- 上游 engine 仍会看到 instance 的请求和出口；
- API `pageno` 只是 query continuation，不是 immutable snapshot，也没有 provider-neutral 的 quota 语义；
- 公共 instance 是否开放 JSON、如何记日志、是否被上游 block，取决于 operator，不能视作统一 SaaS API。

### 4.2 上游 engine source snapshot

以下均来自 SearXNG commit [`d4f00d15d4c2b8260124a9039b80bc9c1c26499b`](https://github.com/searxng/searxng/tree/d4f00d15d4c2b8260124a9039b80bc9c1c26499b/searx/engines)：

- `searx/engines/google.py`：metadata 是 `use_official_api=False`、`require_api_key=False`；通过 Google WML/XML/HTML 结果并检测 `sorry.google.com`、`/sorry`、HTTP 302 等 CAPTCHA/block。[source](https://github.com/searxng/searxng/blob/d4f00d15d4c2b8260124a9039b80bc9c1c26499b/searx/engines/google.py#L48-L56)；[CAPTCHA detection](https://github.com/searxng/searxng/blob/d4f00d15d4c2b8260124a9039b80bc9c1c26499b/searx/engines/google.py#L260-L280)。
- `searx/engines/bing.py`：metadata 是 `use_official_api=False`、`require_api_key=False`，请求 `https://www.bing.com/search` HTML；它不是 Bing Search API。[source](https://github.com/searxng/searxng/blob/d4f00d15d4c2b8260124a9039b80bc9c1c26499b/searx/engines/bing.py#L35-L52)。
- `searx/engines/mojeek.py`：metadata 是 `use_official_api=False`、`require_api_key=False`；注释明确第一页 `s=0` 会触发 rate-limit，使用 HTML search。[source](https://github.com/searxng/searxng/blob/d4f00d15d4c2b8260124a9039b80bc9c1c26499b/searx/engines/mojeek.py#L18-L28)；[rate-limit comment](https://github.com/searxng/searxng/blob/d4f00d15d4c2b8260124a9039b80bc9c1c26499b/searx/engines/mojeek.py#L69-L78)。
- `searx/engines/brave.py`：metadata 是 `use_official_api=False`、`require_api_key=False`，访问 `search.brave.com` HTML；这与同仓库的 `braveapi.py` 不同。[HTML engine](https://github.com/searxng/searxng/blob/d4f00d15d4c2b8260124a9039b80bc9c1c26499b/searx/engines/brave.py#L147-L178)；[official API engine](https://github.com/searxng/searxng/blob/d4f00d15d4c2b8260124a9039b80bc9c1c26499b/searx/engines/braveapi.py#L41-L60)。
- `searx/engines/braveapi.py` 才是本快照中明确的 official API route：`use_official_api=True`、`require_api_key=True`、endpoint `https://api.search.brave.com/res/v1/web/search`、header `X-Subscription-Token`。[source](https://github.com/searxng/searxng/blob/d4f00d15d4c2b8260124a9039b80bc9c1c26499b/searx/engines/braveapi.py#L41-L94)。
- `searx/engines/google_cse.py` 虽然名字包含 CSE，但 metadata 是 `use_official_api=False`、`require_api_key=False`，请求 `www.google.com/cse/cse.js` 并只缓存 token 1 小时；不能把它当作 Google Custom Search JSON API。[source](https://github.com/searxng/searxng/blob/d4f00d15d4c2b8260124a9039b80bc9c1c26499b/searx/engines/google_cse.py#L25-L82)。
- 本快照 `searx/engines` 目录可见 `braveapi.py`、`google_cse.py`，但未见 `mojeekapi.py` 或 `bingapi.py`。这是该 commit 的目录观察，不是对所有版本、第三方 plugin 或未来代码的不存在证明。[目录](https://github.com/searxng/searxng/tree/d4f00d15d4c2b8260124a9039b80bc9c1c26499b/searx/engines)。

### 4.3 可用于高并发的控制点

- **入口 limiter**：官方 limiter 依赖 Valkey，启用方式为 `server.limiter: true` 与 `valkey.url`；按 IP/行为识别可疑 bot，目标包括减少上游 CAPTCHA/block。它没有在文档中给出统一固定 QPS；不能从 limiter 文档推导“每 IP N QPS”。[limiter docs](https://docs.searxng.org/admin/searx.limiter.html)。
- **连接池与 timeout**：官方 outgoing settings 提供 `request_timeout`、`max_request_timeout`、`pool_connections`，并支持 HTTP/SOCKS proxies 与 Tor；engine 可单独覆盖 `max_connections`、timeout、retry-on-HTTP-error。[outgoing](https://docs.searxng.org/admin/settings/settings_outgoing.html)；[engine settings](https://docs.searxng.org/admin/settings/settings_engines.html)。
- **proxy rotation**：本 commit `searx/network/network.py` 的 `get_proxy_cycles()` 把一个 proxy URL 或 list 做 cycle；`call_client()` 在配置允许的 HTTP error 或连接断开时可 retry，client 使用 `max_clients` 建立异步连接池。[network.py](https://github.com/searxng/searxng/blob/d4f00d15d4c2b8260124a9039b80bc9c1c26499b/searx/network/network.py#L146-L159)；[retry](https://github.com/searxng/searxng/blob/d4f00d15d4c2b8260124a9039b80bc9c1c26499b/searx/network/network.py#L264-L305)；[client pool/proxy](https://github.com/searxng/searxng/blob/d4f00d15d4c2b8260124a9039b80bc9c1c26499b/searx/network/client.py#L49-L99)。
- **限制**：所核查 network/engine source 中未见通用 durable job queue 或 response cache；`max_clients`/`max_connections` 是连接并发，不是 provider quota。自动 retry 也不应用于 403/CAPTCHA 或违反 upstream policy 的情形。

**结论**：若必须用 SearXNG，优先自建 instance、启用 limiter、按 engine 设连接与 timeout、只启用有明确 API/terms 的 engine，并让 gateway 负责 provider-level rate limit。不能把 SearXNG 的 proxy list 当作规避上游限制的许可，也不能把自建 instance 当成自有 index。

## 5. Whoogle：Google HTML scraping 与项目终止状态

### 5.1 实际访问方式

Whoogle 的 `app/request.py` 在 commit `0543f86528678ab60a20b3049483975add6b6e40` 设置：

```text
https://www.google.com/search?gbv=1&q=
https://www.google.com/search?udm=2&q=
```

并用 HTTP client 请求 Google HTML；proxy 使用 `WHOOGLE_PROXY_*` 组合为一个 `http/https/socks4/socks5` proxy URL，Tor 通过本地 SOCKS5/控制端口换 identity。[request.py](https://github.com/benbusby/whoogle-search/blob/0543f86528678ab60a20b3049483975add6b6e40/app/request.py#L219-L264)。

源码对 CAPTCHA 的恢复是 Tor-specific：检测到 CAPTCHA 后用新 Tor identity 递归重试，最多 10 次；在指定文件中未见 HTTP 429 的 `Retry-After`、指数 backoff、token bucket 或 provider quota 调度。[request.py](https://github.com/benbusby/whoogle-search/blob/0543f86528678ab60a20b3049483975add6b6e40/app/request.py#L398-L440)。

README 的历史说明也写明：Google blocked no-JS results；Google Custom Search BYOK 是最后 fallback，但现在 “no longer a workable alternative”，并宣布 active work 结束。[README notice](https://github.com/benbusby/whoogle-search/blob/0543f86528678ab60a20b3049483975add6b6e40/README.md#L9-L12)；[BYOK section](https://github.com/benbusby/whoogle-search/blob/0543f86528678ab60a20b3049483975add6b6e40/README.md#L538-L548)。仓库 GitHub metadata 当前标记 archived、MIT；这支持“参考/历史项目”判断，不支持生产维护承诺。

### 5.2 cache、queue、fallback 的实际边界

- `app/routes.py` 设置 `Cache-Control: max-age=86400`，这是 HTTP response header，不等于 server-side search-result cache；同文件的搜索执行是 request 内同步 `generate_response()`。[routes.py](https://github.com/benbusby/whoogle-search/blob/0543f86528678ab60a20b3049483975add6b6e40/app/routes.py#L177-L185)；[sync search/fallback](https://github.com/benbusby/whoogle-search/blob/0543f86528678ab60a20b3049483975add6b6e40/app/routes.py#L351-L421)。
- 所核查 `request.py`/`routes.py` 中未见 search-result cache、durable queue、worker pool、async search scheduler。README 说明的 cache 主要是生成的 User-Agent pool；[README UA cache](https://github.com/benbusby/whoogle-search/blob/0543f86528678ab60a20b3049483975add6b6e40/README.md#L848-L850)。
- `WHOOGLE_FALLBACK_ENGINE_URL` 是 CAPTCHA/internal error/rate-limit 后 redirect，不是上游 API fallback queue。[fallback config](https://github.com/benbusby/whoogle-search/blob/0543f86528678ab60a20b3049483975add6b6e40/README.md#L497-L498)。
- Whoogle 另有 `app/services/cse_client.py`，使用官方 endpoint `https://www.googleapis.com/customsearch/v1`、`key`、`cx` 和 `num<=10`，但项目 README 已将该 BYOK 路线标为不再可行；它不改变 Whoogle 默认 HTML scraping 的性质。[CSE client](https://github.com/benbusby/whoogle-search/blob/0543f86528678ab60a20b3049483975add6b6e40/app/services/cse_client.py#L1-L16)；[request/call](https://github.com/benbusby/whoogle-search/blob/0543f86528678ab60a20b3049483975add6b6e40/app/services/cse_client.py#L94-L156)。

**结论**：Whoogle 不应作为本项目的高并发路线。proxy/Tor/UA rotation 不能替代 official API，也不应被用来绕过 Google 的 CAPTCHA、IP ban 或 rate limit；若有 Google CSE 既有客户资格，应直接写 provider API adapter/gateway，而不是延续 Whoogle scraping。

## 6. YaCy：自托管 index、crawler queue 与 cache-first 查询

YaCy 官方 repository 将项目描述为 Distributed Peer-to-Peer Web Search Engine and Intranet Search Appliance，并包含 search-index server、web interface、crawler 和 scheduler；可作为 private/intranet portal，节点也可选择 P2P/cluster 或 local-only 模式。[官方 repository](https://github.com/yacy/yacy_search_server)；[官方 docs](https://yacy.net/docs/)。

### 6.1 查询路径

官方 Search API：

- `/yacysearch.json` 或 `/yacysearch.rss`；
- `resource=local` 只查询当前 peer，`resource=global` 查询 YaCy network peers；
- `maximumRecords` 未认证时限制为 10；
- `verify=false` 可跳过 URL verification/snippet retrieval；`cacheonly` 只使用可用 cache，适合“查询不再向外发新抓取”的 cache-first 模式；
- `startRecord`/`maximumRecords` 提供 pagination。[Search API](https://wiki.yacy.net/index.php/Dev%3AAPIyacysearch)。

因此，若目标是避免高并发触发 Google/Bing/Mojeek anti-bot，应采用 `resource=local` + 自己的 crawl policy/index，并把 fresh crawling 与 query serving 分开。`resource=global` 虽然可以扩大召回，但会依赖其他 peers 的网络行为，不能当作 private local index。

### 6.2 爬取与队列

官方 Crawler API 通过 `/Crawler_p.html` 启动和监控 crawl profile，支持 URL、sitemap、sitelist、local file，并按 profile 跟踪运行/terminated 状态；还提供 max pages per domain、max checked pages/domain、recrawl 等限制。[Crawler API](https://yacy.net/api/crawler/)。官方 JavaDoc 将 `CrawlQueues` 定义为 crawler queue 管理组件，说明 YaCy 的 queue/scheduler 是产品组成部分，而不是 MCP adapter 临时加的 async wrapper。[CrawlQueues Javadoc](https://yacy.net/api/javadoc/net/yacy/crawler/data/CrawlQueues.html)。

**边界**：YaCy 自托管 index 只能覆盖已 crawl、已允许抓取且可解析的内容；它不提供 Web-wide freshness 保证。仍需遵守目标站点的 robots、访问条件、版权和 crawl policy；不要把“本地索引”写成“无需上游合规”。

## 7. MCP adapter 一手源码对照

### 7.1 Provider-owned adapters

| Adapter | 维护证据/许可证 | 实际 endpoint 与 key | adapter 内已观察到的并发控制 | 结论 |
|---|---|---|---|---|
| **Mojeek/mojeek-search-mcp** | Repo 位于 `Mojeek` organization，GitHub metadata/license 为 MIT；commit `08e1418b305e88819bde0de1802ec46243dc4f4d`。[repo](https://github.com/Mojeek/mojeek-search-mcp)；[commit](https://github.com/Mojeek/mojeek-search-mcp/tree/08e1418b305e88819bde0de1802ec46243dc4f4d) | `https://api.mojeek.com/search`；`MOJEEK_API_KEY` 作为 query `api_key`，固定 `fmt=json`；tool `mojeek_search`。[source](https://github.com/Mojeek/mojeek-search-mcp/blob/08e1418b305e88819bde0de1802ec46243dc4f4d/src/index.ts#L6-L6)；[request](https://github.com/Mojeek/mojeek-search-mcp/blob/08e1418b305e88819bde0de1802ec46243dc4f4d/src/index.ts#L97-L158) | `fetch` 是 async；在该 source 中未见 rate limiter、retry/backoff、cache、proxy pool、semaphore、queue 或 scheduler。 | provider-owned、API 路线清晰；必须在外层按 Mojeek plan QPS/day 限速。 |
| **brave/brave-search-mcp-server** | Repo 位于 Brave organization，package metadata 为 MIT、Brave Software, Inc.；commit `2cf96460c1f78b24e3967b4a60263e7277f87116`。[repo](https://github.com/brave/brave-search-mcp-server)；[package](https://github.com/brave/brave-search-mcp-server/blob/2cf96460c1f78b24e3967b4a60263e7277f87116/package.json) | `https://api.search.brave.com` + endpoint path；`BRAVE_API_KEY`/file，header `X-Subscription-Token`；默认 stdio，可选 HTTP。[API source](https://github.com/brave/brave-search-mcp-server/blob/2cf96460c1f78b24e3967b4a60263e7277f87116/src/BraveAPI/index.ts#L44-L53)；[auth/request](https://github.com/brave/brave-search-mcp-server/blob/2cf96460c1f78b24e3967b4a60263e7277f87116/src/BraveAPI/index.ts#L44-L117) | source 有注释 `Improve rate-limit logic to support self-throttling and n-keys`，当前 `checkRateLimit()` 仍被注释；该 source 中未见 timeout、retry、cache、proxy、semaphore、queue。 | provider-owned；把 Brave response rate headers 透传到 gateway，自行做 self-throttling。 |

### 7.2 Community adapters（只作为源码样本，不标成官方）

| Adapter | 实际 API 与认证 | 源码中观察到的能力 | 关键限制 |
|---|---|---|---|
| **adenot/mcp-google-search** | `https://www.googleapis.com/customsearch/v1`；`GOOGLE_API_KEY` 和 `GOOGLE_SEARCH_ENGINE_ID` 作为 `key`/`cx`；`search` + `read_webpage`。[source](https://github.com/adenot/mcp-google-search/blob/ddbf0dbab75cdcf867a6ed63f0d5039a2288c5a6/src/index.ts#L14-L18)；[CSE call](https://github.com/adenot/mcp-google-search/blob/ddbf0dbab75cdcf867a6ed63f0d5039a2288c5a6/src/index.ts#L97-L105) | `axios` async；读取 `HTTPS_PROXY/HTTP_PROXY`，支持一个 proxy URL；`search` 默认 5、上限 10；`read_webpage` 也走 proxy。[source](https://github.com/adenot/mcp-google-search/blob/ddbf0dbab75cdcf867a6ed63f0d5039a2288c5a6/src/index.ts#L17-L40)；[read](https://github.com/adenot/mcp-google-search/blob/ddbf0dbab75cdcf867a6ed63f0d5039a2288c5a6/src/index.ts#L214-L229) | 指定 source 中未见 rate limiter、retry/backoff、cache、timeout、queue、semaphore 或 concurrency cap。 | Google API 本身已 closed to new customers，不能作为新项目默认依赖。 |
| **fbettag/google-custom-search-mcp** | 使用 Google `customsearch.cse().list(q,cx,num)`；service-account credentials；`google_search` 和 `clear_search_cache`。[source](https://github.com/fbettag/google-custom-search-mcp/blob/321c7e1d5fd1054322e90df2030722f379493a58/server.py#L52-L53) | 有进程内 dict cache，key 为 `query:num_results`，并暴露 clear cache；MCP function 标记 async，但 Google client call 本身是 synchronous。[cache](https://github.com/fbettag/google-custom-search-mcp/blob/321c7e1d5fd1054322e90df2030722f379493a58/server.py#L52-L97)；[clear](https://github.com/fbettag/google-custom-search-mcp/blob/321c7e1d5fd1054322e90df2030722f379493a58/server.py#L230-L234) | 指定 source 中未见 provider-aware rate limiter、retry/backoff、proxy、queue 或 concurrency cap。 | 展示了 adapter-local cache 不能替代 quota governance；cache TTL/持久化仍应按 Google 条款核实。 |
| **leehanchung/bing-search-mcp** | `BING_API_URL` 默认 `https://api.bing.microsoft.com/`；`BING_API_KEY` 放 `Ocp-Apim-Subscription-Key`；web/news/image endpoints。[source](https://github.com/leehanchung/bing-search-mcp/blob/887097adcc0c2b9de67843bed072245afc05dd70/mcp_server_bing/server.py#L66-L71)；[calls](https://github.com/leehanchung/bing-search-mcp/blob/887097adcc0c2b9de67843bed072245afc05dd70/mcp_server_bing/server.py#L108-L137) | `httpx.AsyncClient`、10 秒 timeout；本地全局 counter 设定 1 request/sec、15,000/month；指定 source 中未见 retry/backoff、cache、proxy、semaphore、queue。[rate code](https://github.com/leehanchung/bing-search-mcp/blob/887097adcc0c2b9de67843bed072245afc05dd70/mcp_server_bing/server.py#L71-L90) | Microsoft 已宣布 Bing Search APIs 完全退役；这个 adapter 的源码事实不等于当前 endpoint 可用。 |

**MCP 维护状态结论**：Mojeek/Brave 行的“provider-owned”来自 repository organization 和 package/repo metadata；Google/Bing 行明确标为 community。没有把 GitHub stars、MCP directory listing 或 package publish 当作 provider maintenance 证据。对“没有官方 Google/Bing MCP adapter”的表述仅限本轮核查范围：官方 provider 文档给出 API，但没有在本轮找到其 canonical MCP repository；不写成全网不存在。

## 8. 高并发时的合规控制方案

### 8.1 推荐的 gateway 结构

```text
MCP tools
  -> provider adapter (Mojeek / Brave / existing Google CSE)
  -> policy gateway
       - provider/account allowlist
       - per-provider token bucket or sliding-window limiter
       - bounded async queue + backpressure
       - deadline / cancellation
       - response-header quota ledger
       - cache with provider-approved TTL
       - retry only for transient 429/5xx/timeouts, jittered backoff
       - circuit breaker and partial result
  -> official API or YaCy local index
```

这是一项 **proposed / unvalidated** 架构建议，不是本仓库已实现 contract。关键规则：

1. **先限速再发请求**：每个 provider/account/key 独立计数，不按所有 provider 共用一个全局并发数。Mojeek 用 plan QPS/day；Brave 读取 `X-RateLimit-*`；Google 记录 daily quota；Bing 不接入新任务。
2. **并发上限不等于 QPS**：HTTP connection pool 只限制 in-flight connections；必须另有 rate limiter 和 queue。SearXNG 的 `max_clients`/`max_connections` 只能解决连接资源，不会自动满足上游 quota。
3. **只在有收益时翻页**：Brave 依据 `more_results_available`；Google/Mojeek/Bing 等 provider 的 page/offset 由各自 API 语义控制。避免在高并发下盲目 fan-out pages。
4. **重试要保守**：429、timeout、部分 5xx 可在 deadline 内 exponential backoff + jitter；403、CAPTCHA、invalid key、quota exhausted 不应盲重试。若 provider 提供 `Retry-After` 或 rate reset headers，优先使用它们。
5. **cache 必须受条款约束**：Mojeek 官方明确不同 plan 的 storage rights；不能因为 adapter 有 dict cache 就默认可以长期保存结果。应至少记录 `provider`、`account/plan`、`query_hash`、`retrieved_at`、`expires_at` 和 cache policy version。
6. **durable queue 用于 job，而不是掩盖超额**：队列应在 admission 前阻止超额请求，支持取消、deadline、重启恢复、poison job 和 partial result；不要用无限 queue 把 provider 429 延迟成更晚的 429。
7. **proxy 只做合规网络治理**：允许的组织 proxy、Tor 或 egress isolation 可以解决网络可达性和隔离，但不得用于绕过 API key quota、CAPTCHA、IP block 或 provider terms。对 official API，固定可审计出口通常比 rotating proxy 更容易做 abuse investigation。
8. **把 index 与 live Search 分层**：大量重复/稳定 query 优先由 YaCy local index 或条款允许的 cache 服务；需要 fresh Web Search 的 query 才进入 provider quota。YaCy crawler 作为后台 crawl queue，查询面不要同步触发无限 crawl。

### 8.2 四种路线的推荐顺序

| 场景 | 首选 | 退化路径 | 不建议 |
|---|---|---|---|
| 新项目、需要公开 Web index、可申请 API key | Brave API 或 Mojeek API + gateway | YaCy local index 处理重复/内部内容 | Whoogle/Google/Bing HTML scraping |
| 已有 Google CSE customer 且必须 Google 结果 | 直接 Google CSE adapter + daily quota/cache policy | YaCy 或 Brave/Mojeek 作为 provider fallback | 用 proxy pool 延长 Google HTML scraping |
| 大量重复查询、内部/受控内容 | YaCy local index + scheduled crawler + `resource=local`/`cacheonly` | 明确允许的 API refresh job | 每个 query 都 fan-out 到外部 engines |
| 需要 metasearch、多上游聚合 | 自建 SearXNG + limiter + 只启用合规 API engines | provider-specific gateway fallback | 公共 SearXNG instance、无审计 proxy rotation |

## 9. 证据边界与未完成项

- 没有对任何 provider 做真实 QPS、429、CAPTCHA、proxy pool 或 cache-hit benchmark；文中的数字来自官方 plan/docs 或源码常量，不是本项目测量。
- “SearXNG snapshot 未见 `mojeekapi.py`/`bingapi.py`”“adapter source 未见 queue/cache/retry”只适用于指定 commit/文件；不能写成项目所有 deployment 永远没有该功能。
- 没有验证 Google CSE existing account 的当前合同、具体客户迁移安排、实际 2027-01-01 行为；以 Google official overview 为准，采购/迁移前需重新核实。
- 没有把 provider terms、网页版权、robots、结果长期存储授权扩展成法律意见。Mojeek 官方已明确 API 不授予下游网页第三方内容权利，读取结果 URL 的正文仍需遵守发布者条款。[Mojeek API product page](https://www.mojeek.com/services/search/web-search-api/)。
- 没有检查所有第三方 MCP adapter，也没有把 repository owner 之外的维护承诺推断出来。要上线前应锁定 commit、做 license/security review、凭据 secret scanning、HTTP timeout/cancellation test、quota failure test、cache retention test 和目标 host MCP conformance。

## 10. Primary source ledger

| ID | Owning source | URL / commit | 本报告使用的事实 | 状态/限制 |
|---|---|---|---|---|
| S1 | SearXNG maintainers | [repo](https://github.com/searxng/searxng)、[Search API](https://docs.searxng.org/dev/search_api.html) | metasearch、instance HTTP API、格式与 pagination | provider/instance 行为和上游条款仍需逐 engine 核实 |
| S2 | SearXNG maintainers | [limiter](https://docs.searxng.org/admin/searx.limiter.html)、[outgoing](https://docs.searxng.org/admin/settings/settings_outgoing.html)、[engines](https://docs.searxng.org/admin/settings/settings_engines.html) | Valkey limiter、pool/timeout/proxy/Tor、engine overrides | 没有统一固定 QPS；不替代 live experiment |
| S3 | SearXNG source | [commit d4f00d15](https://github.com/searxng/searxng/tree/d4f00d15d4c2b8260124a9039b80bc9c1c26499b) | Google/Bing/Mojeek/Brave HTML 与 Brave API metadata；network proxy/retry/pool | snapshot facts，不代表所有 release |
| S4 | Whoogle maintainers | [README commit](https://github.com/benbusby/whoogle-search/blob/0543f86528678ab60a20b3049483975add6b6e40/README.md)、[request.py](https://github.com/benbusby/whoogle-search/blob/0543f86528678ab60a20b3049483975add6b6e40/app/request.py) | Google HTML、proxy/Tor、CAPTCHA retry、project end-of-road、UA cache | archived project；不作为生产推荐 |
| S5 | YaCy maintainers | [repo](https://github.com/yacy/yacy_search_server)、[docs](https://yacy.net/docs/)、[Crawler API](https://yacy.net/api/crawler/) | own index、crawler/scheduler、local/global、self-hosted | crawl coverage/freshness 未测 |
| S6 | YaCy official API docs | [Search API](https://wiki.yacy.net/index.php/Dev%3AAPIyacysearch)、[CrawlQueues Javadoc](https://yacy.net/api/javadoc/net/yacy/crawler/data/CrawlQueues.html) | JSON/RSS、resource、cacheonly、max records、queue | Wiki/Javadoc 的版本对应关系需在部署时复核 |
| S7 | Mojeek | [quickstart](https://www.mojeek.com/support/api/search/quickstart.html)、[API product](https://www.mojeek.com/services/search/web-search-api/) | endpoint/key、QPS/day、storage/cache rights、AI/LLM use | plan/contract 可能变化 |
| S8 | Brave | [Web Search](https://api-dashboard.search.brave.com/app/documentation/web-search/get-started)、[rate limiting](https://api-dashboard.search.brave.com/documentation/guides/rate-limiting) | endpoint/header、pagination、sliding window、429、rate headers | plan-specific limits must be read from headers |
| S9 | Google | [REST](https://developers.google.com/custom-search/v1/using_rest)、[overview](https://developers.google.com/custom-search/v1/overview) | `key`/`cx`、endpoint、100/day、closed to new customers、2027-01-01 | existing-customer transition not tested |
| S10 | Microsoft | [Bing retirement notice](https://learn.microsoft.com/en-us/lifecycle/announcements/bing-search-api-retirement) | 2025-08-11 complete decommissioning | current Bing Search API route not viable |
| S11 | Mojeek provider repo | [repo](https://github.com/Mojeek/mojeek-search-mcp)、[commit](https://github.com/Mojeek/mojeek-search-mcp/tree/08e1418b305e88819bde0de1802ec46243dc4f4d)、[source](https://github.com/Mojeek/mojeek-search-mcp/blob/08e1418b305e88819bde0de1802ec46243dc4f4d/src/index.ts) | official-owned MCP endpoint/key/tool；source 未见 rate/cache/queue | adapter snapshot |
| S12 | Brave provider repo | [repo](https://github.com/brave/brave-search-mcp-server)、[commit](https://github.com/brave/brave-search-mcp-server/tree/2cf96460c1f78b24e3967b4a60263e7277f87116)、[source](https://github.com/brave/brave-search-mcp-server/blob/2cf96460c1f78b24e3967b4a60263e7277f87116/src/BraveAPI/index.ts) | official-owned MCP endpoint/key/tool；rate TODO；source 未见 queue/cache/retry | adapter snapshot |
| S13 | Community Google adapter | [adenot commit](https://github.com/adenot/mcp-google-search/tree/ddbf0dbab75cdcf867a6ed63f0d5039a2288c5a6)、[source](https://github.com/adenot/mcp-google-search/blob/ddbf0dbab75cdcf867a6ed63f0d5039a2288c5a6/src/index.ts) | Google CSE key/cx、single proxy、async axios | community repo；未见治理机制只限该 source |
| S14 | Community Google adapter | [fbettag commit](https://github.com/fbettag/google-custom-search-mcp/tree/321c7e1d5fd1054322e90df2030722f379493a58)、[source](https://github.com/fbettag/google-custom-search-mcp/blob/321c7e1d5fd1054322e90df2030722f379493a58/server.py) | official client、process cache、clear cache | cache policy/contract 仍需核实 |
| S15 | Community Bing adapter | [repo](https://github.com/leehanchung/bing-search-mcp)、[commit](https://github.com/leehanchung/bing-search-mcp/tree/887097adcc0c2b9de67843bed072245afc05dd70)、[source](https://github.com/leehanchung/bing-search-mcp/blob/887097adcc0c2b9de67843bed072245afc05dd70/mcp_server_bing/server.py) | Bing endpoint/key、1/s + 15k/month local counter、async httpx | API 已被 Microsoft retired；不能上线依赖 |

## 11. Final position

在当前约束下，最稳妥的路线是：**Mojeek 或 Brave official API adapter + provider-aware gateway + bounded async queue/cache + YaCy local index for repeated or internal search**。SearXNG 只在需要自托管 metasearch、且能接受 query 外发到合法上游时评估；启用 limiter、连接池和审计，不把 proxy rotation 当反爬绕过。Whoogle 作为历史 Google HTML scraping 项目保留在研究范围内，但不作为合法 public API 或高并发生产依赖。Google CSE 仅对已有客户作过渡候选，Bing Search API 当前排除。

## 12. Tavily、Exa、Firecrawl、Jina provider 补充

本节补充官方 vendor MCP 和 API 的核验。RPM/QPS 是 throughput quota，不等于 in-flight concurrency；没有公开证据的能力保留为 evidence gap。

| Provider | 一手可确认的 quota/并发 | native 能力 | MCP/adapter 边界 | 判断 |
|---|---|---|---|---|
| Tavily | Development 100 RPM；Production 1,000 RPM；Crawl 100 RPM；Research task creation 20 RPM；429 + `retry-after` | credits billing；本轮未找到独立 index、通用 cache TTL 或 provider key rotation | 官方 remote/local MCP；源码直接 POST Search/Extract/Crawl/Map/Research；未见通用并发池 | 高并发依赖 paid quota，caller 仍需 token bucket、backoff、dedupe |
| Exa | `/search` 10 QPS、`/contents` 100 QPS、`/answer` 10 QPS；Agent 另有 50 active runs | `maxAgeHours=0` fresh、`-1` cache-only | hosted MCP 有独立匿名 quota；`mcp-remote` 只是 transport bridge；未见 key rotation | 按 endpoint 分开调度；Agent concurrency 不能外推为 Search 并发 |
| Firecrawl | Crawl 支持 `maxConcurrency`；Browser 有 plan-level concurrency；429 区分 rate/concurrency | native `maxAge`、`storeInCache`、Lockdown cache-only、provider proxy | MCP 另有约 15 分钟 response cache；不等于独立 Web index 或统一 API SLA | 按 Crawl/Browser/Extract 分开调度，MCP cache 不能当 upstream capacity |
| Jina Reader/Search | Reader 与 `s.jina.ai` Search 分 endpoint/plan RPM；未找到统一 in-flight ceiling | Reader 支持 `X-No-Cache`、`X-Proxy-Url`；Search architecture 依赖 external providers | MCP SERP source 有约 1 小时 cache；request-scoped server/batch 只是 adapter 行为 | Reader 与 Search 使用不同 scheduler，不能把 Search 当成已证实的独立 index |

证据：

- [Tavily rate limits](https://docs.tavily.com/documentation/api/rate-limits)；[Tavily MCP](https://github.com/tavily-ai/tavily-mcp)
- [Exa rate limits](https://exa.ai/docs/reference/rate-limits)；[Exa MCP](https://github.com/exa-labs/exa-mcp-server)
- [Firecrawl errors](https://docs.firecrawl.dev/api-reference/errors)；[Firecrawl crawl concurrency](https://docs.firecrawl.dev/features/crawl)；[Firecrawl MCP](https://github.com/firecrawl/firecrawl-mcp-server)
- [Jina Reader](https://jina.ai/reader/)；[Jina MCP](https://github.com/jina-ai/MCP)

这组证据进一步支持：官方 vendor MCP 普遍是 thin adapter；高并发来自 provider quota、managed service、endpoint-specific scheduler 或自有 index，而不是 MCP server 自动 key rotation、无限并发或通用 response cache。
