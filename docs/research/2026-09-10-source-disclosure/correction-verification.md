---
title: Correction Verification for Completeness Audit F-001–F-008
status: reviewed-partial-open-items
review_date: 2026-09-10
reviewer: independent reviewer (second pass, no runtime experiments)
scope: >
  仅核对 completeness-audit.md 中与文档措辞/schema 一致性相关的 8 个复核点（本文按来源顺序标注
  F-001–F-008，为复核请求方自定编号，非 completeness-audit.md 原文标签）以及 5 项"新矛盾"检查，
  针对以下四份文档在 2026-09-10 的修订版本：
    - docs/research/research-source-strategy.md
    - docs/design/research-source-strategy.md
    - docs/research/progressive-disclosure.md
    - docs/design/progressive-disclosure.md
  不重新评估、不重新验证 completeness-audit.md 中 BLOCKER-01（Q3 differentiator 未经直接验证）与
  BLOCKER-02（required formats 未 release-complete）本身——这两项需要 frozen-corpus paired
  evaluation 与新的 fixture/runtime 执行，属于本次纯文档复核的范围之外，且复核者被明确禁止执行
  runtime 实验。
related_audit: ./completeness-audit.md
runtime_experiments: none
new_research: none
documents_modified_by_this_review:
  - docs/research/2026-09-10-source-disclosure/correction-verification.md (本文件)
core_documents_modified: none
---

# Correction Verification: F-001–F-008 逐项复核

## 0. 复核方法与范围声明

本复核严格按照任务要求执行：只读取、不修改 `docs/research/research-source-strategy.md`、
`docs/design/research-source-strategy.md`、`docs/research/progressive-disclosure.md`、
`docs/design/progressive-disclosure.md` 四份核心文档；未执行任何 runtime 实验；未新增研究；
未进行 git 操作。所有结论基于对四份文档全文（分别为 501、650、540、908 行）与
`completeness-audit.md`（287 行）的完整阅读，以及针对具体引用行号的 grep 复核。

**重要边界**：completeness-audit.md 本身使用的严重度标签是 `BLOCKER-01`、`BLOCKER-02`、
`HIGH-01`〜`HIGH-05`、`MEDIUM-01`〜`MEDIUM-03`，全文没有出现字面的 "F-00X" 标签（已用
`grep -n "F-00\d"` 全仓库确认零匹配）。复核请求方给出的 "F-001 到 F-008" 是请求方自己对
"8 个待核对点"的编号，对应关系是：F-001=核对点1……F-008=核对点8。本文档下方沿用请求方编号，
但在涉及 completeness-audit.md 原文时标注其原始标签（如 HIGH-03）。

## 1. 逐项结论总览

| 编号 | 主题 | 结论 | 是否构成 blocker |
|---|---|---|---|
| F-001 | required-format gate 措辞（route + fixture，unsupported 不能替代实现） | **Fixed** | 否 |
| F-002 | National Academies=[S5]；[S..] ledger 完整性；design 无未定义 [R1]/[R2] | **Partially fixed** | 否（P1 级，同原 HIGH-03） |
| F-003 | Search 三层 observation、prototype 对应、query_id/partial 一致、caller-only metadata 区分、无隐式 retry/fallback | **Fixed**（含一处非阻塞性 cosmetic 备注） | 否 |
| F-004 | `advance` 作为唯一增量处理机制的 5 项子要求 | **Fixed** | 否 |
| F-005 | `source_snapshot_id` 一致性、`initial` 示例完整性、canonical 四步序列 | **Partially fixed** | 否（文档完整性缺口，非矛盾） |
| F-006 | context closure 的确定性边界与 `semantic_completeness=unknown` | **Fixed** | 否 |
| F-007 | 既有 baseline 先复现，候选组件同 corpus 对比 | **Fixed** | 否 |
| F-008 | file-backed store 作为首个实验而非永久禁数据库 | **Fixed** | 否 |
| 新矛盾检查（5项） | 见第 3 节 | **全部通过** | 否 |

