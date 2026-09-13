---
title: Search 覆盖与排序事实核验
status: research-verification
verified_on: 2026-09-10
scope: SearXNG Google adapter、Search API、排序启发式、分页漂移、URL identity、diversity evaluation
---

# Search 覆盖与排序事实核验

> 本文是对 `search-coverage.md` 的 adversarial evidence verification，不是新的产品决策。除“事实核验”外，字段、算法、阈值和 acceptance plan 仍是 proposed / unvalidated。核验没有执行 live SERP experiment、没有连接目标 SearXNG instance、没有直接调用 Google provider，也没有改动生产代码。

## 结论

- 核心边界基本成立：SearXNG Google adapter 能表达有限的分页、locale / language / country、time-range 和 SafeSearch 请求，但这些是 adapter capability，不是 Google coverage、排序稳定性或过滤准确性的保证。
- 发现并已在原文修正一处具体过度泛化：SearXNG 通用 Search API 文档当前列出的 `time_range` 值是 `day`、`month`、`year`；`week` 是 Google adapter source 的映射，不应写成所有 API / engine 的通用能力。
- `score` 的 source mechanics、Google context-sensitive retrieval、NIST diversity evaluator、RFC 3986 与 WHATWG `rel=canonical` 结论均能由可访问的 primary source 支持，但它们只能支持有限解释，不能推出 source reliability、Web-wide recall 或长期 ordering SLA。
- MMR 与 xQuAD 的原始文献本次没有取得可读取全文；原 memo 已经把它们限定为保守抽象和 research lead，这一处理应保留，不应添加论文参数、实验结论或 superiority claim。
- SearXNG source snapshot 的 license 已核验为 AGPL-3.0；但当前项目尚未选择 SearXNG release / commit，因此 master/snapshot 行为不能直接当作部署版本契约。Windows、CPU-only、MCP protocol / SDK 版本不是本 memo 的 Search primary sources 所能证明的事实，仍需独立验证。

## 核验范围与方法

本次重新打开了 `search-coverage.md` 中驱动设计的关键 primary sources：

1. SearXNG 官方 Search API 文档与 Google engine 文档；
2. SearXNG 官方 `google.py` 与 `results.py` source，并通过 GitHub API 将 source snapshot 固定到 commit `3fdc6d753a339b5f4a7dc5842c94c0d8324726f1`（commit date 2026-09-08）；
3. SearXNG 官方 README、self-hosting 文档和 commit-pinned `LICENSE`；
4. Google Search Central / Search Help 官方文档；
5. NIST TREC Web Track 页面与 `ndeval.c` source；
6. IETF RFC 3986 与 WHATWG HTML Standard；
7. MMR DOI / author-hosted PDF 与 xQuAD primary PDF 的可访问性。

证据状态沿用三类：`Full` = 本次可读取官方 HTML / source text；`Binary-unreadable` = 取得 PDF 但正文无法从工具返回的 compressed object 中读取；`HTTP 403` = primary landing page 被拒绝；`Unverified` = 当前材料不足以支持原 claim。

## Claim ledger

