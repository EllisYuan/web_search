# 研究代理的渐进式披露交互与实证

> 研究日期：2026-09-10  
> 主题：`web_read` 面向 research agent 的 progressive disclosure，而不是面向人类阅读器的简单分页。  
> 性质：本文是选择性 research memo。`事实`来自一手论文、官方规范或官方实现；`解释`是对事实的归纳；`建议`是未锁定、未实现、未验证的 proposal；`待验证`是需要在本项目 corpus、目标 host 和实际 agent 上复测的假设。

## 结论先行

建议把 `web_read` 定义为**可查询、可定位、可扩展、可引用的文档导航工具**，而不是只提供 `URL -> 一次性全文 Markdown` 的转换器。默认交互建议为：

```text
preview metadata/outline
  -> deterministic find
  -> read a structure-aware section or evidence window
  -> expand prerequisites or surrounding context
  -> caller explicitly chooses whether to follow a reference
```

这不是把 server 变成 Deep Research agent。按照项目已接受的 [ADR-0001](../../adr/0001-agent-owns-deep-research.md) 与 [ADR-0004](../../adr/0004-v1-search-read-boundary.md)，planning、source selection、继续研究、冲突判断和最终 synthesis 仍由 caller agent 负责；`web_read` 负责原文读取、结构化 Markdown、bounded output、continuation、定位和状态披露。

### 核心判断

1. **人类 HCI 证据支持“先少量核心内容、再按需展开”，但不能直接当作 agent 证据。** Progressive disclosure 能降低初始复杂度，也会增加 discoverability 和额外交互成本；层级、入口和返回路径必须可见。[S1][S2]
2. **Agent 的直接实证更支持“短而可行动的 observation + 可继续读取的状态”，而不是无界全文。** ReAct 证明了 observation 驱动的循环检索与修正；SWE-agent 的 ablation 显示界面、搜索输出、窗口大小和历史压缩会改变成功率；ToolSandbox 说明应评价完整、多轮、有状态轨迹，而不是只评价一次 tool call。[S5][S6][S7]
3. **长上下文不能被当作默认安全网。** Lost in the Middle 在多文档问答和 key-value retrieval 中观察到明显的 U-shaped position effect；更大的 context window 不自动消除中间位置退化。[S8]
4. **默认路线应是 structure-aware progressive read。** 短文档可 bounded full Markdown；结构清楚的长文档走 `preview -> find -> read/expand`；无 heading、OCR、结构解析失败时退回 fixed blocks + page/coordinate locator；大型全文一次性读取只能显式 opt-in。
5. **preview 与 evidence window 必须是原文、可复核的 deterministic output。** `web_read` v1 不应生成事实性摘要，也不应把模型摘要当作正文抽取；如未来需要摘要，应由 caller 或独立、明确标记的可选能力处理。
6. **MCP Resources 不能作为唯一发现入口。** 官方规范把 Resources 定义为 application-driven，交互模式由 host/application 决定；Tools 才是 model-controlled。`web_read` 应可直接接受 caller 提供的 URL，并可选返回 `resource_link`，而不是等待 host 自动把资源列表注入模型。[S9][S10]

## 1. 证据边界：人类 UI、agent 实证、MCP 规范分开看

### 1.1 人类 HCI 原则不等于 agent 结论

NN/g 对 progressive disclosure 的定义是先展示少量最重要的选项，再按需提供 specialized options；其文章同时强调，入口不可见、层级过深或把高频功能藏得太深会造成额外成本。[S1] Carroll 与 Carrithers 的早期 `Training Wheels in a User Interface` 论文摘要报告，训练界面相对 conventional interface 能减少常见错误，并带来更快学习、更强任务表现和更好的理解；Crossref 记录只能提供摘要，不能据此恢复实验细节。[S2]

这些材料适合支持以下**人类界面原则**：

- 初始状态不要要求用户先理解完整功能集合；
- 低频或高级内容应可按需展开；
- 展开入口必须可发现，且用户能知道会得到什么；
- “少显示”不是永久隐藏，也不是无条件增加层级；
- 任务需要来回比较的内容不宜被拆到彼此难以返回的页面。

但人类能从视觉布局、颜色、空间位置和熟悉的交互控件中推断 affordance；agent 通常需要 schema、`locator`、状态字段、cursor 和明确的下一步动作。因此，下面的 agent 设计不是把 GUI 原则原样搬到 MCP，而是把其中的“低初始复杂度 + 可发现展开”转成结构化 observation。

### 1.2 Information foraging 是导航理论，不是 web_read 的 benchmark

Pirolli 与 Card 的 `Information Foraging` 是 1999 年 *Psychological Review* 的原始理论论文；本次可独立核验到 Crossref 的作者、题目、期刊、年份和页码，但未能读取完整正文。[S3] Chi、Pirolli、Chen 与 Pitkow 的 CHI ’01 论文题为 `Using Information Scent to Model User Information Needs and Actions on the Web`，本次同样只核验到 Crossref metadata 和题目，未把其未读取的正文当作事实。[S4]

