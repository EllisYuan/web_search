# Issue #22 Windows CPU-only mixed/scanned PDF smoke

验证日期：2026-09-15。环境为 Windows 11、Python 3.12.4、pypdfium2 5.13.0、RapidOCR 3.9.2、ONNX Runtime 1.30.0、Pillow 12.3.0、MCP Python SDK 1.30.0。production path 不使用 Tavily、hosted OCR 或 GPU。

## 受控原文对照

测试通过真实 MCP client/server transport，HTTP 仅在 acquisition edge 使用受控 fixture；PDFium、page raster、RapidOCR subprocess 和 ONNX Runtime 均为 production implementation：

| case | fixture 构造 | 必须保留的原文 |
| --- | --- | --- |
| English scanned PDF | `image-en.png` 作为无 text layer 的单页 PDF | `AX-2026-0917`、`12345.67`、`ORCHID` |
| 中文 scanned PDF | `image-zh.png` 作为无 text layer 的单页 PDF | `京东20260917`、`12345.67`、`兰花` |
| same-page mixed PDF | English raster page 叠加 native text layer | native `Reliable native heading NATIVE-22` 与 OCR `AX-2026-0917` / `ORCHID` |
| cross-page mixed PDF | page 1 native text，page 2 English raster | page 1 native `Cross-page native evidence.` 与 page 2 OCR `AX-2026-0917` / `ORCHID` |

source image hash：English `cebad792db3a839b4df47e324605651c5e2a6a24b4617f694da5388d6a7a6b55`，中文 `f66cceb4481c6058ffff0dfdbf8d197dcb518f0d6d190e5a4b95f26063a0a307`。PDF 由 test runtime 生成，Pillow 会写入生成 metadata，因此不把每次生成的 PDF hash 当成固定 fixture identity。所有关键数字与专名均由测试对 output 原文直接断言；same-page native 字符串只出现一次。locator 分别披露 `native_text` 和 `ocr` processing lineage，OCR session 实际断言仅使用 `CPUExecutionProvider`。

另将同一中文 scanned PDF 经真实 stdio MCP server/client 打开，验证 discovery 后的公开 `web_read` call 可运行，并返回 `processing.ocr_used=true`。

## Progressive processing 与 failure

公开 MCP tests 覆盖：

- `max_pages`、caller `max_regions` 与单次最多 4 个 PDF OCR regions 的 server hard limit；第五个 region 不处理并保留 page/region locator。完整 source capture 与 extraction partial、output truncation 分开返回。
- 非顺序 `advance` page、无 refetch、new version、旧 version/cursor，以及 `read/find` 只访问已处理 blocks，不启动 OCR。
- 注入中间 page OCR failure 时保留先前成功 page；failure 与 unprocessed locator 指向失败 page/region，只有新的显式 `advance` 才 retry 并建立 version。
- 同一 `advance` 的后续 target timeout 时不提交 completed prefix；取消 scanned PDF `open` 时清理未发布 PDF 和临时 PNG raster。
- native text 与 OCR block 去重；page crop 仍通过 MCP `ImageContent` 交付，不披露本机路径。

## 结构与边界

真实 columns fixture（SHA-256 `b4dc1d63de677eea6862228a6f7834ed9686eeb9f06cc8302ed45fab211a38e5`）保留 `Left A: 101` / `Right B: 202`；rotated 中文 fixture（SHA-256 `ffc73e1f4c771ad7f7a4115f4186620e2de9cfa76321beecbf2e7af904db1a8d`）保留 `京东20260917` / `兰花`。两者均返回 `structure_incomplete`，正文不构造 Markdown table。该 smoke 证明受控路径真实可运行，不承诺任意 rotation、table、reading order 或 scanned PDF 都能完整恢复；caller 应用 captured page crop 复核结构。

PDF OCR 复用 Issue #21 已固定的 RapidOCR bundled PP-OCR models、SHA-256/license 校验、2/1 intra/inter threads 和 CPU-only provider。单次 raster 限制 12,000,000 pixels / 5,000,000 bytes，source acquisition 限制 2,000,000 bytes，默认 operation deadline 30 秒。临时 PDF 随 `release`、idle expiry 或 server lifecycle 清理，临时 page raster 在每个 OCR target 完成、失败、timeout 或 cancellation 后立即清理。
