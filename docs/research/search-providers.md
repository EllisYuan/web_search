# 通用深度 Web Search MCP：Provider 与现成 Search MCP 选型

> **查证日期：2026-09-08。** 本报告只讨论 Web search provider、现成 Search MCP 与 build-vs-buy。这里的 **Search** 是返回结果、URL、摘要和元数据；**Extract/Fetch** 是读取指定网页正文；**hosted research** 是服务商代为多轮搜索、阅读和综合。三者的计费、延迟、证据可追溯性和隐私边界不同，不能混为同一能力。未调用收费 API、未注册、未接触 credentials；没有编造 benchmark。

## 结论

1. **通用生产候选 shortlist：Brave、Tavily、Exa、Parallel。** Brave 的产品定位包含独立 Web index；Tavily 是 Search + Extract/Map/Crawl 的 Agent 工具箱；Exa 的文档定位包含 semantic search、内容获取和日期/域名过滤；Parallel 偏 task-oriented Search + Extract。
2. **需要真实 SERP、多个 engine、语言/地区参数时选 SerpAPI。** 它是搜索结果 API 聚合层，不是一个可直接等同于独立 index 的 provider。
3. **隐私、自托管和可控性优先时可评估 SearXNG。** 但它是 metasearch：自托管实例仍会把 query 转发给配置的上游 engine；代价是实例、上游 engine、限流、代理、监控和合规由自己负责。
4. **中文与 freshness 不能只看 vendor marketing。** SerpAPI 的 Baidu/Google 参数最明确；Brave、Tavily、SearXNG 有显式语言或时间参数；Exa/Parallel 的公开文档没有同等明确的中文过滤能力，必须做自己的中文评测。
5. **Search MCP 应当视为 adapter/transport，不是数据授权。** MCP server 的 MIT 许可证不覆盖后端 provider 的 API terms、网页版权、缓存和训练限制。
6. **Google/Bing 原生 API 不适合作为新项目默认依赖。** Google Custom Search JSON API 已停止新客户接入，并计划在 2027-01-01 结束现有服务；Bing Search APIs 已于 2025-08-11 退役。[Google 官方说明](https://developers.google.com/custom-search/v1/overview)；[Microsoft 官方说明](https://learn.microsoft.com/en-us/lifecycle/announcements/bing-search-api-retirement)（均访问日期：2026-09-08）。

## 先固定选型口径

**Search 结果质量不等于正文可用性。** 一个 provider 可能能找到正确 URL，却只返回短摘要；另一个 provider 可能擅长抓正文，却不保证结果页的排序或地区相关性。因此评测至少要拆成三段：第一段测 URL 召回与排序，第二段测正文抓取、清洗和引用定位，第三段才测多轮 Research 是否能把证据组织成答案。把三段合并成一个“回答质量”分数，会掩盖最贵的环节究竟发生在 Search、Extract 还是 hosted research。

**Freshness 也有不同含义。** `freshness` 或 `time_range` 通常只是对索引记录的日期做过滤，不代表网页已经实时抓取；`publish_date` 也可能缺失或来自上游元数据。强时效场景应同时记录查询时间、结果日期、抓取时间和正文中的更新时间，并设计无结果、旧缓存和上游限流的降级路径。Exa 的 `maxAgeHours=0` 是更接近强制 live crawl 的控制项，但 live crawl 会增加延迟、失败率和成本；其他 provider 的日期过滤不能直接视为同样语义。[Exa Contents freshness](https://exa.ai/docs/reference/livecrawling-contents)（访问日期：2026-09-08）。

**中文评估需要覆盖不同类型的 query。** 不能只用中文百科问题；应分别准备简体中文、繁体中文、夹杂 English product name、专有名词、新闻标题、站点限定和地区限定 query。特别要观察：是否能召回中国大陆/台湾/香港不同来源，是否错误地把中文 query 翻译成英文，是否把搜索语言和结果界面语言混淆，以及是否能保留中文网页的标题、发布时间和正文编码。SerpAPI 的 `ct`、`hl`、`lr` 是可控参数，不等同于已证明的质量优势；Exa/Parallel 没有明确语言过滤参数，也不等同于中文一定不可用。

**Privacy 要看数据生命周期，不只看一句 ZDR。** 需要逐项问清 query、URL、结果 metadata、网页正文、MCP session、错误日志、计费日志和安全审计日志的保存时间；还要问 provider 是否将 query 转给第三方上游、是否用于训练或产品改进、是否允许结果落盘、是否允许跨境处理。公开产品页的营销声明、一般 Privacy Policy、DPA 和 enterprise order form 可能处于不同法律层级；本报告把冲突处标为 vendor claim 或开放问题，不替采购方作合规承诺。

**MCP 只解决连接方式。** MCP tool schema 可以统一调用入口，却不会统一返回字段、分页语义、重试、计费或证据质量。建议在 MCP 之上再放一层内部 gateway，至少规范 `query`、`provider`、`engine`、`freshness`、`max_results`、`timeout`、`citation` 和 `usage` 字段；对 hosted research 单独设置权限和预算。这样更容易在 Brave、Tavily、Exa、Parallel 之间切换，也能把 SerpAPI 的 engine-specific 参数或 SearXNG 的 instance-specific 配置隔离在 adapter 内。

## Provider 比较

| Provider | 能力边界 | 中文与 freshness | 价格、限制与 privacy/storage/license |
|---|---|---|---|
| **Brave Search API** | Vendor claim 为独立 Web index；覆盖 Web、News、Image、Video 等搜索。Search 返回结果和摘要，不等于正文 Extract。[产品页](https://brave.com/search/api/)（访问日期：2026-09-08） | `freshness` 支持过去 24 小时、7 天、31 天、1 年和自定义日期；`search_lang`、`ui_lang`、`country` 可用于中文/地区化，但排序质量仍应实测。[Web Search docs](https://api-dashboard.search.brave.com/app/documentation/web-search/get-started)（访问日期：2026-09-08） | Search API **$5/1,000 requests**，每月 **$5 free credits**，列示 capacity **50 requests/s**。[Pricing](https://api-dashboard.search.brave.com/documentation/pricing)（访问日期：2026-09-08）按 1 秒 sliding window 限流，超限 HTTP 429；只有成功请求计入 quota/billing。[Rate limiting](https://api.search.brave.com/documentation/guides/rate-limiting)（访问日期：2026-09-08）Query 最多保留 90 天；enterprise 可申请 ZDR。默认条款限制持久化 Search Results 及用于训练/改进 AI，除非套餐明确授权。[Privacy](https://api.search.brave.com/app/documentation/privacy-policy)；[Terms](https://api-dashboard.search.brave.com/documentation/resources/terms-of-service)（访问日期：2026-09-08）。官方 Brave MCP repo 为 MIT，但仍需 Brave API key。[brave-search-mcp-server](https://github.com/brave/brave-search-mcp-server)（访问日期：2026-09-08） |
| **Tavily** | 明确拆分 `search`、`extract`、`map`、`crawl`；另有 `research`。`extract` 最多接收 20 个 URL；`research` 是 hosted multi-step research，不应按普通 Search 估价。[Search API](https://docs.tavily.com/documentation/api-reference/endpoint/search)（访问日期：2026-09-08） | `topic=general/news/finance`；`time_range=day/week/month/year`；文档还列出 language 与 `filter_by_language`，适合构造中文/时效过滤，但召回质量仍需基准集。[API credits/docs](https://docs.tavily.com/documentation/api-credits)（访问日期：2026-09-08） | Free **1,000 credits/month**；PAYG **$0.008/credit**；Basic/Fast/Ultra-fast Search 各 1 credit，Advanced 2 credits；Extract 按每 5 个成功 URL 计 1/2 credits；Research `mini` 为 4–110、`pro` 为 15–250 credits。[Credits](https://docs.tavily.com/documentation/api-credits)（访问日期：2026-09-08）Development 100 req/min、Production 1,000 req/min，超限 429 + `retry-after`。[Rate limits](https://docs.tavily.com/documentation/rate-limits)（访问日期：2026-09-08）文档宣称 zero data retention，但 Privacy Policy 又写 query data 可为服务改进而保留/使用，并可能在自有 index 无法检索时分享给 third-party index provider；应以 DPA/合同为准。[Privacy](https://www.tavily.com/privacy)（访问日期：2026-09-08）。官方 Tavily MCP 为 MIT，暴露 search/extract/map/crawl，支持 remote HTTP 与 `npx` 本地运行。[tavily-mcp](https://github.com/tavily-ai/tavily-mcp)（访问日期：2026-09-08） |
| **Exa** | Semantic search、category/domain/date 过滤、`contents` 正文、高亮、summary；`contents` 是 Extract，不是 Search。还提供 Answer、Deep Search 等更高层能力。[Search](https://exa.ai/docs/reference/search)；[Contents](https://exa.ai/docs/reference/contents-api-guide-for-coding-agents)（访问日期：2026-09-08） | `startPublishedDate/endPublishedDate`、`includeDomains/excludeDomains`、`category`、`userLocation`；`maxAgeHours=0` 可强制 live crawl。公开 Search 文档没有语言筛选参数，中文能力不能从文档直接推出。[Search reference](https://exa.ai/docs/reference/search)（访问日期：2026-09-08） | 当前官方 API pricing 页面为 `https://exa.ai/pricing?tab=api`（root `https://exa.ai/pricing` 可访问）。Search **$7/1,000 requests**，基础价格覆盖每次前 10 个 results；常规 API 超过 10 个 results 另按 $1/1,000 results。公开 pricing 页没有明确说明 `text`/`highlights` 的包含范围，因此这里不将它们断言为免费或额外收费，上线前需按 endpoint、模式和实际 usage 核对。x402 guide 明确 Search 内请求 `summary` 另按 $1/1,000 results 计费，并称其 bundled pricing 与 API key billing 相同，但 x402 还存在最多 10 results 的自身限制，不能把所有调用限制也等同。独立 `/contents` 按 $1/1,000 pages **per content type**（`text`、`highlights`、`summary`）计费；Search 后再调用独立 Contents 是另一笔计费，不能假定跨请求去重。[Pricing](https://exa.ai/pricing?tab=api)；[x402 pricing](https://exa.ai/docs/reference/x402-guide)；[Contents guide](https://exa.ai/docs/reference/contents-api-guide)（访问日期：2026-09-08）。Deep Search $12/1,000，Deep-reasoning $15/1,000；新账号 $20 signup credits，Free Tier 另有 $10 monthly credits。默认 Search 10 QPS、Contents 100 QPS、Answer 10 QPS。[Rate limits](https://exa.ai/docs/reference/rate-limits)（访问日期：2026-09-08）Privacy Policy 明示 Query Data 可用于产品改进、training/fine-tuning，未给出普通 API retention period；enterprise ZDR 需单独核合同。[Privacy](https://exa.ai/privacy-policy)（访问日期：2026-09-08）。官方 Exa MCP endpoint `https://mcp.exa.ai/mcp`，工具含 `web_search_exa`、`web_fetch_exa`，可选 `agent_run`；repo 为 MIT。[exa-mcp-server](https://github.com/exa-labs/exa-mcp-server)（访问日期：2026-09-08） |
| **Parallel** | Search 接受自然语言 `objective` 和可选 `search_queries`，返回 URL、title、publish_date、LLM-oriented excerpts；另有 Extract。Search 与 hosted research/task 不应混算。[Search quickstart](https://docs.parallel.ai/search/search-quickstart)（访问日期：2026-09-08） | 产品页是 vendor claim：页面持续更新、可配置 freshness；但公开 Search 资料未给出与 Brave/Tavily/Exa 同等明确的 language、country、date filter。中文、新闻和地区化查询必须 POC。[Search product](https://parallel.ai/products/search)（访问日期：2026-09-08） | Search 10 results/request：Turbo/Fast **$1/1,000 requests**，Basic/Advanced **$5/1,000**，extra results $1/1,000；Pricing 页列 Search 600/min，free plan up to 5,000 requests/month。[Pricing](https://parallel.ai/pricing)（访问日期：2026-09-08）另一个产品页写 up to 80,000 free requests，vendor pages 不一致，不能据此做预算。Vendor claim：不用于 training、ZDR/enterprise 选项；FAQ 未给一般 retention period，且写 US-based data centers。[FAQ](https://docs.parallel.ai/resources/faqs)；[Privacy](https://parallel.ai/privacy-policy)（访问日期：2026-09-08）。官方 Search MCP repo 为 MIT，endpoint `https://search.parallel.ai/mcp`，匿名 endpoint 可用于轻量探索，较高 limits 需 auth；工具是 `web_search`、`web_fetch`。[search-mcp](https://github.com/parallel-web/search-mcp)；[MCP quickstart](https://docs.parallel.ai/integrations/mcp/quickstart)（访问日期：2026-09-08） |
| **SerpAPI** | SERP aggregation API，按 engine 获取 Google、Baidu、YouTube 等结果；可得到 web/news/image/shopping 等真实 SERP 结构。它不是自有统一 index。[Search API](https://serpapi.com/search-api)（访问日期：2026-09-08） | Google 支持 `hl`/`gl`/`lr`/location 等；Baidu `engine=baidu`，`ct=2` 简体、`ct=3` 繁体，并有 `gpc` 时间范围。适合中文 engine 与地区化结果，但每个 engine 语义不同。[Baidu API](https://serpapi.com/baidu-search-api)（访问日期：2026-09-08） | Free 250 searches/month；Starter 1,000/$25，Developer 5,000/$75，Production 15,000/$150；只计成功 search，pagination 单独计一次，cached/failed 不计。[Pricing](https://serpapi.com/pricing)（访问日期：2026-09-08）标准 search data 保留 31 天；Enterprise ZeroTrace 可不存 search parameters/data，仍受法律义务限制。[Legal](https://serpapi.com/legal)（访问日期：2026-09-08）。官方 SerpApi MCP repo 为 MIT；`search`、`search_table`、`search_dashboard`，hosted endpoint `https://mcp.serpapi.com/<API_KEY>/mcp`，仍按 SerpApi API key/配额计费。[serpapi-mcp](https://github.com/serpapi/serpapi-mcp)（访问日期：2026-09-08） |
| **SearXNG** | Open-source metasearch：从实例配置的多个上游 engine 聚合结果，不是固定 index。API 支持 `GET/POST /search`，`json/csv/rss` 需实例在 `settings.yml` 开启；实际 engine/类别由实例配置决定。[Search API](https://docs.searxng.org/dev/search_api.html)（访问日期：2026-09-08） | 支持 `language`、`time_range=day/month/year`、safesearch 等，但某个上游是否支持由 engine 决定；中文效果取决于实例、上游、IP 和限流。[Search API](https://docs.searxng.org/dev/search_api.html)（访问日期：2026-09-08） | 软件无 SaaS request fee；成本变成 server、带宽、proxy/Tor、缓存、监控和维护。自建实例可控制日志、出口和配置；公共实例必须信任 operator，可能记录、转交请求，且被上游验证码/IP block。[Own instance](https://docs.searxng.org/own-instance.html)（访问日期：2026-09-08）项目为 AGPL-3.0。[Repository](https://github.com/searxng/searxng)（访问日期：2026-09-08）。本次核查未找到 `searxng/searxng` 官方维护的统一 MCP server；现成 adapter 的 license/安全性需逐仓库核验。 |

## 推荐的最小 POC

若团队尚未确定 provider，建议按首批场景选两家候选做最小 POC，而不是一次性接入全部服务：用同一组中文、英文、新闻和技术文档 query，记录结果 URL、摘要、日期、响应时间、HTTP status、usage 和是否发生 live crawl，不保存超出条款允许范围的内容。POC 产出应包括失败样例和降级规则，而不只有平均分；本轮没有实施 POC，也没有估计工期。若主要需求是中文 engine 与地区参数，可比较 SerpAPI 和 Brave；若要统一 Search/Extract 工具，可比较 Tavily 与 Exa。需要自控实例日志和出口时再评估 SearXNG；若硬性要求 query 不离开自有网络，SearXNG 也不能直接满足，须使用获准的内部 index 或先确认允许外发的 query policy。

## 现成官方 Search MCP 的边界

- **Brave**：官方 Brave-maintained repo 支持 STDIO/HTTP；除 web/news/image/video/local 外还有 `brave_llm_context` 等工具，必须提供 `BRAVE_API_KEY`。[Repo](https://github.com/brave/brave-search-mcp-server)（访问日期：2026-09-08）。MCP 官方旧 repo 已说明 Brave Search server 被 Brave 自己的 repo 替换，不要把旧包当 canonical。[MCP servers repo](https://github.com/modelcontextprotocol/servers)（访问日期：2026-09-08）。
- **Tavily/Exa/Parallel/SerpAPI**：均有 vendor-maintained repo 或官方 hosted endpoint，能减少本地 adapter 工作；但请求仍到 vendor backend，API key、quota、privacy、storage 和网页内容授权仍按 provider 条款执行。各链接见上表。
- **SearXNG**：主项目只提供 HTTP Search API；第三方 MCP adapter 不等同官方产品。MCP Registry 是“发现服务器”的目录，不应视为 security/quality verification。[Registry](https://registry.modelcontextprotocol.io/)（访问日期：2026-09-08）。
- **Search MCP ≠ hosted research**：例如 Exa MCP 的 `web_search_exa`/`web_fetch_exa` 是基础 search/fetch，`agent_run` 才是可选的多步研究；Tavily 的 `research` 也应独立统计。优先只暴露基础 Search/Fetch 工具，避免 Agent 无意升级到高成本托管研究。

## Cost formula（假设明确，单位不可直接相加）

- **Brave**：假设 10,000 次成功 Search、忽略每月 $5 free credit，`10,000 / 1,000 × $5 = $50`。
- **Tavily**：PAYG 假设 10,000 次 Basic Search，`10,000 credits × $0.008 = $80`；同样请求若 Advanced，`20,000 × $0.008 = $160`。Extract/Research 另算 credits。
- **Exa**：假设每次最多 10 results，10,000 次普通 Search 的基础调用费为 `10 × $7 = $70`；这不是包含所有 content 功能的总价承诺。若再独立抓 1,000 pages Contents、只请求一种 content type，按公开单价再加 `$1`，同时请求两种 content type 则分别计费。Search 内 `text`/`highlights` 的包含范围不能从单列的 Contents 价格反推，需按实际 usage 核对；不要重复计算已被实际套餐包含的 content，也不要假定跨请求免计费。Search request、result、page 三种 meter 不可和 Tavily credits 直接比较。
- **Parallel**：假设 10,000 次 Fast，`10 × $1 = $10`；Basic 则约 `$50`。free quota 在 vendor 页面出现 5,000 与 80,000 两种说法，预算应按付费保守估算并向 vendor 确认。
- **SerpAPI**：假设每月 5,000 次成功 search，直接对应 Developer plan `$75/month`；分页会额外消耗 search。月包价格不能与按请求 PAYG 线性比较。

## Build-vs-buy 与候选短名单

- **Buy hosted provider + 官方 MCP**：上线最快、Search/Extract 能力成熟，适合先做产品验证；缺点是 vendor lock-in、价格/限流变更、数据跨境和上游条款依赖。短名单：Brave（通用 index）、Tavily（Agent workflow）、Exa（semantic research）、Parallel（Search + Extract）。
- **Build SearXNG + 自己的 MCP gateway**：适合需要自托管配置、可替换上游和自控日志的场景，但自托管仍会把 query 转发到上游 engine。若业务硬性要求 query 不能离开自有网络，公开 Web search（包括 SearXNG）都不能满足，除非另有不外发的私有 index 或获批准的内部搜索源；需要承担运维、反爬/验证码、结果质量、AGPL 合规和每个上游 engine 的条款。不要把“免费软件”误算成“免费搜索”。
- **Hybrid 推荐**：统一内部 `SearchProvider` contract；用自建 MCP gateway 做 allowlist、timeout、max results、quota、audit 和 fallback；按条款只缓存允许缓存的 URL/metadata，不默认保存全文。一个可行起点是 Brave 或 Tavily 主路由，SerpAPI 处理 Baidu/特殊 SERP，SearXNG 作为隐私或故障转移路径。

### 开放问题（需要在 POC/采购阶段补齐）

1. 在目标中文 query set 上，各 provider 的 Recall@k、首条准确率、重复率、地区排序和 freshness 延迟是多少？本报告没有 benchmark 数据。
2. Parallel 的 free quota（5,000 vs 80,000）和 ZDR 对 MCP endpoint、error log、第三方上游的实际适用范围是什么？
3. Tavily 产品文档的 zero-retention 表述与 Privacy Policy 的 retention/improvement 表述如何由 DPA 统一解释？
4. Exa 普通 API 的 Query Data retention period、enterprise ZDR 具体是否覆盖 MCP 与 Contents 正文？
5. Brave/SerpAPI/SearXNG 的网页正文缓存、版权、robots 和下游持久化边界，是否满足目标业务法域？
6. 目标部署分别允许哪些地区处理、哪些第三方上游以及哪些 hosted MCP？自托管 SearXNG 只能改变实例位置和中间层控制，不能消除第三方 query 外发；企业私有部署也要核对其 index、proxy、telemetry 与实际出口。
