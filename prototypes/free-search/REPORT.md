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

## 后续低频复测与真实 batch

在原始两窗口之后，运行了 `lowfreq-20260909`：3 个固定 query、SearXNG Google 与 DDGS Brave，串行间隔 10 秒。DDGS Brave 三项均返回 10 条 URL；response headers 已保存，`Retry-After` 在这些 200 响应中为 null，不能据此推断 429 时一定会提供该 header。SearXNG Google 第一项后连续出现 `RemoteDisconnected`，HTTP response 没有 status code；container 虽报告 `Up`，本机 `/healthz` 也连接后被意外关闭。该状态归为 instance/transport failure，不能算作上游 JSON `unresponsive_engines`。

随后运行 `real-batch-20260909-v2`（pinned venv，8 秒间隔）：

| index | route | backend | status | URL | upstream request | retry |
|---:|---|---|---|---:|---:|---:|
| 0 | DDGS | Brave | success | 10 | 1 | 0 |
| 1 | SearXNG | Google | transport_error (`RemoteDisconnected`) | 0 | 1 | 0 |
| 2 | DDGS | missing-backend | unsupported_backend | 0 | 0 | 0 |

`batch-index.json` 的 `partial_failure_preserved=true`：第一项成功结果已独立写盘，后续失败没有覆盖它；第三项也证明显式 invalid backend 不会 fallback 到 `auto`。这是真实 sequential batch 的部分失败观测，不是生产并发、整体 deadline 或 retry policy 的 benchmark。第一次误用系统 Python 的 batch 也保留为 `real-batch-20260909`，其中两个 DDGS 项因 `ModuleNotFoundError` 失败；之后用 pinned venv 重跑，不能把前一次当上游故障。

container 状态命令一度显示 `Up 5 hours`，但服务端不响应；重启命令未产生可确认的健康恢复。这个“container process 存活 ≠ HTTP 服务可用”的事实需要进入后续 adapter health check 设计。

## Adapter health check（2026-09-12）

延续上一节“container process 存活 ≠ HTTP 服务可用”的问题，本轮在 `probe.py` 的 `searxng_search()` 里加了两处改动；DDGS 路线不变，它没有本机常驻 instance 概念，不适用同类检查。

1. **请求内 health probe**：每次真正发 `/search` 前先对同一 SearXNG 实例发一次 `/healthz`（2 秒超时，与 `run.ps1` 启动时的探测一致）。探测失败记为新终态 `instance_unhealthy`，**不再发起后续 search 请求**（本地 instance 都连不上，再打一次必是同一条坏连接），该条 `upstream_request_count` 记为 0。停掉容器后实测：`/healthz` 不是快速拒绝，而是整整等到 2 秒超时才报 `URLError: <urlopen error timed out>`（[样例](runs/instance-down-20260912/en01-searxng-google.json)）——比此前 `lowfreq-20260909` 观察到的 `RemoteDisconnected` 更慢、更隐蔽，进一步说明不能把“端口没报错”当作健康。
2. **`unresponsive_engines` 原因归类**：把 JSON 里 `unresponsive_engines` 的自由文本原因（不区分大小写子串匹配）映射到 DDGS 路线已有的共享状态：含 `captcha` → `challenge`，含 `too many request` → `rate_limited`，其余归一个新的兜底 `upstream_engine_unresponsive`；原始 `unresponsive_engines` 列表继续完整保留在输出里，没有改动 DDGS 侧逻辑。这只是字符串归类，不代表已理解全部可能的原因文本。

对健康实例做了一次小规模真实复测（`healthcheck-20260912`，2 query × 3 backend）：

| query | backend | status | 观察 |
|---|---|---|---|
| zh01 | duckduckgo | challenge | `unresponsive_engines=[['duckduckgo','CAPTCHA']]`，[样例](runs/healthcheck-20260912/zh01-searxng-duckduckgo.json) |
| zh01 | brave | success | 10 URL |
| zh01 | google | success | 10 URL |
| en01 | brave | success | 10 URL |
| en01 | google | challenge | `unresponsive_engines=[['google','CAPTCHA']]`，[样例](runs/healthcheck-20260912/en01-searxng-google.json) |
| en01 | duckduckgo | challenge | `unresponsive_engines=[['duckduckgo','CAPTCHA']]` |

