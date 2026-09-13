# Web Search

本项目为 agent 提供联网 Search 和 Web Read 能力，支持 agent 发现信息来源并逐步读取内容。

## Language

**Search**:
为 query 获取并整合候选 URL 的操作，结果包含用于选择来源的相关信息，不包含目标网页的正文读取。
_Avoid_: Web Read、Deep Research、完整研究报告

**Web Read**:
读取指定 URL 的正文并呈现为结构化 Markdown 的操作；URL 可以来自 Search，也可以由 agent 直接提供，长正文可通过渐进式披露继续读取。
_Avoid_: Search、完整研究报告

**Search Batch**:
一次提交的一组数量受限的 query，各 query 的搜索结果分别成组呈现。
_Avoid_: 合并问题、混合结果集

**Source**:
agent 获取信息的来源网站；“多个来源”指多个独立网站的信息覆盖，不要求来自多个搜索引擎。
_Avoid_: 搜索引擎数量

**Progressive Disclosure**:
agent 逐步获取所需网页内容的交互方式，而非首次读取就接收全部内容。
_Avoid_: 一次性全文输出

**Deep Research**:
agent 围绕研究问题循环搜索、评估信息并形成结论的过程。
_Avoid_: 单次 Search