因此，本 memo 只把 `information scent` 用作**解释性类比**：标题、命中词、表格标题、页码、section path、图注和引用关系都可以成为 caller 选择下一步读取的可复核线索；不能把“信息气味”当成已经证明对本项目 agent 的效果量。

### 1.3 Agent 的直接实证

#### ReAct：observation 驱动的继续检索

ReAct 将 `Thought`、`Action`、`Observation` 交错：Thought 不改变外部环境，Action 触发环境反馈，Observation 进入下一轮上下文。[S5, §2] 在 HotpotQA 示例中，agent 先搜索、检查结果、改写实体查询、再次读取；在 FEVER 中，当证据不足时会继续检索或输出 `NOT ENOUGH INFO`。[S5, Appendix C.1-C.2]

论文在 WebShop 报告 ReAct 成功率 40.0%，Act 为 30.1%；在 ALFWorld 中，论文列出的最佳 ReAct prompt 为 71%，Act 为 45%。这些结果是特定模型、prompt 和任务下的结果，不是 web_read 的普遍性能保证。[S5, Table 3-4]

论文还展示了人在中间 Thought 节点做小幅编辑后，后续行动可以改变并完成任务；原文描述为 `by a human simply editing two thoughts`。[S5, Appendix A.3, Figure 5] 这支持“中间状态可纠正”这一设计方向，但不证明 server 应保存或暴露模型隐式 reasoning trace。对本项目，更安全的映射是保存可操作的 read state、locator、coverage 和错误状态，而不是把 hidden chain-of-thought 当作 API。

#### SWE-agent：界面和 observation 形状会改变结果

SWE-agent 明确将 ACI 设计为 agent 的操作界面，并给出原则：命令要简单，高阶操作要少步骤，反馈应有信息量但避免冗余；原文短引为 `Environment feedback should be informative but concise.`。[S6, §2]

该论文的 ablation 对本项目尤其有价值：

- 专用 edit + linting 为 18.0%，去掉 linting 为 15.0%，去掉专用 edit 为 10.3%；
- 汇总式搜索为 18.0%，迭代式搜索为 12.0%，不提供搜索工具为 15.7%；
- 30 行文件窗口为 14.3%，100 行为 18.0%，整文件为 12.7%；
- 只保留最近 5 次 observation 为 18.0%，保留完整历史为 15.0%。

这些不是 web_read 的可直接复制参数，而是**同一 paper 内的界面比较证据**：过小窗口会丢上下文，整文件会带入噪声；逐条浏览大量搜索结果会拖长轨迹；过多旧 observation 可能比压缩后的历史更干扰。SWE-agent 的任务是代码修复，不是文献研究，因此应把上述数值当作 domain-specific evidence，而不是目标阈值。[S6, Table 3, §5.1]

#### ToolSandbox：完整轨迹和中间状态应进入 evaluation

ToolSandbox 将 benchmark 定位为 stateful、conversational、interactive，包含 1,032 个场景、34 个 tools、11 个 domain；其平均轨迹为 13.9 turns 和 3.80 tool calls。[S7, §1-3, Table 4] User、Agent 和 Execution Environment 通过 Message Bus 交互，环境保存状态和对话历史，并在每一轮后检查 snapshot。论文原文包括：`Allows for fully interactive, dynamic trajectory collection`、`Multiple trajectories can lead to the same outcome.`[S7, §2.2-2.3]

其 `milestones` 与 `minefields` 机制说明：只看最终答案会掩盖 agent 是否完成了中间依赖、是否在失败后恢复、是否调用了不存在的 tool。对 web_read，等价的评测对象应包括：是否先查看结构、是否找到了正确 representation、是否补读了表头/脚注、是否在 no-match 时正确报告 coverage、是否因 stale cursor 重复调用，而不只是最终答案是否包含某个词。[S7, §2.3, Appendix A.7]

#### Lost in the Middle：大 context 不是稳定导航

Liu 等人的长上下文论文在 multi-document question answering 和 synthetic key-value retrieval 中移动相关信息位置。正文报告相关信息在开头和结尾通常更容易被利用，中间位置出现明显下降，形成 `U-shaped performance curve`；论文还指出 `extended-context models are not necessarily better`。[S8, §1-4, Figure 1, Figure 5, Figure 7]

在 multi-document QA 中，实验通过 10、20、30 篇文档改变干扰量和答案文档位置；在 key-value retrieval 中使用 75、140、300 个 key-value pairs。论文也报告：把 query 放在数据前后能改善 key-value retrieval，说明上下文结构和 query 可见性本身会影响结果。[S8, §2-4, Figure 9]

对本项目的含义不是“永远切碎文本”，而是：

- 证据应优先靠近 response 开头并带明确 locator；
- 不要把无关长正文和命中证据混在同一个默认 observation；
- `expand` 应补齐限定条件，而不是重新倒入整个文档；
- `full` 应是显式模式，用于最终核对或短文档，而不是默认导航。

## 2. MCP 的可用原语与限制

### 2.1 Tools：model-controlled、可结构化、可返回 resource link

