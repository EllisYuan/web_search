# #25 — interruption recovery 与最终 v1 gate

## 结论

本次实现了 operation deadline checkpoint、MCP cancellation / EOF cleanup、delivery interruption 观察、browser invalidation，以及 PDF completed-target publication。**完整 Web Read v1 gate 尚未通过，#25 保持 open。** Accepted spec 的 implementation 状态及 parent / map 均未改写。

本记录区分受控 failure injection、真实 native / browser / OCR 执行，以及独立 MCP Inspector client。成功读取若因 structure warning 或 bounded extraction 返回 `partial`，仍检查可靠文字与缺口；不会将 `partial` 自动解释为没有实现该格式。

## 实现语义

- processing 在 admission 后共享一个 deadline；每次 HTTP、PDF target / raster、OCR 开始前检查 cancellation 和剩余时间。过期的 `asyncio.timeout_at` 不能单独阻止立即完成的 coroutine，因此调度边界另有显式 checkpoint。
- PDF `advance` 只提交已经完整完成的 targets，剩余 targets 写入 `failures` / `unprocessed_ranges`。提交、retained-state accounting 和 resource rollback 之间不引入 await；cancellation 在完成同步 accounting 后重新抛出。没有完成 target 时保留旧 version。
- version / cursor 的正文不变。`recovery` 是最近一次 interruption 的 operation observation，独立于 version artifact；`read/find` 重读包含历史 timeout 的 snapshot 不产生新的 timeout 事件。
- MCP response 丢失在 commit 后发生时，已有句柄可通过 `read/find` 观察当前 version。首次 open 没有交付句柄时不承诺找回。没有 status action、后台 extraction 或隐式 retry。
- `interact` 在 processing / delivery interruption 后标记 `browser_invalid`，后续 interaction 在调用 browser 前拒绝。旧 text / image / PDF artifact 保留。
- AnyIO shield 保护 cleanup；native worker launch 尚未返回 handle 时发生 cancellation，parent 仍取得 handle 后 kill / wait，不遗留未归属的进程。HTTP stream 的异步 close 同样被保护。
- `mcp_delivery.py` 是对 MCP Python SDK low-level `_handle_request` 的小型 adapter：SDK 的 handler cancellation 与 response send 位于不同 try 区域；delivery cancellation 不能取消其他请求。该 adapter 使用 SDK 内部接口，升级 MCP dependency 时必须复跑本矩阵。
- Python MCP `ClientSession.call_tool` 的本地 task cancellation 不发送协议 cancellation。测试显式发送 `notifications/cancelled`；disconnect 测试显式关闭输入 stream。没有声称向已断开 client 交付 tool error。

## 可复跑命令

```powershell
.venv/Scripts/python.exe -m pytest -q tests/test_interruption_recovery.py tests/test_pdf_ocr_web_read.py::test_pdf_ocr_advance_timeout_commits_completed_targets_and_reports_gap --tb=short -p no:cacheprovider
.venv/Scripts/python.exe -m pytest -q --tb=short -p no:cacheprovider
.venv/Scripts/python.exe -m mypy src tests
.venv/Scripts/python.exe -m ruff check src tests
.venv/Scripts/python.exe -m ruff format --check src tests
.venv/Scripts/python.exe tests/inspector_smoke.py --inspector-package .scratch/issue13-inspector/node_modules/@modelcontextprotocol/inspector --output docs/testing/issue25-inspector-smoke.json
.venv/Scripts/python.exe tests/resource_smoke.py --output docs/testing/issue25-resource-smoke.json
```

Inspector package 是本机已安装的 2.6.0；在其他机器上将 `--inspector-package` 指向相同版本的安装目录。Python / browser / OCR dependencies 使用 `uv.lock`，Chromium 安装方式见根 README。无需真实 Tavily key；Search HTTP fixture 与真实账户分开。

## 受控 interruption matrix

`tests/test_interruption_recovery.py` 通过公开 MCP `ClientSession` 发起 tool calls；stage barrier、HTTP Source、browser / OCR success fixture 等注入均在测试内明确标注。

| 区域 | 观测 |
| --- | --- |
| HTTP、PDF extraction、PDF raster、PDF OCR、image OCR、webpage OCR、browser render | cancellation notification 与真实 transport EOF；确认不发布未完成 state、lease / artifact cleanup |
| 初次 open 的 commit 前 / 后 | commit 前无 state；commit 后 cancellation 保留已提交 state，EOF / lifecycle 清理；句柄只在测试内部可见，不能声称 caller 已取得 |
| PDF、image、webpage image advance 与 browser interaction | 在 processing barrier 中取消；旧 version / cursor 可读，expiry 跳过 busy state，release 等待 cleanup 后不复活 state |
| PDF advance completed prefix | 第 2 page 完成、第 3 page timeout / cancellation；新 snapshot 可 find，第 3 page 有 failure locator / unprocessed range，旧 cursor 内容保持，显式 retry 可继续 |
| advance / interact response delivery | 在 commit / accounting 后注入 cancellation 或 BrokenResourceError；随后用已有句柄 find 新 version、read 旧 cursor；interact 明确返回 browser_state_invalid |
| read / find deadline | 返回 timeout；不调用 HTTP、PDF / raster 或 OCR |
| webpage image deadline | 第一张 image OCR 中断后不抓第二张；保留 DOM、captured asset，披露 image region 与未 capture 的 source_url |
| HTTP body 中断 | 真正执行带 await 的 response close，取消请求完成前释放 stream |
| worker launch race | 真实 OS child + 受控 handle-return barrier；取消后 kill / wait，PID 不再存在。这不是 OCR accuracy evidence |