| ID | 原 memo 的 design-driving claim | 判定 | Primary evidence 与限制 | 对本项目的转移结论 |
|---|---|---|---|---|
| V1 | SearXNG Search API 提供 `q`、`language`、`pageno`、`time_range`、`format`、`safesearch` 等参数；部分能力依赖 engine / instance，机器格式可能返回 `403`。 | **Confirmed with correction** | [SearXNG Search API](https://docs.searxng.org/dev/search_api.html), Sections “Search API” / “Parameters”，Full HTML。短引文：“time_range and safesearch affect only engines that support those features”；`pageno` 从 1 开始；未启用 format 会返回 `403 Forbidden`。当前通用文档列 `time_range` 为 `day`、`month`、`year`，没有证明通用 page size 或 immutable cursor。 | 原文已修正：`week` 只能作为具体 adapter capability 记录，不能写成通用 API 保证；schema 应保留 requested / effective / unsupported 差异。 |
| V2 | Google adapter 支持 paging、`max_page=50`、以 10 为 page offset，映射 locale / language / country、time-range、SafeSearch，并识别 Google block / CAPTCHA。 | **Confirmed for pinned source; release boundary corrected** | [Google engine docs](https://docs.searxng.org/dev/engines/online/google.html), Full HTML，明确 “Google supports up to 50 pages of results”；[commit-pinned `google.py`](https://raw.githubusercontent.com/searxng/searxng/3fdc6d753a339b5f4a7dc5842c94c0d8324726f1/searx/engines/google.py), Full source。source 中有 `paging = True`、`max_page = 50`、`start = (params["pageno"] - 1) * 10`、`time_range_dict`（含 `week`）、`filter_mapping`、`unwrap_google_url()` 和 `detect_google_sorry()`。GitHub API [commit record](https://api.github.com/repos/searxng/searxng/commits/3fdc6d753a339b5f4a7dc5842c94c0d8324726f1) 将 snapshot 固定；没有选择具体 release。 | 可记录 adapter request / response capability，但不能据此承诺 Google 的结果数、过滤准确度、跨页无重复、长期稳定或覆盖率。目标部署版本必须复核。 |
| V3 | SearXNG 是 metasearch aggregator；自建 instance 仍请求 external search services，上游可见 instance IP，CAPTCHA / block 会减少结果。 | **Confirmed** | [SearXNG README](https://github.com/searxng/searxng), Full page partially available，短引文：“SearXNG is a metasearch engine”；[self-hosting docs](https://docs.searxng.org/own-instance.html), Full HTML，说明请求发送到 external services、upstream 可见 instance IP，以及 upstream CAPTCHA / block 的结果损失。 | `backend=google` 只能说明调用了 SearXNG 的 Google adapter；不能把 aggregator 层称为独立 Google index，也不能把 engine 数量当作 source independence。后半句是对 source 事实的解释，不是 provider 保证。 |
| V4 | SearXNG `score` 由 engine weight、positions、priority 等 aggregation mechanics 形成，并经过 category / template / image grouping；不是 calibrated relevance。 | **Confirmed mechanics; bounded interpretation** | [commit-pinned `results.py`](https://raw.githubusercontent.com/searxng/searxng/3fdc6d753a339b5f4a7dc5842c94c0d8324726f1/searx/results.py), Full source。`calculate_score()` 初始 weight、engine weights、positions、priority；`close()` 计算 score；`get_ordered_results()` 先按 score，再做 category/template/image 分组重排；duplicate merge 保留 positions。source 没有声明 calibrated relevance。 | 原文将字段改名为 `aggregator_score` 并保留 `score_basis` 的建议仍合理，但“不是 calibrated relevance”是根据算法性质作出的保守解释，不应改写为数学证明或可信度判断。source snapshot 未锁 release。 |
| V5 | Google 结果受 location、language、device、time、context、personalization 等影响；Google 不保证 indexing 或固定排序。 | **Confirmed, but no project SLA follows** | [How Search works](https://developers.google.com/search/docs/fundamentals/how-search-works), Full HTML：Google 使用 “hundreds of factors”，结果可受 “location, language, and device” 影响，且 “Indexing isn't guaranteed”。[Ranking systems guide](https://developers.google.com/search/docs/appearance/ranking-systems-guide), Full HTML：multiple systems / signals、freshness、deduplication、site diversity。[Why search results differ](https://support.google.com/websearch/answer/12412910?hl=en), Full HTML：time、context、location、language、device、recent searches / personalization。 | 可以支持 live SERP、context-sensitive、best-effort continuation 的边界；不能量化 drift、recall、filter precision，不能产生跨时间 / 地点 / 用户的 ordering SLA。 |
| V6 | TREC diversity qrels 与 NIST `ndeval.c` 可作为 facet / subtopic coverage 与 redundancy evaluation 的可复核基线。 | **Confirmed with wording correction** | [TREC 2009 Web Track](https://trec.nist.gov/data/web09.html), Full HTML：提供 “Diversity task relevance judgments” 与 “ndeval.c (v1.3)”。[NIST `ndeval.c`](https://trec.nist.gov/data/web/09/ndeval.c), Full C source：四字段 qrel、nonzero Boolean relevance、`alpha-nDCG`、`IA-P`、default `alpha=0.5`、greedy ideal。未出现在 qrels 的 run document 没有 relevance pointer，不贡献 gain / intent count 但占据 rank；默认 topic divisor 是 qrel/run intersection，`-c` 改为 complete qrel-topic set。TREC 页面没有提供完整 assessor protocol。 | 原文已改为准确的 unjudged 语义。必须报告 pool construction、unjudged rate、qrel version、alpha 与 averaging denominator；NIST evaluator 不是本项目已批准的 assessor protocol，也不证明 Web recall。 |
| V7 | RFC 3986 支持分层 URI identity；query semantics 与 equivalence application-dependent，不能只用后缀 heuristic；`rel=canonical` 是偏好提示而非 ownership proof。 | **Confirmed** | [RFC 3986 §§3.4, 6](https://www.rfc-editor.org/rfc/rfc3986), Full HTML：query 是 “non-hierarchical data”；存在 “many application-dependent versions of equivalence”；normalization 强度从 syntax-based 到 protocol-based。[WHATWG canonical](https://html.spec.whatwg.org/multipage/links.html#link-type-canonical), Full HTML：`rel=canonical` 指向当前文档的 “preferred URL”，帮助搜索引擎减少 duplicate content；标准不定义通用 URI equivalence 或 ownership。 | `url_original`、`strict_key`、可选 `semantic_key` 和 observed evidence 分层保存的 proposal 有证据基础；仍需离线 fixture 和低 false-merge 验证。 |
| V8 | MMR / xQuAD 可提供 relevance–redundancy–aspect coverage 的 reranking / evaluation baseline。 | **Unverified as primary-paper detail; conservative abstraction retained** | [MMR DOI](https://doi.org/10.1145/290941.291025) redirect 到 ACM 后返回 `HTTP 403`；CMU author-hosted [MMR PDF](https://www.cs.cmu.edu/afs/cs/Web/People/jgc/publication/MMR_DiversityBased_Reranking_SIGIR_1998.pdf) 为 compressed PDF，正文不可读。[xQuAD PDF](https://terrierteam.dcs.gla.ac.uk/publications/ecir2010_rodrygo_div.pdf) 同样不可从工具返回 readable full text；只取得 PDF / metadata / search lead。 | 只保留“可作为待验证 baseline 的 relevance + novelty/redundancy + explicit aspects”这一保守抽象；不新增论文公式、参数、实验结果或 superiority claim。是否进入 v1 server 仍未决定。 |
| V9 | SearXNG 自建组件为开源方案，license 是 AGPL-3.0。 | **Confirmed for pinned source snapshot only** | commit-pinned [LICENSE](https://github.com/searxng/searxng/blob/3fdc6d753a339b5f4a7dc5842c94c0d8324726f1/LICENSE), Full HTML：明确 “GNU AFFERO GENERAL PUBLIC LICENSE, Version 3, 19 November 2007”。GitHub [release page](https://github.com/searxng/searxng/releases) 本次未显示可用于锁定的 release/version；因此 license 与 source behavior 均不能自动代表未来部署 artifact。 | 可继续把 AGPL-3.0 作为该 source snapshot 的事实，但选型 / 分发前仍应核对目标 tag / commit 的 license、依赖及部署条款。 |
| V10 | CPU-only、Windows、MCP protocol / SDK 互操作和具体版本可作为 Search schema 设计事实。 | **Unverified / out of scope for this memo** | 本次 Search primary sources 没有证明 Windows CPU-only 性能、MCP protocol / SDK version 或目标 client 互操作；SearXNG source 也不等于本项目 runtime 结果。项目 ADR 将这些作为 accepted boundary / 后续验证议题，但那不是外部技术事实证据。 | 不把这些约束写成 Search provider capability。需要另一个受控 prototype / interoperability validation；本次不重新打开 ADR。 |

## 已应用的原文修正

仅修改 `search-coverage.md` 中与证据直接相关的内容：

1. 在 §1.2 增加 `time_range` 的 API / adapter 区分：通用文档列 `day`、`month`、`year`；Google source 才额外映射 `week`。
2. 将 Google adapter 的表述从“mobile layout”收紧为 XML-oriented layout，并说明 source 采用 Nokia user agent、normal web version 需要 JavaScript。
3. 将 NIST `ndeval.c` 的 unjudged 说法改为“无 gain / intent count 但占 rank，在这些指标中等价于 non-relevant”，避免声称 source 直接写入 `rel=0`。
4. 将 SearXNG `google.py` 与 `results.py` 的 citation 固定到 commit `3fdc6d753a339b5f4a7dc5842c94c0d8324726f1`，并在 license 单列 commit-pinned [S15]。

未修改其他 topic、ADR、CONTEXT、scope 或 accepted product boundary。

## 仍未验证的高影响事项

- **目标 SearXNG version / instance variance：** 当前核验锁定了一个公开 master commit snapshot，但没有目标 deployment release；需验证实际 enabled format、timeout、locale traits、Google parser 与 instance configuration。
- **Google adapter 的真实 coverage 与稳定性：** 没有 live SERP experiment；page 1 / page 2 overlap、drift、duplicate / skip、CAPTCHA rate、语言和时间过滤 precision 均未测。
- **Source ownership grouping：** RFC / canonical 证据只支持 conservative identity layers；没有决定 PSL / DNS / publisher metadata 组件，也没有人工 adjudication set。
- **Judgment protocol：** facet taxonomy、assessor 是否进入 `web_read`、binary vs graded label、agreement / adjudication workload 尚未验证。
- **MMR / xQuAD primary details：** 全文访问仍受限；不能据此批准算法参数或 server-side reranking。
- **CPU / Windows / MCP interoperability：** 不属于本 memo 已核验的 Search source capability，需要单独验证；不能从 SearXNG 文档或 Google adapter 推出。
- **Provider / license / retention constraints：** 本文未做法律意见或完整 dependency audit；目标 release 的 license、upstream terms、raw SERP metadata retention 仍需进一步审查。

## 评测设计的保守落点

在上述限制下，以下只是可进入 acceptance proposal 的最小可审计结构，不是已批准阈值：

- 每次 request 记录 `route`、`backend`、engine、query、requested filters、effective support、page、retrieved_at、adapter snapshot / version（若可得）与 upstream state。
- 对 query family 使用 facet / source-type / contrary evidence provenance；Search server 不自行规划 query、读取正文或综合答案。
- 以 bounded judged pool 评测 `pool_relative_recall`、`facet_coverage`、`source_group_coverage`、duplicate rate 与 partial rate；明确 pool denominator、unjudged rate 和 assessor protocol。
- continuation 只作为 best effort；记录 `current_page`、overlap / duplicate / missing 与 drift evidence，不把 `pageno` 或 opaque token 写成 immutable snapshot cursor。
- 保留 upstream order；任何 MMR-like / aspect-aware rerank 先作为离线 baseline，不能覆盖原始 rank，也不能把分数升级为 credibility。

## Source ledger

以下链接均在 2026-09-10 重新访问；owning institution / authors 和可读性限制按实际访问结果记录。

| ID | Primary source | Owning institution / authors | 版本 / 状态 | 访问限制与支持内容 |
|---|---|---|---|---|
| L1 | [SearXNG Search API](https://docs.searxng.org/dev/search_api.html) | SearXNG maintainers | Official docs，2026-09-10 | Full HTML；Parameters sections。支持 `q`、`language`、`pageno`、`time_range`、`format`、`safesearch`，并说明 engine support / instance format caveat。 |
| L2 | [SearXNG Google engine docs](https://docs.searxng.org/dev/engines/online/google.html) | SearXNG maintainers | Official docs，2026-09-10 | Full HTML；支持 50-page adapter bound、XML layout / JS caveat 与 locale mappings 的文档说明。 |
| L3 | [`google.py` at commit](https://raw.githubusercontent.com/searxng/searxng/3fdc6d753a339b5f4a7dc5842c94c0d8324726f1/searx/engines/google.py) | SearXNG maintainers | Commit `3fdc6d753a339b5f4a7dc5842c94c0d8324726f1`，2026-09-08 | Full source；具体实现可复核，但不是项目已选 release。 |
| L4 | [`results.py` at commit](https://raw.githubusercontent.com/searxng/searxng/3fdc6d753a339b5f4a7dc5842c94c0d8324726f1/searx/results.py) | SearXNG maintainers | Same commit，2026-09-10 accessed | Full source；支持 score / merge / grouping mechanics。 |
| L5 | [SearXNG README](https://github.com/searxng/searxng) | SearXNG maintainers | Repository README，2026-09-10 | Full page partially available；支持 metasearch / aggregation 定义。 |
| L6 | [SearXNG self-hosting](https://docs.searxng.org/own-instance.html) | SearXNG maintainers | Official docs，2026-09-10 | Full HTML；支持 upstream external service、instance IP、CAPTCHA / block caveat。 |
| L7 | [SearXNG LICENSE at commit](https://github.com/searxng/searxng/blob/3fdc6d753a339b5f4a7dc5842c94c0d8324726f1/LICENSE) | SearXNG maintainers | AGPLv3 text at pinned commit | Full HTML；只证明该 snapshot，不证明未选 release。 |
| L8 | [How Search works](https://developers.google.com/search/docs/fundamentals/how-search-works) | Google Search Central | Official docs，2026-09-10 | Full HTML；supports hundreds of factors, context dependence, indexing not guaranteed。 |
| L9 | [Ranking systems guide](https://developers.google.com/search/docs/appearance/ranking-systems-guide) | Google Search Central | Official docs，2026-09-10 | Full HTML；supports multiple systems / freshness / deduplication / site diversity。 |
| L10 | [Why search results differ](https://support.google.com/websearch/answer/12412910?hl=en) | Google Search Help | Official support docs，2026-09-10 | Full HTML；supports time/context/location/language/device/personalization variability。 |
| L11 | [TREC 2009 Web Track](https://trec.nist.gov/data/web09.html) | NIST | TREC 2009 page，2026-09-10 | Full HTML；lists diversity qrels and `ndeval.c v1.3`; no complete assessor protocol。 |
| L12 | [NIST `ndeval.c`](https://trec.nist.gov/data/web/09/ndeval.c) | NIST | v1.3 C source，2026-09-10 | Full source；supports qrel fields, alpha-nDCG / IA-P, alpha and unjudged rank semantics。 |
| L13 | [RFC 3986](https://www.rfc-editor.org/rfc/rfc3986) | IETF | URI Generic Syntax §§3.4, 6，2026-09-10 | Full HTML；supports application-dependent query semantics and normalization layers。 |
| L14 | [HTML Standard: canonical](https://html.spec.whatwg.org/multipage/links.html#link-type-canonical) | WHATWG | Living Standard，2026-09-10 | Full HTML；supports preferred URL / duplicate-content hint, not ownership or general equivalence。 |
| L15 | [MMR DOI](https://doi.org/10.1145/290941.291025) and [CMU PDF](https://www.cs.cmu.edu/afs/cs/Web/People/jgc/publication/MMR_DiversityBased_Reranking_SIGIR_1998.pdf) | Carbonell & Goldstein; ACM / Carnegie Mellon | SIGIR 1998 | DOI redirect landing page returned HTTP 403; CMU PDF was binary/compressed and not readable in this environment；no full-text claim。 |
| L16 | [xQuAD primary PDF](https://terrierteam.dcs.gla.ac.uk/publications/ecir2010_rodrygo_div.pdf) | Santos et al.; ECIR 2010 author / team host | ECIR 2010 | PDF was obtained but readable full text was unavailable；no formula / parameter / result claim。 |

## 与既有决策的关系

- **符合 ADR-0001：** query planning、facet coverage、source selection、冲突判断和 synthesis 仍由 caller agent 负责；Search 只提供候选 URL / SERP metadata，`web_read` 独立读取正文。
- **符合 ADR-0002：** 本次没有引入 paid API；SearXNG license 只按 pinned source snapshot 记录，目标 release 仍需审查。
- **符合 ADR-0003：** 没有建议 server 改写、脱敏或判断 query 是否适合外发。
- **符合 ADR-0004：** 没有引入隐式 fallback、multi-engine v1、默认 retry 或 server-side `deep_search`；Google-only route 的能力被描述为 bounded best effort，而不是 provider SLA。
