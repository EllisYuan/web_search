# `disclosure-interaction.md` 独立证据核验

> 核验日期：2026-09-10。本文不是对原 memo 的重述，而是尝试反驳其设计驱动事实，并记录可由 primary source 直接支持的范围。`confirmed` 只表示来源与原文能够支持该有限表述，不表示该事实已经证明适用于本项目；`corrected` 表示原文或 scope 需要收窄；`unverified` 表示本次没有足够的 primary evidence。未核验的 vendor blog、abstract-only record、动态 `main` branch、未来版本和本项目效果，不作为已证实事实。

## 核验范围与方法

本次独立复核了原 memo 中最影响 progressive disclosure 设计的 10 组 claims：人类 progressive disclosure 定义；ReAct 的 observation loop 与 task-specific results；SWE-agent 的 ACI/ablation；ToolSandbox 的 stateful trajectory evaluation；Lost in the Middle 的位置效应；MCP `Tools`、`Resources`、`Pagination` 三页官方规范；以及 Python/TypeScript SDK README 的实现示例。重点检查：

- 是否能从原始论文、官方规范或官方实现直接定位，而非只依赖 vendor blog 或摘要；
- 数字、版本和协议语义是否被原文支持；
- 原 memo 是否把其他 domain 的证据外推成 `web_read` 结果；
- access 是否是正文全文、部分正文、摘要/metadata 或动态页面。

本次**没有**新增验证 `web_read` 在本项目 corpus、目标 host、Windows CPU-only pipeline、HTML/JS/PDF/OCR/image coverage 上的质量 A/B、互联网泛化或 SLA；但项目已有一个必须继承的 Web Read functional-smoke baseline，不能把整条功能路径写成“尚未运行”。该 baseline 来自用户评审后关闭的 GitHub #7 resolution（2026-09-09）及 pinned report commit `4c210d1`：报告可读内容显示，CPU-only 路径已覆盖静态/JS HTML、text/scanned/mixed PDF、网页文字图片、独立图片 URL，以及 12 页扫描件的逐页 preview/continuation 与混合 PDF 的 partial failure；RapidOCR 3.9.2、ONNX Runtime 1.29.0、pypdfium2、Trafilatura、Playwright/Chromium 已在受控 smoke 中运行，OCR sessions 核验为 `CPUExecutionProvider`。这只是 constrained functional evidence，不是新的 research-agent quality A/B、公开互联网泛化、正式性能 benchmark 或 SLA。后续 proposal 应优先继承并复测这条 baseline，不应无理由替换既有 RapidOCR/ONNX Runtime CPU/pypdfium2 路径；组件版本和最终 contract 仍未锁定。

## 已有项目 baseline（非本轮新增运行）

| 证据 | 状态 | 可支持的有限结论 | 不能支持的结论 |
|---|---|---|---|
| GitHub #7 resolution，用户评审关闭 | `confirmed` by project record, comment body access limited | Web Read 的各格式功能路径和 Progressive Disclosure 方向已获评审后继续推进；resolution URL 是 <https://github.com/EllisYuan/web_search/issues/7#issuecomment-5599723724> | 本次 WebFetch 无法显示 comment body，因此不从 issue 页面单独重建细节；仍以项目现有 resolution 记录和 pinned report 为准 |
| pinned `REPORT.md` at commit `4c210d1` | `confirmed` as existing project evidence | 受控 functional smoke 已运行：静态/JS HTML、text/scanned/mixed PDF、网页文字图片、独立图片 URL；12 页扫描件逐页 preview/continuation；混合 PDF partial failure；中文/英文样本；CPU-only OCR path | 不是真实互联网质量、research-agent quality A/B、长期稳定性、完整 manifest coverage、正式 performance benchmark 或 SLA；39 manifest entries 也不等于 39 个真实网站 |
| Existing CPU pipeline | `confirmed` for this baseline; not a final lock | Report shows RapidOCR 3.9.2、ONNX Runtime 1.29.0、pypdfium2、Trafilatura、Playwright/Chromium；OCR det/cls/rec sessions use `CPUExecutionProvider` | 不据 smoke 直接批准最终 license/version/contract；但后续 design 不能在没有反证时把这些已运行路径替换成其他候选 |

