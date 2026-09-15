# #24 — Windows resource admission validation

## 验收状态

2026-09-15，用户在获知下列验收差距后明确要求“关单并推送”。本票据此按当前实现交付并关闭，关闭不代表所有原始验收条件均已通过。Application-level admission、state preservation 和 worker isolation 已实现；严格的 OS-level 全局 RAM / browser temporary storage hard quota 未实现。当前不能宣称 process-tree RSS 或 Chromium profile 的瞬时用量绝不超过采样阈值。

本记录与 #22 / #23 的格式质量 evidence 分开，也不代表完整 Web Read v1、任意网站兼容率或资源 SLA。

## 配置与限制层级

数值使用十进制 bytes，配置见 [limits.py](../../src/web_search/limits.py)。

| 项目 | 当前值 | 实施方式 |
| --- | --- | --- |
| caller output default / maximum | 12,000 / 100,000 chars | schema validation；不 silent clamp |
| caller PDF page default / maximum | 10 / 100 pages | 每 action budget |
| caller OCR region default / maximum | 4 / 4 regions | 每 action budget |
| 新工作并发 | process-wide 2 | 非排队 admission reservation，多个 service 共用 controller |
| retained Python state | 每 state 32 MB、总计 128 MB | publication 前记账；拒绝超额 commit，不驱逐旧 state |
| versions / cursors | 每 state 16 / 128 | 显式拒绝新增；保留旧 version / cursor |
| application-owned temporary storage | 总计 256 MB、每工作预留 32 MB | 写入前预留；已删除的当前工作 scratch 文件归还预留 |
| browser sessions / profile reservation | 2 / 每个 16 MB | session admission；profile 实际大小每 50 ms 检查，非 filesystem quota |
| worker RSS | 768 MB | 每 50 ms 检查，超额终止 worker |
| worker committed memory | 2 GB | Windows Job Object 在 native decode / OCR 前施加 kernel limit |
| process-tree RSS admission | 3 GB | 开始前读取实际 RSS，并计入每个 active work 的 768 MB reservation；不是 kernel aggregate cap |

Browser 原有 512 MB RSS guard、文件大小、decoded image / raster pixel 上限、CPU OCR provider 和 deadline 仍由 server 控制。Caller 不能提高这些限制。

Worker 的 RSS 与 committed memory 不是同一种度量：初次将 Job committed-memory limit 设为 768 MB 时，正常 ONNX 初始化失败；已提高到 2 GB，并验证空 PDF 正常路径及真实超额 allocation refusal。不能把较低的 observed RSS 直接当成 ONNX 的 commit 上限。

Windows API 依据：[Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)、[JOBOBJECT_EXTENDED_LIMIT_INFORMATION](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information)。这些 API 不提供 Chromium profile 的 filesystem quota。

## 可复现运行方式

```powershell
.venv/Scripts/python.exe tests/resource_smoke.py --output docs/testing/issue24-smoke.json
.venv/Scripts/python.exe -m pytest -q --tb=line -p no:cacheprovider
.venv/Scripts/python.exe -m mypy src tests
.venv/Scripts/python.exe -m ruff check src tests
.venv/Scripts/python.exe -m ruff format --check src tests
```

Smoke 使用真实 MCP subprocess stdio、loopback HTTP、Chromium、PDF native workers、RapidOCR 和 CPUExecutionProvider，不依赖真实 Tavily key 或公网。JSON 记录 hardware、packages、file bytes / SHA-256、PDF page points、image pixels、raster DPI、region、每次 MCP arguments / result、CPU seconds、包含 browser / OCR 子进程的 sampled peak RSS / private bytes 及 temporary storage。

Cold 表示新 MCP process 的首次 workload；warm 表示复用同一 MCP process 与 OS caches。每次 OCR 仍启动新的 CPU worker / engine；不宣称 warm OCR engine 或清空 OS cache。

每次 call 都保存 JSON；只有所有 assertions、release 和 process exit 检查完成后才写入 `completed: true`。`completed: false` 是未完成运行，不能用于宣称完整 smoke 通过。采样不能证明不存在采样间隔内的瞬时峰值；并发 calls 的 process-tree measurements 会重叠，不能相加。

## 观测与注入的区分

- 普通 workload、browser、PDF、OCR 及 concurrent browser / OCR 使用实际 system capacity。
- `injected_gate`、`injected_ram`、`injected_disk` 明确通过 fixture gate / OS capacity probe 拒绝工作，不冒充实际 disk-full 或实际 RAM 耗尽。
- 同一有效 state 在这些拒绝之后继续 `read` / `find`，gate 关闭时仍可 `release`；之后显式新 call 才恢复，不自动 retry。
- Public MCP tests 另在 worker / filesystem 边界注入 allocation / storage failure，并验证 partial artifact、旧 state、release / expiry race 和恢复。
- Windows Job Object allocation test 使用真实 worker 请求大于 2 GB limit 的 allocation，并检查其 `resource_exhausted` 分类；不是只替换 exception 的测试。

当前机器为 Windows 11 build 26200，14 physical / 18 logical CPUs，RAM 16,799,621,120 bytes。[最新 JSON](issue24-smoke.json) 的启动时间为 2026-09-15T12:02:09Z，available RAM 为 542,195,712 bytes；首次静态 open 即被 production admission 拒绝，`completed: false`。没有发现遗留的本任务 smoke process，也未终止其他程序。完整两项并发需要至少 1.536 GB 的 available-memory reservation，因此尚需在资源充足时完成最终运行。

## Regression 与 review

- 新增 resource tests：19 passed，包括真实 Windows worker、PDF timeout 分类、regions allocation partial 及 1.8 MB PDF 多页 scratch reservation 回收。
- 使用受控 available-RAM probe 的 browser tests：12 passed。Chromium、worker kernel limit 和 RSS guard 仍真实执行。
- 首次全量运行：167 passed、93 failed，大量 Web Read 在 acquisition 前因机器 RAM 紧张被 admission 拒绝。Contract tests 已加入明确的 available-RAM fixture；独立 smoke 不使用该 fixture。
- 修正后首次全量运行：258 passed、2 failed（146.43 s）。剩余两个 stdio subprocess 未继承 pytest 的 RAM fixture；在 stdio contract bootstrap 显式注入 capacity 后，`tests/test_stdio.py` 全部 4 passed（24.15 s）。
- 推送前最终全量运行：260 passed（181.71 s）。这是独立完整运行的结果，包含 Search / Web Read regressions；contract capacity fixture 不代表真实资源 smoke 通过。
- mypy：40 source files 通过；Ruff check 与 format check 通过。
- Standards review：0 findings。
- Spec review：PDF worker isolation、resource failure 分类、TimeoutError 分类、scratch reservation 回收问题已修复；严格全局 RAM / browser temporary storage hard quota 仍为 1 项部分实现。

本次依用户指示关单；完整真实资源 smoke 与严格 OS quota 保留为明确的未完成项，不因关单被改写为通过。不能把这些 provisional limits 当作已收敛的最终验收结论。
