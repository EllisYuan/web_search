---
status: accepted
---

# MCP 提供 web_search 与 web_read，Deep Research 由 agent 负责

在 [issue #5](https://github.com/EllisYuan/web_search/issues/5) 的方案讨论中，用户确认 MCP 提供可组合的检索工具，多轮 Deep Research 由调用方 agent 循环完成。`web_search` 只负责 URL 获取与整合，整套 MCP 另提供 `web_read` 读取网页并渐进式披露内容；相较于 MCP 内完成规划和综合并一次交付报告，选择这一边界是为了让 agent 决定搜索哪些问题、读取哪些来源以及何时继续研究。

首批服务用户个人的 agent 工作流。“多个来源”以多个独立网站的信息覆盖为目标，不以搜索引擎数量定义。`web_search` 支持数量受限的 batch，并按 query 分组返回；`web_read` 可独立读取 agent 提供的 URL，无需先调用 `web_search`。

`web_read` 首次返回 metadata、目录（若有）和限长正文，后续支持按 section 或位置继续读取，以及页内关键词定位。使用原文抽取，不依赖模型生成摘要；完整返回字段与具体配额后续设计。
