# 研究型 Source 与 Progressive Disclosure

日期：2026-09-10。用途：保存两项独立研究的一手依据、专题分析与独立核验；不是 production implementation，也不是最终契约批准。

## 用户提出的研究问题

- **Source 策略**：研究型报告到底需要什么样的信息源，如何定义信息量、广度、深度与证据充分性；据研究提出具体 Search 方案，不先凭直觉固定 URL 数量或来源配额。
- **Progressive Disclosure**：作为项目的核心亮点与难点独立深入研究，不预设只有 cursor 分页一种答案。
- **完整内容范围**：静态 HTML、JavaScript 页面、PDF 都需要支持，不能因技术限制轻易漏掉高价值资料；既有已接受范围还包括扫描 PDF、网页文字图片和独立图片 URL 的 OCR。免费开源、Windows、CPU-only 约束继续有效。

“具体深度搜索方案”不自动等于增加 `deep_search` tool。已确认的边界仍是 `web_search` 提供候选 URL 与 SERP metadata，`web_read` 独立读取指定 URL，Deep Research 的规划与综合由调用方 agent 完成。研究中建议的新增模式、数据结构、运行配额和组件选型必须与 accepted 决策分开。

## 已有项目证据

### 免费 Search

- [prototype 实测报告](../../../prototypes/free-search/REPORT.md)：SearXNG / Google 和 DDGS / Brave 的短窗口、低频复测、失败分类与部分失败记录；不能推出长期稳定性或全网 Recall。
- [ticket #6](https://github.com/EllisYuan/web_search/issues/6)：本轮开始时仍 open。本轮研究不替代用户的 prototype resolution。

### CPU-only Web Read

- [ticket #7 resolution](https://github.com/EllisYuan/web_search/issues/7#issuecomment-5599723724)：2026-09-09 用户评审后关闭，确认各格式功能路径和 Progressive Disclosure 方向可继续。
- [pinned prototype 报告](https://github.com/EllisYuan/web_search/blob/4c210d1/prototypes/cpu-web-read/REPORT.md) 与 [运行 trace](https://github.com/EllisYuan/web_search/tree/4c210d1/prototypes/cpu-web-read/runs)：已有受限 functional smoke，不是本轮新增运行，也不是公开互联网样本的完整质量/性能 benchmark。
- 候选 pipeline 为 Trafilatura / Playwright / pypdfium2 / RapidOCR / ONNX Runtime CPU；记录“曾运行”不等于批准最终组件、许可组合或版本锁定。本轮应核对候选的当前一手依据。
- 受控样本覆盖了中文/英文的独立图片、扫描 PDF、网页文字图片、静态 HTML、JS 页面和 text PDF；另有长扫描件逐页 preview 对照及注入部分页失败。不能从受控 reference 的 OCR 正确率推广到真实互联网、多栏、低清晰度、公式或图表语义。
- 主工作区本地 `.worktrees/cpu-web-read` 中的旧报告仍有“ticket open”历史描述，tracker 的后来 resolution 优先说明 ticket 状态；不改动该独立 worktree。

## 阅读顺序

综合结论在专题研究与核验完成后位于：

- [研究型报告的 Source 策略](../research-source-strategy.md) 与 [proposed Search 设计](../../design/research-source-strategy.md)。
- [Progressive Disclosure 深入研究](../progressive-disclosure.md) 与 [proposed 设计](../../design/progressive-disclosure.md)。

本目录保存五个互补专题及其 verification：`source-methodology`、`search-coverage`、`format-fidelity`、`disclosure-interaction`、`disclosure-representation`。最终完整性审查记录为 [`completeness-audit.md`](completeness-audit.md)；审查发现的八项问题（required-format gate、引用错配、instance/upstream 观测层级、增量 OCR 机制、identity 字段、context closure 边界、baseline 继承、database 措辞）已在四份综合文档中修正，复核记录见 [`correction-verification.md`](correction-verification.md)。这些研究不是对全部文献的穷尽式 systematic review；每份报告应声明实际核验范围、无法访问的来源与待验证假设。

可浏览版本：[`../research-navigation.html`](../research-navigation.html) 由 [`../build-research-navigation.py`](../build-research-navigation.py) 从四份 Markdown 渲染生成；Markdown 是权威来源，修改后需重新运行脚本。

## 证据口径

1. 文献支持的事实必须追到 owning primary source，并说明实际读取范围。
2. 原论文或框架在其他任务上的实验结果，不是本项目已复现的 benchmark。
3. 工程建议标为 proposed；示例 JSON 与交互 trace 标为假设示例。
4. 内容类型支持不等于任意内容无损，抽取失败、未处理区域、OCR 不确定性与输出截断必须分开。
5. 新的 runtime 实验、ticket resolution、最终 schema、SLA 和 git commit 不在本次研究已完成事项之列。
