# R8 运行前来源补注

本文件在 E1/E2 执行前补充事前计划，原计划保留。

- R1 历史 typed MXU 要求 M/N/K 为32的倍数。因此 M=1 在本轮只作为**逻辑 CPU slice 和 byte 公式**，不进入 target native-kernel 可执行结论。若后续目标采用 Mpad=32，需另计实际 padded MAC、zero-fill、transport 和有效输出 mask；本轮不默认这些免费。M=32 仅满足历史 geometry，不认证当前 dtype/accumulator/tiling 支持。
- 两种多 cluster mapping 的输入均从同一个外存 X 开始，输出均以同一外存 Y 结束。N-shard 各 core 直接 store 自己的非重叠 output；不增加没有下游需求的 c0 gather。若下一子图要求 c0 resident，则需另立边界、给 N-shard 加相应移动。
- full-resident 与 tiled live-set 是 source payload storage 的**充分研究分配**，不等于目标最小存储或已通过保留区/bank/layout 检查。source input/W 冷读取一次的字节守恒不等于实际 AXI bytes。
- 当前未把 register 容量、实际保留区或 bank端口塞进假设中的4MiB。所有 native admission 字段保持 pending。
