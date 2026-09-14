# Issue #21 Windows CPU-only smoke

验证日期：2026-09-15。环境为 Windows 11、Python 3.12.4、RapidOCR 3.9.2、ONNX Runtime 1.30.0、Pillow 12.3.0。production dependency 由 `uv.lock` 安装，没有 Tavily key、hosted OCR 或 GPU。

## 受控 reference

通过真实 MCP client/server memory transport 与 production subprocess worker 打开两张受控 PNG：

- `image-en.png`，1400×420，SHA-256 `cebad792db3a839b4df47e324605651c5e2a6a24b4617f694da5388d6a7a6b55`。原文对照包含 `AX-2026-0917`、`12345.67`、`ORCHID`。
- `image-zh.png`，1400×420，SHA-256 `f66cceb4481c6058ffff0dfdbf8d197dcb518f0d6d190e5a4b95f26063a0a307`。原文对照包含 `京东20260917`、`12345.67`、`兰花`。

两项均完整命中上述关键数字/专名。每次 inference 的 det/cls/rec session 都实际报告且断言仅有 `CPUExecutionProvider`，intra/inter threads 为 2/1。每项均在单个 30 秒 operation deadline 内完成；这是功能 smoke，不是 latency SLA。

另对历史下载、固定 source commit `4a3070f304467e6d426e78a82afea5cb1181f305` 的 RapidOCR 官方真实公开图片复测 production OCR。英文 URL 为 `https://raw.githubusercontent.com/RapidAI/RapidOCR/4a3070f304467e6d426e78a82afea5cb1181f305/python/tests/test_files/en.jpg`，SHA-256 `7945522d6cf648b4bfb0a9480efdec00b833d1df5b60aef8ce815a1bc1a82f41`；保留 `46K shots`、`7858 movies` 与正文，title 被分成 `3` / `MovieShotsDataset`，因此不宣称 format fidelity。中文 URL 为 `https://raw.githubusercontent.com/RapidAI/RapidOCR/4a3070f304467e6d426e78a82afea5cb1181f305/python/tests/test_files/ch_en_num.jpg`，SHA-256 `b94c1bf68af9ceb3c550b86931d7b48d4181c26c9f5ace2492e64042f36a02ca`；保留 `正品促销`、`-40℃深度防冻不结冰`、`极速发货`、`冰点标准`、`破损就赔`、`假一赔十`，价格 `5.8起` 被拆为两个 OCR blocks，说明复杂排版仍需原始 asset 复核。真实 input 与上述受控 fixture 不混算。

## Model 与 license

| file | SHA-256 | source | license |
|---|---|---|---|
| `ch_ppocr_mobile_v2.0_cls_mobile.onnx` | `e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c` | RapidOCR 3.9.2 ModelScope catalog, PP-OCRv4 cls | Apache-2.0 |
| `PP-OCRv6_det_small.onnx` | `090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f` | RapidOCR 3.9.2 ModelScope catalog, PP-OCRv6 det | Apache-2.0 |
| `PP-OCRv6_rec_small.onnx` | `6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884` | RapidOCR 3.9.2 ModelScope catalog, PP-OCRv6 rec | Apache-2.0 |

每次 `open` / `advance` 响应会从实际安装内容重算 model SHA-256 并披露 source/license。依赖 license：RapidOCR Apache-2.0、ONNX Runtime MIT、Pillow MIT-CMU。

## Contract 与 failure

公开 tests 覆盖 output truncation、region budget、旧 version/cursor、成功/失败 region 的 atomic commit、`read/find` 不执行 acquisition/inference、原始 image `ImageContent`、release cleanup、decode failure cleanup、低置信度/复杂结构 partial disclosure。受控 injection 与真实 OCR 分开断言；结果不声明任意图片、rotation、table 或低清晰度输入都能成功。

production OCR 对每张 image 都保守返回 `structure_incomplete`：单个高分 OCR block 也不能证明 image 内不存在 table/figure、reading-order 或漏字问题；caller 可用原始 image asset 核对。受控 columns、lowres、rotated fixtures 的真实 inference 保留关键文字，并显式标注该结构缺口。

production worker 对中文 fixture 的独立 cold measurement：wall 3.244 s、50 ms sampling peak RSS 339.4 MiB、sampled CPU 6.984 s、stderr 为空。该单次观测只用于确认 Windows CPU 路径与约束量级，不是 SLA，也没有把 shared pages 解释为 private memory。

hard-limit tests 实际覆盖：2,000,001-byte image 在 decode/OCR 前拒绝；4000×4000（16,000,000 decoded pixels）PNG 在 inference 前以 `resource_exhausted` 拒绝；5-region `advance` 超过 server 4-region limit，在 processor 前拒绝；10 ms injected advance timeout 不发布新 version并保留已提交文字。临时 capture 在 decode/pixel failure、`release`、idle expiry 和 process lifecycle 后清理。
