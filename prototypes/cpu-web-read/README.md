# CPU-only Web Read prototype

Throwaway prototype，用于评审「验证 CPU-only web_read 的完整读取范围与渐进式披露」。不代表生产 MCP、最终 tool schema、性能 SLA 或已接受的选型。

Windows / Python 3.12。所有命令从本 worktree 根目录执行。

```powershell
./prototypes/cpu-web-read/run.ps1 -Group ocr -Name ocr-baseline -Constrained
```

首次执行建立独立 `.venv`，安装 `requirements.lock` 的 pinned wheels 和开源 Chromium headless shell，生成中英文 fixture，通过 localhost:8767 提供固定 URL。默认串行；不修改其他 session 的进程或 container。存在 resource gate 拒绝时，记录 deferred 并跳过，不计为格式成功或失败。

```powershell
# 完整读取范围
./prototypes/cpu-web-read/run.ps1 -Group read -Name read-baseline
# 用户授权的受限功能 smoke（不是性能基线）
.venv-system/Scripts/python.exe prototypes/cpu-web-read/probe.py run --ids image-en,image-zh --name constrained-images --constrained
# 重复 cold / retained-engine warm；PDF 12 页渐进处理
.venv/Scripts/python.exe prototypes/cpu-web-read/probe.py run --ids long-scan --name long-progressive --repeats 2
# 保留成功页 + page 2 两次注入失败
.venv/Scripts/python.exe prototypes/cpu-web-read/probe.py run --ids mixed --name partial-failure --inject-page 2
```

`corpus.json` 记录固定 URL、语言、输入类别、fixture hash 和 reference；`references.json` 为 OCR 前目视转写的公开图片区域。`prepare.py` 生成的 fixtures 是受控公开实验内容，不冒充真实网站。`public-derived-*` 是真实公开图片的受控 HTML / PDF wrapper，不是新的独立样本。Microsoft YaHei 仅用本机已有 font 生成 fixture，记录 font hash，不分发 font。

`runs/<name>/<case>-0.json` 保存原文、page/image locator、OCR confidence / bbox、逐阶段 wall time 和 process CPU time、first preview、全文 position 续读、关键词范围、失效 state 和完整重建 trace。`*-resources.json` 记录 100 ms sampled process-tree peak RSS / CPU，包含 worker 的 browser 子进程；短命子进程可能漏采，fixture HTTP server 不计入 worker RSS。RSS 相加可能重复计共享页；不能等同 private memory。

默认护栏：HTTP / browser 30 s，case 180 s，文件 20 MiB，12 pages，150 DPI，12 million pixels，OCR intra/inter threads 2/1，tree RSS 3 GiB，available RAM 至少 2 GiB，启动 CPU 三秒均值不高于 25%。这些均是本次运行护栏，不能作为产品要求。逐阶段 `cpu_self_s` 不含 browser 子进程；总量见资源文件。download 单独列出，`advance` 包含子阶段，禁止重复求和。

`--constrained` 是用户明确授权的功能 smoke 模式，将 available RAM 门槛降至 512 MiB、CPU 门槛放宽至 60%、tree RSS 上限设为 2 GiB。它只判断 pipeline 是否可以运行；其耗时、CPU/RAM 不作为正式性能基线。Windows 上优先使用 standalone CPython；Anaconda Python 曾使 ONNX Runtime DLL 初始化失败。

首个 preview 只处理 PDF 第一页或 HTML 正文；`process_next` 再处理下一页或 image。搜索只覆盖已处理范围。失败页显式保留，有限重试耗尽后读后续页；`end_of_available` 不等于 `end_of_document`。version 指向抓取的 source / rendered DOM snapshot；当前不做远端 revalidation，state expiry/version mismatch 演示明确标记为注入。

局限：静态 HTML 的正文与图片被依次追加，未重建二者交错顺序；HTML 图片入口只覆盖 article/main 下的 src/data-src，不代表 CSS background、canvas、跨域 iframe 或完整 srcset；同页 PDF 以是否存在覆盖 image 区域的 text layer 决定跳过 OCR，该 heuristic 需要实测反例。OCR bbox 是 raster/image pixels，PDF image region 另记录 PDF points；不伪称文字准确或已由用户评审。首版候选默认 Chinese/English 模型并不证明其他语种覆盖。

原始下载和 rendered DOM 仅留本机 gitignored 路径。分享时以 commit 中的 manifest、短 reference、观测和 trace 为准；报告应说明本轮实际运行范围，未执行样本不能算通过。
