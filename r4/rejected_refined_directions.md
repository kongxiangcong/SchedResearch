# R4 拒绝与细化的方向

日期：2026-09-05。范围是本轮源图与研究硬件假设，非所有NPU。

| 主张/方向 | 决策 | 实际依据与新的边界 |
|---|---|---|
| 官方Qwen/FLUX都是标准Transformer/DiT，可直接替换R3 motif名字 | Reject | Qwen3.5-4B是3linear+1full混合；FLUX klein双/单流计算不同；distilled CFG1没有运行时双分支。 |
| 4B参数等于4GB驻留显存 | Reject | Qwen text权重约8.412GB；FLUX main BF16约7.751GB，text/VAE/激活另计。 |
| B的旧CP提示没有胜S，故所有轻量dynamic无效 | Reject泛化 | 优化静态priority校正后，收费结果有2个微小正例，最佳+0.197%且区间跨零；仍未过门，但不能说所有策略必定负。 |
| B2已获得强静态后的有意义净收益 | Reject当前主张 | 70配置均负，最接近0仍为−0.223%；主B0最大+0.105%在增量收费后消失。 |
| 看到resource idle与ready inversion即可立项 | Reject | static opportunity union平均0.917%；单动作多数退化，最终critical-path效果必须另测。 |
| 将attention中间task合并即可免费降低SRAM/traffic | Reject | 实际物化的score/prob仍需内部scratch与读写；已按每core最大scratch预留。 |
| 原两SRAM端口模型代表独立MXU/VPU重叠 | Reject | 同core整task同port把它们串行；补四个半带宽端口保持总128B/cycle并允许重叠，仍未让B2通过门。 |
| 放大到cluster/chip更容易得到收益 | Defer | 单cluster收益门未通过，增加域会混入通信/资源增配和barrier；不做无依据规模扩张。 |
| 现在设计有限总event/epoch硬件 | Defer | 本轮仍全history，且收益门不足；优先补真实服务与全width state tiling，保留R3有限状态问题。 |
| memory plan contract + ready dispatch有独立novelty | Reject宽泛主张 | LATTICE、SPDI、TaskStream、ASPEN、HwSch均有紧邻先例；当前无已测硬件delta。 |

细化后的主问题是：**真实全宽state/weight tile与共享端口服务实测，会不会产生本轮缩尺、规则、无bank/credit模型遗漏的因果机会？** 如要继续，先收集可重复的服务/释放/可见事件，而不是新增scheduler功能。编译器侧的优先级一致性、full-width memory planning和代价校准是为检验这个问题服务，不能把研究自动改成另一个泛化编译框架。
