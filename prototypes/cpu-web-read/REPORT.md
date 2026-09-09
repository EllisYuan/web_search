# CPU-only Web Read prototype：受限 smoke 已完成，正式 benchmark 待定

记录日期：2026-09-09。对应 [验证 CPU-only web_read 的完整读取范围与渐进式披露](https://github.com/EllisYuan/web_search/issues/7)。**这是进度记录，不是 resolution。受限 smoke 已验证候选 pipeline 的功能路径；正式性能 benchmark、真实公开样本覆盖和最终产品决策仍待用户评审。ticket 保持 open。**

已先认领 ticket，读取 [已确认的产品边界](https://github.com/EllisYuan/web_search/issues/5#issuecomment-5594196457) 和 [深度 Web Search MCP 技术路线](https://github.com/EllisYuan/web_search/issues/1)。在独立 `.worktrees/cpu-web-read` / `prototype/cpu-web-read` 中开展；主工作区原有未提交文件没有纳入本分支。

## 实际完成

- Windows 11 / Python 3.12.4 独立 `.venv` 已安装，完整 44-package pin 在 `requirements.lock`，CPU Intel Core Ultra 5 125H、18 logical CPUs、约 15.65 GiB RAM。见 `environment.json`。
- RapidOCR 3.9.2 / ONNX Runtime 1.29.0；bundled PP-OCRv6 det/rec small + PP-OCRv4 cls 三份模型的 SHA-256 与官方包内 catalog 全部一致，见 `models.json`。pypdfium2 5.13.0、Trafilatura 2.2.0、Playwright 1.62.0。Chromium headless shell 151.0.7922.34 / revision 1234 下载完成。
- 模型文件已核对；受限 smoke 已创建实际 OCR sessions，并对 det/cls/rec 逐一断言 `get_providers() == ['CPUExecutionProvider']`。未调用 hosted OCR 或模型摘要。
- 39 条 manifest entries：六类必需输入各有中文/英文可再生成受控 fixture；再含 mixed PDF、同页 text/image、多栏、90° rotation、低清晰度、12-page scan、13-page limit、无目录长文和失败样本。不是 39 份独立真实网站样本；已运行的范围见下方结果，未运行项仍不计通过。
- 两份官方公开 OCR 图片已固定到 source commit、下载并记录 hash/resolution；在 OCR 前目视转写的区域 reference 位于 `references.json`。真实图片的本机 HTML/PDF wrapper 显式标记 `public-derived-*`。独立公开扫描 PDF、公开 HTML/JS/PDF 和公开 404 URL 已入 manifest，尚未执行读取。
- `probe.py` 已写入并通过受限 smoke 的 HTTP fetch → HTML / rendered DOM / PDF / OCR → 原文 state 路径；包含原文 preview、逐 page/image 推进、section / position 读取、关键词覆盖范围、page/image locator、有限失败重试和完整重建 trace。未运行的 manifest case 仍不能算已验证。
- `run.ps1` 是单命令入口；`summarize.py` 可重算观测并生成单文件 `trace-viewer.html`。viewer 只嵌入实际保存的 trace，不生成模拟成功数据。
- 已通过 Python syntax compile、PowerShell Parser syntax 检查、fixture 生成、三份 model hash 比对、summary 重算，以及受限 smoke 的 end-to-end OCR/browser/PDF 运行。

## 受限 smoke 新进展

用户随后明确授权降低门槛。使用 standalone CPython 3.12（避开 Anaconda DLL search path）和 `--constrained` 后，英文/中文独立图片已成功完成真实 OCR：两条结果均 `status=ok`、CER=0、reference line coverage=1.0；三个 ONNX Runtime sessions（det/cls/rec）均记录 `['CPUExecutionProvider']`，intra/inter threads=2/1。worker process-tree sampled peak RSS 分别约 313.7 / 327.4 MiB，wall time 4.208 / 2.956 s；这些只是受限 smoke 观测，不是性能基线。原始 JSON 位于 `runs/constrained-images-system/`。

先前 Anaconda-based `.venv` 的第一条 smoke 在 model load 阶段失败，错误是 `DLL load failed while importing onnxruntime_pybind11_state: 动态链接库(DLL)初始化例程失败。`。换用 standalone CPython 新 venv 后，直接 import `onnxruntime 1.29.0` 成功并列出 `AzureExecutionProvider` / `CPUExecutionProvider`；probe 的实际 sessions 仍严格断言只使用 `CPUExecutionProvider`。这属于 Windows Python runtime 环境问题，不能归因于 CPU OCR 质量。

新增受限 smoke 结果：

| 范围 | 结果 |
|---|---|
| 独立图片，中文/英文 | 均 `ok`，CER=0，reference line coverage=1.0；det/cls/rec 均 `CPUExecutionProvider`；sampled peak RSS 约 327/314 MiB |
| 扫描 PDF，中文/英文，各 2 pages | 均 `ok`，每页保留 `page` locator，CER=0，coverage=1.0；sampled peak RSS 约 434/404 MiB |
| 网页内文字图片，中文/英文 | 均 `ok`；正文 unit 与 OCR image unit 分开，image locator 保留；CER=0 |
| 静态 HTML，英文/中文 | 均 `ok`；中文小页面使用透明 DOM fallback，heading 已纳入目录候选 |
| JS HTML，英文/中文 | 均 `ok`；browser render stage 执行，关键词均命中 |
| text PDF，中文/英文 | 均 `ok`；text layer 模式，未重复 OCR |
| 12-page long scan，progressive | `ok`；首个 preview 约 2.37 s、只含 page 1；全文约 17.6 s |
| 12-page long scan，eager 对照 | `ok`；首个 preview 约 17.7 s，全文约 17.7 s |
| mixed PDF，第 2 页注入两次失败 | `partial`；第 1/3 页保留，第 2 页 failure locator/attempts 可见；重建文本一致，`end_of_document=false` |

以上均是用户授权的 `--constrained` 功能 smoke，不是稳定性能 benchmark；CPU/RAM 受 host 负载影响，不能据少量 controlled fixture 推导生产 SLA。原始结果位于 `runs/constrained-images-system/`、`runs/constrained-scans-system-v3/`、`runs/constrained-read-system/`、`runs/constrained-html-fallback-system/`、`runs/constrained-long-progressive-system/`、`runs/constrained-long-eager-system/` 和 `runs/constrained-mixed-failure-system/`。

## 为什么没有正式 benchmark

为避开另一个 session 的重负载，先公开了实验护栏，并在启动 worker 前检查 host CPU / available RAM。六条中英文基础 OCR case 的启动检查均被资源条件拒绝。原始记录位于 `runs/ocr-admission/*-gate.json`，汇总可由 `summarize.py` 重算。

| case | CPU 三秒采样 % | available RAM MiB | 结果 |
|---|---:|---:|---|
| image-en | 34.7 | 979.8 | deferred |
| scan-en | 42.3 | 1060.0 | deferred |
| inline-en | 35.1 | 962.0 | deferred |
| image-zh | 23.1 | 908.2 | deferred |
| scan-zh | 30.6 | 824.6 | deferred |
| inline-zh | 20.8 | 810.1 | deferred |

原始时间为 2026-09-09 05:59:31–05:59:47 UTC。启动门槛是 CPU ≤25% 且 available RAM ≥2 GiB；这些只是提前公布的实验保护条件，不是产品 SLA。后续观察 available RAM 曾降至约 375 MiB，仍有明显 host 负载。未擅自停止其他 session 的进程、Docker/WSL 或用户应用，也没有降低门槛强行制造 benchmark。

`other_workloads: []` 只表示当时未从可见 process command line 找到指定 free-search probe，并不证明系统空闲或可见所有 session。Search ticket 已回填 smoke 结果也不能证明其后台资源已经释放。

这里的 **0 measured results、6 deferred admission attempts** 是早先严格 gate 窗口的历史记录，不是当前 smoke 结果；它们不应解释为 OCR 失败率 100%、不支持中文、GPU 必需、性能不达标或候选不可行。正式 benchmark 仍未完成。

## 后续补测顺序

1. 先评审当前 controlled smoke 的原文对照、locator、partial failure 和 progressive trace。
2. 如果需要扩大证据，再跑 public image / public scan、columns / rotated / lowres、corrupt/encrypted/blank/interrupted/denied/missing 和公开 404；真实/注入分开。
3. 正式性能窗口另行安排，比较 cold/warm、download/render/extraction/OCR/preview/continuation 和 process-tree RSS；受限 smoke 数值不直接作为 SLA。
4. `summarize.py` 重算后回填 ticket；由用户评审后才形成 resolution / 关闭。

执行方式与实现局限见 [README](README.md)。当前未改 map 的 Decisions so far，因为没有已完成决策；将来修改前须重新读取 map 最新正文。