因此本核验将“**功能路径已跑通受限 smoke**”与“**渐进披露改善 research-agent quality**”明确分层：前者是项目已有 evidence，后者仍是 open empirical question。

## Claim ledger

| ID | 原 memo claim | 状态 | 核验结果与限制 |
|---|---|---|---|
| C1 | Progressive disclosure 先展示少量核心选项，再按需提供 specialized options；入口和层级必须可发现 | `confirmed`，但仅为 human UI guidance | Nielsen Norman Group 原文明确给出 “Initially, show users only a few of the most important options” 和 “Offer a larger set of specialized options upon request”，并指出入口不明显、层级过深和过多步骤会增加成本。该页是 practitioner article，不是 research-agent experiment，因此原 memo 中“可迁移为 observation 设计方向”是 interpretation，不是实证结论。Primary: https://www.nngroup.com/articles/progressive-disclosure/ |
| C2 | ReAct 交错 `Thought`/`Action`/`Observation`，支持查询修正与 `NOT ENOUGH INFO` | `confirmed`，scope 已正确收窄 | arXiv HTML §2 与 Appendix C.1–C.2 可读；HotpotQA 示例有搜索、检查、改写查询、再次读取，FEVER 示例含 `NOT ENOUGH INFO`。这支持“observation 驱动循环”这一有限描述，不支持 server 暴露 hidden reasoning trace。Primary: https://arxiv.org/html/2210.03629。Limit: 论文 task/model/prompt 与本项目不同。 |
| C3 | ReAct WebShop 40.0% vs Act 30.1%；ALFWorld 最佳 ReAct 71% vs Act 45% | `confirmed`，不得泛化 | Table 3–4 中可核验这些 task-specific numbers；ALFWorld aggregate row 也列 ReAct average 57%、best-of-6 71%，Act best-of-6 45%。原 memo 已注明不是 `web_read` 保证，这个限定必须保留。Primary: https://arxiv.org/html/2210.03629。 |
| C4 | SWE-agent ACI 要求反馈 informative but concise；ablation 显示窗口、search、history 形状改变结果 | `confirmed`，但只能作 domain-specific interface evidence | arXiv HTML §2 与 §5.1/Table 3 支持该原则和原 memo 列出的方向：edit+linting 18.0% vs no linting 15.0%、no edit 10.3%；summarized search 18.0%、iterative search 12.0%、no search 15.7%；30-line 14.3%、100-line 18.0%、full file 12.7%；last 5 observations 18.0%、full history 15.0%。这些不是 `web_read` 默认窗口或阈值。Primary: https://arxiv.org/html/2405.15793v3。Limit: 代码修复环境；页面为 arXiv HTML，附录后段不完整。 |
| C5 | ToolSandbox 用完整、有状态、多轮轨迹及 milestones/minefields 评价，而不是只看一次 call 或最终答案 | `confirmed`，但数字来源需保留访问限制 | 可读的 arXiv HTML 支持 1,032 scenarios、34 tools、11 domains、平均 13.9 turns、3.80 tool calls，以及 stateful execution、trajectory snapshots、milestones/minefields。该 evidence 支持将中间依赖纳入 evaluation 的设计方向，不证明 progressive disclosure 更好。Primary: https://arxiv.org/html/2408.04682。Limit: 本次读取的 HTML/抽取在附录后段不完整；未据此宣称完整 benchmark 复现。 |
| C6 | Lost in the Middle 显示中间位置下降、U-shaped curve；长 context 不自动消除退化 | `confirmed`，原 memo 的 transfer 已正确标为 interpretation | arXiv HTML §2.3、§3.2、Figures 5/7/9 支持：multi-document QA 使用 10/20/30 documents，key-value retrieval 使用 75/140/300 pairs；相关信息在开头/结尾更易利用，extended-context models “not necessarily better”。更准确的 scope 是：当输入同时适合比较的模型时，更大 nominal context window 不保证更好的 context use；不能说长 context 在所有超窗任务都无益。Primary: https://arxiv.org/html/2307.03172。 |
| C7 | MCP `Tools` 为 model-controlled；可有 `structuredContent`、resource links、`isError`，`tools/list` pagination 和 deterministic ordering | `confirmed`，但“必须使用这些字段”是 proposal | 官方 2026-07-28 `Tools` specification 明确 Tools 是 model-controlled；`tools/list` supports pagination，server SHOULD deterministic order；tool result 可含 `structuredContent`、TextContent、resource links；execution error 用 `isError: true`。规范没有定义 `preview`/`find`/`EvidenceWindow`，所以原 memo 以此推出的字段只是 project proposal。Primary: https://modelcontextprotocol.io/specification/2026-07-28/server/tools。 |
| C8 | MCP `Resources` 是 application-driven，不能假设 `resources/list` 自动注入或存在统一 picker | `confirmed`，但不等于每个 host 都没有 picker | 官方 `Resources` specification 原文说明 host/application 决定如何纳入 context，可通过 UI explicit selection、search/filter 或 heuristics 自动 inclusion；协议不规定单一 interaction model。也确认 `resources/list`、`resources/read`、templates、text/binary contents 与 annotations。原 memo 的“不能把 Resources discovery 当唯一入口”是合理 project interpretation，而非 host capability matrix。Primary: https://modelcontextprotocol.io/specification/2026-07-28/server/resources。 |
| C9 | MCP cursor 是 opaque，page size 由 server 决定；client 不应解析/修改；标准 list operations 有 pagination | `confirmed`，且 custom `web_read` continuation 仍是项目语义 | 官方 pagination 页明确 cursor opaque、server determines page size、client MUST NOT assume fixed size or parse/modify cursor；列出的 operations 为 `resources/list`、`resources/templates/list`、`prompts/list`、`tools/list`。原 memo 正确指出 MCP 不自动定义正文 `web_read` continuation；绑定 snapshot/representation/query 的做法是 proposed contract。Primary: https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/pagination。 |
| C10 | Official Python/TypeScript SDK README 展示 tool/resource registration 和 structured result 形状 | `confirmed` as mutable README examples; version claims unverified | Python README 当前页面可见 `@mcp.tool()`、`@mcp.resource()`、`client.call_tool()` 和 `result.structured_content`，并称 stable line 为 SDK v2；TypeScript README 可见 `McpServer.registerTool`、Zod `inputSchema` 和 text `content` result。两者均为 repository `main` 的动态 README，无 commit hash 或 fixed release tag；不能从该页锁定 SDK version、runtime compatibility 或 target host behavior。Primary: https://github.com/modelcontextprotocol/python-sdk and https://github.com/modelcontextprotocol/typescript-sdk。 |