`SearXNG / Google` 在 2026-09-09 两窗口里是 6/6 无失败，这次同一 query 却直接 CAPTCHA——再次证明没有一条路线能据既有样本宣称长期稳定，不是这次改动引入的回归。随后重跑 `real_batch.py`（`real-batch-20260912-healthcheck`）复现了同一批 job：`zh01/searxng/google` 这次原因文本是 `"Suspended: CAPTCHA"`（不是单纯 `"CAPTCHA"`），仍被正确归类为 `challenge`，且延迟只有 55ms——说明这是几秒前刚触发的 CAPTCHA 引发了实例内 engine suspension 的快速拒绝，不是一次新的独立上游探测（呼应上一节对 Brave suspension 的同样告诫）。`health_check` 字段本身在健康路径里稳定在个位数至十几毫秒（[样例](runs/real-batch-20260912-healthcheck/01-zh01-searxng-google.json)），没有明显拖慢整体请求。

`retry_count` 本轮仍是诚实的静态 0：caller 显式发起可审计 attempt 的机制还没有建，`batch-observations.json` 里已经预留的 `attempts` 形状留给后续单独一轮再确认 CLI 和 `batch-index.json` 的呈现方式。

## 24 query 完整 top-10 审阅（2026-09-12）

目标是用 `probe.py --window <name> --ids all --pause 2` 跑满 `corpus.json` 全部 24 个 query × 6 条 route/backend（`ddgs:duckduckgo`、`ddgs:brave`、`ddgs:google`、`searxng:duckduckgo`、`searxng:brave`、`searxng:google`），对每条实际返回的结果做 top-10 相关性标注。实际执行了两窗口：`corpus24-w1-20260912`（UTC 约 15:41–15:49）与 `corpus24-w2-20260912`（同一参数加 `--reverse`，UTC 约 15:49–15:58），各 144 次调用，合计 288 次。container 全程健康（`Up`），未触发 `docker start` 或 `run.ps1` 重启。**结果是这轮没能做到"24 query 完整 top-10"：288 次调用只有 8 次 success，其余 280 次全部是 `rate_limited`/`challenge`。**

**必须先说明的敏化背景**：这是当天第四轮真实上游调用——前面已经跑过 `healthcheck-20260912`、`instance-down-20260912`、`real-batch-20260912-healthcheck`，以及 `run.ps1` 附带触发的 `corpus-prep-check` 6-query smoke。开跑前上游大概率已被当天累计请求量敏化。**下面的数字不代表免费上游的典型/baseline 状态**，只能证明"同一天连续高频复测会触发近乎全锁定"；上一节"下一步问题"里点名要做的跨天、低频复测本轮仍未做，上游在低频、干净状态下的真实表现仍未验证。

两窗口合计按 route/backend 拆分：

| route | backend | 调用数 | success | rate_limited | challenge | 观察 |
|---|---|---:|---:|---:|---:|---|
| ddgs | duckduckgo | 48 | 1 | 0 | 47 | 唯一成功落在 zh01 |
| ddgs | brave | 48 | 3 | 45 | 0 | zh01–zh03 各成功 1 次后转 rate_limited |
| ddgs | google | 48 | 0 | 48 | 0 | 两窗口全程 0 成功 |
| searxng | duckduckgo | 48 | 0 | 0 | 48 | 两窗口全程 0 成功 |
| searxng | brave | 48 | 4 | 44 | 0 | zh01–zh04 各成功 1 次后转 rate_limited |
| searxng | google | 48 | 0 | 0 | 48 | 两窗口全程 0 成功 |
| 合计 | — | 288 | 8 | 137 | 143 | — |

8 次成功全部发生在 window 1 开头、按 corpus 顺序最先出现的 4 个 query（zh01–zh04）：最后一次成功是 `zh04 searxng brave`（15:42:27），4 秒后 `zh04 ddgs brave` 就转为 `rate_limited`（15:42:35），此后到 window 1 结束（65 次 rate_limited + 71 次 challenge）再没有出现过 success。**Window 2 全程 144 次调用 0 成功**（72 次 rate_limited + 72 次 challenge），比此前任何一次单条 engine 的 suspension（如 Brave 的 `suspended_time=180`）都更彻底——这次是六条 route/backend 组合同时、持续锁定，不是某一条 engine 的局部拒绝。`ddgs:google`、`searxng:duckduckgo`、`searxng:google` 三条组合两窗口合计 0 成功，本轮完全没有拿到它们的候选样本。

