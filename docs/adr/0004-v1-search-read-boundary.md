---
status: accepted
---

# v1 web_search 与 web_read 边界

在 2026-09-10 的决策访谈中，确定首版 MCP 面向需要较大信息量与 Source 覆盖的 Deep Research agent，但暂不实现 server-side `deep_search` facade。首版先交付两个可组合的工具：`web_search` 负责发现候选来源，`web_read` 负责读取指定 URL 的正文。

## Web Search

- `web_search` 的首要承诺是可解释失败，而不是始终返回结果。
- route / backend 由调用方显式选择，server 不做隐式 fallback。
- ~~v1 先实现 SearXNG / Google，并只启用 Google engine~~；不在一次请求内混合多个 upstream engine。SearXNG / Google 这一具体选型已被 [issue #6](https://github.com/EllisYuan/web_search/issues/6) 的实测否决，上游改由后续选型 ticket 决定；「不混合多个 upstream engine」的原则不变。
- `web_search` 返回候选 URL 与 SERP metadata（包括 title、snippet、rank 和 upstream 状态），不自动读取正文，也不生成综合答案。
- batch 逐 query 返回独立结果；部分成功时保留已完成项，并在顶层标记 `partial`。
- 默认不 retry。调用方若需重试，应发起新的可审计 attempt。
- health 只在请求内检查；process 或 container 存活不能作为 HTTP service 可用的证明。

## Web Read

- `web_read` 接受调用方提供的 URL，不要求 URL 必须来自 `web_search`。
- server 尽量抽取完整主要正文并转换为结构化 Markdown。
- 对超长正文按 heading / paragraph 分段并施加 byte / character hard limit；返回 `truncated` / `next_cursor`，由调用方继续读取。
- v1 不把 `web_read` 变成最终综合或可信度判断工具；页面内容仍是 untrusted data。
- 在 2026-09-10 的后续回答中，用户再次确认不能因技术支持而遗漏高价值来源：首版覆盖静态 HTML、需要 JavaScript 的页面和 PDF。结合此前已接受的 [产品边界](../design/search-mcp-scope.md)，OCR 仍包括扫描 PDF、网页文字图片和独立图片 URL；开源、Windows、CPU-only 约束不变（其中「不依赖付费 API」一条已于 2026-09-13 由 [ADR-0005](0005-paid-search-api-allowed.md) 解除，仅影响 Search 上游选型，不影响 Web Read）。这是支持范围，不是对任意页面无损或必定成功的承诺。

## Deferred boundary

`deep_search` 暂不实现；若后续重新讨论，其职责另行决定，本轮不预设它拥有 planning 或 synthesis。当前 [ADR-0001](0001-agent-owns-deep-research.md) 的 agent-owned Deep Research 边界继续有效。

## 尚未收敛

本文记录已逐项确认的选择，不代表完整 tool contract 已确认，也不是 prototype ticket #6 的 resolution。内容类型支持范围已确认；Search 的 Source 覆盖与验收方式、Web Read 的完整性判定、渐进式披露的具体交互、配额和跨调用读取一致性尚未锁定。

2026-09-10 用户要求先独立研究研究型报告的信息源需求和 Progressive Disclosure，再据结果提出具体方案。研究入口见 [专题索引](../research/2026-09-10-source-disclosure/README.md)。在研究和后续确认前，不将“简单 cursor”当作最终设计，也不擅自删除 ADR-0001 已确认的目录、section / 位置续读与页内关键词定位要求。