**关于 completeness-audit.md 原有的两个 Blocker**：BLOCKER-01（Q3 differentiator 未经直接
A/B 验证）与 BLOCKER-02（required formats 未 release-complete）在本次复核范围之外——它们的
"missing evidence" 明确要求 frozen-corpus paired evaluation、新的 clean-machine fixture 运行等
runtime 证据，不是文档措辞问题，无法通过本轮纯文档编辑关闭。四份文档的 frontmatter 仍然如实
标注 `implementation_status: proposed/unvalidated`、`runtime_experiments: none`，说明这两项
Blocker **依然未关闭**，这是预期状态，不是本轮修补的失败。

## 2. F-001 – F-008 逐项详情

### F-001 — required-format gate（Fixed）

- `docs/research/progressive-disclosure.md:471`：
  > "每一种 required format（静态 HTML、JS 页面、text/mixed/scanned PDF、网页文字图片、独立
  > image URL）都有**可运行的 acquisition/extraction route**，并通过代表性的成功 fixture
  > （范围内的中文与英文）和失败 fixture；`unsupported/partial/refused` 只能是针对单个输入的
  > 诚实结果，不能替代某种 required format 的实现。"
- `docs/design/progressive-disclosure.md:803`：措辞更严格，额外加了
  > "只靠总是返回 `unsupported` 通过验收视为未满足本 gate。"

两份文档的 gate 定义一致：要求 route 存在、要求中英文成功 fixture、要求失败 fixture、明确
`unsupported/partial/refused` 不能替代实现。判定：**Fixed**。

### F-002 — Source citation 精确性（Partially fixed）

- National Academies 引用：`docs/research/research-source-strategy.md:33` 使用 `[S5]`，
  与 ledger 行 `docs/research/research-source-strategy.md:470`（`| S5 | National Academies...`）
  一致。**此项 Fixed。**
- 设计文档未定义的 `[R1]`/`[R2]`：对 `docs/design/research-source-strategy.md` 和
  `docs/design/progressive-disclosure.md` 分别执行 `grep "\[R\d"`，**零匹配**——两份设计文档
  都没有使用 `[R#]` 这种引用记号（它们要么不用行内 bracket 引用，要么复用 `[S#]` 并声明"研究
  报告提供完整 ledger"，如 `docs/design/progressive-disclosure.md:856`）。因此"没有未定义的
  [R1]/[R2]"这一具体断言**成立，但是以"该记号未被使用"的方式成立**，不是"存在 R 编号且都有
  定义"。**此项 Fixed（vacuously）。**
- **仍未修复的问题（对应原审计 HIGH-03，且比原文措辞更严重）**：
  `docs/research/progressive-disclosure.md:22` 仍写
  > "W3C selector/state、MCP statelessness/pagination、RFC 3986/3629、Unicode UAX #29
  > 支持明确 representation、normalization、offset unit 和 state……[S9–S17]"

  但该文档第 16 节 ledger（`docs/research/progressive-disclosure.md:503-515`）只定义到
  **S13**（S9=Pagination、S10=W3C Web Annotation、S11=RFC3986、S12=RFC3629、S13=UAX29）。
  `[S9–S17]` 这个引用范围隐含 S14、S15、S16、S17 四个编号，但**这四个编号在本文件 ledger 中
  根本不存在**——不是"owning source 指向不够精确"，而是**引用范围超出了 ledger 实际定义的
  上界，属于悬空引用（dangling citation range）**。这直接落在复核请求方 F-002 的核对范围内
  （"所有 [S..] 在同一文件 ledger 有定义"）。

  另外，`[S9–S17]` 把 S9（MCP Pagination）纳入"MCP statelessness"的证据范围，而 ledger 里
  没有任何一条专门对应"MCP Basic statelessness"页面——这正是原审计 HIGH-03 指出的问题，
  **本轮修补未处理**。作为对比，`docs/design/progressive-disclosure.md:861` 已经在
  Source references 列表里加入了 "MCP Basic 2026-07-28"，设计文档比研究文档做得更完整，
  这一点原审计已经指出过，现状不变。

  **判定：Partially fixed。** 命名的具体案例（National Academies=[S5]）已修复；[R1]/[R2]
  子项因未使用该记号而不适用；但"所有 [S..] 在同一文件 ledger 有定义"这一更一般的要求在
  `docs/research/progressive-disclosure.md:22` 处仍不成立，且问题比原始 HIGH-03 描述的更明确
  （悬空编号，不只是不够精确）。