20/24 个 query（zh05–zh08、en01–en08、mix01–mix08）本轮两窗口都是零返回，没有任何 top-10 数据；只有 zh01–zh04 这 4 个 query 拿到了真实候选，而且只来自 `ddgs:duckduckgo`（仅 zh01）、`ddgs:brave`（zh01–zh03）、`searxng:brave`（zh01–zh04）三条 route/backend。

对这 4 个 query 实际返回的全部结果做了 top-10 逐条标注，rollup：

| route | backend | 覆盖 query | reviewed top-10 | relevant | 保守独立 Source | known URL/site 命中 |
|---|---|---|---:|---:|---:|---|
| ddgs | duckduckgo | zh01 | 10 | 6 | 3 | 1 request 命中 known URL，1 命中 known site |
| ddgs | brave | zh01–zh03 | 30 | 20 | 10 | 2 命中 known URL，3 命中 known site |
| searxng | brave | zh01–zh04 | 40 | 24 | 17 | 2 命中 known URL，3 命中 known site |

`quality-annotations.json` 本轮新增 47 条判断（zh01 +15、zh02 +7、zh03 +15、zh04 +10），累计 99 条，覆盖 8/24 个 query id（`en01`、`en02`、`mix01`、`mix02`、`zh01`、`zh02`、`zh03`、`zh04`）；总体分布 `{relevant: 64, partial: 25, irrelevant: 8, unknown: 2}`；`scope` 字段已如实更新为这次只覆盖 zh01–zh04 的部分结果；`user_accepted` 仍为 `false`。规则细节与全部理由见 [quality-annotations.json](quality-annotations.json)，独立 Source 归并沿用上一节同一套保守约定，未新引入例外。

几个具体例子：

- `SearXNG Brave / zh02` 直接命中官方 FAQ：[样例](runs/corpus24-w1-20260912/zh02-searxng-brave.json) 标题就是"玉山的高度為何？"，corpus 指定的 `known_relevant_urls` 裸域名 `https://www.ysnp.gov.tw/` 本身当天也出现在结果里，两条都判 relevant——这是本轮少见的精确命中，不代表整体候选质量。
- `DDGS DuckDuckGo / zh01` 的 [结果](runs/corpus24-w1-20260912/zh01-ddgs-duckduckgo.json) 里 `aiotools.readthedocs.io` 的 "Task Group" 文档判 irrelevant：这是第三方库自己的同名概念，不是 Python 官方 `asyncio.TaskGroup`，同名不同物。
- `zh03`（台风 + 指定月份）的 [结果](runs/corpus24-w1-20260912/zh03-ddgs-brave.json) 里新浪财经、中新网等 4 条标题只写"今秋"/"2026年秋季"，没有明确到指定月份，按 query 自己的 `relevance_rule`（需同时匹配月份）判 partial，即使台风预测主题完全相符。
- `zh04`（台/港/新个资保护）的 [结果](runs/corpus24-w1-20260912/zh04-searxng-brave.json) 里 `law.pdpc.gov.tw`（台湾个人资料保护委员会筹备处）与新加坡官方 PDPC（`pdpc.gov.sg`）撞名但不同源；因为台湾本身是 query 指定的三地之一，仍判 relevant，`reason` 字段专门写明这不是新加坡 PDPC，避免后续误读；域名相似不代表同一机构。
- 两窗口 stdout 共出现 3 次 `h2 connection driver error: peer closed connection without sending TLS close_notify`（window 1 一次、window 2 两次），两次运行退出码仍为 0，判定为传输层噪声，未计入上述失败分类统计。

**仍未验证**：

- 24 个 query 里有 20 个本轮完全没有 top-10 数据（zh05–zh08、全部 en0x、全部 mix0x），"24 query 完整 top-10 审阅"这个目标本轮只完成了 4/24。
- `ddgs:google`、`searxng:duckduckgo`、`searxng:google` 三条 route/backend 组合两窗口合计 0 成功，无法据此判断它们在非饱和状态下的候选质量或相关性表现。
- 今天的近乎全锁定是否等于免费上游的真实上限，还是单纯当天累计请求量过大导致，尚未通过跨天、低频复测区分；六条 route/backend 是否共享同一个上游/IP 级限流，还是六个 engine suspension 恰好同时触发，本轮也没有隔离验证。
- zh01–zh04 之外的任何 query，在 top-10 位置 4–10 的表现此前从未审阅过；即使是 zh01–zh04，今天新增的 top-10 覆盖也只来自 3 条 route，不是全部 6 条。
- 以上不构成任何 route 的"获胜"结论，也不改变 ticket #6 的验证状态；本节不写入 map 的 Decisions so far。

