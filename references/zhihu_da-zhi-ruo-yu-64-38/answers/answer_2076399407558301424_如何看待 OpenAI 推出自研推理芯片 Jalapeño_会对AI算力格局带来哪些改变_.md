---
type: "answer"
id: "2076399407558301424"
title: "如何看待 OpenAI 推出自研推理芯片 Jalapeño？会对AI算力格局带来哪些改变？"
author: "乱序摸鱼"
created: "2026-08-27 20:03:16+0800"
updated: "2026-08-27 20:03:16+0800"
source_url: "https://www.zhihu.com/question/2075750690551613079/answer/2076399407558301424"
content_need_truncated_in_detail: "False"
question_id: "2075750690551613079"
---

# 如何看待 OpenAI 推出自研推理芯片 Jalapeño？会对AI算力格局带来哪些改变？

- 类型：回答
- 问题：如何看待 OpenAI 推出自研推理芯片 Jalapeño？会对AI算力格局带来哪些改变？
- 原文：[知乎回答](https://www.zhihu.com/question/2075750690551613079/answer/2076399407558301424)

## 一、又来了一家“吊打英伟达”

“吊打英伟达”这几个字，这几年在 AI 芯片圈已经快被用成公版素材了。每次 Hot Chips、GTC，或者哪家新公司的发布会一开，大家第一件事还是条件反射地往后翻，先找最刺激的那几页：这一代又堆到了多少 PFLOPS，HBM 带宽终于跨过了多少 TB/s，Tensor Core 今年又发明了一种名字更长、bit 数更短的浮点格式；最好再来一张精心挑过坐标轴的性能曲线，自家的柱子一路顶到页眉，对手缩在下面负责提供比例尺。芯片发布会如果不能让上一代旗舰在某个精挑细选的 workload 上显得像十年前的产品，多少会让市场部觉得这一代硅片白做了。

![image](data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='1380' height='826'></svg>)

Jalapeño 这次当然也没能免俗。

SemiAnalysis 给这篇文章起的标题非常直接——**OpenAI Jalapeño: Better Than Nvidia Blackwell**。

[https://newsletter.semianalysis.com/p/openai-jalapeno-better-than-nvidia](https://link.zhihu.com/?target=https%3A//newsletter.semianalysis.com/p/openai-jalapeno-better-than-nvidia)

700W，216GiB HBM4，15.4TB/s 内存带宽，13.4PFLOPS MXFP4，再配上 GPT-OSS、DeepSeek R1 和 Kimi K2.5 上漂亮得有点刺眼的 throughput/W 和 latency 曲线，传播素材基本齐活。某些固定 latency operating point 上甚至还能看到几十倍乃至上百倍的 throughput 差距，做标题的人看到这里，大概已经可以提前下班了。

但做芯片的人看到这种图，第一反应是， 又来了个吹牛逼的。

我们通常会开始问一些特别破坏气氛的问题：你比较的是哪一个 operating point？batch 多大？context 多长？STP 还是 MTP？拿来除的是 package TDP 还是 workload 真正跑起来的 power？kernel 调到了什么程度？两边 software stack 的 maturity 是不是在同一个阶段？最后还有一个性能发布会最不喜欢回答的问题——这个东西到底是一块实验室里刚刚把 benchmark 跑顺的 engineering sample，还是已经能够一车一车拉进数据中心，插上电以后半年不让 firmware 工程师住在机房里的产品？

这些问题很扫兴，但芯片行业有一个坏习惯：**物理世界最后总会把 PPT 上省略掉的注释补回来。**

更有意思的是，SemiAnalysis 最后也开始替前面的标题踩刹车。他们明确承认，用 Blackwell 和 Jalapeño 做比较并不完全公平，真正合适的对手其实应该是同样使用 HBM4、产品周期也更接近的 Rubin。这个判断其实很正常。一颗面向 2026 年以后大规模 inference、从零围绕低精度和低 latency 设计的 custom ASIC，在某些 inference workload 上跑赢上一代通用 GPU，如果完全跑不赢，反而才应该把架构师叫进会议室问一下这几年到底在忙什么。

所以我不太想沿着“OpenAI 一颗芯片把 NVIDIA 打趴下了”这个故事继续讲。因为这个故事对真正做架构的人来说，实在有点浪费 Jalapeño。

我们平时做 NPU，其实最痛苦的从来不是“怎么让下一代峰值算力再涨一点”。峰值算力反而是最好讲的：矩阵单元加一点，频率顶一点，工艺吃一点，HBM 再贵一点，总归能够在 PPT 上把数字往右边推。真正麻烦的是，当一颗芯片已经大到不能随便再长、功耗已经高到散热团队看到你就想换楼层、软件又背着几代兼容包袱的时候，下一代到底还能从哪里挤性能。

昇腾这边尤其有这种压力。如果按照传统代际演进的节奏，一代架构最后能够稳稳拿到 **30% 左右的有效性能提升**，其实已经不能算差。问题是 AI 行业这几年把所有人的胃口养坏了。模型半年一个世代，GPU 发布会动不动 2×、3×，系统级 benchmark 再叠一点 MTP、speculative decoding、scale-up、软件优化，最后一张图看起来仿佛每十八个月地球上的算力就要重新发明一次。

然后轮到芯片架构师做年度规划，领导很自然地问一句：“下一代能不能也翻倍？”

这时候你看着 floorplan 里已经塞得像春节高铁站一样的 compute、SRAM、NoC、PLL、PHY，再看看功耗 budget、IR drop、timing closure 和 HBM 价格，通常很难保持发布会上的那种乐观。因为硅片不会因为 KPI 比较有激情就多长 30% 面积，memory wall 也没有绩效考核。

30% 这个数字真正让人压力大的地方就在这里：**当整个行业还在用倍数讲故事的时候，成熟架构的每一代只能在挤牙膏了，越来越像从石头里榨油。** 微架构多拿 10%，compiler 再挤 5%，memory system 想办法少浪费几个百分点，NoC 把几个长尾 latency 收回来，frequency 最后再求 physical design 同学帮忙从 timing path 里捡一点，七拼八凑以后把 30% 做出来，已经是全村一起帮忙抬轿子。

而 Jalapeño 真正让我感兴趣的地方，恰恰是 OpenAI 没有继续沿着“把每一个模块再做大 30%”这条路死磕。它开始换题目。

OpenAI 没有把最核心的 KPI 写成 PFLOPS，而是 **Time to Last Token** 和 **Tokens per Joule**。也就是说，它问的已经不是“矩阵单元理论上每秒能乘多少次”，而是“在用户能够接受的 latency 下，一焦耳电到底能够产生多少真正送到用户手里的 token”。

这两个问题看起来只差了一层单位，真正落实到微架构里，答案完全不一样。你要追峰值 FLOPS，最自然的事情是扩大 matrix engine、提高 utilization、增加数据复用；但如果目标变成低 latency 下的 tokens/J，那么那些过去躲在 profiler 角落里、看起来不够性感的东西突然全部变成一等公民：launch latency、barrier、memory fence、KV cache movement、small-shape utilization、prefetch timing、NoC hop、collective synchronization，甚至一个 thread 到底什么时候因为数据没来而在那里干等。

做过性能分析的人都见过一种非常经典的场面：每一个单独的算子拿出来都已经优化得很漂亮，Cube 说自己 90% 利用率，Vector 说自己 IPC 也不错，DMA 说带宽没跑满不能怪我，最后整个模型性能就是不行。大家单独都没犯错，但机器整体就是在乱序摸鱼。

一旦题目变成这样，30% 这件事情也会开始有另外一种解法。不是继续追着每一个执行单元问“明年还能不能再快 30%”，而是回过头去问：**我们今天这台机器里，到底还有多少时间和能量花在了“不做有用计算”这件事情上？**

## 二、Jalapeño 承认一次 LLM Inference 根本不是一种 Workload

做 AI 芯片久了以后，人很容易形成一种惯性：看到一个 bottleneck，就想配一个 accelerator；Matrix 慢了加 Cube，Attention 慢了补 Vector，数据搬不动就继续堆 DMA 和带宽，最后一颗芯片什么都有，像一个什么科室都舍不得砍的三甲医院。问题是，LLM inference 偏偏不是一种 workload，甚至同一个 request 在不同阶段，对硬件的要求都完全不一样。

OpenAI 在 Hot Chips 上把这个问题拆得很直接：Prefill 主要是 **compute bound**，需要尽可能高的矩阵吞吐；Draft Model 往往是极低 batch、极度 latency-sensitive，算力再大也没用，关键是这一小步必须尽快结束；到了 Speculative Verify / Decode，又迅速变成 **memory-bandwidth bound**，如果叠加 MoE，中间还会夹着一阵阵很不客气的 expert communication。

如果按照传统 accelerator 的思路，看到三个 bottleneck，最自然的答案就是做三种机器：Prefill 一池，Decode 一池，Draft 再来一池，每个 phase 都针对自己的 workload 做到最高 utilization，Spreadsheet 里一定很好看。

真正放进数据中心以后，事情通常没那么配合。Input/output ratio、cache hit、reasoning token、context length 都在变，今天 Prefill 排队，明天 Decode 排队，于是经常出现一边机器忙得冒烟，另一边几万美元一颗的 accelerator 坐着喝茶；更麻烦的是，Prefill 刚生成的 KV cache，Decode 下一秒就要用，如果两者被拆到不同机器或者不同 rack，这一大坨状态刚算完还没捂热，就要穿过 HBM interface、package I/O、scale-up fabric 和 switch 搬到下一站。

PPT 里这通常只是一个箭头，真正做到系统里，箭头后面站着 PHY、SerDes、buffer、flow control、queueing、synchronization 和一长串功耗数字。做架构的人都知道，最贵的往往就是这种看起来两厘米长的箭头。

所以 Jalapeño 在这里做了一个我觉得很漂亮的选择：**KV 不动，让 active silicon 动。**

OpenAI 没有把 Prefill、Draft 和 Verify 固定拆成几种 accelerator，而是做一颗相对 balanced 的 chip，让 compute、memory 和 communication resource 都留在同一个体系里；Prefill 阶段 compute 多干活，Decode 阶段 memory subsystem 接过压力，暂时用不到的单元进入 dark silicon，而 KV cache 尽量保持 local，不为了追求某一个 phase 漂亮的局部 utilization，反复把状态在机器之间搬家。

这背后其实是一个很朴素的系统原则：**局部 utilization 高，不等于整个 request 的效率高。** 两个 accelerator 都能做到 95% utilization，但如果中间多搬一次 KV、多等一次 network synchronization、再多付一套 HBM 和 I/O 的 baseline power，两个局部都很勤奋的模块，完全可以拼成一台整体上特别会摸鱼的机器。

这也是为什么 Jalapeño 后面的很多设计其实是一脉相承的。单看 peak compute，13.4PFLOPS MXFP4、700W 并没有夸张到让 NVIDIA 架构师睡不着觉，真正醒目的反而是 **216GiB HBM4、15.4TB/s bandwidth**，以及它把 core 和 HBM 做成 spatial slice：每个 core slice 对自己的 HBM slice 有低延迟 local view，常见 tensor-parallel collective 走专门的 low-latency network，其余不规则通信再交给 general NoC。

这其实是在重新强调 locality：**先把经常一起用的数据放近一点，再讨论执行单元还能不能快 20%。** 对程序员来说两个 tensor 可能只是地址不同，对 floorplan 来说一个可能住深圳，一个住北京，中间还得换两次车，而物理距离从来不会因为 programming model 写得优雅就自动消失。

OpenAI 自己还算过，如果只拿 HBM bandwidth 除模型权重，理论上可以做到大约 **1000–2000 token/s/user**，加上 speculative decoding 甚至能推到 **5000–10000 token/s/user**，但真实系统离这个 ceiling 还很远。我反而觉得这组数字比“13.4PFLOPS”更有意义，因为它说明今天 inference 最大的问题，越来越不是 roofline 不够高，而是我们离 roofline 太远。15.4TB/s 已经在那里，算力也在那里，真正丢掉的性能藏在 long-latency memory path、barrier、global fence、prefetch miss、NoC contention、collective synchronization、small-shape bubble，以及各种“理论上可以 overlap、trace 上就是没 overlap 起来”的地方。

## 三、最让我感兴趣的，是 OpenAI 为什么会把 Out-of-Order 搬回 NPU

Jalapeño 最值得琢磨的设计，我觉得不是 13.4PFLOPS，而是它居然选择了 **Out-of-Order core + L1 cache + prefetch + decoupled execution units**。这件事如果只看框图，很容易理解成“OpenAI 也开始做乱序了”，但真正有意思的因果关系其实反过来：**不是先决定做 OoO，再找 workload 来证明它合理，而是从今天 LLM inference 的数据流一路往下推，最后自然推到了硬件动态调度。**

SIMT 当年当然是一个非常漂亮的答案。GPU 面对的是大量彼此独立的 thread，一个 warp 因为 memory miss 停下来，scheduler 换另一个 warp 继续跑，只要 occupancy 足够高，就可以拿更多 thread 去遮住几百个 cycle 的 latency。几十年来 GPU 越做越宽、register file 越来越大、warp scheduler 越来越复杂，背后其实一直维持着同一个假设：**机器里永远有足够多彼此独立的工作，可以拿空间换时间。**

问题是今天的 Attention、MoE、KV Cache、Collective Communication、Persistent Kernel，再叠加越来越低的 batch 和越来越苛刻的 TPOT，真正有意义的执行单元越来越不是 thread，而是 **Tile**。几十个甚至上百个 thread，很多时候只是一起搬一块 tensor、做一个 MMA、完成一个 Reduce，它们在算法意义上并没有那么强的独立性；到了低 batch decode，GPU 最擅长的“再找几十个 warp 把 latency 藏掉”甚至开始失灵，因为 workload 根本没有凭空多长出几十份 independent work。

所以一个很自然的问题就来了：既然真正的数据流节点已经变成了 **Load Tile、MatMul Tile、Reduce Tile、Collective Tile**，为什么还一定要先把它拆成成百上千个 thread，再让 warp scheduler 努力从这些 thread 里重新把并行性拼回来？

这有点像先把一个项目组拆成三千个员工，再成立一个庞大的调度中心，每天重新计算谁其实应该一起干活。过去这么做有非常充分的历史原因，但 workload 已经变了，抽象是不是还应该原封不动保留下来，就值得重新算账。

尤其是今天 LLM 推理里真正难处理的 latency，早就不只是普通 DRAM miss：下一块 K/V tile 到没到，prefetch 有没有踩准，MoE expert 最终路由到哪里，collective 什么时候结束，NoC 此刻堵不堵，这些事情编译器根本不可能在几千个 cycle 以前全部算准。你当然可以继续要求 compiler 把流水排得像高铁时刻表一样漂亮，但物理世界总喜欢在运行时临时下一场暴雨。

这时候，硬件重新拿回一点 scheduling freedom 反而很自然：**ready 的 Tile 先跑，没有 ready 的先挂着；Cube 等 operand 的时候 Vector 可以往前走，collective 没回来时独立的 prefetch 可以先发，Load、Compute、Communication 不需要因为一道固定 barrier 全员罚站。**

这才是我理解 Jalapeño 做 OoO 的根本原因。

它也没有必要把 CPU 那套几百 entry ROB 原样搬进 NPU。真正重要的是把乱序粒度从 scalar instruction 提升到 tensor/tile operation，让一个 ROB entry、scoreboard entry 或 dependency token 后面压着几百 Byte、几 KB 甚至更多计算。粒度一大，rename、wakeup/select、ROB、issue queue 这些 OoO 最贵的东西就被更多有效工作摊薄了。天下当然还是没有免费的乱序执行，只不过以前一个 ROB entry 管一条 ADD，现在一个 entry 后面可能是一整块 Tile MatMul，这个账突然就好算了很多。

也正因为如此，我越来越怀疑，**SIMT 会不会正在从“AI 计算天然应该长成的样子”，重新退回到“GPU 历史上极其成功的一种实现”。**

这两句话差别很大。

NVIDIA 很难第一个站出来说经典 SIMT 可能不再是未来 LLM inference 最自然的 abstraction，因为 CUDA、warp、thread block 以及几十年软件生态都建立在这套世界观上；但 OpenAI 没有这个历史包袱，它掌握的恰好又是全球最真实、规模最大的 LLM inference workload，所以由 OpenAI 来重新问这个问题，反而再合适不过：**先看 2026 年模型的数据流到底长什么样，再决定机器应该怎么长，而不是因为 GPU 已经长成这个样子，就继续把模型努力翻译成 GPU 喜欢的样子。**

甚至如果今天把 NVIDIA 的公司历史、graphics 包袱和 CUDA 兼容要求全部清零，让一群顶级架构师只面对 Transformer、MoE、Agent 和 reasoning workload，从第一张白纸重新画一颗 inference processor，我并不认为最后还会得到今天这种经典 SIMT，至少不会原封不动。因为真正的数据并行已经越来越天然地表达成 Tile，而不是 thread。

这一点在我们自己的架构讨论里其实也很值得反思。我见过一种思路，为了证明 SIMT 必须继续存在，专门去寻找“SIMD 做不了、SIMT 能做”的 workload（DeepEP的原子操作），再用这些例子反过来证明 SIMT 不可替代。我一直觉得这个论证顺序有点拧巴：**架构应该从未来 workload 的主矛盾往下推，而不应该先决定某种架构不能动，再去给它寻找必须存在的理由。** 如果未来真正需要的是 dynamic control flow、gather/scatter、稀疏、expert routing，就应该把这些能力本身设计好，而不是把“能力”永远绑定到“SIMT”这个历史实现上。

OpenAI 在软件上也刚好把这一套接起来了。Gluon 建在 Triton 之上，仍然是 Tile/SPMD 风格，但显式暴露 **layout、tensor placement、physical mapping、prefetch、synchronization**，TensorInfo 描述 layout，persistent program 描述长期驻留的数据流，下面再由 OoO hardware 去吸收 runtime 才能看到的 memory、network 和 dependency 抖动。于是从上到下的逻辑非常顺：

**模型形成 Tile Dataflow → Triton/Gluon 用 Tile 表达计算 → Layout 描述数据放在哪里 → Compiler/Agent 搜 mapping、placement 和 pipeline → OoO hardware 处理“什么时候真的 ready”。**

这个软硬件边界，我觉得比过去把所有复杂度一股脑塞给 compiler 健康得多。

过去几年 NPU 有一种很强的信仰：硬件越 deterministic 越好，DMA 什么时候发、double buffer 怎么切、barrier 放在哪里、Cube 和 Vector 如何 overlap，最好全部在编译期排完；结果硬件确实简单了一点，软件却慢慢长成了一个小型操作系统，程序里到处是 async、event、semaphore、barrier、queue 和手工流水，一个 tile size 改下去，先得祈祷隔壁三个同步关系别一起炸。

所以硬件 OoO 对软件真正的收益，并不只是“性能再高一点”，而是**把大量手工排流水、同步和 latency hiding 的责任从软件拿回来**。软件只需要表达真正的数据依赖和并行性，硬件负责面对运行时的不确定性：哪个 Tile ready 就先跑，哪个没回来就先挂着。

这反而特别适合 Agent 写代码。

Agent 擅长搜索 layout、tiling、mapping、kernel structure，却没必要把大量 token 花在维护脆弱的 cycle-level 时序关系上；如果高性能 kernel 的正确性依赖“第 37 行 async copy 必须比第 52 行 barrier 提前 143 cycle”，人会疯，Agent 也不会开心。更好的接口应该是让 Agent **描述并行性，而不是手搓时序**，把动态 latency 留给硬件解决。

从这个意义上说，Out-of-Order NPU 和 Agentic Programming 其实是互相成全的：Agent 负责探索大的结构空间，硬件负责处理最后那些只有运行起来才知道的随机性。

这几年我自己在推 tile-based superscalar / out-of-order NPU，也是从另一头一路走到这个结论：当 Tile 已经成为软件和硬件共同认可的执行粒度以后，再无限增加软件可见的异步复杂度去隐藏 latency，未必是唯一答案，让硬件重新承担一部分 dynamic scheduling，反而可能让 ISA、Compiler 和 Runtime 一起变干净。

大家起点不同，面对的模型也不同，最后画出来的框图却开始往同一个方向收敛。这种事情在体系结构里其实很有意思。

英雄所见略同自己说出来多少有点不好意思，不过硅片通常比人诚实：**如果几拨人沿着完全不同的路，最后都撞到了同一堵墙，大概率说明墙真的在那里。**

## 四、CUDA 不会死，真正变化的是谁有资格定义下一台计算机

“CUDA moat is dead”这种话，放在 Twitter 上很合适，放到体系结构里就有点太着急了。CUDA 真正的护城河从来不只是一个 programming model，也不是几套 kernel library，而是几十年累积下来的 compiler、driver、framework integration、debugger、profiler、通信库、部署工具、运维经验，以及最重要的一件事——全球有几百万开发者已经习惯了这台机器应该怎么用。Jalapeño 今天能证明的，并不是这些东西突然都没价值了，而是当 workload owner 本身大到每天烧掉天文数字的 token，它其实根本不需要把整片 CUDA 生态复制一遍。

这就是 merchant silicon 和 captive silicon 最本质的区别。NVIDIA 要面对的是全世界，它必须假设明天有人拿 GPU 去跑一个今天从来没见过的 workload，所以很多历史包袱不能删、很多 corner case 必须兼容、很多只服务 1% 用户的能力也得留着；OpenAI 只需要服务 OpenAI，甚至只需要把那几十种、几百种最贵的核心 workload 做到极致，就足以覆盖绝大部分 inference 成本。于是 NVIDIA 不敢删除的东西，OpenAI 可以删，NVIDIA 必须兼容的历史，OpenAI 可以不兼容，最后这些“生态保险费”到了 floorplan 上，就会重新变成面积、功耗、带宽和延迟。

当规模足够大以后，specialization 的账终于开始算得过来了。

所以我觉得未来 AI 算力格局最先发生的变化，不是 NVIDIA 突然消失，而是训练和推理会越来越像两个不同的市场。训练的 workload 还在高速变化，模型结构、精度、并行策略都没完全稳定，flexibility 仍然非常值钱，GPU 在这里短时间内很难被真正替代；但成熟模型的大规模 inference 完全是另一回事，当同一批 kernel 每天被重复跑上亿次以后，哪怕每个 token 只省几个百分点，最后都会变成真实的电费、机柜和资本开支。未来“训练继续用 GPU，推理逐步转向自研 ASIC”很可能不会是什么激进路线，而会像今天 CPU 配 GPU 一样自然。

第二个变化是，真正的大模型公司会越来越不像一家纯软件公司，而更像半导体系统公司。Google 有 TPU，Amazon 有 Trainium 和 Inferentia，Meta 有 MTIA，现在 OpenAI 也正式下场，这背后的共同逻辑其实很简单：当模型做到足够大以后，再想从系统里抠出最后 30%、20%、10% 的效率，就不可能只靠改模型代码，Model、Compiler、Runtime、Microarchitecture、Memory System、Package、Network、Rack 必须一起动。过去 AI Lab 的核心资产是模型和数据，未来可能还要加上一套自己定义计算机的能力。

这对 NVIDIA 真正危险的地方，也不一定是订单突然没了，而是**定价权开始松动**。OpenAI 的 ASIC 哪怕最终只承担 20% 的 inference，只要 NVIDIA 相信“必要的时候这 20% 可以变成 40%”，采购谈判的桌子就已经和以前不一样了。对一个一年要采购几十亿美元甚至更多算力的大客户来说，自研芯片不需要把 NVIDIA 全部替掉，只要让替代这件事变得可信，项目本身可能就已经值回票价。

从这个角度看，Jalapeño 是否“全面打赢 Rubin”甚至都不是最重要的问题。

更长期、更值得整个芯片行业警惕的，是 AI 可能第一次反过来改变芯片自身的迭代速度。

过去做 ASIC 最痛苦的地方之一，就是周期太长。今天看错 workload，三年以后 tapeout 回来的不是芯片，是一块刻着当年架构判断的昂贵纪念碑。也正因为这样，GPU 的 programmability 一直特别值钱，因为它本质上是在替未来的不确定性买保险。

Jalapeño 有意思的地方，是 OpenAI 开始用 AI 自己去缩短这个 feedback loop：architecture exploration、RTL generation、verification、kernel bring-up、performance tuning 一路往前压，甚至声称 AI-assisted flow 在一些 block 上已经拿到了真实 PPA 收益，例如 matrix unit area 缩小约 10%。如果这一条链真的能持续缩短，ASIC 最大的传统缺点——**迭代太慢**——就会一点点被削弱。

这件事情一旦发生，GPU 和 ASIC 之间那条经典的 flexibility–efficiency Pareto frontier 本身都会移动。

过去我们的直觉是：越专用越高效，但越容易过时；越通用越浪费，但生命周期长。可如果未来架构探索、RTL、验证和软件 bring-up 的周期都能被 AI 压缩，专用硬件不再需要三四年赌一次方向，那么“专用”这件事情的风险会明显下降，GPU 原来靠通用性买来的那份保险，也就没有以前那么贵重了。

所以我不会把 Jalapeño 看成“OpenAI 打败 NVIDIA”的故事。

第一代 silicon、engineering sample、benchmark 口径、2027 年真正上量以后 reliability、fleet utilization、rack deployment，还有一堆事情没有验证，任何一个环节都可能在数据中心里给 PPT 补上现实主义的一课。

但它至少发出了一个很清楚的信号：

**AI 算力竞争正在从“谁能买到最多 GPU”，进入“谁有能力重新定义自己的计算机”。**

再往后，真正决定效率的可能不只是 PFLOPS，而是 ISA 怎么表达 Tile，Compiler 怎么做 layout，Runtime 怎么安排 KV，Microarchitecture 怎么隐藏 latency，Memory System 怎么减少搬运，Package 怎么缩短互联距离，Network 怎么把 collective 做轻，最后再回到一个越来越现实、也越来越残酷的问题：

**一度电，到底能变成多少有价值的 intelligence。**

从这个角度再回头看 Jalapeño，最有意思的地方其实不是它今天领先了多少百分点，而是很多过去已经被行业默认“答案就是这样”的问题突然重新打开了：scratchpad 还是 cache，静态调度还是 Out-of-Order，SIMT 还是 Tile，compiler 做全部 scheduling 还是让硬件拿回一部分动态自由度，甚至 programming model 到底应该优先讨好人，还是优先讨好 Agent。

对做架构的人来说，这反而是最值得兴奋的地方。

当最基本的问题又重新值得争论时，通常说明上一代答案已经开始不够用了。

## 最后，OpenAI里面就是这几个人把芯片搓出来了？

![image](data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='1774' height='887'></svg>)

很神奇吧？这么几个人，9个月+外包给博通，就把芯片做出来了，软件/硬件都是颠覆式重构

![image](data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='1625' height='968'></svg>)

## 那么，我们海思是不是也可以呢？（对不起，这是个招聘帖）

请私信我加入我们的out-or-order NPU团队

![image](data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='1448' height='1086'></svg>)

我们有Agenitc Circuit大杀器，一样可以达到相同的效果

![image](data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='1672' height='941'></svg>)