**可操作的剩余修正建议**：
1. 把 `docs/research/progressive-disclosure.md:22` 的引用范围改为文件里实际存在的编号
   （例如 `[S9-S13]`），或者新增一条 ledger 行专门指向 MCP Basic statelessness 页面并单独引用它；
2. 不要让 `[S9–S17]` 这类范围隐含 S9（Pagination）本身证明 statelessness——按原审计
   HIGH-03 的 actionable correction，statelessness 语句应该直接指向 MCP Basic 页面，而不是
   通过 Pagination 页面推断。

### F-003 — Search 示例的三层 observation 与一致性（Fixed，含一处非阻塞 cosmetic 备注）

逐条核对（引用 `docs/research/research-source-strategy.md` 第 9 节示例，行号见下）：

- 三层分离（instance/engine/upstream）：`docs/research/research-source-strategy.md:398`
  明确 "`observation` 分 instance / engine / upstream 三层"，并说明各层职责。
- `upstream_http_status`/`upstream_request_id` 为 `null` 且带 `evidence_status`：
  `docs/research/research-source-strategy.md:367, 380` 均为
  `{"upstream_http_status": null, "upstream_request_id": null, "evidence_status": "not_observed"}`。
- 失败示例对应 prototype 已观察形态（本地 200 + `unresponsive_engines`）：
  `docs/research/research-source-strategy.md:379`
  `"state_basis": "unresponsive_engines"`，正文 398 行明确"prototype 已观察到本地 HTTP 200
  伴随 engine suspension"。设计文档同一断言见
  `docs/design/research-source-strategy.md:356`（"这个失败示例刻意对应 prototype 已经观察到
  的形态：本地 SearXNG instance 返回 HTTP 200，JSON 的 `unresponsive_engines` 报告 engine
  被 suspend"）。
- request/response `query_id` 一致、顶层 `partial` 与 per-query status 一致：
  `docs/design/research-source-strategy.md:246-250, 356`（"示例中的第一条 query 成功、第二条
  失败，因此顶层 `partial=true` 与 per-query `status` 一致"）。
- caller-only metadata 与 transport 输入区分：
  `docs/design/research-source-strategy.md:235`（"`claim_id`、`facet_id`、`query_family`、
  `evidence_goal` 和 `query_plan_hash` 是 caller-only 的 planning metadata……transport 真正
  需要的输入只有 `route`、`backend`/`engine`、`query`、requested filters 和 `pageno`"）。
- 无隐式 body read/fallback/retry：
  `docs/design/research-source-strategy.md:647`（"no body read, no synthesis, no truth/authority
  score, no implicit fallback/retry"）；`retry_performed: false` 出现在
  `docs/design/research-source-strategy.md:316, 347`，并在 368 行声明为 v1 default。

**判定：Fixed。**

