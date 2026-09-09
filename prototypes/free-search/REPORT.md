# 免费 Search：真实 smoke 结果

日期：2026-09-09。状态：**完成首轮可行性 smoke，待继续验证与用户评审**。

已证明能从免费公开搜索页面发现相关 URL；也已复现 CAPTCHA、HTTP 429、engine suspension、HTTP 200 无结果页面，以及 Search 找到 URL 后目标站点 DNS 失败。**当前没有一条路线可以据这些样本宣称长期稳定。** 暂时值得继续验证的是 SearXNG Google 与 DDGS Brave；这只是实验建议，不是已接受选型。

## 范围与分母

- 运行前准备 24 query。本轮先取 6 个：简体/繁体各 1、英文 2、mixed 2，覆盖技术文档、事实和多网站对比；在两个短时间窗口跑 2 route × 3 engine × 6 query，共 **72 次调用**。
- 另取 3 个时效 query，在 DDGS Brave、SearXNG Google 上各跑一次，共 **6 次补测**，见 [freshness-review.md](freshness-review.md)。全部真实 Search 共 **78 次调用、458 条返回结果（未跨调用去重）**。
- 两窗口时间约 UTC 01:38–01:40 / 01:42–01:44；补测截至 UTC 01:45:45（Singapore 时间加 8 小时）。分钟级复测只能发现初步波动，不代表跨天/跨出口稳定性。
- 两窗口保留前 10 条；逐条审阅所有返回的 **top-3，共 123 个排名位置、52 个不同 query–URL**。ranks 4–10 未做完整相关性审阅，不能声称 P@10 已验证。
- 标注是 agent 对 URL/title/snippet 的人工式审阅，**未经用户确认**。`relevant`、`partial`、`unknown`、`irrelevant` 分开；严格相关数只计 `relevant`。没有使用自动 keyword 命中冒充人工判断。

## 两窗口结果

“返回”指拿到至少一个 URL，不等于结果相关。latency 包含成功和失败；SearXNG suspension 会快速失败，所以较小 median 不能当性能优势。

| route / engine | 第一窗口返回 | 第二窗口返回 | 实际失败 | latency median / min–max（ms） | 严格相关 / 已审阅 top-3 | known URL 命中请求 / 12 |
|---|---:|---:|---|---|---:|---:|
| DDGS / Brave | 6/6 | 6/6 | 两窗口未失败；**补测另有 429** | 1790 / 1431–2332 | 34/36 | 8/12 |
| DDGS / DuckDuckGo | 2/6 | 1/6 | 9 次 CAPTCHA，HTTP 202 | 1662 / 1552–2518 | 5/9 | 0/12 |
| DDGS / Google | 2/6 | 5/6 | 5 次 HTTP 200 但无可解析结果 | 2218 / 2042–2974 | 14/21 | 1/12 |
| SearXNG / Brave | 6/6 | 1/6 | 1 次 Too many requests，随后 4 次 suspended | 880 / 198–3260 | 17/21 | 6/12 |
| SearXNG / DuckDuckGo | 0/6 | 0/6 | 12 次 JSON 上游 CAPTCHA | 1202 / 534–2201 | 0/0，不可计算 | 0/12 |
| SearXNG / Google | 6/6 | 6/6 | 本轮未观测失败 | 1052 / 902–2523 | 30/36 | 8/12 |

`known URL` 是事先给定少量 URL 的规范化精确匹配（保留 query，去除 fragment，解码 URL），**不是全网 Recall**；部分参考只是官网入口。`known_site_hit_top10_requests` 另外记录 hostname 匹配：依表顺序为 10、3、5、6、0、10 / 12。文档版本或路径不同不会伪装成精确命中。

精确 URL 重复数在每次最终 top-10 中均为 0，但 adapter 自身已经做 normalization/dedup，且同站版本页与镜像仍然重复。全部结果、原始 latency 数组及各 query 的分母在 [smoke-summary.json](smoke-summary.json)；可用 `summarize.py` 重算。

## 质量与独立 Source

site 分组按本轮观察到的域名/所属网站显式归并，不用“最后两段 hostname”猜测公共后缀。Source 再合并已识别镜像及同一 project 的 docs/GitHub；疑似衍生且未核实独立创作的 Runebook 页面不进入保守独立 Source 数。完整规则和例外写在每条 [标注](quality-annotations.json)。不是所有网站的所有权或内容来源审计。

第一窗口 SearXNG Google 的逐 query top-3 示例：

| query | 相关 / 3 | 保守相关 Source 数 | 观察 |
|---|---:|---:|---|
| Python TaskGroup 异常 | 3 | 1 | 英文与两个中文 Python 文档版本，同一 Source |
| 玉山主峰海拔 | 3 | 3 | 国家公园、Wikipedia、Tripadvisor；SERP 为繁体和简体混合 |
| PostgreSQL multicolumn | 2 | 2 | 官方文档和 Neon 相关，索引总章只算 partial |
| SQLite/DuckDB 比较 | 3 | 3 | DataCamp、MotherDuck、Reddit；独立网站不代表中立观点 |
| SearXNG JSON 配置 | 1 | 1 | Search API 相关；JSON engine 是另一件事，issue 故障帖仅 partial |
| Docker WSL2 backend | 3 | 2 | Docker docs 与 Docker blog 归同一 Source，另有 Reddit |

关键反例：