## 跨天低频换 upstream 复测（2026-09-13）

上一节列出的"今天的近乎全锁定是否等于免费上游的真实上限，还是单纯当天累计请求量过大导致"，本轮做了一次针对性隔离：距 corpus24 两窗口约 13 小时（2026-09-13 UTC 05:05 开始），改测三个此前**从未测过**的 upstream，并把节奏放到最慢。

配置：`ddgs:mojeek,ddgs:startpage,ddgs:brave` × 6 个代表性 query（zh01/zh05/en01/en05/mix01/mix05），单进程串行、`--pause 20`、retry=0、无 proxy，共 18 次调用。证据在 [runs/alt-smoke-20260913](runs/alt-smoke-20260913)。

| upstream | 成功 / 18 中的 6 | 失败现象 |
|---|---:|---|
| DDGS / Brave | 4/6 | 2 次 HTTP 429（en05、mix01） |
| DDGS / Mojeek | 0/6 | 6 次 HTTP 403 |
| DDGS / Startpage | 0/6 | 6 次 HTTP 200 但无结果 |

三条 route 的失败性质各不相同，都经原始响应体核实：

- **Mojeek** 的 403 响应体只有 371 bytes，明写 `Sorry your network appears to be sending automated queries so we can't process your search at this time.`——是针对自动化查询的显式拒绝，不是限流后的临时退避。
- **Startpage** 两次请求（GET 首页 + POST `/sp/search`）都是 HTTP 200，但响应体含 `anubis_challenge`，即 Anubis Proof-of-Work 挑战页，当前 adapter 未完成该挑战。`probe.py` 据"HTTP 全 200 且无结果"把它归为 `empty_or_parse_failure`，**这个分类在本例中偏保守**：从原始响应看更准确的终态是 `challenge`。分类逻辑本轮未改，作为已知偏差记录在此。
- **Brave** 的 2 次失败是 HTTP 429，与此前观察一致。

一处需要澄清的**误报**：Brave 的成功响应里 `marker_hints` 也含 `captcha`，但这几次都正常解析出 10 条结果（如 en01 命中 PostgreSQL 官方文档）。`evidence()` 的 marker 是页面正文子串命中，本就声明为 hints 而非证据；本轮真正的限流判据是 HTTP 429。

**这一轮回答了什么**：跨天冷却 + 20 秒间隔 + 从未使用过的 upstream，三个条件同时满足，Brave 仍出现 429，另两个 engine 则在**第一次**调用就被拒——后两者与"当天累计负载"无关，是这些站点对自动化访问的固有策略。因此"换一个限制更少的免费 engine"不成立：Mojeek 明确拒绝自动化查询，Startpage 有独立的 PoW 反自动化机制。

**这一轮没有回答什么**：18 次调用只测 availability，成功结果未做 top-10 相关性与独立 Source 审阅，不进入 [quality-annotations.json](quality-annotations.json)。出口 IP 未独立测量，仍不能排除本机出口在此前几轮中已被标记。DDGS 9.16.0 把 `bing` 标为 disabled，未测；Qwant 等需另配 SearXNG，本轮未覆盖。stdout 再次出现 `h2 connection driver error ... TLS close_notify` 传输噪声，未计入失败分类。

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
3. **DDGS Brave 真实 429**：时效补测 [en04](runs/freshness-smoke/en04-ddgs-brave.json) 的 HTTP 观测直接记录 429；下一不同 query 又成功。没有重试失败 query。补测已记录 response header 名称和 `Retry-After` 值；成功的 200 响应没有该值，不能据此推断 429 时一定会提供它。
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

之后再补齐 24 query 的 top-10 逐项审阅，尤其是时效性、默认语言与显式过滤；real_batch 的 caller 可审计 retry/attempt 机制仍未接入（2026-09-12 已先接入 adapter health check 与失败原因归类，见上节）。免费上游恢复策略及 suspension 是否暴露给 caller 已成为明确的待验证问题，可留在当前 ticket 继续验证。

目前没有用户确认的候选、性能阈值或 resolution，因此不关闭 ticket，也不把本报告写入 map 的 Decisions so far。资产保存在独立 prototype branch，供用户直接审阅。