**非阻塞 cosmetic 备注**：`docs/design/research-source-strategy.md` 第 5.1 节 Request 示例
（199-231 行）只展示一个 query（`q-c1-primary`），而第 5.2 节 Response 示例（237 行起）展示
两个 query，其中 `q-c1-counter`（321 行）在配对的 Request 示例里从未出现。这是一处"示例配对
不完整"的文档完整性瑕疵——不是语义矛盾，因为出现的 `query_id` 本身没有被错误复用或重新赋值，
只是 Request 示例没有把两个 query 都列出来。建议：在 5.1 节 Request 示例的 `queries` 数组里
补一条 `q-c1-counter`，使两份示例严格配对，避免读者误以为 counter query 是从别处冒出来的。

### F-004 — `advance` 作为唯一增量处理机制（Fixed）

五项子要求全部在 `docs/design/progressive-disclosure.md` 第 6.6 节确认：

1. **同步、有界、caller 发起，唯一机制**：`docs/design/progressive-disclosure.md:420`
   （"`advance` 是本 proposal 为'增量 OCR / 增量处理'选定的**唯一**默认机制：一个
   synchronous、bounded、由 caller 显式发起的动作……它不是 background job，不产生
   queued/server-side pending state"）。
2. **`next_cursor` 不触发 OCR/网络**：`docs/design/progressive-disclosure.md:329`
   （"`next_cursor` 只读取当前 representation 里已经**发布**的内容，不触发新的网络请求、
   渲染或 OCR"）。
3. **`processing_continuation` 与 `next_cursor` 分开**：`docs/design/progressive-disclosure.md:
   329, 796`（"二者可以同时出现，也可以只出现一个"；"`next_cursor` 与 `processing_continuation`
   各自的存在与否互不隐含"）。
4. **旧 cursor/citation 不静默改指新 revision**：`docs/design/progressive-disclosure.md:440,
   794`（"旧的 cursor 和 citation 在 `advance` 之后继续对旧 representation 有效，**不会**被
   静默重新解析到新 revision"）。
5. **`pending` 不等于 `missing`/`no_match`**：`docs/design/progressive-disclosure.md:438`
   （"`pending_ranges` 既不是'missing'（capture 缺失），也不是'no_match'（find 未命中），
   必须用独立状态表示"）。

`need_new_acquisition`（未曾 capture 时的行为，`docs/design/progressive-disclosure.md:436`）
与失败不自动重试（439 行）也已明确写入。**判定：Fixed。**

### F-005 — `source_snapshot_id` 一致性与 canonical 序列（Partially fixed）

- **`source_snapshot_id` 统一命名**：在 `docs/design/progressive-disclosure.md` 全部 JSON
  示例（6.1/6.2/6.3/6.4/6.6 节）中一致使用 `source_snapshot_id`，未发现历史遗留的其他命名
  （如 `snapshot_id`）与之混用。**Fixed。**
- **`initial` 示例的完整性**：`docs/design/progressive-disclosure.md` 第 6.1 节
  （277-331 行）给出完整 request+response JSON：response 含真实的 bounded verbatim 段落文本
  （"This fictitious field survey covers three sample plots..."）、
  `output.status: "truncated"`（伴随 `truncation_reason`）、`next_cursor: "opaque-cursor-1"`
  （322 行）。**Fixed。**
