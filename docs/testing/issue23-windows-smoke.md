# Issue #23 Windows 网页 image OCR smoke

验证日期：2026-09-15。环境为 Windows 11 build 26200、Python 3.12.4、MCP Python SDK 1.30.0、Playwright 1.62.0、RapidOCR 3.9.2、ONNX Runtime 1.30.0、Pillow 12.3.0。production dependency 来自 `uv.lock`，没有 Tavily key、hosted OCR 或 GPU。

## 公共 MCP trace

运行：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_stdio.py::test_real_stdio_media_advance_assets_and_webpage_ocr_without_key -q
```

该 test 通过真实 subprocess `stdio` transport 启动 production MCP server，并由 MCP Python client 依次调用公开 `web_read` contract：

1. `open https://example.org/source-page` 返回 DOM text `Webpage image fixture.` 与 image OCR text `AX-2026-0917`；OCR locator 披露 `lineage=image_ocr`、opaque `asset_id`、normalized `source_region` 和 `caption=Captured evidence`。
2. 同一 `read_id` / `version` 的 `find` 命中 `AX-2026-0917`，match 保留同一 `asset_id`；`asset_type=image` 返回 MCP `ImageContent`，没有 refetch。
3. `release` 返回 `released=true`；subprocess 结束后临时目录中的 `.image` / `.pdf` 均为空。

最终结果为 `1 passed`，stderr 为空。trace 使用受控 `MockTransport` Source，验证的是真实 MCP serialization、subprocess lifecycle、production RapidOCR worker 与公开 action contract，不是 live 网站兼容性测试。

## Static 与 rendered HTML CPU-only smoke

运行：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_webpage_image_ocr.py -q
```

最终结果为 `16 passed`。其中两条没有注入 OCR success：

- static HTML 引用 `image-en.png`，production OCR 保留 `AX-2026-0917` 与 `12345.67`。
- 真实 loopback JavaScript 页面由 headless Chromium 渲染，初始中文 image 保留 `京东20260917`；caller 显式执行 `load_more` 后，新 version 同时提交 DOM text `New rendered image` 与新英文 image 的 `AX-2026-0917`。

两条 response 的 RapidOCR det/cls/rec session 均实际报告且断言仅使用 `CPUExecutionProvider`。受控 fixtures：

| file | pixels | SHA-256 | reference text |
|---|---:|---|---|
| `image-en.png` | 1400×420 | `cebad792db3a839b4df47e324605651c5e2a6a24b4617f694da5388d6a7a6b55` | `AX-2026-0917`、`12345.67`、`ORCHID` |
| `image-zh.png` | 1400×420 | `f66cceb4481c6058ffff0dfdbf8d197dcb518f0d6d190e5a4b95f26063a0a307` | `京东20260917`、`12345.67`、`兰花` |

其余 public MCP tests 使用 deterministic injected processor 覆盖 multiple image、capture failure、OCR failure、region budget、output truncation、精确 `asset_id`、旧 version isolation、`read/find/asset` 无隐藏工作及 cleanup。注入结果不计入真实 OCR 准确率。

## 边界

本次 smoke 只覆盖 `<img src>` / `<img data-src>` 的受控中英文 PNG。它不声明任意公开网站、authenticated image、CSS background image、`srcset` 选择、animation、rotation、低清晰度、table/figure reading order 或 format fidelity 均能成功。结构不可靠时保留可靠 DOM text、caption 与原始 asset，并用 `structure_incomplete` 提醒 caller 核对。
