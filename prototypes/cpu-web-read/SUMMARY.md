# 实测汇总（自动重算）

尚需用户评审。cold = 首次 process/engine；warm = 同一 process 保留 engine 后重读。
stage_wall_s 的 advance 与子阶段存在包含关系，不能简单累加。RSS 是 100 ms 采样值，不是 OS 精确 peak。

| run / case | state | preview s | total s | peak MiB | CER |
|---|---|---:|---:|---:|---:|

实际结果 0 条；resource gate 拒绝 6 次。拒绝不计格式成功率。