- **canonical 四步序列（`initial -> continuation -> advance -> targeted read`）**：
  `docs/research/progressive-disclosure.md` 第 7.4 节（263-272 行）用概念性文字描述四步，
  并在 265 行明确链接到 `../design/progressive-disclosure.md` 第 6.1、6.6 节，且诚实注明
  "不重复完整 JSON……本报告不重复维护第二份 schema 副本"（272 行）——**这个交叉引用本身没有
  夸大**，它没有声称设计文档提供了完整的分步 JSON walkthrough。

  但实际核对设计文档链接到的两节内容后发现，四步里只有第 1 步（`initial`）有完整的
  request+response JSON；其余三步的 JSON 证据不完整：
  - 第 2 步"output continuation"（用 `next_cursor` 作为下一次请求的输入去续读）：
    对整份 `docs/design/progressive-disclosure.md` grep `next_cursor`，该字符串**只在
    response 侧出现过一次**（322 行的示例值）和一次 schema 类型声明（474 行
    `next_cursor?: string`），**全文没有任何一个 request JSON 把 `next_cursor` 作为输入
    字段使用**——即"用上一步的 next_cursor 继续读"这一步骤没有对应的具体 JSON 示例。
  - 第 3 步 `advance`：第 6.6 节（418-441 行）**只给出 request JSON**（424-434 行附近），
    响应字段（`processed_ranges`、`pending_ranges`、`failed_ranges`、`alignment_status`）
    只以散文形式描述（435-440 行），**没有 response 的 JSON 代码块**。
  - 第 4 步"在新 representation 上做 targeted read"：`find`/`read` 的 JSON 示例
    （`docs/design/progressive-disclosure.md:337-348, 372-385`）里的 `representation_id`
    都固定是 `"opaque-rep-1"`——也就是第 1 步 `initial` 产生的**旧** representation，
    全文没有一个 JSON 示例展示"用 `advance` 产生的新 `representation_id` 去做 `find`/`read`"
    这一具体动作。

  这是一处**文档完整性缺口**，不是语义矛盾——两处提到 canonical 序列的文字本身互相一致，
  也没有虚假声称已经给出完整 JSON。但复核请求方 F-005 的措辞（"设计文档有完整示例，或研究
  文档链接到它"）如果理解为"链接指向的内容应当完整覆盖四步"，则**该期望目前没有被满足**。

  **判定：Partially fixed。** `source_snapshot_id` 一致性与 `initial` 示例本身已完全满足
  要求；四步 canonical 序列存在概念性描述且交叉引用诚实、不夸大，但作为"完整示例"，
  第 2 步与第 4 步缺少具体 JSON，第 3 步缺少 response JSON。

**可操作的剩余修正建议**：在 `docs/design/progressive-disclosure.md` 第 6.1 或新增小节里，
补一个"continuation request"JSON 示例（把 `next_cursor: "opaque-cursor-1"` 作为输入字段
传入）；在第 6.6 节补一个 `advance` 的 response JSON 示例（哪怕是 hypothetical，需标注
状态）；在第 6.2/6.3 节各补一个使用**新** `representation_id`（例如 advance 产生的
`opaque-rep-2`）的 `find`/`read` 示例，从而让研究文档 7.4 节的链接名副其实。

### F-006 — Context closure 的确定性边界（Fixed）

- 研究文档：`docs/research/progressive-disclosure.md:228`
  （"每个 context block 都应携带 `closure_basis`……响应应携带 `unknown_context`/
  `unresolved_context` 和恒为 `unknown` 的 `semantic_completeness` 字段……**空的
  `unknown_context` 列表从不意味着语义完整**"）。
- 设计文档 schema：`docs/design/progressive-disclosure.md:456-460`
  （`context_closure_basis`、`unknown_context`、`unresolved_context`、
  `semantic_completeness: "unknown"` 字段定义）。