官方 2026-07-28 Tools specification 将 Tools 定义为 model-controlled；server 必须提供 tool 名称、description 和 `inputSchema`，可选 `outputSchema`，tool result 可包含 TextContent、`structuredContent`、resource links 或 embedded resources。[S9]

规范还建议 deterministic tool ordering，以利于 client cache 和把 tools 放入 model context 时的 prompt cache；`tools/list` 支持 pagination，tool result 的 execution error 应通过 `isError: true` 给 model 可行动的反馈，而不是把所有问题伪装成 protocol error。[S9]

对 `web_read` 的直接 implication 是：

- `structuredContent` 应承载 `source`、`mode`、`matches`、`evidence`、`coverage`、`warnings`、`nextCursor`；
- TextContent 作为兼容和人类可读回退，不能成为唯一接口；
- extraction failure、OCR low confidence、JS content unavailable、truncated 等应成为结构化状态；
- tool 可以返回 `resource_link`，但不能假设 link 一定会出现在 `resources/list`。[S9]

### 2.2 Resources：application-driven，不能假设自动发现

官方 Resources specification 将 Resources 设计为 application-driven，host/application 可以用 UI 显示、让用户筛选，或按 heuristics 自动纳入 context；协议本身不规定一种交互模式。[S10, User Interaction Model]

`resources/list` 支持 cursor pagination，`resources/read` 按 URI 返回 text 或 binary contents，resource templates 支持参数化 URI；资源也可以带 `audience`、`priority`、`lastModified` annotations。[S10]

由此得出的**解释**是：`web_read` 不能把 Resource discovery 当作唯一入口。目标 agent 可能没有可用的 resource picker，也可能不会主动 `resources/list`；工具必须直接接受 caller 提供的 URL。若 server 选择返回稳定 snapshot，可以把 snapshot 或 evidence ledger 作为可选 Resource 暴露，但主体 navigation 仍由 `web_read` tool 完成。

### 2.3 Pagination：cursor 是 opaque，不能被当作页码

官方 pagination specification 规定 cursor 是 opaque string，page size 由 server 决定；client 只应透传，不能解析或修改。支持 pagination 的标准 list operation 包括 `resources/list`、`resources/templates/list`、`prompts/list` 和 `tools/list`。[S11]

这不等于 MCP 自动替 `web_read` 的正文分页。自定义 `web_read` result 需要自行定义 `nextCursor` 或 `continuation` 语义，并将其绑定到相同的 source snapshot、representation、query constraint 和 extraction version；query 或 source version 发生变化时，应创建新的 continuation，而不是复用旧 cursor。这部分是本项目 proposal，不是 MCP 标准提供的语义。

### 2.4 官方 SDK implementation examples

Official Python SDK README 展示了以 decorator 注册 tool 和 resource template：

```python
@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

@mcp.resource("greeting://{name}")
def greeting(name: str) -> str:
    """Greet someone by name."""
    return f"Hello, {name}!"
```

README 还展示 client 通过 `call_tool("add", {"a": 1, "b": 2})` 调用并读取 `result.structured_content`。[S12] 这是验证 MCP server/tool/resource registration 形状的 implementation example；当前页面属于动态 repository `main`/SDK v2 README，不是 immutable SDK version 或本项目应采用的版本锁定，也没有证明目标 host 的 resource read UI。

Official TypeScript SDK README 可读到 `McpServer.registerTool`、Zod `inputSchema` 和 `{ content: [{ type: 'text', text: ... }] }` 的 tool result 示例；当前页面是动态 repository `main`/SDK v2 README，没有 immutable commit pin，也没有展示完整 client `readResource` 或 pagination code，因此不能据此锁定 SDK version 或补出未显示的 API。[S13]

## 3. 推荐的交互模型（proposal，未锁定）

### 3.1 四类动作

建议把下列动作作为同一 `web_read` tool 的 `action` 候选，或拆成多个小 tool；两种暴露方式都尚未决定，需用目标 host smoke test 比较。字段名为 proposal，不是已批准 contract。

#### `preview`

目标是提供可导航的确定性 overview，而不是摘要：

```json
{
  "action": "preview",
  "source": "https://example.org/report",
  "max_outline_items": 40,
  "include": ["metadata", "outline", "representation_status"]
}
```

建议返回：

- `source`: `requestedUrl`, `resolvedUrl`, `mediaType`, `retrievedAt`, `contentHash`；
- `representation`: `static_html`, `rendered_dom`, `pdf_text`, `ocr_text`, `image` 等；
- `outline`: heading path、page range、table/figure markers；
- `length`: pages/blocks/chars 等 server-observed counts；
- `warnings`: `javascript_required`, `headings_missing`, `ocr_low_confidence`, `content_truncated`；
- `coverage`: 当前 representation 的覆盖范围。

不要在 `preview` 中输出“本章主要结论是……”这类 model-generated summary。可以输出原始标题、首句、section label 和确定性 match reason，例如 `exact_title_match`。

#### `find`

目标是 query-targeted preview，不做事实性 synthesis：

```json
{
  "action": "find",
  "source": "https://example.org/report",
  "query": "primary endpoint",
  "scope": "document",
  "limit": 5
}
```