## Demonstrably corrected or narrowed claims

1. **SDK version/compatibility must remain unverified.** README 的 “SDK v2”/“main” 是当前动态页面信息，不是 immutable version pin；原 memo 已避免锁定版本，但后续实现不能把 README example 当作 contract。
2. **Lost in the Middle 的结论必须带 scope qualification。** 可证实的是位置效应与“更大 context window 不必然更好”；不可推出“large-context all-at-once 在所有文档任务都失败”或“更大窗口总是无益”。原 memo 的策略表应继续使用“主要失败模式/待验证”，而不是普遍定律。
3. **SWE-agent numbers 不能变成 web_read 默认参数。** 它们确实存在于 Table 3，但任务是 SWE-bench code repair；100-line window、last-5 observations 等只应作为待验证 ablation 的候选，不应写成目标阈值。
4. **MCP normative semantics 与 project design semantics 必须分开。** Tools/Resources/Pagination 官方页支持 protocol primitives，不支持 `preview`、`find`、`read`、`expand`、`EvidenceWindow`、`coverage`、`negativeResult` 或 cursor binding 的具体 contract；这些继续标注为 proposal。
5. **ToolSandbox 数字的 source access 要诚实披露。** 本次只依赖可读取的 arXiv HTML/抽取内容，附录后段不完整；因此可以核验正文/表格中列出的 headline figures，但不能声称完整复核论文所有附录或复现 benchmark。