- `DDGS Brave / en01` 第一窗口前三条是 PostgreSQL current、12、16 的同页，**3 URL 只有 1 Source**。旧版本相关但可能不能支撑当前版本结论。
- `SearXNG Brave / zh01` 的 BookStack 标题明确为 Python 官方文档镜像，应与 python.org 合并；独立 hostname 不是独立证据。
- `DDGS Google / zh02` 的前三条出现 Facebook、Threads 和百岳列表，主峰高度覆盖弱；HTTP 成功不能替代相关性判断。
- `JSON engine` 文档在多个 route 上排名靠前，但回答的是“如何把外部 JSON 变为 engine”，不是“如何开启 Search JSON 输出”。这个误命中在严格标注中算 irrelevant。
- 相关 snippet 也可能不准确，例如 CSDN 的 `enable_api` 配置片段未由官方验证。质量评估只判断来源是否值得读，没有验证所有第三方内容事实。

## 失败原因与可复核定位

1. **DuckDuckGo CAPTCHA**：看 [DDGS 样例](runs/smoke-1-ddgs/en01-ddgs-duckduckgo.json)，HTTP 202，有 `anomaly.js` / `challenge-form`；初期成功不保证下一 query 成功。SearXNG [样例](runs/smoke-1-searxng/zh01-searxng-duckduckgo.json) 虽是本地 HTTP 200，JSON 的 `unresponsive_engines` 明确 CAPTCHA，container log 进一步给出 `SearxEngineCaptchaException`。没有解 CAPTCHA、换付费 proxy 或绕过访问控制。
2. **SearXNG Brave 限流及状态延续**：第二窗口 [zh02](runs/smoke-2/zh02-searxng-brave.json) 报 `Too many requests`；[en01](runs/smoke-2/en01-searxng-brave.json) 等后续调用标为 suspended。日志显示 `SearxEngineTooManyRequestsException`、`suspended_time=180`。后面四项是实例拒绝继续访问该 engine，**不应算四个新的上游 429**。SearXNG JSON 未保留原始上游 HTTP status，因此本报告不凭本地 HTTP 200 或 exception 猜造它。
3. **DDGS Brave 真实 429**：时效补测 [en04](runs/freshness-smoke/en04-ddgs-brave.json) 的 HTTP 观测直接记录 429；下一不同 query 又成功。没有重试失败 query。本轮未采集 `Retry-After`，不能断言其缺失。
4. **Google HTTP 200 无结果页面**：[en01](runs/smoke-1-ddgs/en01-ddgs-google.json) 返回 5,594 bytes，DDGS 抛 `No results found.`。检查本机保存 HTML，可见搜索表单、导航和页脚，缺少结果项；其他失败样例保守记为 `empty_or_parse_failure`。**未证实真实搜索空集，也未证实所有样例都是 selector bug**。第二窗口同 query 成功。该 DDGS engine 使用 `/wml/search` 并由默认 `us-en` 生成 `lr=lang_en`、`cr=countryUS`；参数限制、上游页面变化和 fingerprint 均可能参与，因果还未隔离。
5. **Web Read 独立失败**：已发现的玉山官网 [独立读取观测](readability-observations.json) 出现 `URLError: [Errno 11002] getaddrinfo failed`。当时其他五站正文均 HTTP 200，提取文本包含预期术语。这里只能确认本机该次 DNS 失败，不能推断官网离线，也不能把它计为 Search 失败。
6. **本地执行环境限制**：首次 sandbox 中 gh 网络受限、WSL 报 `E_ACCESSDENIED`；正常用户环境中可访问 GitHub/Docker/WSL。这些准备阶段错误没有计入 Search 统计。

## 默认语言、过滤与 batch

| 能力 | 本轮状态 |
|---|---|
| DDGS 默认语言行为 | `region=us-en`，不是自动中文；中文/mixed query 常有英文文档，Google backend 还发送 language/country restriction。见每条 language 标注 |
| SearXNG 默认语言行为 | 请求未传 language，使用 image/settings 默认；中文 query 仍可混合中英文，不能视为只返回 query 语言 |
| DDGS language/region 显式过滤 | pinned code 有 region；实际过滤效果**未验证**。Brave 代码使用 country，未用 `_lang`；不视为完整语言过滤 |
| SearXNG `language` 显式过滤 | API 支持该参数，engine 效果**未验证** |
| DDGS `timelimit` / SearXNG `time_range` | 本轮未传，实际效果**未验证**；补测是在 query 内写时间，不是参数过滤测试 |
| 任意起止时间过滤 | 本 prototype **不支持**；相对 day/month/year 不等于 arbitrary start/end |
| 成功、空结果、timeout、全失败、retry exhausted | [batch-observations.json](batch-observations.json) 有逐 query 分组的离线演示，明确 injected，不进入上游成功率；真实 deadline enforcement / 并发调度仍未验证 |

## 下一步问题

继续本 ticket 时，优先做跨天、低频的固定 query 复测，隔离 Windows/Docker 出口与 adapter 参数差异，记录上游 request count、Retry-After、suspension 和 HTTP 元数据。已观察到限制，不宜直接放大为 24 query 的压力测试。

之后再补齐 24 query 的 top-10 逐项审阅，尤其是时效性、默认语言与显式过滤；将实际 batch 请求中的部分失败接入，而不只演示 fixture。免费上游恢复策略及 suspension 是否暴露给 caller 已成为明确的待验证问题，可留在当前 ticket 继续验证。

目前没有用户确认的候选、性能阈值或 resolution，因此不关闭 ticket，也不把本报告写入 map 的 Decisions so far。资产保存在独立 prototype branch，供用户直接审阅。