建议默认按以下顺序做可复现 matching：exact phrase、case/Unicode/hyphen normalization、heading/table/caption/footnote scan、paragraph/block matching。可选 semantic retrieval 只能作为额外 route，必须仍返回 verbatim text、match type 和 locator；不能只返回 embedding 命中后的生成摘要。

`find` 的空结果不应是简单的 `not_found`。建议：

```json
{
  "matches": [],
  "coverage": {
    "status": "partial",
    "scope": "rendered_dom_text",
    "explanation": "The initial HTML was not searched; image text and unloaded tabs were not searched."
  },
  "negativeResult": {
    "meaning": "not_found_in_searched_representation"
  }
}
```

#### `read`

目标是按结构或稳定 locator 读取原文：section、subsection、page、table、figure、paragraph 或 evidence block。建议同时提供 `sectionPath`、`page`、`blockId`、`charRange`（如可稳定生成）和 source/version hash；不要把纯 character offset 作为唯一 locator，因为 HTML reflow、PDF layout 和 OCR 都可能改变它。

```json
{
  "action": "read",
  "source": "https://example.org/report",
  "locator": {"sectionId": "sec-3"},
  "include": ["body", "tables", "captions", "footnotes"]
}
```

响应仍应是结构化 Markdown 的 bounded slice，而不是模型改写的 prose。若被 hard limit 截断，必须返回 `truncated: true` 和可继续的 `nextCursor`。

#### `expand`

目标是围绕已知 match 或 evidence 扩展，并优先补齐会改变 interpretation 的前置条件：

```json
{
  "action": "expand",
  "source": "https://example.org/report",
  "matchId": "m-1",
  "direction": "both",
  "includePrerequisites": true
}
```

`includePrerequisites` 的推荐类别：

- section heading；
- table caption、header、unit；
- figure caption、legend；
- footnote；
- definition；
- sample/time-range qualifier；
- preceding limitation or exception paragraph。

这里的“扩展”不是无条件扩大 token 数，而是补齐证据解释所需的最小语义边界。

### 3.2 Citation-ready `EvidenceWindow`

建议所有 `find` 命中都能升级为以下形式；这是 proposal，未实现：

```json
{
  "evidenceId": "ev-1",
  "quote": "The primary endpoint was measured at week 12.",
  "contextBefore": ["3.2 Outcomes"],
  "contextAfter": ["Secondary endpoints were assessed at week 24."],
  "prerequisites": [
    {
      "type": "table_caption",
      "text": "Table 4. Primary endpoint by treatment group."
    },
    {
      "type": "footnote",
      "text": "Values are adjusted for baseline score."
    }
  ],
  "locator": {
    "sourceId": "src-1",
    "sectionPath": ["Results", "Outcomes"],
    "page": 17,
    "blockId": "p-442"
  },
  "contentHash": "sha256:...",
  "extractionMethod": "pdf_text",
  "ocrConfidence": null
}
```

server 可以保证的事实应限于 quote、locator、hash、retrieved time、extraction state；`claim`、`supports/contradicts` 等判断若由 caller model 生成，必须标记为 caller-created，不应伪装成 server 已验证。

### 3.3 Reference following 必须由 caller 控制

`web_read` 可以返回链接、引用文本、`resource_link` 或“相关引用候选”，但默认不自动 fetch 全部引用，也不自动扩展到 cited source。建议结果提供：

```text
relatedReferences[] = {
  url,
  anchorText,
  relation: "cites" | "cited_by" | "same_document_link",
  locator,
  selected: false
}
```

只有 caller 明确发起下一次 `web_read`，才读取该 URL。这样保持 ADR-0001 的 agent-owned source selection，也避免 citation graph 让一次读取不可预测地扩张。

### 3.4 No-model-extraction baseline 与 optional summary 的冲突

当前产品边界要求 `web_read` 使用原文抽取，不依赖模型生成摘要。建议 v1 明确保持：

- `preview` 是 deterministic metadata/outline/match cue；
- `find` 是原文窗口；
- `read/expand` 是结构化 Markdown 原文；
- 不输出未经标记的 model summary。

未来若实验显示某些任务需要摘要，可另设 caller-selected `summarize` route 或外部 agent 步骤，且必须标记 `generated: true`、`sourceCoverage`、`model`/`prompt` provenance 和引用回链；不能静默把摘要混进 extraction，也不能让摘要替代 evidence window。provider/model integration 不在本 memo 选择范围内。

## 4. 策略比较：渐进式不是盲目追求少 token

“Do to the extreme”应理解为同时优化 coverage、quote fidelity、caveat preservation、tool-call burden、latency、cost 和 correction，而不是只最小化 output tokens。