除上述收窄外，本次没有找到足以证明原 memo 其他核心设计事实为错误的 primary evidence。`Information Foraging`、`Training Wheels in a User Interface`、`Using Information Scent...`、`Guidelines for Human-AI Interaction` 与 `Xerox Star` 在原 memo 中已标为 metadata/summary-only 或 human guidance；本次没有把其未读正文升级为 agent evidence，因此不改写为 confirmed。

## 未核验的高影响 claims

- progressive disclosure 的 `preview -> find -> evidence window` 是否比 bounded full Markdown、fixed chunks 或 all-at-once 在 research-agent tasks 上提升 coverage/quote fidelity；当前没有直接 A/B evidence。
- structure-aware parser 的 heading/table/caption/footnote association 是否低于 fixed chunks 的错误成本；尤其是多栏 PDF、跨页脚注、OCR。
- HTML/JS-rendered、PDF text、scanned PDF/OCR、图片文字和 multilingual/no-heading input 的 coverage semantics、locator 稳定性与 negative-result calibration。
- MCP host 是否实际提供 Resource picker、自动 injection、URI read 或 tool-result resource handling；官方规范不能替代目标 host conformance test。
- `nextCursor` 与 source snapshot、contentHash、extraction version、query constraint 的绑定策略是否在页面 mutation、重复调用和 partial failure 下可审计。
- summary route 是否有净收益；任何 model-generated summary 都仍与 no-model-extraction baseline 冲突，不能在 `web_read` 中静默启用。
- 本项目 Windows/CPU-only implementation 的**新增** HTML rendering、OCR、PDF extraction 和 latency/accuracy benchmarks；已有 pinned report 的受限 functional smoke 不应被抹掉，也不能升级为正式性能 benchmark、公开互联网质量或 SLA。

## 最终判定

原 memo 的核心 thesis 没有被本次 primary-source review 推翻：渐进式披露应作为一个待验证的、caller-controlled navigation loop，而不是把全文压缩成摘要。证据层级应明确分为两层：项目已有 `4c210d1` Web Read report/Issue #7 resolution 已证明受控 CPU-only 格式路径与逐页 preview 方向实际运行过；但它没有证明 overview/find/evidence-window loop 对 research-agent 的质量提升。论文与 MCP evidence 仍支持接口和评测假设，不支持直接锁定 schema、窗口大小、SDK version 或默认 mode。下一步应在已有 RapidOCR/ONNX Runtime CPU/pypdfium2 等 baseline 上做 frozen-corpus paired evaluation 和 host capability/conformance matrix，不应无理由替换这些已运行路径。

## Accessed primary URLs

- https://www.nngroup.com/articles/progressive-disclosure/
- https://arxiv.org/html/2210.03629
- https://arxiv.org/html/2405.15793v3
- https://arxiv.org/html/2408.04682
- https://arxiv.org/html/2307.03172
- https://modelcontextprotocol.io/specification/2026-07-28/server/tools
- https://modelcontextprotocol.io/specification/2026-07-28/server/resources
- https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/pagination
- https://github.com/modelcontextprotocol/python-sdk
- https://github.com/modelcontextprotocol/typescript-sdk
- https://github.com/EllisYuan/web_search/issues/7#issuecomment-5599723724
- https://github.com/EllisYuan/web_search/blob/4c210d1/prototypes/cpu-web-read/REPORT.md
