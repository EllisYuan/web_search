---
status: accepted
---

# query 内容约束由调用方模型负责

在 [issue #5](https://github.com/EllisYuan/web_search/issues/5) 的方案讨论中，用户选择让 MCP 聚焦搜索任务，仅做基本入参校验，不对 query 做敏感信息检测或脱敏。query 的生成与适合外发的内容边界由调用方模型负责，tool description 应清楚说明 query 将用于外部搜索，帮助模型组织输入；description 是调用指引，不是强制脱敏机制。

与在 MCP 中加入内容识别、改写或拦截相比，这一选择避免 MCP 猜测和改变 query 的含义，同时意味着调用方传入的敏感内容不会由 MCP 自动移除。基本入参校验的具体规则仍待工具契约设计时确定。
