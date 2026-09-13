---
status: superseded-in-part
superseded_by: 0005 (仅「不依赖付费 API」一条)
---

# 首版仅接受免费、开源方案

> **2026-09-13 更新**：本页「不依赖付费 API」一条已被 [ADR-0005](0005-paid-search-api-allowed.md) 推翻，依据是 [issue #6](https://github.com/EllisYuan/web_search/issues/6) 的实测结论。其余内容——自建组件必须开源、Windows 本机、CPU-only——继续有效。

在 [issue #5](https://github.com/EllisYuan/web_search/issues/5) 的方案讨论中，用户确认自建组件必须开源、不依赖付费 API，同时允许使用公开搜索引擎和本机资源。现有调研中的付费 provider 推荐不构成选型决定，付费服务的试用额度也不能替代这一约束；开源要求适用于自建组件，不要求上游公开搜索引擎本身开源。

首版在 Windows 本机开发部署，CPU 即可运行，暂不引入 GPU；后续计划发布到服务器。服务器的部署形态与资源预算尚未确定。
