# #15 Search Batch 验收记录

需求来源：[#15](https://github.com/EllisYuan/web_search/issues/15)；父 spec：[#12](https://github.com/EllisYuan/web_search/issues/12)。本记录区分 deterministic contract tests、Windows client smoke 与 #11 的历史 live evidence，不将三者混为真实账户验证。

## Windows client smoke

2026-09-13 在 Windows 11 build 26200、CPU-only 环境运行 **MCP Inspector CLI 2.6.0**，Node.js 24.11.1；server 使用 Python 3.12.4、MCP Python SDK 1.30.0 和 HTTPX 0.28.1。transport 为真实 subprocess `stdio`，是独立 Node MCP client 与 Python server 的实际连接，不是直接调用 Python helper。

完整 client 输出、输入参数与条件保存在 [issue15-smoke.json](issue15-smoke.json)，`observed_at` 使用 UTC。七个场景已在 review 后的最终实现上全部重跑通过，JSON text content 与 `structuredContent` 一致；每个场景的 Inspector stdout/stderr 均检查未包含配置的 dummy key。

| 场景 | client 实际可见结果 |
| --- | --- |
| production discovery | 唯一 tool 为 `web_search`；`queries` 为 1–20 项，`max_results` 为 0–20；batch / query 两层均包含全部 Search 参数，无 `route`、key、answer/raw/image/usage 参数；description 说明逐项错误、等待提示与默认 30s 单请求期限 |
| 正常 batch 与逐 query 覆盖 | 三项均为 `ok`，`partial=false`；candidate URL 回显实际收到的 depth：`basic`、`advanced`、`basic`；重复 query 独立保留 |
| partial batch | `ok`、401、400 按输入位置返回，`partial=true`，成功 candidate 保留 |
| 全部失败 batch | 401、400、429、432、433 的五项错误全部返回，`partial=false`；432/433 的 `message` 分别包含 `plan_limit_exceeded` / `payg_limit_exceeded` |
| rate limit | 429 为 `rate_limited`，`retry_after_seconds=120`；同 batch 成功项仍为 `ok`，`partial=true` |
| timeout | 不发响应的连接与持续 trickle 的连接均为 `timeout_error`；中间成功项保留，`partial=true`；没有伪造等待提示 |
| transport / upstream errors | 连接中断为 `network_error`；500、418、malformed response 为 `upstream_error`；四项均保留，`partial=false` |

配置通过临时 `mcpServers` 文件的 `env.TAVILY_API_KEY` 传入一个 dummy key，不按 query 切换 key。discovery 启动实际 production entry point `python -m web_search`，不发送 Search 请求。调用场景使用 `tests/fixture_http_stdio_server.py`，复用生产 `serve`，只在内部注入 transport 与 **0.3s 测试期限**；production 默认仍是 **30s**，tool schema 和环境变量没有增加 timeout 或 endpoint override。

与 #13/#14 的 MockTransport smoke 不同，本次调用实际连接 `127.0.0.1` 临时端口上的受控 HTTP service。test-only transport 拒绝任何非 Tavily `/search` POST 的目标，再将请求送至该 loopback service；没有公网请求、真实 key 或收费 Search。响应 body 故意回显 Authorization header；malformed 与 trickle 路径也包含 dummy credential，以验证错误输出和日志隔离。

### 复现

先按根目录 README 安装 Python dependencies。Inspector 已安装时，smoke 不需要公网；首次下载 Inspector 才需要访问 npm registry：

```powershell
npm install --prefix .scratch/issue13-inspector --no-save --ignore-scripts --package-lock=false --registry https://registry.npmjs.org --cache .scratch/issue13-npm-cache @modelcontextprotocol/inspector@2.6.0
.venv\Scripts\python tests/inspector_smoke.py --inspector-package .scratch/issue13-inspector/node_modules/@modelcontextprotocol/inspector --output docs/testing/issue15-smoke.json
```

`tests/inspector_smoke.py` 现在执行本票的七个场景。#13/#14 的原始 JSON 是历史证据，不用当前脚本覆盖它们。Inspector 每个场景会启动新进程；**同一 session 的恢复证据来自下面的 contract tests**，不是将不同 Inspector 进程的成功拼接成恢复结论。

## Deterministic contract tests

主 seam 沿用父 spec：真实 MCP client/server session 的 discovery / `web_search`，只在 Tavily HTTP 与时间边界提供受控输入。没有新增 helper 单测 seam。tests 不依赖真实 SERP 排名、账户额度、DNS 服务或公网。

- `tests/test_search_failures.py`：有效秒数（含 `0`）、HTTP-date、过去时间、缺失/非法/非有限值；固定 UTC 时钟验证日期换算。返回等待提示不自动 sleep 或 retry，两次显式调用才产生两次 attempt。
- 同文件的混合失败测试通过 MockTransport 注入带 `socket.gaierror` / `ConnectionRefusedError` 原因的 transport failure，并与慢成功、429/432/433、malformed response、timeout 混合；验证完成顺序不同仍按输入排列，所有项保留且不泄漏 dummy key。
- 同文件的真实 HTTP 混合 batch 覆盖慢成功、trickle timeout、连接中断、400/401/429/432/433/500/418 和 malformed response；受控 gate 保证后输入的成功项先完成，不依据偶然调度顺序作结论。
- `test_repeated_timeouts_release_http_connections_and_next_batch_still_completes`：用有界 connection pool 连续三轮执行两个未完成请求，再执行混合失败 batch，最后同一 session 完成正常 20-query Search Batch。每轮在 MCP session / HTTP client 关闭前，从上游 socket 观察客户端断连。pool 大小只是测试条件，不是 production worker 数或产品并发要求。
- `test_queued_queries_get_their_own_deadline_not_a_batch_deadline`：20 个未完成请求都实际到达 HTTP service 并各自返回 `timeout_error`；随后同一 session 的正常 Search 成功。没有因整个 batch 共用一个截止时间而丢掉排队项。
- `tests/test_stdio.py::test_real_stdio_rate_quota_timeout_and_subsequent_search`：真实 `stdio` subprocess 在同一 session 完成 discovery、限流/额度、timeout partial、后续成功，并检查 stderr 与公开输出。

总 deadline 的判别力已做 mutation 验证：临时移除 `asyncio.timeout(timeout_seconds)` 的期限，仅保留 HTTPX phase timeouts，真实 trickle 连接持续每 0.02s 给出数据，恢复测试触发 8s 外层测试保护并失败；恢复原期限后通过。最终代码保留总 deadline。该观测说明 read timeout 不能代替总期限，不是 8s 或 0.3s 的性能承诺。

### 父 spec 验收矩阵归属

下表名称均位于仓库 `tests/`，同一 `pytest` suite 收集；Windows 展示由上面的 Inspector 场景补充，不另造重复业务入口。

| 父 spec 场景 | 测试归属 |
| --- | --- |
| discovery / 启动 / 无 key fail fast | `test_web_search.py::test_discovery_and_single_query_search`；`test_startup.py`；`test_stdio.py`；Inspector production discovery |
| 1/20/0/21、必填字段、基本类型 / enum / range | `test_search_batch.py::test_twenty_queries_are_accepted_and_twenty_one_are_rejected_whole`、`test_invalid_parameters_reject_the_whole_batch_before_any_request`；`test_web_search.py::test_invalid_input_is_rejected_before_http_without_echoing_input` |
| 参数继承、逐字段覆盖、缺失不传、`false` / `0` / `[]` | `test_search_batch.py::test_query_parameters_override_batch_field_by_field`、`test_every_parameter_inherits_and_can_be_overridden`、`test_each_parameter_alone_reaches_tavily_from_either_level`、`test_parameters_absent_at_both_levels_are_not_sent` |
| 参数组合 / 日期基本校验 | `test_search_batch.py::test_http_400_marks_only_that_query_invalid_request`、`test_malformed_dates_are_rejected_at_both_levels`、`test_valid_dates_reach_tavily_unchanged` |
| 原 query / candidate 字段 / rank / published_date / 排除额外字段 | `test_web_search.py::test_preserves_metadata_and_excludes_unrequested_content`；discovery single-query test |
| 完成顺序不同 / 重复 query | `test_search_batch.py::test_reverse_completion_order_still_returns_results_in_input_order`、`test_duplicate_queries_stay_separate_items`；`test_search_failures.py` 的两个 mixed-failure tests |
| 合法空结果 / malformed response | `test_web_search.py::test_distinguishes_empty_success_from_malformed_response`；`test_search_batch.py::test_empty_candidates_count_as_ok_so_batch_is_not_partial` |
| `partial` 真值表 / 不新增统计字段 | `test_search_batch.py` 的全成功、mixed、all-failed tests；`test_search_failures.py` 的 mixed / repeated / queued tests；Inspector 正常 / partial / 全失败 |
| 400/401/429/432/433/500/未分类 HTTP 错误 | `test_web_search.py::test_http_failures_are_safe_per_query_errors_without_retry`；`test_search_failures.py::test_real_http_mixed_batch_preserves_slow_success_and_all_failure_categories` |
| `Retry-After` 秒数 / HTTP-date / 缺失 / 非法 | `test_search_failures.py::test_retry_after_seconds_are_optional_advice_not_automatic_retry`、`test_retry_after_http_date_uses_a_controlled_clock` |
| transport 与 timeout 区分 / 隔离 / 资源释放 / 恢复 | `test_web_search.py::test_transport_errors_do_not_leak_exception_text_or_retry`；`test_search_failures.py` 的 mixed / repeated / queued tests；同一 stdio session recovery test |
| 至多一次 attempt / 无 fallback、正文读取或费用管理 | HTTP 边界对请求目标、方法与每 query attempt 次数的断言；mixed、repeated 和 Retry-After tests；参数 body 精确断言 |
| 凭据隔离 | HTTP error、transport error、malformed、trickle 的 dummy-secret fixtures 与 DEBUG `caplog`；`test_web_search.py::test_secret_echo_in_candidate_is_not_disclosed`；stdio stderr 和 Inspector stdout/stderr 检查 |

最终检查命令：

```powershell
.venv\Scripts\python -m mypy --cache-dir .scratch/issue15-mypy-cache
.venv\Scripts\python -m ruff check src tests --no-cache
.venv\Scripts\python -m ruff format --check src tests --no-cache
.venv\Scripts\python -m pytest -q -p no:cacheprovider
```

最终结果：**155 tests passed**（9.48s），无 skip；mypy strict 检查 14 个 source files 通过，Ruff check / format check 通过。三个真实 HTTP 混合失败、重复 timeout 恢复和排队 deadline tests 另连续执行五轮，15 次均通过。`uv build --offline --out-dir .scratch/issue15-dist` 成功生成 wheel 与 sdist。以上耗时仅为本机测试运行记录，不是 Search latency 指标。

本机已有 `.pytest_cache` 的写权限受限，执行时关闭 pytest cache plugin；这只关闭缓存，不跳过 tests，也不改变现有目录权限。

### Code review

针对基线 `ff539d1` 到本票 staged diff 执行了独立 Standards / Spec review，不包含用户预先存在的未提交文档与 prototypes。

- **Standards**：无硬性 documented violation；两条低优先级启发式建议。已将并发 semaphore 的 `limit` 改名为 `attempt_slots`。MCP session、stdio、Inspector 各自的 envelope 断言保留，以便每个公开入口的契约独立可读，不为少量测试重复增加抽象。
- **Spec**：未发现缺项、越界功能或错误实现。final full suite 与 Inspector 重跑在 review 之后完成。

## 历史 live evidence 与边界

[#11 初始实测](https://github.com/EllisYuan/web_search/issues/11#issuecomment-5652708001) 提供 basic/advanced 成功、401、mixed 与 all-failed 的历史先例；[补充说明](https://github.com/EllisYuan/web_search/issues/11#issuecomment-5652709603) 修正 batch wall time 的记录。本票没有运行新的 live probe，没有关闭或修改 #11。

**429、432、433 的真实账户路径仍未验证。** 本次没有主动 flooding、耗尽额度、改支付设置、充值或发账单请求。fixture 的 432/433 只验证 wrapper 编码与展示，不证明账户计费状态或恢复时间。

30s / 20-query 是保护性基线，不是 SLA；production 每 batch 的并发上限仍为 5，不代表 process-wide rate limit 或可持续 RPM。timeout 只取消本地等待与连接，不承诺撤销上游已开始的工作或避免费用。历史小样本最大 latency 不当作 P95。本票不声称 Search 质量、Source 覆盖、Web Read 或完整 Deep Research 已验收；也不收敛它们尚未确定的契约。
