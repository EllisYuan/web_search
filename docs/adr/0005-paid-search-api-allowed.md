---
status: accepted
supersedes: 0002 (部分)
---

# 允许 web_search 使用付费 Search API

[ADR-0002](0002-free-open-source-solutions-only.md) 确立「自建组件开源、不依赖付费 API，允许使用公开搜索引擎」。在 [验证免费 Search 的 URL 发现质量与上游稳定性](https://github.com/EllisYuan/web_search/issues/6) 的实测中，该约束下唯一可行的上游路线——直接抓取公开搜索引擎网页——被证明不足以支撑目标产物。用户于 2026-09-13 决定解除其中的付费 API 限制。

## 被推翻的部分

仅推翻 ADR-0002 的「不依赖付费 API」一条。以下继续有效，不受本 ADR 影响：

- 自建组件必须开源。
- 首版 Windows 本机开发部署，CPU 即可运行，暂不引入 GPU。
- 开源要求适用于自建组件，不要求上游搜索服务本身开源。

## 依据

跨 5 轮真实测试（合计约 400 次上游调用，证据在 [prototype/free-search](https://github.com/EllisYuan/web_search/tree/prototype/free-search)）：

- 6 条 route/backend 无一稳定；同一 route 跨轮次可从 6/6 成功翻转为直接 CAPTCHA。
- 同日累计负载下，288 次调用仅 8 次成功，第二窗口 144 次调用六条 route 同时全部失败。
- 跨天冷却 13 小时、20 秒间隔、改用三个从未测过的 upstream 后：Mojeek 首次调用即 403 并明示拒绝自动化查询，Startpage 返回 Proof-of-Work challenge，Brave 仍出现 429。

失败原因不是 adapter 实现或调用节奏，而是「把公共搜索引擎的网页入口当作可编程检索接口」这一前提。SearXNG 官方文档亦说明其会将请求转发给上游、因而可能被上游判定为 bot；它是聚合与故障隔离层，不能消除上游限制。Mojeek 与 Startpage 的表现进一步说明这不是某一家的策略，而是这类站点的普遍立场。

## 取舍

保留免费约束意味着放弃实时全网检索，退到本地索引 + 低频 best-effort；解除该约束则以部署成本换取可编程、有明确配额与 SLA 的检索能力。用户选择后者，理由是 Deep Search agent 的高强度检索是产品核心，不可牺牲。

代价是部署者需自备 API key 并承担调用费用。**自建组件仍然开源**——付费的是上游服务，不是本项目代码；这与 ADR-0002 保留部分不冲突。

## 边界

本 ADR 只解除约束，不选定 provider。具体上游选型、配额与成本模型、是否保留免费路线作为 fallback，由后续选型 ticket 决定。

解除的范围仅限「不依赖付费 API」。自建全网 search index（含 Common Crawl、垂直爬虫）继续排除在项目范围外，不因本 ADR 重议。

「不绕过登录、paywall、CAPTCHA 或网站访问控制」的约束不受影响，继续有效。