| 策略 | 强项 | 主要失败模式 | 建议角色 |
|---|---|---|---|
| Bounded full Markdown | 调用少；实现和人工复制简单；适合短文档 | 长文档噪声高；中间证据注意力失败；容易遗漏表脚注 | 短文档默认候选；用户明确要求全文时 opt-in |
| Fixed chunks | cursor 和上限容易定义；无 heading 时仍可工作 | 切断标题、表格、caption、footnote、定义；调用次数上升 | 无结构/OCR/解析失败的 fallback |
| Structure-aware blocks | 保留 section、table、figure、page 和语义边界 | 解析复杂；错误 inferred structure 可能误导 | 长文档默认候选 |
| `preview -> find -> read/expand` | 先给少量高价值线索；caller 可根据 observation 调整 query | 需要至少一次导航调用；outline 或 matching 质量不足时会迷路 | 推荐默认 loop |
| Evidence windows | 引用 ready；可把 caveat/prerequisite 放在同一窗口 | 窗口太小会丢限定条件；补读需要额外调用 | 研究问答、法规、科学 PDF 默认增强 |
| Model summary | token 压缩高；人工浏览快 | hallucination、unsupported abstraction、丢 qualifier；无法替代原文定位 | v1 不启用；未来仅 explicit optional route |
| Large-context all-at-once | 逻辑简单；一次保留全局上下文 | cost/latency 高；中间位置利用下降；agent 难以知道下一步 | 显式 final-review 模式，非默认导航 |

从 SWE-agent 的搜索和窗口 ablation 以及 Lost in the Middle 的位置实验看，最合理的目标不是“一律更小”，而是**让每次 observation 足够完成当前决策，同时把下一步继续读取的 locator 明确交给 agent**。[S6][S8]

## 5. 四个 worked long-document examples

### 5.1 HTML 标准/政策文档：标题清楚、限定条件分散

**场景。** 长 HTML 标准有清晰 headings，但 retention、exception、effective date 分散在章节、脚注和附录。

**建议 loop。**

```text
preview
  -> outline + section/page ranges + footnote count
find("retention period")
  -> exact matches with sectionPath and blockId
read(section="Data retention")
  -> bounded structured Markdown
expand(matchId, includePrerequisites=true)
  -> definition + exception + footnote + effective-date qualifier
```

**关键行为。** `find` 的三个命中不应被 server 合并成“本政策允许保存 X 天”；caller agent 负责比较冲突。若正文有链接到 another policy，结果只放 `relatedReferences`，由 caller 决定是否继续读取。

**负面结果。** 若只搜索了 extracted HTML text，应返回 `not_found_in_searched_representation`；不能写成“政策没有 retention period”，因为图片、折叠面板、附件或未加载脚注可能未被搜索。

### 5.2 JavaScript-rendered documentation：静态 HTML 为空

**场景。** 初始 HTML 是 app shell，正文、tabs、折叠 API 示例由 JavaScript 加载。

**建议 preview 状态。**

```json
{
  "representation": {
    "staticHtml": "insufficient",
    "renderedDom": "available"
  },
  "warnings": ["content_not_present_in_initial_html"]
}
```

**建议 loop。**

1. `preview` 先声明当前读取的是 initial HTML 还是 rendered DOM；
2. 若 server 的 HTML/JS pipeline 已完成，`find` 只在 rendered representation 上搜索并返回 `representation`；
3. 如果 tab 尚未加载或需要 click 才有内容，返回 `partial` / `unknown` 和下一步所需的 caller-visible state；
4. 不自动追踪所有 XHR endpoint，也不自动跟随文档内部链接；
5. caller 可显式请求同一 URL 的另一 representation 或直接提供 API URL。

**为什么。** 把未渲染 shell 当作完整正文会把 parser failure 误报为 negative fact；MCP tool error/coverage 语义应让 agent 能自我修正，而不是收到一个看似成功的空 Markdown。[S9]

### 5.3 多栏科学 PDF：表格、图注、脚注决定解释

**场景。** 研究报告有 two-column layout、Table 4、Figure 2 和跨页 footnotes；query 命中表格中的一个数值。

**结构块。**

```text
Document
├── Section
│   ├── Paragraph
│   ├── Equation
│   ├── Table
│   │   ├── Caption
│   │   ├── Header
│   │   ├── Body
│   │   └── Footnotes
│   └── Figure
│       ├── Caption
│       └── Legend
```

**证据窗口。** 命中 `12.4` 时，`read/expand` 至少返回：表格标题、column、row、unit、page、相关 footnote、extraction method，以及是否 OCR。只返回 `12.4` 不具备 citation-ready 质量。

**对照策略。** bounded full Markdown 可能在多栏重排时把表头与数值分离；fixed chunks 可能把 footnote 切到下一 chunk；structure-aware block 即使需要更多 parser 工作，也能把 interpretation prerequisites 绑定到 evidence。这个判断是 proposal，需要在项目 PDF/OCR corpus 上验证，不是本次文献已证明的通用 benchmark 结果。

### 5.4 扫描 PDF/图片型多语言报告：无 heading、OCR 不完整

**场景。** 扫描报告没有 text layer，标题不一致，中英文混排，关键信息可能只在 chart 或图片文字中。

**建议 fallback。**

```text
OCR text
  -> page/block fixed slices
  -> token/phrase match with bbox
  -> image/page resource link
  -> confidence and coverage warning
```

命中应包括：

```json
{
  "matchType": "ocr_token",
  "ocrConfidence": 0.71,
  "locator": {"page": 6, "bbox": [120, 340, 440, 390]},
  "coverage": {"status": "partial", "scope": "ocr_text_only"}
}
```