- 设计文档规则文字：`docs/design/progressive-disclosure.md:485`
  （"Context closure 的能力边界必须明确：它只能补齐**结构或 index 中可确定性找到的链接**……
  不属于这些确定性链接的内容不会被 closure 自动补入"）；`docs/design/progressive-disclosure.md:
  501, 797` 重复"空的 `unknown_context` 列表从不意味着语义完整"。

两份文档的措辞、字段命名完全一致。**判定：Fixed。**

### F-007 — 既有 baseline 先复现（Fixed）

- 研究文档：`docs/research/progressive-disclosure.md:293`
  （"**第一步：复现已有 baseline，而不是重新挑选组件。**……后续 prototype 的第一优先级是在
  同一/相近 corpus 上复现这条路径本身，作为唯一 baseline"），逐项列出 Trafilatura、
  Playwright/Chromium、pypdfium2、RapidOCR+ONNX Runtime CPU（296-299 行）；候选组件对比在
  第二步（301 行起），且明确"不做整体替换"（309 行）。
- 设计文档：`docs/design/progressive-disclosure.md:607`
  （"**第一优先级：复现已有 baseline。**……后续 prototype 的第一步是在同一/相近 corpus 上
  **复现这条已验证路径**，而不是从候选列表里另选组件"）。

两份文档表述一致。**判定：Fixed。**

### F-008 — file-backed store 是首个实验（Fixed）

`docs/design/progressive-disclosure.md:576`：
> "推荐把 file-backed content-addressed store + small metadata index 作为**第一个要验证的
> 实验**——这是'从简单开始，先用能满足需求的最小方案'的工程判断，不是'永久排除数据库'的产品
> 决策；用户没有禁止数据库，如果 file-backed 方案在 retention/TTL/并发/查询场景上暴露出具体
> 不足，评估数据库方案是合理的下一步。"

研究文档中三处提及 database/file-backed（`docs/research/progressive-disclosure.md:34, 465,
490`）未发现与此矛盾的表述。**判定：Fixed。**

## 3. 新矛盾检查（5 项）

1. **状态枚举与示例是否一致**：核对过的 JSON 示例（`capture`/`extraction`/`output` 三轴
   状态、`status: "truncated"`/`"partial"`/`"complete"`、`alignment_status: "ambiguous"` 等）
   在四份文档中命名一致，未发现同一状态在不同文档用不同拼写或不同含义。**通过。**
2. **两种 continuation（`next_cursor` vs `processing_continuation`）是否语义冲突**：
   见上文 F-004 第 3 点，`docs/design/progressive-disclosure.md:329, 796` 明确二者独立、
   互不隐含，可同时出现也可只出现一个。**无冲突，通过。**
3. **是否有同一 view 内重复放置完整正文两次而无说明**：
   `docs/design/progressive-disclosure.md` 第 10 节（Markdown/output projection policy，
   约 624-640 行）明确"同一个 `BoundedView` 内应避免把同一段正文同时完整塞进
   `content_parts`（typed blocks）和 `markdown_projection` 两份"，并给出 budget
   double-counting 的处理指引。**已有明确约束，通过。**
4. **JSON 代码块语法是否有效**：用 Python `json.loads()` 对四份文档中所有 ` ```json ` 代码块
   做解析测试，结果：`docs/research/research-source-strategy.md` 1 个块、
   `docs/design/research-source-strategy.md` 2 个块、`docs/research/progressive-disclosure.md`
   0 个块（该文档明确不重复维护 JSON 副本）、`docs/design/progressive-disclosure.md` 8 个块，
   **合计 11 个块，0 个解析失败**。**通过。**
5. **本地相对链接是否存在**：核对以下相对链接指向的文件，均存在于磁盘：
   - `prototypes/free-search/REPORT.md`（被
     `docs/research/research-source-strategy.md:12` 与
     `docs/design/research-source-strategy.md:12` 的 `../../prototypes/free-search/REPORT.md`
     引用）；
   - `docs/research/2026-09-10-source-disclosure/format-fidelity.md`、
     `docs/research/2026-09-10-source-disclosure/format-fidelity-verification.md`（被
     `docs/design/research-source-strategy.md:541` 附近引用）；
   - `docs/design/progressive-disclosure.md`（被
     `docs/research/progressive-disclosure.md:228, 265` 的
     `../design/progressive-disclosure.md` 引用）；
   - `docs/research/progressive-disclosure.md`（被
     `docs/design/progressive-disclosure.md` frontmatter `related_research` 引用）。
   **全部存在，通过。**

## 4. 真正的 blocker 清单