针对矩阵与 PDF prefix 的首次定向运行：40 passed（12.24 s）。追加 malformed input coverage 后，独立 interruption test file 最终为 42 passed（9.72 s）。

## 独立目标 client

[Inspector JSON](issue25-inspector-smoke.json) 保存 MCP Inspector CLI 2.6.0 的真实 stdio 输出，11 个场景通过：

- 无 key 只发现 `web_read`，dummy key 同时发现 `web_search` / `web_read`。
- Read 正常 HTML、partial PDF、全失败 extraction envelope，以及 text / structuredContent 一致性。
- Inspector 对 `isError:true` 输出完整 tool result，并以非零 exit code 和 stderr `tool_is_error` 展示失败。Smoke 保留该真实 exit code，不能把它作为 server transport failure。
- Search batch override、partial、全失败、rate / quota、timeout、network / upstream error regression；没有 live Tavily calls。

Inspector CLI 每个场景启动新 process；此 evidence 不覆盖同一 Inspector session 内的 stateful expiry / interruption recovery。该部分当前由 Python MCP client tests 覆盖，不能与独立 Inspector evidence 混为一谈。

## 真实 Windows CPU-only resource smoke

[Resource JSON](issue25-resource-smoke.json) 记录真实 loopback HTTP、stdio subprocess、Chromium、PDFium、RapidOCR、ONNX CPU 路径。正常 workload 不替换 available RAM probe；`injected_gate` / `injected_ram` / `injected_disk` 单独标注。

本次启动 available RAM 为 1,601,159,168 bytes；完成 59 次 calls，包含 cold / warm 两轮 static HTML、text / mixed / scanned PDF、独立 image、webpage image、JavaScript browser，以及资源拒绝后的 read / find / release。后续 `defaults:100_page_pdf` 在 admission 被实际 `resource_exhausted` 拒绝，`completed:false`。该记录比 #24 的首次 open 即拒绝提供更多实测，但完整 resource smoke 仍未通过。

依赖版本、hardware、CPU / sampled RSS、temporary bytes、corpus SHA-256、page points / pixel / region 位于 JSON。OCR model source / SHA-256 / provider 位于各响应的 `processing`；所有真实 OCR 路径使用 `CPUExecutionProvider`。Hard-limit 数值与 admission / sampling / kernel limit 的区别沿用 [#24 配置说明](issue24-windows-smoke.md)，本次未放宽限制以通过 smoke。

## 尚未通过的最终 gate

1. 真实 resource smoke 的 defaults / hard-limit / concurrent workload 尚未完成。需要充足 available RAM 下运行到 `completed:true`；不能以 contract capacity fixture 替代。
2. #24 遗留的 process-wide RSS 和 Chromium temporary storage 仍是 admission / sampled guard，未实现严格 aggregate OS / filesystem quota。
3. 独立目标 client 的完整 stateful recovery acceptance，以及每种必需格式在三个 interruption 阶段的完整组合矩阵，尚未全部提供 evidence；当前 Inspector CLI 验证限于上文 11 个场景。
4. 初次 PDF extraction / 多 region image worker 尚未返回完整结果时，parent 会终止该 worker，保留先前已提交 state；没有提供 worker 内尚未返回 prefix 的逐 artifact recovery evidence。不能据 PDF advance prefix tests 扩展为所有 processing 路径均已逐 artifact 验收。

上述缺口使完整 v1 gate 保持未通过。不能关闭 #25 或将 accepted spec 的 implementation 状态改为完整 v1。

## 最终验证

- 最终完整 regression：**302 passed（163.28 s）**，包含既有 Search、真实 stdio、Chromium / PDF / CPU OCR tests，以及本次 42 个新增 interruption / validation cases。
- mypy：44 source files 通过。
- Ruff check 通过；44 files 的 format check 通过；`git diff --check` 通过。
- MCP Inspector CLI：11 个场景通过，Read 全失败以实际 exit code 5 / `tool_is_error` 展示。
- Contract tests 沿用明确的 available-RAM fixture；它们不替代 `completed:false` 的真实 resource smoke，也不改变上方未通过的 gate。