`preview` 可以确定性地报告 page count、识别语言、OCR block、字号/粗体线索、table-like region 和 image region；不应把这些线索综合成“第 6 页讨论了某主题”的模型摘要。若 query 是中文而 OCR 只保留英文转写，也应披露 representation 限制；caller 可以改写 query 或请求 page image，而不是得到全局 negative claim。

## 6. 评测计划（proposal，未运行）

### 6.1 Paired controlled evaluation

用同一批 frozen source snapshots、同一组 research tasks、同一 agent/model、同一 upstream/host adapter 和相同 hard budget，比较下列 variants：

1. bounded full Markdown；
2. fixed chunks；
3. structure-aware blocks；
4. `preview -> find -> read/expand`；
5. evidence-window-enhanced loop；
6. large-context all-at-once。

每个 variant 都应接收相同的 source content 和 extraction representation；不能让某个 variant 偷换成更好的 OCR 或额外 reference crawl。source snapshot 要冻结 URL content/hash、HTML/PDF/OCR representation 和 version。

### 6.2 指标

同时记录：

- **Tool-call burden**：总 tool calls、无效重复 calls、重复 source/locator requests；
- **Read latency**：first useful preview、first evidence、final answer 的端到端 latency；
- **Token/byte budget**：发送给 agent 的 input/output tokens 或 bytes；不能把小 output 自动等同于高质量；
- **Answer coverage**：gold claim recall，以及是否覆盖关键 section/table/figure；
- **Unsupported claims**：答案中无法回到 source locator 的 claim rate；
- **Missing caveats**：遗漏 footnote、unit、scope、time range、exception、uncertainty 的比例；
- **Quote fidelity**：quote 与 frozen snapshot 的 exact/normalized match、locator 可复核率；
- **Negative-result calibration**：no-match 时是否正确区分 `not_found_in_searched_representation`、`partial` 与 `unknown`；
- **Correction quality**：发现 OCR/JS/section 错误后，agent 是否能利用 warning 和 cursor 修正；
- **Coverage honesty**：truncated、image-only、unloaded JS content 是否被显式披露。

### 6.3 Ablations

建议至少做以下 ablation；数字、阈值和默认 mode 均为待验证内容：

- 去掉 `outline`，只给正文；
- 去掉 `find`，只给固定 chunks；
- 去掉 `expand` prerequisites，观察 table/footnote qualifier 丢失；
- 将 bounded full Markdown 与 structure-aware blocks 放在同一总 byte/token budget；
- 有/无 `warnings` 与 `coverage`；
- `resource/list` discovery only vs direct URL tool entry；
- caller-controlled reference follow vs automatic follow；
- raw evidence only vs raw evidence + optional generated summary（后者必须单独标记，不能混入 baseline）；
- response 中有/无 stable `sourceId`、`contentHash`、`blockId` 和 opaque `nextCursor`。

### 6.4 Adversarial corpus

应建立覆盖以下 failure modes 的 frozen corpus：

- relevant fact 在长 context 开头、中间、结尾；
- 大量词面相似的 decoy sections；
- 没有 headings 或 headings 由字体/布局推断；
- table value 与 caption/header/footnote 分离；
- footnote 改变主句含义；
- JS shell、delayed hydration、折叠 tab、infinite scroll；
- native-text PDF、two-column PDF、扫描 PDF、图像型 PDF；
- OCR 的低置信度、混合中英文和非拉丁 script；
- 相关信息只在 image、chart、caption 或 alt text；
- query no-match、partial extraction、stale cursor、content mutation；
- 页面正文内含 indirect prompt-injection text，验证它不会改变 tool policy、reference-following policy 或预算。

## 7. 具体 implications

### 对 `web_read` contract

- 必须接受 caller 直接提供的 URL，不要求 URL 先来自 `web_search`；
- 返回 bounded structured Markdown，并带 `truncated` / `nextCursor`；
- `preview`、`find`、`read`、`expand` 可作为 mode/action proposal，尚未锁定为最终 tool shape；
- `find` 应返回原文和 locator，不返回只依赖模型生成的摘要；
- `EvidenceWindow` 必须能包含 caption/header/footnote/qualifier；
- no-match 必须附带 representation scope 和 coverage；
- 引用跟随必须由 caller 明确选择；
- 失败、部分成功、OCR/JS/解析限制必须可解释；
- 不把 MCP Resources 自动发现当作 host 的共同最小能力；
- 不在 v1 增加 server-side `deep_search` facade，不把 planning/synthesis 放进 `web_read`。

### 对 evaluation 和产品决策

- 不用 token 数单独评价 progressive disclosure；
- 不把“调用次数少”直接视为好，必须同时看 answer coverage、quote fidelity 和 missing caveats；
- 不把人类 HCI 的层级收益当作 agent 证据；
- 不把某个 provider/model 或 MCP SDK 版本从旧 repo claim 推导为长期选择；
- 先用真实 HTML、JS、PDF、OCR、图片型来源测 read pipeline，再决定结构块和 cursor 的默认参数；
- 保留 bounded full Markdown 作为 baseline，才能知道 progressive loop 是否真的降低无效读取而非仅增加复杂度。

