# 免费 Search smoke prototype（THROWAWAY）

对应 [验证免费 Search 的 URL 发现质量与上游稳定性](https://github.com/EllisYuan/web_search/issues/6)，属于 [深度 Web Search MCP 技术路线](https://github.com/EllisYuan/web_search/issues/1)。这不是生产 MCP，没有最终选型、SLA 或用户接受的性能阈值。

**已运行，2026-09-09。** 先读 [实测报告](REPORT.md)；逐调用 JSON 在 [runs](runs)，可重算统计在 [smoke-summary.json](smoke-summary.json)。ticket 保持 open，等待后续验证和用户评审。

## 运行

Windows PowerShell，已有 Python、uv 和运行中的 Docker Desktop Linux daemon：

```powershell
powershell -File prototypes/free-search/run.ps1
```

脚本只准备本目录 `.venv`、固定 dependency、启动 loopback-only container，然后执行 6 query × 6 route/engine 的串行 smoke。每次使用新 window 名，拒绝覆盖同名观测目录。首次会下载 PyPI packages 和固定 digest 的 Docker image；无需 key、付费 API 或 proxy。已有同名 container 时需使用同一 image 与本目录 settings mount；不要把其他实例改名占用。

已准备好环境时可直接运行（本轮实际使用的入口）：

```powershell
prototypes/free-search/.venv/Scripts/python.exe prototypes/free-search/probe.py --window my-smoke
```

只运行 DDGS：

```powershell
prototypes/free-search/.venv/Scripts/python.exe prototypes/free-search/probe.py --window my-ddgs --routes ddgs:duckduckgo,ddgs:brave,ddgs:google
```

离线复核已保存的观测，不发起网络请求：

```powershell
prototypes/free-search/.venv/Scripts/python.exe prototypes/free-search/summarize.py
prototypes/free-search/.venv/Scripts/python.exe prototypes/free-search/batch_demo.py
```

`summarize.py` 只统计 `smoke*` 目录，并要求每个 top-3 URL 已有显式标注。新实验宜用默认时间戳目录名，单独审阅后再扩展统计范围；不能自动把未标注结果算相关。

独立正文检查入口是 `readability.py`，与 Search 分开。它拒绝覆盖已经存在的 `readability-observations.json`。

停止临时服务：

```powershell
docker stop web-search-prototype-searxng
```

## 证据索引

| 文件 | 内容 |
|---|---|
| [corpus.json](corpus.json) | 运行前写定的 24 query，中文/英文/mixed 各 8，含 intent、相关性规则与非完整参考 URL 集 |
| [probe.py](probe.py) | 固定 backend，保存实际 engine、HTTP 观测、原始 engine 解析顺序与 DDGS 返回顺序、SearXNG JSON |
| [requirements.txt](requirements.txt) | DDGS 及全部本次 Python dependency 的精确版本 |
| [settings.yml](settings.yml) | 自建 SearXNG，只保留 DuckDuckGo、Brave、Google 并启用 JSON |
| [searxng-image.json](searxng-image.json) / [docker-version.json](docker-version.json) | 实际 image revision、version、license metadata 与 Docker 环境 |
| [searxng-container.log](searxng-container.log) | 本次 container 日志；CAPTCHA、TooManyRequests、180 秒 suspension |
| [quality-annotations.json](quality-annotations.json) | 52 个 query–URL 的 agent 手工 SERP 标注；含语言、site/source 分组和判断理由；未经用户接受 |
| [smoke-summary.json](smoke-summary.json) | 72 次两窗口 smoke 的 latency 原始数组、返回率、top-3 质量与逐 query 观测 |
| [runs/lowfreq-20260909](runs/lowfreq-20260909) | 低频复测：3 query × SearXNG Google / DDGS Brave，补采 response headers、Retry-After 和 upstream request count |
| [runs/real-batch-20260909-v2](runs/real-batch-20260909-v2) | 真实 sequential batch：DDGS Brave 成功、SearXNG transport error、invalid backend；每项独立落盘 |
| [freshness-review.md](freshness-review.md) | 6 次独立时效补测及 top-3 审阅，未混入两窗口统计 |
| [readability-observations.json](readability-observations.json) | 6 个指定已发现 URL 的独立正文检查，含 DNS 失败 |
| [batch-observations.json](batch-observations.json) | 离线 replay / fault injection，明确标记 injected；不进入真实成功率 |

HTTP 原始响应保存于 **本机** `raw-private/`，被 gitignore 排除；公开 JSON 保存 response hash/bytes、状态、结果、SearXNG JSON 和失败原因，不发布请求 cookie、完整 SERP HTML 或机器出口 IP。`local_body` 是本机定位，不是 GitHub artifact 链接。上游已有 snippet/score 原样留在结果中，不是本项目定义的 score。

## 本轮预算与准备成本

- CPython 3.12.4；`ddgs==9.16.0`、`primp==2.0.0`、`lxml==6.1.3`、`click==8.5.0`。DDGS package metadata 为 MIT，base 安装不含 API/MCP extra；没有 LLM、OCR、GPU 或付费服务依赖。
- SearXNG `2026.9.8-3fdc6d753`，revision `3fdc6d753a339b5f4a7dc5842c94c0d8324726f1`，image digest `sha256:3547509b419cd6a67333d6d68bd1ffad8d46d3669d82e7a7bd538f7b45827432`；image license metadata 为 AGPL-3.0-or-later。[官方 repository](https://github.com/searxng/searxng/tree/3fdc6d753a339b5f4a7dc5842c94c0d8324726f1)。
- 使用**本机已有** Docker Desktop 4.56.0 / Docker Engine 29.1.3 / WSL2 kernel `6.6.87.2-microsoft-standard-WSL2`。未测干净 Windows 安装成本；SearXNG 本轮依赖 Linux container，不能称 Windows 原生零准备。Docker Desktop 的 license 与开源 Docker Engine 有区别；官方说明 personal use 免费，其他使用条件需按官方范围区分。[Docker Desktop license](https://docs.docker.com/subscription-billing/desktop-license/)。
- 不额外部署 Valkey/Redis，不配置外部 proxy；DDGS 走 Windows host，SearXNG 走 Docker/WSL2 NAT。公网出口 IP、地理位置和两条路线是否共享同一外部 IP 未独立测量。系统 timezone 不能当出口地区；不能将差异全部归因于 adapter。
- 每调用前 10 条，query timeout 配置 12 秒，SearXNG client timeout 17 秒，调用后 pause 2 秒，probe retry=0。这是实验配置，非已接受产品限制；DDGS timeout 也不是经验证的硬性整体 deadline。
- 第一个窗口两个 route 进程曾短暂重叠，单进程 concurrency=1、总体最多 2；第二窗口单进程、6 route/engine 交错，concurrency=1。未做高并发压测。
- DDGS 每 query 新 client、无 probe result cache；其 engine 使用随机 browser fingerprint / User-Agent，版本 pin 不保证请求身份完全固定。SearXNG 保留实例状态并发生 engine suspension，未重启规避限流；上游 cache 不可观测。

## 已核对的 API 陷阱

DDGS 9.16.0 的 `bing` engine 标为 `disabled=True`；`_get_engines` 遇到不存在/禁用 backend 会 fallback 到 `auto`。probe 显式检查 registry 并拒绝 fallback。DDGS 还会 rerank/deduplicate；`upstream_parsed_results` 是 adapter 从 SERP 解析的顺序，不是未处理 HTML 的绝对排名，`results` 是最终返回顺序。相关 pinned code 可在安装后的 `.venv/Lib/site-packages/ddgs/` 复核。[DDGS 官方 repository](https://github.com/deedy5/ddgs)。

SearXNG JSON 需要 `search.formats` 配置。HTTP 200 JSON 内可能有 `unresponsive_engines`；成功判定不能只看 HTTP。本轮已保留 `raw_response` 的 engine/positions/score；没有把 SearXNG score 与 DDGS 相关性标注合并。[官方 Search API](https://docs.searxng.org/dev/search_api.html)。

**边界**：仅 Search 可行性与有限批处理展示；没有交付生产 MCP、完整 Web Read、长期稳定性验证或最终技术路线 resolution。
