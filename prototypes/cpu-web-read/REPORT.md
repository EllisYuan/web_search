# CPU-only Web Read prototype：准备完成，实测等待资源

记录日期：2026-09-09。对应 [验证 CPU-only web_read 的完整读取范围与渐进式披露](https://github.com/EllisYuan/web_search/issues/7)。**这是进度记录，不是 resolution。当前没有 OCR / extraction benchmark，也没有已验证的读取质量或 Progressive Disclosure 结论。ticket 保持 open，等待实测和用户评审。**

已先认领 ticket，读取 [已确认的产品边界](https://github.com/EllisYuan/web_search/issues/5#issuecomment-5594196457) 和 [深度 Web Search MCP 技术路线](https://github.com/EllisYuan/web_search/issues/1)。在独立 `.worktrees/cpu-web-read` / `prototype/cpu-web-read` 中开展；主工作区原有未提交文件没有纳入本分支。

## 实际完成

- Windows 11 / Python 3.12.4 独立 `.venv` 已安装，完整 44-package pin 在 `requirements.lock`，CPU Intel Core Ultra 5 125H、18 logical CPUs、约 15.65 GiB RAM。见 `environment.json`。
- RapidOCR 3.9.2 / ONNX Runtime 1.29.0；bundled PP-OCRv6 det/rec small + PP-OCRv4 cls 三份模型的 SHA-256 与官方包内 catalog 全部一致，见 `models.json`。pypdfium2 5.13.0、Trafilatura 2.2.0、Playwright 1.62.0。Chromium headless shell 151.0.7922.34 / revision 1234 下载完成。
- 模型文件已核对，**尚未创建实际 OCR sessions**。代码显式配置 CPU 并将在创建 session 后断言 `get_providers() == ['CPUExecutionProvider']`；当前不能写成“已实测 CPU-only 推理”。未调用 hosted OCR 或模型摘要。
- 39 条 manifest entries：六类必需输入各有中文/英文可再生成受控 fixture；再含 mixed PDF、同页 text/image、多栏、90° rotation、低清晰度、12-page scan、13-page limit、无目录长文和失败样本。不是 39 份独立真实网站样本，也没有全部下载/运行。
- 两份官方公开 OCR 图片已固定到 source commit、下载并记录 hash/resolution；在 OCR 前目视转写的区域 reference 位于 `references.json`。真实图片的本机 HTML/PDF wrapper 显式标记 `public-derived-*`。独立公开扫描 PDF、公开 HTML/JS/PDF 和公开 404 URL 已入 manifest，尚未执行读取。
- `probe.py` 已写入 HTTP fetch → HTML / rendered DOM / PDF / OCR → 原文 state 的候选 pipeline；包含原文 preview、逐 page/image 推进、section / position 读取、关键词覆盖范围、page/image locator、有限失败重试和完整重建 trace。**这些路径尚未 runtime 验证**，不能把代码中存在相应分支当作范围已通过。
- `run.ps1` 是单命令入口；`summarize.py` 可重算观测并生成单文件 `trace-viewer.html`。当前 viewer 明确显示无实测，不嵌入模拟成功数据。
- 已通过 Python syntax compile、PowerShell Parser syntax 检查、fixture 生成、三份 model hash 比对、summary 重算。未执行 end-to-end OCR/browser/PDF 质量验证。

## 为什么没有 benchmark

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

因此这里的 **0 measured results、6 deferred admission attempts** 不应解释为 OCR 失败率 100%、不支持中文、GPU 必需、性能不达标或候选不可行。当前唯一可确认的是：本次测量窗口的资源条件不足。

## 资源可用后的明确续跑顺序

1. `probe.py gate` 确认 CPU / available RAM；先串行 `image-en,image-zh,scan-en,scan-zh,inline-en,inline-zh`，保留 providers 和逐条 raw 对照。
2. OCR 基础能运行后，执行 public image / derived wrapper / public scan、columns / rotated / lowres。按 `references.json` 固定区域算 CER；核对数字、专名、reading order。有具体反例再加 CPU OCR 对照候选。
3. 执行 HTML / JS / text PDF / same-page mixed PDF，检查 heading、page、image 归属和噪声；补足真实中文 JS / 中文扫描 PDF 的代表性，不以受控成功代替公开样本质量。
4. `long-scan --repeats 2` 与同样参数的 `--eager` 独立比较；观察 first preview 是否只等第一页，以及冷 process/模型载入和 retained-engine warm 的差异。当前代码中 `full_document_ready` 仅是同一 progressive run 的下界记录，不能冒充独立 eager benchmark。
5. `mixed --inject-page 2` 演示 page 2 两次失败后保留 page 1 / page 3；再执行 corrupt/encrypted/blank/interrupted/denied/missing 和公开 404，真实/注入分开。回放完整 trace，并核查重建、不重复、不遗漏、end 与 truncated、section 无效、position 越界和 state 失效。
6. `summarize.py` 重算质量、stage wall time、process CPU、含 browser 子进程的 sampled peak RSS；标注资源干扰和未完成样本，再把真实结果与 commit asset 回填本 ticket。由用户评审后才形成 resolution / 关闭。

执行方式与实现局限见 [README](README.md)。当前未改 map 的 Decisions so far，因为没有已完成决策；将来修改前须重新读取 map 最新正文。