## 8. 高影响 open gaps

1. **缺少针对 research agent 的直接 progressive disclosure A/B 证据。** 现有直接 agent 证据来自 ReAct、SWE-agent、ToolSandbox 和 long-context retrieval；它们支持交互观察、界面设计和上下文位置的重要性，但未直接比较“overview -> find -> evidence window”与其他 web document reader。
2. **结构感知解析的错误成本未测。** 错误 inferred heading、错误 table reconstruction 或错误 caption association 可能比 fixed chunks 更危险；需要人工标注和 quote/locator audit。
3. **没有可移植的最佳窗口大小。** SWE-agent 的 100-line result 是代码任务中的 observation，不应直接作为 web_read 的 char/token/page 默认值；本项目需要按 source type、host 和 model 复测。
4. **OCR/图片文字的 coverage semantics 尚未收敛。** 需要定义“全文抽取完成”与“仅 OCR text 可搜索”的可见区别，以及低置信度对 evidence eligibility 的影响。
5. **MCP host 的 Resources behavior 仍需真实验证。** 官方规范明确 Resources 为 application-driven，但不同 host 是否提供 picker、自动注入、URI read 或 tool result resource handling，需要实际 capability/conformance matrix；不能靠 protocol 名称推断。
6. **summary 是否有净收益未验证。** 它可能减少首次读取成本，也可能增加 unsupported claim 和 caveat loss；在 raw evidence baseline 之外做明确 ablation，不能在 extraction 内静默开启。
7. **多语言/no-heading navigation 未验证。** 需要在中文、英文、混合 query、无 heading HTML、扫描图片和跨脚本 OCR 上测 query normalization、match recall 与 negative-result honesty。
8. **预算与 continuation 绑定未验证。** 需要验证同一 `source snapshot + extraction version + query constraint` 下的 cursor 能否稳定继续，页面变化、重复调用和 partial failure 时如何返回可审计状态。

## 9. Source ledger

访问日期均为 2026-09-10。`全文` 表示本次能读取可检索正文；`摘要/metadata` 表示只读取到摘要或书目信息；`不可用` 表示 URL 或 PDF 正文未能可靠读取，未据此扩展事实。

