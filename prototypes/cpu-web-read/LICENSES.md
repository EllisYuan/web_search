# 依赖与样本来源核对

2026-09-09 安装后的 distribution metadata + 一手来源核对；用于本次 prototype，不锁定生产选型。完整版本见 `requirements.lock`。

| component | installed version | metadata license |
|---|---|---|
| RapidOCR | 3.9.2 | Apache-2.0 |
| ONNX Runtime | 1.29.0 | MIT |
| pypdfium2 | 5.13.0 | BSD-3-Clause, Apache-2.0, dependency licenses |
| Trafilatura | 2.2.0 | Apache-2.0 |
| Playwright | 1.62.0 | Apache-2.0 |
| psutil | 7.2.2 | BSD-3-Clause |
| Pillow | 12.3.0 | MIT-CMU |
| ReportLab | 5.0.1 | BSD |
| pypdf | 6.18.0 | BSD-3-Clause |

RapidOCR 的 [官方 repository](https://github.com/RapidAI/RapidOCR) 提供 ONNX Runtime CPU 路线，其 [LICENSE](https://github.com/RapidAI/RapidOCR/blob/4a3070f304467e6d426e78a82afea5cb1181f305/LICENSE) 为 Apache-2.0。[ModelScope pinned model card](https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.2/README.md) 明确标注 `license: Apache License 2.0`；本地下载的 card hash 在 `public-sources.json`。三份实际 bundled model URL、expected hash 和实际 hash 在 `models.json`；没有分发 wheel/model binary。

ONNX Runtime 的 [Python API](https://onnxruntime.ai/docs/api/python/api_summary.html) 提供 execution provider / session 配置；probe 必须检查每一个实际 session，不能只报告系统 available providers。pypdfium2 的 [官方 repository](https://github.com/pypdfium2-team/pypdfium2) 说明 wrapper、PDFium 和第三方 dependency license 需要分别保留；没有将其简化成单一 BSD。

Trafilatura 的 [Python usage](https://trafilatura.readthedocs.io/en/latest/usage-python.html) 用于核对 extraction 接口；Playwright 的 [browser 文档](https://playwright.dev/python/docs/browsers) 说明版本配套 browser 与 headless shell 安装。本实验安装 Playwright 配套的开源 Chromium headless shell，不依赖用户个人 browser profile、付费 API 或 hosted browser。

公开图片来自固定 commit 的 RapidOCR tests。OCRmyPDF 的 [fixture README](https://github.com/ocrmypdf/OCRmyPDF/blob/ffee83231532f4f67b8c0e756cddec67446570c9/tests/resources/README.rst) 指明 `linn.pdf` 来自 Wikimedia LinnSequencer，样本许可需按该 repository 的 `REUSE.toml` 逐项核对；本轮尚未下载/再分发该扫描 PDF。外部内容不因位于开源 repo 就自动获得 code license。

受控 fixture 使用本机已有 Microsoft YaHei font；记录 font hash、仅生成实验图片，不分发 font 文件。所有下载与 browser binary 都在 gitignored 路径。
