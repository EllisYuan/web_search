# 时效 query 补测（独立于两窗口统计）

2026-09-09 UTC 约 01:45，3 个预先写定 query × 2 条路线，共 6 次调用；返回 5 次、50 条 URL。不是两轮稳定性实验，未传 `timelimit` 或 `time_range`。以下逐项审阅 top-3 的 URL/title/snippet，没有读取全部目标正文，不确认“最新”或发布日期事实。

| query / route | rank | 返回内容 | 审阅 |
|---|---:|---|---|
| zh07 / DDGS Brave | 1 | Python 3.12.14 release | 错误 minor version，不能回答 3.14 query |
| zh07 / DDGS Brave | 2 | Python 3.14.6 release | 相关 release，snippet 标 2026-06-10；不证明最新 |
| zh07 / DDGS Brave | 3 | Python 3.14.7 release | 相关 release，snippet 标 2026-08-05；安全修复与最新性仍须查正文 |
| zh07 / SearXNG Google | 1 | Medium “Python 3.14 in 2026” | 版本相关文章，不能据此确认最新安全发布 |
| zh07 / SearXNG Google | 2 | 官方 What's new in Python 3.14 | 功能总览相关，但不是 2026 安全 release 证据 |
| zh07 / SearXNG Google | 3 | Real Python November 2025 news | 年份不匹配，非所问发布窗口 |
| en04 / DDGS Brave | — | HTTP 429 | 真实上游失败，不参与相关性分母 |
| en04 / SearXNG Google | 1 | Python Source Releases | 官方列表入口，需继续定位 3.14 和 September 2026 |
| en04 / SearXNG Google | 2 | Python documentation by version | 官方版本索引，SERP 展示 3.13，不足以直接回答所问版本/月 |
| en04 / SearXNG Google | 3 | Simon Willison 2026-09-01 weblog | snippet 实际是 3.15 release candidate；错误 minor version |
| mix08 / DDGS Brave | 1 | Wikipedia Firefox version history | 版本历史入口，未直接定位指定月 release notes |
| mix08 / DDGS Brave | 2 | Firefox.com release notes index | 官方入口相关，需要继续选版本 |
| mix08 / DDGS Brave | 3 | Browser Calendar，标题 2025、snippet 2026 | 显式不一致，不把索引 snippet 当已核验发布日期 |
| mix08 / SearXNG Google | 1 | Firefox.com release notes index | 官方入口相关，需要继续选版本 |
| mix08 / SearXNG Google | 2 | Firefox 154.0 release notes | snippet 为 2026-08-18，与 September 不符 |
| mix08 / SearXNG Google | 3 | 日文 Firefox 9.0.1 release notes | 很旧的版本且语言漂移，不满足指定年份月份 |

原始 URL、title、snippet、rank、HTTP 和时间在 [runs/freshness-smoke](runs/freshness-smoke)。审阅者为 agent，尚未用户确认。

结论：免费 Search 能找到 release 入口，但精确版本/月份条件会漏执行或被相邻版本干扰。本轮不计算“freshness 准确率”，因为尚未定义和核验每个问题的完整时点 ground truth，也未评估参数过滤。此处不将搜索返回的发布日期转述为已证实事实。
