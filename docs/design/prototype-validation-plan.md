---
status: planned
planned_on: 2026-09-09
---

# 免费 Search 与 CPU-only Web Read prototype 验证

本文件索引 2026-09-09 制定的验证计划，完整实验问题与方案存于各自 GitHub ticket；计划和临时实验护栏不是最终选型或已接受的性能阈值。

2026-09-10 核对状态：Search [#6](https://github.com/EllisYuan/web_search/issues/6) 已有真实 smoke 与失败观测，但仍 open；Web Read [#7](https://github.com/EllisYuan/web_search/issues/7#issuecomment-5599723724) 已完成受限 functional smoke 并经用户评审关闭。#7 只确认 CPU-only 各格式功能路径与 Progressive Disclosure 方向可继续，不代表正式性能 benchmark、真实互联网样本覆盖或最终 tool schema 已通过。进一步设计以 [Source / Progressive Disclosure 专题研究](../research/2026-09-10-source-disclosure/README.md) 为入口。

前提是已确认的 [Search MCP 产品边界](https://github.com/EllisYuan/web_search/issues/5#issuecomment-5594196457)，总览见 [深度 Web Search MCP 技术路线](https://github.com/EllisYuan/web_search/issues/1)。

| 顺序 | 决策 ticket | 首先要排除的风险 |
|---|---|---|
| 1 | [验证免费 Search 的 URL 发现质量与上游稳定性](https://github.com/EllisYuan/web_search/issues/6) | 免费上游受阻或结果无法支撑真实 query 的独立网站覆盖。 |
| 2 | [验证 CPU-only web_read 的完整读取范围与渐进式披露](https://github.com/EllisYuan/web_search/issues/7) | 三类 OCR 在 CPU 上的质量与资源问题，以及原文不能可靠续读或定位。 |

两个 ticket 都是 map 的原生 sub-issue，并依赖已关闭的产品边界 ticket；相互不 blocking，可以独立认领。顺序是验证优先级，不代表 Search 必须先于 Web Read 才能调用。

每次执行先认领一个 ticket；用真实输入、可复核原文、逐条观测和失败样例解决问题。候选组件与实验预算只用于 prototype，不是产品契约。完成后将可运行的 throwaway artifact 及真实 branch/commit 链接回填对应 ticket，由用户参与评审后才能发布 resolution 并关闭。
