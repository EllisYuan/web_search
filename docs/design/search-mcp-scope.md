---
status: accepted
confirmed_on: 2026-09-09
---

# Search MCP 产品边界

来源：[确认深度搜索的产品边界与首版取舍](https://github.com/EllisYuan/web_search/issues/5) 与用户的 grill-with-docs 对话。用户已逐项作出决策，并于 2026-09-09 确认整体共同理解及阶段划分，本轮产品边界决策完成。后续设计项与验证计划不代表已经实现或验证。

Tracker 同步：已发布 [产品边界 resolution](https://github.com/EllisYuan/web_search/issues/5#issuecomment-5594196457) 并关闭对应 ticket；[深度 Web Search MCP 技术路线](https://github.com/EllisYuan/web_search/issues/1) 索引该决策。后续验证入口见 [prototype 验证计划索引](prototype-validation-plan.md)。

## 2026-09-10 续议说明

本页保留 2026-09-09 的决策基线，并做两处对齐：(1) 2026-09-09 原始表述用 `search` 指代获取候选 URL 的工具，[ADR-0001](../adr/0001-agent-owns-deep-research.md)/[ADR-0004](../adr/0004-v1-search-read-boundary.md) 已统一为 `web_search`，下方”已确认”条目同步改写，这是命名对齐，不是新增能力；(2) 后续已逐项确认的 Search route、默认不 retry、请求内 health 与 Markdown 分段读取见 ADR-0004；本页较早的“有限自动重试”表述不应覆盖后续默认不 retry 的选择。完整 tool contract 尚未整体确认。

用户在 2026-09-10 要求两项独立研究：研究型报告需要的信息源及据此制定的 Search 方案，以及作为项目核心亮点的 Progressive Disclosure 方案。HTML、JavaScript 页面、PDF 和三类 OCR 仍属首版范围；不得因技术实现方便而排除高价值来源。研究提出的具体机制和数值不自动成为 accepted 决策，也不重新引入 `deep_search` tool。

[Web Read prototype #7](https://github.com/EllisYuan/web_search/issues/7#issuecomment-5599723724) 已经用户评审并关闭，确认 CPU-only 各格式功能路径及 Progressive Disclosure 方向可继续；原始实验位于 `prototype/cpu-web-read`，resolution 指向 commit `4c210d1`。其 constrained functional smoke 不代表公开互联网质量、正式性能 SLA 或最终 tool schema 已验证。后续研究应在这份已有证据上深入，而不是把整个 Web Read 路线视为尚无任何运行证据。

## 已确认

- 首批服务用户个人的 Deep Search agent 项目；Windows 本机开发部署，后续计划发布到服务器。以通用 MCP 接口提供能力，Claude Code 可作为集成测试入口。
- `web_search` 获取并整合 URL，不读取目标网页正文，也不交付研究报告。
- 整套 MCP 提供 `web_read`，对网页内容进行渐进式披露。
- `web_read` 独立可用，接受 agent 直接提供的 URL，无需先调用 `web_search`。
- `web_read` 首次返回 metadata、目录（若有）和限长正文；后续支持按 section 或位置继续读取，以及页内关键词定位。使用原文抽取，不依赖模型生成摘要。
- 首版读取范围必须支持普通 HTML、需要执行 JavaScript 的页面、PDF 和 OCR；OCR 覆盖扫描 PDF、网页中的文字图片和独立图片 URL，范围限定为公开内容。
- 多轮 Deep Research 由 agent 循环完成。
- 使用场景覆盖一个或多个问题，以及多个独立网站的信息覆盖；不以多个搜索引擎作为目标定义。
- `web_search` 支持数量受限的 batch，按 query 分组返回；数量上限后续确定。
- Search 返回内容以 `url`、相关度 `score`、`title` 等信息为讨论起点；完整字段与 `score` 语义尚未决定。
- 自建组件开源，允许使用公开搜索引擎和本机资源。~~不依赖付费 API~~ —— 2026-09-13 依据 [ADR-0005](../adr/0005-paid-search-api-allowed.md) 解除；自建组件开源的要求不变。
- CPU 即可运行，首版暂不引入 GPU。
- MCP 对 query 只做基本入参校验，不做脱敏；调用方模型负责 query 内容约束，tool description 提供指引。
- 不专门限制语种，默认期望搜索结果大致匹配 query 语言，不要求结果严格同语种。`language`、起止时间等参数作为后续接口设计议题，本轮不锁定字段或具体语义。
- 当前不设 latency / timeout 数值阈值，速度尽可能快；具体阈值在测试阶段依据实测决定，同步或后台任务形态留到后续设计。
- 部分失败时保留成功结果，明确失败项和原因，不因个别失败丢弃整个 batch。2026-09-09 的原始表述曾写“只做有限自动重试”；2026-09-10 的 [ADR-0004](../adr/0004-v1-search-read-boundary.md) 已改为 Search v1 默认不 automatic retry、不做 implicit backend fallback，retry 由 caller 以新的可审计 attempt 显式发起并保留原失败状态。Web Read 的 browser/OCR escalation 是新的 representation/route 决定，不是 Search retry。

## 后续设计项

以下属于用户已确认的后续阶段范围，具体方案尚未选定。

- URL 获取整合：batch 上限、去重与来源覆盖、排序与 `score` 语义、返回字段、language 和起止时间过滤。详细参数按用户要求留到接口设计。
- Web Read：内容定位、分页与截断、状态与缓存、长 PDF 和 OCR 的按需处理、同步或后台任务形态。
- 本机与服务器运行：免费开源组件与搜索上游选型、CPU 资源预算、transport、protocol / SDK 版本与互操作测试、服务器部署形态。
- 测试：依据实测确定 latency / timeout、重试次数、并发、页面与文件大小等阈值，以及量化验收标准；本轮不将任意数值写成已确认约束。

## 需要验证的关键假设

以下为验证计划，不是实测结论。

| 假设 | 验证方式 |
|---|---|
| 免费公开搜索上游能满足 agent 的 URL 发现与跨网站覆盖需求 | 用同一组真实 query 比较候选路线，记录有效 URL、独立网站覆盖、重复率、限流或阻断以及 batch 部分失败情况。 |
| 不硬性限制语种时，默认结果能大致匹配 query 语言 | 覆盖中文、英文与混合 query；记录实际结果语言和相关性，单独核对后续 language / 时间过滤参数的上游能力。 |
| CPU 上能完成 HTML、JS、PDF 与三类 OCR 内容的读取 | 分类型记录正文与识别质量、耗时、CPU / RAM 使用及失败样例；据此确定运行阈值。 |
| 渐进式披露能让 agent 找到所需原文，并可靠继续读取 | 验证首次 preview、目录、section / 位置续读、关键词定位；覆盖长页面、无目录内容、扫描 PDF 和部分提取失败。 |
| 同一 MCP 工具契约能服务目标 agent 并接入 Claude Code | 验证双方实际使用的 transport、protocol 与能力支持，完成工具发现、调用、batch 返回、续读和错误处理的集成测试。 |

## MCP 互操作说明

MCP 是通用协议，规定 client/server 的消息、工具调用与能力交换；实际接入仍需双方支持相同的 transport、protocol 和所用能力。通用协议不等于所有 client 的扩展能力或运行限制相同，因此 Claude Code 在这里是测试入口，而非产品绑定对象。依据：[MCP 官方架构说明](https://modelcontextprotocol.io/docs/learn/architecture)，核对日期 2026-09-09。

## 决策记录

- [MCP 与 agent 的职责边界](../adr/0001-agent-owns-deep-research.md)
- [免费与开源约束](../adr/0002-free-open-source-solutions-only.md)
- [query 内容约束归属](../adr/0003-caller-owns-query-disclosure.md)
- [v1 Search 与 Web Read 边界](../adr/0004-v1-search-read-boundary.md)
