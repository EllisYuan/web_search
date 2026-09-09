# 实测汇总（自动重算）

尚需用户评审。cold = 首次 process/engine；warm = 同一 process 保留 engine 后重读。
stage_wall_s 的 advance 与子阶段存在包含关系，不能简单累加。RSS 是 100 ms 采样值，不是 OS 精确 peak。

| run / case | state | preview s | total s | peak MiB | CER |
|---|---|---:|---:|---:|---:|
| constrained-html-fallback-system / html-zh process_cold | ok | 0.457 | 0.457 | 66.6 | — |
| constrained-html-fallback-system / inline-en process_cold | ok | 0.525 | 3.105 | 398.0 | 0.0000 |
| constrained-html-fallback-system / inline-zh process_cold | ok | 0.469 | 3.027 | 404.0 | 0.0000 |
| constrained-image-en / image-en process_cold | failed | 6.811 | 6.811 | 136.3 | 1.0000 |
| constrained-images-system / image-en process_cold | ok | 3.876 | 3.879 | 313.7 | 0.0000 |
| constrained-images-system / image-zh process_cold | ok | 2.565 | 2.607 | 327.4 | 0.0000 |
| constrained-long-eager-system / long-scan process_cold | ok | 17.665 | 17.668 | 577.9 | 0.0000 |
| constrained-long-progressive-system / long-scan process_cold | ok | 2.372 | 17.596 | 558.3 | 0.0000 |
| constrained-mixed-failure-system / mixed process_cold | partial | 0.133 | 2.357 | 276.8 | 0.0000 |
| constrained-read-system / html-en process_cold | ok | 1.228 | 1.228 | 75.0 | — |
| constrained-read-system / html-zh process_cold | failed | — | 0.576 | 72.3 | — |
| constrained-read-system / inline-en process_cold | failed | — | 0.493 | 64.2 | — |
| constrained-read-system / inline-zh process_cold | failed | — | 0.466 | 66.1 | — |
| constrained-read-system / js-en process_cold | ok | 2.339 | 2.339 | 366.6 | — |
| constrained-read-system / js-zh process_cold | ok | 1.279 | 1.279 | 367.4 | — |
| constrained-read-system / text-en process_cold | ok | 0.178 | 0.182 | 48.9 | 0.0000 |
| constrained-read-system / text-zh process_cold | ok | 0.140 | 0.142 | 48.5 | 0.0000 |
| constrained-scans-system / scan-en process_cold | failed | 0.264 | 0.264 | 55.7 | 1.0000 |
| constrained-scans-system / scan-zh process_cold | failed | 0.145 | 0.146 | 44.4 | 1.0000 |
| constrained-scans-system-v2 / scan-en process_cold | failed | 0.144 | 0.144 | 44.4 | 1.0000 |
| constrained-scans-system-v2 / scan-zh process_cold | failed | 0.096 | 0.096 | 48.8 | 1.0000 |
| constrained-scans-system-v3 / scan-en process_cold | ok | 2.581 | 4.058 | 404.1 | 0.0000 |
| constrained-scans-system-v3 / scan-zh process_cold | ok | 2.234 | 3.554 | 433.5 | 0.0000 |

实际结果 23 条；resource gate 拒绝 6 次。拒绝不计格式成功率。