| ID | 来源与 owning institution/authors | 类型/可读范围 | 本文使用的事实与精确定位 | 访问限制 |
|---|---|---|---|---|
| S1 | Jakob Nielsen, Nielsen Norman Group, `Progressive Disclosure` (2006) | 官方 practitioner article；全文可读 | 定义：“Initially, show users only a few of the most important options.”、“Offer a larger set of specialized options upon request.”；文章也讨论 discoverability、层级深度和额外交互成本。URL: <https://www.nngroup.com/articles/progressive-disclosure/> | 非 peer-reviewed agent experiment；是实践指导，不作为 agent 直接实证 |
| S2 | John M. Carroll & Caroline Carrithers, `Training Wheels in a User Interface`, *Communications of the ACM* (1984) | Crossref 摘要/metadata | 摘要称训练界面可防止常见错误，并相对 conventional interface 带来 faster learning、stronger achievement、improved comprehension。URL: <https://api.crossref.org/works/10.1145/358198.358218> | 未读取完整 paper；不据此报告样本、统计或具体 task |
| S3 | Peter Pirolli & Stuart Card, `Information Foraging`, *Psychological Review* 106(4), 643–675 (1999) | Crossref metadata | 核验原始理论论文题目、作者、期刊、年份、页码；仅把它作为 information foraging 理论 lineage，不扩展未读正文。URL: <https://api.crossref.org/works/10.1037/0033-295X.106.4.643> | 摘要未在 Crossref record 提供；作者 PDF 返回 403 |
| S4 | Ed H. Chi, Peter Pirolli, Kim Chen & James Pitkow, CHI ’01, `Using Information Scent to Model User Information Needs and Actions on the Web` (2001) | Crossref/Google Research metadata；摘要正文不可读 | 核验题目、作者、venue、年份、页码和 information scent 研究 lineage；未把摘要不可用时的理论细节写成事实。URL: <https://api.crossref.org/works/10.1145/365024.365325> | ACM 页面 403；Google Research 页面无可读摘要 |
| S5 | Shunyu Yao et al., `ReAct: Synergizing Reasoning and Acting in Language Models`, arXiv:2210.03629 (2022) | arXiv HTML 正文可读 | §2 的 Thought/Action/Observation loop；Appendix C 的查询修正与 `NOT ENOUGH INFO`；Appendix A.3 Figure 5 的 `by a human simply editing two thoughts`；Tables 3-4 的 task-specific results。URL: <https://arxiv.org/html/2210.03629> | 论文任务不是 web_read；结果依赖特定 model/prompt/task |
| S6 | John Yang et al., `SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering`, arXiv:2405.15793v3 (2024) | arXiv HTML 正文可读 | §2 的 `Environment feedback should be informative but concise.`；§5.1/Table 3 的 edit/search/window/context ablations；ACI 命令和 history compression。URL: <https://arxiv.org/html/2405.15793v3> | 主要是 code environment；其数值不能直接迁移到网页文档 |
| S7 | Jiarui Lu et al., `ToolSandbox: A Stateful, Conversational, Interactive Evaluation Benchmark for LLM Tool Use`, arXiv:2408.04682 / Findings of NAACL 2025 | arXiv HTML 正文可读至大部分正文/附录 | §1-3/Table 4 的 1,032 scenarios、34 tools、11 domains、13.9 turns、3.80 tool calls；§2.2-2.3 的 dynamic trajectories、snapshots、milestones/minefields。URL: <https://arxiv.org/html/2408.04682> | 附录后段不完整；不是专门的长文档 disclosure benchmark |
| S8 | Nelson F. Liu et al., `Lost in the Middle: How Language Models Use Long Contexts`, *TACL* 12 (2024), 157–173 | arXiv HTML 正文、附录和表图可读 | §1-4、Figure 1/5/7/9：U-shaped position curve、10/20/30 documents、75/140/300 key-value pairs、query-aware context、extended-context models not necessarily better。URL: <https://arxiv.org/html/2307.03172> | 结论是位置与任务实验，不是 web_read interface A/B |
| S9 | Model Context Protocol official specification, `Tools`, version 2026-07-28 | 官方规范全文可读 | Tools 为 model-controlled；`tools/list`/`tools/call`、`inputSchema`/`outputSchema`、`structuredContent`、`isError`、resource links、deterministic ordering 和 pagination。URL: <https://modelcontextprotocol.io/specification/2026-07-28/server/tools> | 规范不规定 web_read 的 preview/chunk/evidence semantics，也不保证 host UI |
| S10 | Model Context Protocol official specification, `Resources`, version 2026-07-28 | 官方规范全文可读 | Resources 为 application-driven；`resources/list`、`resources/read`、templates、text/binary contents、annotations、subscriptions；规范不强制一种 interaction model。URL: <https://modelcontextprotocol.io/specification/2026-07-28/server/resources> | host 的实际 Resource picker/auto-injection 仍需单独验证 |
| S11 | Model Context Protocol official specification, `Pagination`, version 2026-07-28 | 官方规范全文可读 | cursor 是 opaque；server 决定 page size；标准 pagination operation 为 resources/tools/prompts list；client 不得解析或修改 cursor。URL: <https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/pagination> | 自定义 web_read continuation 仍需项目自己的 contract |
| S12 | Official Model Context Protocol Python SDK repository | 官方 implementation README 可读 | `@mcp.tool()`、`@mcp.resource("greeting://{name}")`、client `call_tool` 和 `result.structured_content` 示例。URL: <https://github.com/modelcontextprotocol/python-sdk> | 只据 README 可读示例；未锁 SDK version，未据此推断 resource client API |
| S13 | Official Model Context Protocol TypeScript SDK repository | 官方 implementation README 可读 | `McpServer.registerTool`、Zod `inputSchema`、TextContent result example。URL: <https://github.com/modelcontextprotocol/typescript-sdk> | README 未展示完整 resource read/pagination example；未锁 version |
| S14 | Saleema Amershi et al., `Guidelines for Human-AI Interaction`, Microsoft Research / CHI 2019 | 官方 project/blog summary；summary 可读 | 官方 blog 列出初次交互、持续交互、出错时和长期使用四组 guideline，例如说明能力/质量、支持 invoke/close/correct、在不确定时缩小服务范围、提供 global control 和能力变化通知。URL: <https://www.microsoft.com/en-us/research/blog/guidelines-for-human-ai-interaction-design/> | 本文把它作为 human-AI design guidance，不当作 research-agent empirical proof；原始 PDF 本次不可检索 |
| S15 | J. Johnson et al., `The Xerox Star: A Retrospective`, *IEEE Computer* 22(9), 11–26 (1989) | Crossref metadata；原始 PDF 不可可靠检索 | 核验 progressive disclosure 早期 UI lineage 的书目信息与 DOI。URL: <https://doi.org/10.1109/2.35211> | 不据本次不可读 PDF 报告 property-sheet 细节；具体定义使用 S1 |

## 10. 最终建议

在不改变已接受产品边界的前提下，首个可验证设计应是：

```text
web_read(url)
  -> bounded deterministic preview/outline
web_read(url, action="find", query=...)
  -> verbatim matches + locators + coverage
web_read(url, action="read", locator=...)
  -> structure-aware Markdown slice
web_read(url, action="expand", matchId=...)
  -> evidence window + table/caption/footnote/qualifier prerequisites
```

这条路线把 progressive disclosure 的价值限定为：**减少无关 observation、给 agent 可复核的 navigation scent、在需要时扩大上下文、保留失败和不确定性，并把继续研究的决定权留给 caller**。它不承诺 token 越少越好，不自动生成研究报告，不自动跟随引用，也不把 host Resources 的可见性假定成通用能力。是否优于 bounded full Markdown、fixed chunks 或大型全文读取，必须用同一 frozen corpus、同一 agent/model 和上述 paired evaluation 复测后再决定。