**本次复核范围内（F-001–F-008 + 5 项新矛盾检查）没有发现新的 blocker。** 两处
partially-fixed（F-002 的悬空引用范围、F-005 的 canonical 序列 JSON 不完整）按
`completeness-audit.md` 自身的严重度框架衡量，都属于 **HIGH（P1，evidence traceability /
文档完整性问题）**，不是会推翻架构或重新引入被移除需求的 P0/blocker——不影响四份文档作为
proposed research/design baseline 的可用性，但在把它们当作 implementation contract 之前应该
关闭。

**completeness-audit.md 原有的 BLOCKER-01 与 BLOCKER-02 依然未关闭**，且不在本次纯文档复核
的能力范围内（关闭它们需要 frozen-corpus paired evaluation 与新的 fixture/runtime 执行）。
因此，按任务要求的条件（"若所有 blocker 均已修复"）：**条件不成立**——不满足更新
`completeness-audit.md` frontmatter 状态与插入链接行的前提条件。本次复核**不修改**
`completeness-audit.md`，其原有 8 项 findings（2 Blocker + 5 High + 3 Medium）与 Verdict
保持完全不变。

## 5. 可操作的剩余修正建议汇总

1. （对应 F-002 / 原 HIGH-03）修正 `docs/research/progressive-disclosure.md:22` 的引用范围，
   使其不超出 ledger 实际定义的 S1-S13；为 MCP Basic statelessness 单独建一条 ledger 行并
   直接引用，不要让 statelessness 断言依赖 Pagination（S9）推断出来。
2. （对应 F-005）在 `docs/design/progressive-disclosure.md` 补齐 canonical 四步序列中缺失的
   JSON 证据：continuation request（以 `next_cursor` 为输入）、`advance` 的 response JSON、
   以及在 advance 产生的新 `representation_id` 上做 `find`/`read` 的示例。
3. （非阻塞 cosmetic，对应 F-003）把 `docs/design/research-source-strategy.md` 第 5.1 节
   Request 示例的 `queries` 数组补齐到与 5.2 节 Response 示例一致（补入 `q-c1-counter`）。
4. （范围外，但复核者认为应提醒）BLOCKER-01、BLOCKER-02 仍需按 `completeness-audit.md`
   第 3 节给出的 actionable correction 执行 frozen-corpus paired evaluation 与
   release-fixture 运行，本轮文档修补未涉及、也不能替代这部分工作。

## 6. 本次审查的范围限制（必须显式声明）

- 本复核**只针对文档文本与 JSON 示例的静态一致性**，不构成、也不暗示对最终 tool contract、
  实现或 runtime 行为的批准。
- 未执行任何 runtime 实验、未新增研究；所有"证据"均来自对四份文档与 completeness-audit.md
  现有文本的阅读与 grep 交叉核对，以及一次本地 Python `json.loads()` 语法校验（不涉及网络、
  不涉及目标系统）。
- 未重新核实 completeness-audit.md 第 4 节"Primary-source spot checks"中列出的外部
  primary source 内容是否仍然可访问或未变化——那些核查发生在 2026-09-10 之前，本复核未重新
  抓取这些外部 URL。
- 未评估 MEDIUM-01/02/03（healthcare framework 迁移性、provenance clustering、search
  coverage 验证）——复核请求方的 8 个核对点未涵盖这三项，它们在 completeness-audit.md 中
  的状态未受本次复核影响。
- 未评估 HIGH-01（`docs/design/search-mcp-scope.md:37` 的 stale retry wording）、
  HIGH-02（cursor lifecycle 的 host/persistence 证据缺失）、HIGH-04（`asset` optional
  wording）、HIGH-05（dependency approval gate）——这四项分别涉及本次复核范围之外的文件
  （`docs/design/search-mcp-scope.md`）或需要 runtime/target-host 证据，不在复核请求方给出的
  8 个核对点之内，其在 completeness-audit.md 中的状态同样未受本次复核影响。
- 本文档的结论仅反映 2026-09-10 时点四份核心文档的内容；四份文档此后如再被编辑，需要重新复核。
