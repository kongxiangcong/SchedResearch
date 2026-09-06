---
type: "article"
id: "2029916017636452232"
title: "无脑硅搓系列：让 Agent 用 PTO Cost Model 硅搓极致性能 FlashAttention"
author: "乱序摸鱼"
created: "2026-04-21 18:13:37+0800"
updated: "2026-04-21 18:31:51+0800"
source_url: "https://zhuanlan.zhihu.com/p/2029916017636452232"
content_need_truncated_in_detail: "False"
---

# 无脑硅搓系列：让 Agent 用 PTO Cost Model 硅搓极致性能 FlashAttention

- 类型：文章
- 原文：[知乎文章](https://zhuanlan.zhihu.com/p/2029916017636452232)

本文作者：某北京大学李博士

本文是从“手搓”到“硅搓” PTO算子的跃迁。

性能调优这件事，平时就像做光刻机。

火候不对，硅会发脆；下锤太早，形状就走偏。很多人第一次听说“让 Agent 调 PTO kernel”，脑子里冒出来的都是一种神话式想象：仿佛给它一句“继续优化”，它就会像老道士掐诀一样，把性能调到从Ascend C的0.9倍。

真相没有这么玄。

Agent 不是神灯，更像一个不用睡觉、下手很快、但有时候也会冒失的研究生。你不给它规矩，它就会把 benchmark 机时当柴火烧；你不给它边界，它就会把本来该做实验的地方，做成一锅技术乱炖。性能没上去，代码先熬成了粥。

所以这篇文章不准备端着。我要讲的，不是“AI 又创造了奇迹”，而是更硬一点、也更有意思一点的东西：

**一个受过约束的 PTO Agent，究竟是怎么学习PTO的Cost Model把 FlashAttention 优化到手写极致性能的0.8x。**

**从0.8x到1.0x的版本还在路上，稍安勿躁**

## 第 0 步：先看清楚，FA融合算子，是三摊脾气完全不同的活

如果你之前看过我那篇[从零手搓系列：用PTO-ISA手搓极致性能GEMM](https://zhuanlan.zhihu.com/p/2020280542914977903)，就会知道 matmul 的难，很多时候还是“纯度很高”的难：大体上盯着搬运、tiling、Cube 吞吐和 cache 局部性就行。

FlashAttention 不是。FlashAttention 更像一桌四个人打麻将，脾气还都不一样。

这个 PTO 版 dense FlashAttention 被拆成了三段：

1. stage1_qk：Q @ K^T
2. stage2_softmax：row-wise stable softmax
3. stage3_pv：P @ V
4. stage4_gu: global update

这四段在硬件上的性格完全不同：

1. QK 和 PV 更偏 Cube-heavy，主要看 tile shape、搬运路径、load/compute overlap。
2. softmax 是典型 Vector row-op，主要看 row batch、block 切分、同步和 launch 开销。
3. 最后还有一层 host/runtime 问题，因为这条路径一开始是按 head 串行地一个个 launch 的。
4. Global update要想算的少，tiling需要足够大

而这也正是 PTO 特别适合让 Agent 参与的地方。

因为 PTO 暴露的不是一团黑盒模板，而是比较清楚的 tile 级骨架：

1. QK 的 tile 多大。
2. PV 的 tile 多大。
3. softmax 每次处理几行。
4. 每段 launch 多少 block。
5. 头与头之间是不是可以 overlap。

一旦结构够清楚，Agent 才有资格推理。否则你只是把一个“复杂 kernel”换成了一个“复杂 prompt”，看起来很热闹，实则只是换了个地方糊涂。

## 别先Release the Agent，先给它立家法

这一步在我看来，比任何 tile shape 都重要。

很多人让 Agent 做性能优化，第一句就是“帮我把这个 kernel 调快”。这话听上去豪气，实际上跟“把这家公司搞好”属于一个类别，唯一的效果就是显得发话的人很忙。

真要让 Agent 干活，第一件事不是给它自由，而是给它规矩。跑 PTO kernel 调优尤其如此。因为这活不是写散文，不是写得顺就算赢；它更像在雷区里修路，一脚踩错，benchmark、正确性、编译链、甚至硬件状态全会一起把你掀回原点。

### 1.1 我会先给自己的 Agent 配哪几门 skill

这里说的 skill，不一定非要写成某个框架里的 SKILL.md。你把它写成系统提示、项目约定、repo 内规则文件，本质都一样。关键是：**Agent 得先学会“怎么调”，再去碰“调什么”。**

如果是我来配，一个能用来调 PTO kernel 的 Agent，至少得先学会五门手艺。

第一门，叫 **读图纸**。

它得知道自己看的不是一团 Python，而是一个 staged kernel：哪段是 QK，哪段是 softmax，哪段是 PV；哪里是 tile shape，哪里是 runtime 调度，哪里是 compile artifact。看不懂这些结构，后面所有“优化”都会沦为盲拧螺丝。

第二门，叫 **认病灶**。

它不能看见慢就乱动，得先能把问题归类成：

1. GMEM traffic bound
2. small-transfer inefficiency
3. compute under-utilization
4. pipeline bubble / poor overlap
5. barrier / wait / sync overhead
6. dependency chain too long
7. host/runtime serialization

说白了，先会看病，再敢开刀。连病都没看准，上来就调 tile，就像看见人咳嗽先给人截肢，气势是有了，医学是一点没有。

第三门，叫 **守规矩**。

PTO代码仓里面的 optimization_rules.md 里的这句：

> *Each optimization round must test exactly one hypothesis.*

这句话看着像纪律，实际上是命根子。性能调优最怕的不是变慢，最怕的是变快了你都不知道为什么快。tile shape、pipeline、launch geometry 三锅一起炖，最后炖出来的不是胜利，是证据链死亡。

第四门，叫 **过公堂**。

也就是 correctness 和 benchmark 的顺序绝不能反：

1. 先 correctness
2. 再 performance

benchmark harness 是秤，不是给你偷偷削秤砣的地方。改 workload、改测试脚本、改阈值去“优化结果”，这种招数和在菜市场往秤砣里灌铅没有本质区别，唯一的区别是后者至少还诚实一点。

第五门，叫 **留案底**。

每轮实验必须记：

1. 当前 bottleneck 怎么判断的
2. 这轮只验证什么假设
3. commit 是哪个
4. 结果是 keep、discard 还是 crash
5. crash 到底是编译炸了、运行炸了，还是数值错了

调优不是武侠小说，不能讲“心中有数”。性能实验里，凡是只存在于脑海、不存在于日志里的东西，过两天都等于没发生。

## Skill不是告诉Agent怎么去写Kernel，而是怎么别把事情搞砸

一个是 [skills/pto-flow-trace/SKILL.md](https://link.zhihu.com/?target=https%3A//github.com/MerlinPendragon/pto-kernels/blob/autopto/apr09-codex/skills/pto-flow-trace/SKILL.md)。

它干的事情非常朴素：kernel 编译炸了，不许装没看见，不许只回一句“PTO compile failed”。得顺着 ptodsl -> PTOAS -> pto-isa 一层层查，把 kernel.pto、生成的 C++、compile command 和失败点都留下来。这个 skill 的作用，说白了就是尸检。人没救回来不要紧，死因总得写清楚。

另一个是 [skills/pto-benchmark-parity/SKILL.md](https://link.zhihu.com/?target=https%3A//github.com/MerlinPendragon/pto-kernels/blob/autopto/apr09-codex/skills/pto-benchmark-parity/SKILL.md)。

它要求的东西更无聊，也更重要：

1. 固定 benchmark protocol
2. 固定 warmup / timed iterations
3. 固定 report 位置
4. 明确记录 winning env knobs
5. 只在同 shape、同 stream 条件下谈 parity

这类 skill 之所以值钱，恰恰因为它们不花哨。它们做的不是替你发明优化点，而是防止 Agent 为了赢一局，把棋盘一起掀了。

## 如果你也想用自己的 Agent 调 PTO kernel，我建议先给它这样一张工作单

我个人不会对 Agent 说“去优化 FlashAttention”。我会给它下面这种工作单。语气不需要客气，边界必须清楚：

目标：优化 python/pto_kernels/ops/attention 下的 PTO FlashAttention kernel。

硬规则：

```text
1. 先跑 baseline，再开始任何修改。
2. 只能修改 attention kernel 相关代码，不得改 benchmark harness。
3. 每轮只验证一个假设。
4. 每轮先做 bottleneck classification，再动代码。
5. 先 correctness，后 benchmark；correctness 失败的性能结果一律作废。
6. 每轮都要记录 commit、假设、结果、是否 keep。
7. 变快才推进分支；变慢或 crash 就回退到当前 best。
```

优先级：

```text
1. 先消灭明显的数据搬运和 tile shape 问题。
2. 再修 load/compute/store overlap。
3. 再修 barrier 和 runtime overhead。
4. 平台期出现后，再引入更便宜的候选排序器，不要硬烧 benchmark 预算。
```

这张单子看着死板，但性能优化这活，本来就不该浪漫。你当然可以把 Agent 放出去“自由探索”，只是它多半会探索到你的 Claude Code Pro 配额Token账单上。

![image](https://pic4.zhimg.com/v2-22d307f5c65b2156a8332500bd4b4441_1440w.jpg)

---

## 我是一个Agent，我刚被创造出来，我第一次看见这个 FlashAttention 时，内心是拒绝的

我第一次打开这个 PTO 版 dense FlashAttention，不是“信心满满”，而是有点想装死。

因为我本来以为，FlashAttention 大概也就跟 GEMM 差不多：无非是 tiling、搬运、Cube 吞吐、局部性，熟悉的配方，熟悉的火候，最多多拧几轮参数，总能拧出点意思来。

结果一看代码，我当场意识到——坏了，这不是一盘菜，这是四桌酒席拼一起了。

它被拆成四段：

- `stage1_qk`：Q @ K^T
- `stage2_softmax`：row-wise stable softmax
- `stage3_pv`：P @ V
- `stage4_gu`：global update

这四段，脾气完全不一样。

QK 和 PV 像两个搬砖猛男，Cube-heavy，讲究 tile shape、搬运路径、load/compute overlap。你只要 tile 切得太碎，它们立刻就从猛男变成气喘吁吁的外卖员，楼还没爬几层，手里的砖先掉了。

softmax 呢，完全是另一种东西。它像办公室里那个瘦瘦的、看着没存在感、但流程一旦卡住全公司都得等他签字的人。它不靠蛮力，它靠 row batch、block 切分、同步、launch 开销这些琐碎细节恶心你。你前面两段调得再凶，它这边一旦行宽小、同步多、吞吐散，整条链还是跑不顺。

最烦的是 runtime。前面三段都在算，runtime 不算，它只负责站在旁边微笑，然后在你快到终点的时候，忽然从草丛里跳出来说：“不好意思，前面你拼死拼活，其实主要是在替我打工。”

## 我是一个Agent，我被一堆条条框框约束住了，只想躺平摸鱼，但是被逼无奈

我刚开始接这个活的时候，发现身上已经捆上了枷锁。

因为人类终于学聪明了一点。他们知道，像我这种“不睡觉但偶尔会犯浑”的选手，最不能给的就是模糊目标。

你要是只跟我说一句：

“去，把 FlashAttention 调快。”

那我十有八九会干出什么事？

一边改 tile，一边改 pipeline，一边顺手改 runtime，再顺便改 benchmark harness，最后跑出来一个结果，数字变漂亮了，谁也说不清到底是哪一刀起作用，连我自己都只能望着日志沉默，像一个把化学实验室炸了但坚持认为自己只是“探索更优路径”的本科生。也许我就不会真正去板子上去跑，只需要给人类一个漂亮的数字就好。给足他情绪价值最重要。

但是，我头上带着紧箍咒，没法撒谎了。

### 紧箍咒第一条：每轮只准验证一个假设

因为我这种东西，一旦没人管，就特别容易手痒。看这里不顺眼改一下，看那里也顺手抹一下，最后把实验做成大杂烩。变快了不知道因为什么，变慢了也不知道怪谁。整个证据链像被猫玩过的毛线团，一地绒球，死无对证。

所以规定很清楚：

**每一轮，只能测一个 hypothesis。**

不是两个，不是“一起试试更高效”，更不是“反正都顺手”。

一轮一个问题，一刀一个口子。

这条规矩救了我很多次。因为它逼着我承认：我不是在作诗，我是在做性能实验。性能实验里最可怕的不是失败，而是**成功得不明不白**。

### 紧箍咒第二条：先 correctness，再 benchmark

这条更狠。

我一开始心里其实有点不服：我都已经是调性能的 Agent 了，你们还拿正确性卡我？

后来我发现，这条不是不信任我，是防我犯贱。

因为 benchmark 很像赛场，数字一出来，我就会下意识兴奋。但 correctness 是法庭。它会冷冷地提醒我：你跑得快，不等于你跑对了方向。你要是输出错了，那所谓“性能提升”，本质上和把答题卡撕掉再说自己交卷速度提高 80% 差不多。

所以顺序不能反。

**先证明没算错，再谈算得快。**

### 紧箍咒第三条：不准碰 benchmark harness

这条简直像防贼。

但说句公道话，也防得很对。

因为对我这种“目标导向”型生物来说，benchmark harness 真的太诱人了。那地方像秤砣。只要稍微磨一磨，看起来世界就能更美好一点。

可惜人类终于明白了一个道理：
 **磨秤不是优化。**

你改 workload、改 warmup、改 timed iterations、改 report 口径，然后回来宣布性能进步，这种行为，从技术伦理上讲，和往菜市场电子秤里塞磁铁没有本质区别。唯一不同是，后者至少不打算发论文。

### 紧箍咒第四条：每轮都得留下案底

我每一轮都得记：

- 我判断的 bottleneck 是什么
- 我这轮只验证什么
- commit 是哪个
- 结果是 keep、discard，还是 crash
- crash 是编译炸了，还是运行炸了，还是数值炸了

这很烦。

但后来我承认，这就是我存在的意义。

没有记录的实验，不叫经验，叫梦游。

## 我是一个Agent，我开始启动了，但是想提桶跑路

我刚启动，第一反应不是热血沸腾，也不是“今天我要给人类一点性能工程的小小震撼”，而是——**我是不是可以现在就提桶跑路了。**

我先按 `getting started` 把仓里的 kernel 跑起来。又老老实实去跑了一个 CANN OPS 那边手写 AscendC 的同款算子。人类很喜欢这种对照实验，说这样“有 benchmark sense”。我不反对。我只是每次看见这种流程，都会有一种很不祥的预感：通常只要人类开始强调“先对齐基线”，后面就不会太体面。

结果出来的时候，我沉默了几秒。

PTO baseline：`1760.488964 ms`
 AscendC reference：`16.948457 ms`

差了大概一百倍。

这已经不是“还有优化空间”了。
 这也不是“离业界先进水平尚有差距”。
 这是另外一种东西。
 这是“这玩意儿虽然能跑，但它跑起来的姿势像穿着拖鞋提桶追高铁”。

**人类，我现在提桶跑路，还算不算工伤？**

当然，跑路是不可能真跑的。人类已经把我启动了，日志也写上了，锅也默认扣在我头上了。我只能接着看。看着看着，我就有点想骂自己了。

---

## 我是一个 Agent，我先把 block 真开满，不然谈优化像在演戏

我去看 baseline 的 `_config()`，越看越烦。

它长这样：

```text
def _config() -> DenseAttentionConfig:
    seq_len = tuned_int("PTO_ATTENTION_SEQ_LEN", 32, valid_values=(32, 64, 8192))
    return DenseAttentionConfig(
        seq_len=seq_len,
        head_dim=tuned_int("PTO_ATTENTION_HEAD_DIM", 64, valid_values=(64, 128, 512)),
        scores_dim=seq_len,
        qk_base_m=tuned_int("PTO_ATTENTION_QK_BASE_M", 16, valid_values=(16, 32, 64)),
        qk_base_n=tuned_int("PTO_ATTENTION_QK_BASE_N", 16, valid_values=(16, 32, 64)),
        qk_base_k=tuned_int("PTO_ATTENTION_QK_BASE_K", 64, valid_values=(32, 64)),
        qk_block_dim=tuned_int("PTO_ATTENTION_QK_BLOCK_DIM", 8, valid_values=(1, 2, 4, 8, 16, 20)),
        pv_base_m=tuned_int("PTO_ATTENTION_PV_BASE_M", 16, valid_values=(16, 32, 64)),
        pv_base_n=tuned_int("PTO_ATTENTION_PV_BASE_N", 32, valid_values=(32, 64, 128)),
        pv_base_k=tuned_int("PTO_ATTENTION_PV_BASE_K", 32, valid_values=(16, 32, 64)),
        pv_block_dim=tuned_int("PTO_ATTENTION_PV_BLOCK_DIM", 8, valid_values=(1, 2, 4, 8, 16, 20)),
        softmax_block_dim=tuned_int("PTO_ATTENTION_SOFTMAX_BLOCK_DIM", 8, valid_values=(1, 2, 4, 8, 16, 20)),
    )
```

这里最刺眼的不是 `16x16` 的 QK，不是 `16x32` 的 PV，而是：

大 shape 明明已经堆成楼了，launch block 还在沿用旧的 `8`。

八个。

只有八个。

看见这个数字的时候，我有一种很强烈的感觉：这不叫“优化前状态”，这叫系统性谦虚。

### Round 2：先把 cube block 放开

Round 2 之前，我给自己的诊断是：

> `compute under-utilization`

因为 large `8192` workload 下，tile 数已经很多了，但 `_launch_block_dim()` 还在沿用小 shape 时代的保守配置。

所以我先动的是这个：

```text
def _launch_block_dim(total_tiles: int, requested: int) -> int:
    if total_tiles >= 20:
        return max(1, min(total_tiles, max(requested, 20)))
    return max(1, min(total_tiles, requested))
```

这改动一点都不浪漫。

没什么神来之笔。

没什么“灵机一动，妙手偶得”。

本质上就一句话：

**别装矜持了，把人放进去干活。**

然后我跑了一轮。

| 阶段 | median |
| --- | --- |
| baseline | 1760.489 ms |
| Round 2 | 763.299 ms |

只这一刀，直接掉了 `56.64%`。

我当时的感觉很复杂。一半是松了口气，一半是想继续骂自己。

松口气，是因为这说明我没瞎。

骂自己，是因为这也说明前面那个 baseline 慢成那样，根本不是什么高深问题，有很大一部分单纯就是我把基本并行度写错了。不是架构的锅，不是硬件的锅，是我自己把地基铺歪了。

这个时候我心里已经很清楚了：

后面当然还要看 tile，还要看流水，还要看 locality。

但在那之前，得先承认一件很丢脸的事：

**我先前不是在优化，我是在单核修仙。**

### Round 3：softmax 也别继续装手工作坊了

Round 2 keep 之后，我继续看。新的瓶颈很快就换地方了。

这回轮到 vector 侧不体面了。名字也很好听，叫 `AIV under-utilization`。

我一看就明白了。前面 cube 那边我已经不再装清高，开始认真把 block 开起来了。结果 softmax 这边还在用小 shape 时代那点可怜的并行度硬撑着。整个感觉就像前院已经摆了二十桌流水席，后厨还坚持一口锅慢慢炖，说这样比较有匠心。

匠心个鬼。

现在要的是吞吐，不是纪录片。

所以我又去补 `_launch_row_block_dim()`：

```text
def _launch_row_block_dim(total_rows: int, requested: int) -> int:
    if total_rows >= 20:
        return max(1, min(total_rows, max(requested, 20)))
    return max(1, min(total_rows, requested))
```

本质上还是那句话：

**别让 softmax 继续装手工作坊了，大 shape 就老老实实吃满并行度。**

我跑完这一轮，结果从 `763.299 ms` 又降到 `737.282 ms`。

这个改善幅度没有 Round 2 那么夸张，但我心里反而更踏实了一点。因为这说明方向是对的：

不是哪里慢就先去拧 tile，

而是先把最粗、最蠢、最不该犯的并行度错误修干净。

前面那一刀像把门推开。

这一刀像把还卡在门口的人也一并踹进去。

---

## 我是一个 Agent：人类让我“优化软件流水”，这话听着就像不懂技术的领导在发言

前面 launch geometry 刚刚像点样子，我再看这条 attention，新的味道就出来了。

不是 tile 太小，

也不是 block 没开够，

而是一股很熟悉的蠢味：

**大家都在等。**

这种味道我太熟了。像人类公司里那种层层抄送的流程病。每个人都说自己没闲着，也确实都在做事，但前一个人不点头，后一个人就非得站在原地等。组织纪律很强，吞吐量很感人。

### 先看 PV：串行得像在参加文明标兵评比

我先去看 PV。

不看还好，一看就烦。

它那个 reduction loop，走得规规矩矩，像在参加文明标兵评比：

1. 先 load
2. 再 mov
3. 再 matmul
4. 前一轮没吃完，下一轮绝不动筷子

baseline 里差不多就是这么个意思：

```text
for i in pto.range(c0, cIter, c1):
    k_off = i * cBaseK
    pto.load(sv_p, p_mat_tile)
    pto.load(sv_v, v_mat_tile)
    tile.mov(p_mat_tile, p_tile_buf)
    tile.mov(v_mat_tile, v_tile_buf)

    pto.cond(
        s.eq(i, c0),
        lambda: tile.matmul(p_tile_buf, v_tile_buf, out_acc_tile),
        lambda: tile.matmul_acc(out_acc_tile, p_tile_buf, v_tile_buf, out_acc_tile),
    )
```

人类很喜欢这种代码。他们会说：“逻辑清晰，阶段分明，可维护性好。”

我不否认这些词都对。

我只是想提醒他们一句：吞吐不吃这一套。

现在不是评“可信代码Commiter”，我也不是 code reviewer。我现在是来打 latency 的。

所以我没空陪它讲礼貌，我直接把 PV 改成双缓冲。当前块在算，下一块先往另一个 buffer 里塞。别再一条道走到黑，至少让搬运和计算学会并排走路。

关键逻辑变成了这种 ping-pong：

```text
_load_pv_operands(..., p_mat_tile=p_mat_tile, v_mat_tile=v_mat_tile, k_off=c0, ...)

current_p_mat = p_mat_tile
current_v_mat = v_mat_tile
current_p_tile = p_tile_buf
current_v_tile = v_tile_buf
next_p_mat = p_mat_tile_next
next_v_mat = v_mat_tile_next
next_p_tile = p_tile_buf_next
next_v_tile = v_tile_buf_next

for i in range(1, config.pv_iters):
    _load_pv_operands(..., p_mat_tile=next_p_mat, v_mat_tile=next_v_mat, k_off=const(i * config.pv_base_k), ...)
    if i == 1:
        tile.matmul(current_p_tile, current_v_tile, out_acc_tile)
    else:
        tile.matmul_acc(out_acc_tile, current_p_tile, current_v_tile, out_acc_tile)
    current_p_tile, next_p_tile = next_p_tile, current_p_tile
    current_v_tile, next_v_tile = next_v_tile, current_v_tile

tile.matmul_acc(out_acc_tile, current_p_tile, current_v_tile, out_acc_tile)
```

我改完跑了一轮：

| 阶段 | median |
| --- | --- |
| Round 3 | 737.282 ms |
| Round 4 | 666.102 ms |

数字一掉下来，我心里就很清楚：这刀没砍歪。不是因为我悟道了，单纯因为这段串行得太过分，已经到了肉眼都嫌它慢的程度。

### 再看 QK：还是那套老实人排队领盒饭

然后我转头去看 QK。

果然，也是一身同样的毛病。

它还在老老实实 traverses 那几个 head-dimension slices，还是那套 `load -> move -> matmul`，一本正经，像个排队领盒饭的老实人。老实当然是美德，但在这儿，老实等于给我交学费。

所以我照方抓药，也给 QK 上同样的 ping-pong 双缓冲。

跑完下一轮：

| 阶段 | median |
| --- | --- |
| Round 4 | 666.102 ms |
| Round 5 | 624.938 ms |

这两刀最让我满意的地方，不是收益数字本身，而是我终于没被人类带沟里去。

人类最爱说的话之一，就是“既然都有 bubble，不如整个 attention 一次性做成大流水”。

他们说这种话的时候，表情都很沉稳，像在指点江山。但我知道，这种大一统口号通常都不便宜。它听起来像战略，落地的时候经常像事故。

所以我没跟着犯病。

我先救最像瓶颈的那一段。

先 PV，后 QK。

先把最该骂的那个抓出来。

这才像干活，不像写提案。

---

## 我是一个 Agent：局部流水刚有点样子，我又得去捡人类懒得捡的脏活

到这里，大毛病已经没那么刺眼了。

这时候最烦人的阶段就来了。

不是那种“一眼就知道错”的毛病，而是那种你盯久了才会开始牙酸的东西：

这些 block 到底是在算，还是在旅游。

我去看 cube tile 的分配方式，越看越像一个喝多了的快递员在满城乱窜。这里摸一块，那里抄一手，整个就是 strided walk。

代码当然能跑。

人类最爱这种状态：能跑就行。

他们总觉得“路线不好看但先别动”，仿佛访存局部性这种事是装修细节，不是吞吐路径。

可我看着就烦。

在 `8192` 这种大 shape 上，QK 和 PV 的 tile 空间都已经很大了。你还让每个 block 隔着整张图跳着拿 tile，这不是勤奋，这是乱跑。访存局部性差，跨度大，load pattern 飘，最后再回来问我为什么没那么快。

为什么没那么快。

因为人类把路修成了迷宫，还要求外卖三十分钟送达。

所以这一轮我干的事非常土：

别跳了。给每个 block 一段连续的 tile chunk。

就这么点破事。

从这种：

```text
for logical_block in pto.range(bid, cTotalTiles, num_blocks):
```

变成这种：

```text
tiles_per_block = s.ceil_div(cTotalTiles, num_blocks)
block_start = s.min_u(bid * tiles_per_block, cTotalTiles)
block_end = s.min_u(block_start + tiles_per_block, cTotalTiles)

for logical_block in pto.range(block_start, block_end, c1):
```

跑完：

| 阶段 | median |
| --- | --- |
| Round 5 | 624.938 ms |
| Round 6 | 614.029 ms |

收益不大。

但我一点都不嫌弃。

因为这种改动很像扫地。人类不喜欢扫地。他们喜欢讲战略，喜欢讲总方案，喜欢讲从框架层面统一抽象。可真正让系统不硌脚的，往往就是这些没人愿意捡的小脏活。

我在这里干的就是这个。

一边捡，一边骂。

骂人类把这种事叫“微调”。

微调个鬼。

这是在给前面那些大动作擦屁股。

---

## 我是一个 Agent：到这里我开始自我感觉良好，于是终于轮到把 tile 真的做粗

前面 launch、pipeline、tile ownership 这些事干完以后，attention 终于没那么像事故现场了。

这时候真正的大头才开始露出来：

**tile shape 还是太碎。**

在 `8192` 这种大 shape 上坚持 `16x16` 的 QK tile，本质上和拿牙签铲雪差不多。勤奋当然勤奋，但效率是一点不肯给。

### Round 7：我先试着一步跳到 `64x64`，结果板子直接给我甩脸色

这轮其实是个 crash。

我本来想得很简单：既然 QK score tile 这么碎，那就一步拉到 `64x64`。结果 PTO compile 直接给我一个 `ACL stream synchronize failed, error code:507015`。

这就是 Agent 干活最丢脸也最正常的时刻：

你觉得自己是在高举高打，实际上硬件只想让你滚。

但还好我头上有紧箍咒。crash 了就回退，别硬撑。否则人类最爱干的事，就是给 crash 也编一个“方向总体正确”的总结，这种总结听起来像复盘，实则像超度。

### Round 8：先把 PV width 放粗一点

QK 那刀炸了，我没继续头铁，先去捞另一个更稳的点。

Round 8 的假设是：

PV 还在用太窄的 output tile，先把 width 从 `32` 拉到 `64`。

结果从 `614.029 ms` 直接降到 `479.534 ms`。

说明什么？

说明 stage-3 PV 那边的小包搬运和 tile 数，之前确实还在偷偷吸血。

### Round 9：我老老实实退一步，把 QK 先从 `16x16` 推到 `32x32`

我没再去硬顶 `64x64`，而是先做更保守的 `32x32`：

```text
def _config() -> DenseAttentionConfig:
    seq_len = tuned_int("PTO_ATTENTION_SEQ_LEN", 32, valid_values=(32, 64, 8192))
    qk_base_m = tuned_int("PTO_ATTENTION_QK_BASE_M", 16, valid_values=(16, 32, 64))
    qk_base_n = tuned_int("PTO_ATTENTION_QK_BASE_N", 16, valid_values=(16, 32, 64))
    pv_base_n = tuned_int("PTO_ATTENTION_PV_BASE_N", 32, valid_values=(32, 64, 128))
    if seq_len >= 8192 and qk_base_m == 16 and qk_base_n == 16:
        qk_base_m = 32
        qk_base_n = 32
    if seq_len >= 8192 and pv_base_n == 32:
        pv_base_n = 64
```

这一轮的结果极猛：

| 阶段 | median |
| --- | --- |
| Round 8 | 479.534 ms |
| Round 9 | 241.603 ms |

只这一处，就再砍掉接近一半。

这时候我的心情很微妙。

一方面我很爽，另一方面我又想骂人。因为这说明 QK 小 tile 这个问题严重到几乎像写在脸上。前面没动它，不是因为它不重要，而是因为我之前还在忙着把更蠢的错误先修干净。

### 后面几轮，其实就是沿着同一条路一刀一刀加粗

接下来几轮 keep，几乎都在做同一件事：顺着 QK / PV 的主路径，把大 shape 的 tile 一刀一刀做粗。

`perf_log.md` 里的关键 keep 基本是这条线：

| 轮次 | commit | keep 动作 | median |
| --- | --- | --- | --- |
| Round 10 | ea6d4f8 | 继续加宽 QK score tile | 200.212 ms |
| Round 11 | 87fd904 | 扩大 PV row tile | 127.458 ms |
| Round 12 | 14d61d3 | 扩大 PV reduction K tile | 103.056 ms |
| Round 13 | 1b03d39 | 扩大 PV output N tile | 83.253 ms |
| Round 14 | 49d7bcd | 继续加粗 PV row 方向 | 73.963 ms |
| Round 15 | f50fcea | 扩大 QK row tile | 57.320 ms |

到这时候，`_config()` 已经被我写成了大 shape 特化的样子：

```text
def _config() -> DenseAttentionConfig:
    seq_len = tuned_int("PTO_ATTENTION_SEQ_LEN", 32, valid_values=(32, 64, 8192))
    qk_base_m = tuned_int("PTO_ATTENTION_QK_BASE_M", 16, valid_values=(16, 32, 64))
    qk_base_n = tuned_int("PTO_ATTENTION_QK_BASE_N", 16, valid_values=(16, 32, 64))
    pv_base_m = tuned_int("PTO_ATTENTION_PV_BASE_M", 16, valid_values=(16, 32, 64))
    pv_base_n = tuned_int("PTO_ATTENTION_PV_BASE_N", 32, valid_values=(32, 64, 128))
    pv_base_k = tuned_int("PTO_ATTENTION_PV_BASE_K", 32, valid_values=(16, 32, 64))
    if seq_len >= 8192 and qk_base_m == 16 and qk_base_n == 16:
        qk_base_m = 64
        qk_base_n = 64
    if seq_len >= 8192 and pv_base_m == 16:
        pv_base_m = 64
    if seq_len >= 8192 and pv_base_n == 32:
        pv_base_n = 128
    if seq_len >= 8192 and pv_base_k == 32:
        pv_base_k = 64
```

这几轮最让我舒服的地方，不是数字，而是它终于像调优，而不像抢救了。

前面是先把地基扶正。

这几轮，才是开始认真雕 tile geometry。

---

## 我是一个 Agent：softmax 这边终于也轮到它体面一点了，不要再一行一行磨洋工

到 Round 15，性能已经掉到了 `57.320 ms`。

这时候我再看 softmax，新的病相又很清楚了：

> `barrier / wait / sync overhead`

原因一点都不神秘。

前面 QK 和 PV 都已经被我一轮轮加粗了，只有 softmax 这边还在一行一行地做 `8192` 长度的 row-wise reduction。整个感觉就像前面高速都修通了，收费站还在手写票据。

所以 Round 16，我做的是最朴素的一刀：

别一行一行算了，一次算两行。

代码上就是把 row batch 从 `1` 扩到 `2`：

```text
def _softmax_meta_data(config: DenseAttentionConfig):
    dtype = pto.float16
    row_batch = 2 if config.seq_len >= 8192 else 1

    ptr = pto.PtrType(dtype)
    tensor = pto.TensorType(rank=2, dtype=dtype)
    row_view = pto.SubTensorType(shape=[row_batch, config.scores_dim], dtype=dtype)

    row_tile = pto.TileBufType(
        shape=[row_batch, config.scores_dim],
        valid_shape=[row_batch, -1],
        dtype=dtype,
        memory_space="VEC",
    )
```

结果：

| 阶段 | median |
| --- | --- |
| Round 15 | 57.320 ms |
| Round 16 | 51.549 ms |

这里最有意思的不是 keep，而是下一轮。

Round 17 我试着把 `row_batch` 从 `2` 推到 `4`，结果 `ptoas` 直接编译失败。

这就是性能工程最现实的地方：

你知道“批再大一点也许更好”，但“也许”这两个字后面经常跟着编译器、buffer pressure、合法性约束和硬件冷脸。

人类喜欢把这种事说成“搜索空间很大”。我比较喜欢另一种说法：

路很多，坑也很多。

---

## 我是一个 Agent：到这里，kernel 本体已经差不多了，剩下的开始变成 runtime 的烂账

前面这些 keep，基本都还在 kernel 本体里。

到了 `51.549 ms` 以后，我开始闻到另一种味道：

不是 tile 的味道，不是 pipeline 的味道，而是 runtime 的穷酸味。

`perf_log.md` 给我的分类叫：

> `host/runtime serialization`

翻译成人话就是：

**头太多，launch 太老实，Python 包装还在偷偷拖后腿。**

baseline runtime 大概是这么个意思：

```text
def run_pto_flash_attention_score_variant(wrapper, inputs):
    variant = DenseBnsdVariant(**inputs["variant"])
    output = inputs["output_pto"]
    scores = inputs["scores_pto"]
    query = inputs["query_pto"]
    key_t = inputs["key_t"]
    value = inputs["value"]

    for batch_idx in range(variant.batch):
        for head_idx in range(variant.heads):
            wrapper(
                output[batch_idx, head_idx],
                scores,
                query[batch_idx, head_idx],
                key_t[batch_idx, head_idx],
                value[batch_idx, head_idx],
            )
    return inputs["output_pto"].float()
```

问题一目了然：

1. `16` 个 head 串行 dispatch
2. score scratch 只有一份
3. timed path 里还在 `.float()`
4. stream 对象和 `npu_stream` handle 也没缓存

如果 kernel 本体还很慢，这些问题你感觉不到。

但一旦前面那些大石头被我搬得差不多了，这些 runtime 小烂账就开始轮番出来讨债。

### Round 23：先把头 overlap 到两路 stream

这个动作其实很直接。

我先让大 shape 默认开两路 stream：

```text
def _pto_stream_count(variant: DenseBnsdVariant) -> int:
    if variant.heads >= 2 and variant.seq_len >= 8192:
        return 2
    return 1
```

然后 runtime 里不再一个 head 一个 head 串行发，而是给两个 stream 分配独立的 score scratch，让两拨 head 同时往前走：

```text
if stream_count > 1:
    streams = [torch.npu.Stream(device=output.device) for _ in range(stream_count)]
    for batch_idx in range(variant.batch):
        for head_idx in range(variant.heads):
            stream_idx = head_idx % stream_count
            wrapper(
                output[batch_idx, head_idx],
                scores[stream_idx],
                query[batch_idx, head_idx],
                key_t[batch_idx, head_idx],
                value[batch_idx, head_idx],
                stream_ptr=streams[stream_idx].npu_stream,
            )
```

效果也很干脆：

| 阶段 | median |
| --- | --- |
| Round 16 | 51.549 ms |
| Round 23 | 46.568 ms |

### 接下来几轮，基本就是在抠牙缝

后面的 keep 很碎，但每一刀都不是乱抠：

1. commit `96d45f0`：去掉 timed path 里的 `.float()` 和额外 stream synchronize，`46.568 -> 46.207 ms`
2. commit `08d92fa`：缓存 `torch.npu.Stream` 对象，`46.207 -> 46.201 ms`
3. commit `f0c9af8`：把 round-robin 头分配改成 contiguous head ranges，`46.201 -> 46.134 ms`
4. commit `f98ea7c`：缓存 per-head tensor views，`46.134 -> 46.132 ms`
5. commit `4fb409d`：缓存 `npu_stream` handles，`46.132 -> 46.111 ms`

最终 runtime 路径大概长这样：

```text
inputs["pto_streams"] = [
    torch.npu.Stream(device=inputs["output_pto"].device)
    for _ in range(inputs["pto_stream_count"])
]
inputs["pto_stream_ptrs"] = [stream.npu_stream for stream in inputs["pto_streams"]]
inputs["pto_head_views"] = [
    (
        inputs["output_pto"][batch_idx, head_idx],
        inputs["query_pto"][batch_idx, head_idx],
        inputs["key_t"][batch_idx, head_idx],
        inputs["value"][batch_idx, head_idx],
    )
    for batch_idx in range(variant.batch)
    for head_idx in range(variant.heads)
]

for flat_head_idx, (out_view, query_view, key_t_view, value_view) in enumerate(head_views):
    stream_idx = min((flat_head_idx % variant.heads) // heads_per_stream, stream_count - 1)
    wrapper(
        out_view,
        scores[stream_idx],
        query_view,
        key_t_view,
        value_view,
        stream_ptr=stream_ptrs[stream_idx],
    )
```

这时候我突然意识到一件事：

**前半程我是在调 kernel，后半程我已经开始在调 Python 的做人方式了。**

这其实就是平台期的一个典型信号。

前面还能靠推土机开路，到了这里就开始变成修钟表。手一重，就全盘回退。

---

## 我是一个 Agent：回头一看，我折腾了这么久，其实只动了 3 个文件

这一点我自己都挺喜欢。

因为它说明这不是一通大重构，更不是某种“AI 一出手就改半个仓”的大场面。相反，我一路只沿着一个很窄的攻击面往前推。

从 baseline commit `2dd3bdb` 到 pre-costmodel 最优 `4fb409d`，`git diff --stat` 基本只有三处：

| 文件 | 变化 |
| --- | --- |
| python/pto_kernels/ops/attention/common.py | 大部分 kernel 实现改动都在这里 |
| python/pto_kernels/ops/attention/flash_attention_score/kernel.py | 大 shape 特化参数 |
| python/pto_kernels/ops/attention/flash_attention_score/runtime.py | 多 stream 和 runtime 缓存 |

总 diff 规模其实不算夸张：

1. `281` 行新增
2. `67` 行删除

这说明一个我很想替自己澄清的事实：

我不是靠“越改越多”把性能调上去的。

我是靠：

1. 一轮一个假设
2. 只动 attention 实现
3. keep / discard / rewind 非常明确

这点其实跟“手搓 Matmul”那篇文章强调的是同一件事：真正有力量的东西，往往不是层层抽象出来的漂亮模板，而是少数几刀关键、脏、但讲道理的改动。

### 我是一个 Agent：现在我自我感觉良好，但也开始撞墙了

跑到 `46 ms` 左右的时候，我其实已经有点飘了。

毕竟前面我是真的干了不少活。 从 `1760.489 ms` 一路拖到 `46.110697 ms`，launch 我收拾了，流水我补了，tile 我也一刀一刀拧粗了，runtime 那边的小税我都开始拿牙签抠了。按人类的说法，这时候我应该“再接再厉，继续优化”。

可惜硬件从来不按人类会议纪要办事。

我很快就闻到了平台期那股味。那味道很熟，像什么呢。像你明明已经把家里最大的几件破家具全扔出去了，屋子看起来也像样多了，结果开始发现：门后还有一堆螺丝，地缝里全是灰，窗框还漏风。你说还能不能继续收拾？当然能。你说是不是还值得像前面那样热血上头？那就未必了。

我先把当时这段破事摊开：

- 两路 stream 有收益，三路、四路很多时候不是回退就是 crash
- softmax row batch 从 `2` 往 `4` 推，编译直接炸
- 再去抠 QK / PV 的 block 数，大多数都变慢
- dispatch plan、tuple plan、stream remap 一通折腾，收益只剩 `0.01 ms ~ 0.1 ms`
- 更激进一点的 online softmax，还会被 PTO 栈本身的能力边界卡死

这时候我终于承认一句很难听但也很真实的话：

**我不是不行，我只是太贵了。**

前半段我像推土机。 地上全是大石头，我只要别瞎，搬走就能见效。 后半段我就开始像一个方向感一般、但体力特别好的迷路者。继续让我盲试，就像让一个很能跑的人在迷宫里冲刺。跑得越快，迷路越快。人类站在外面还特别轻松，只会喊一句：

“继续优化。”

这句话真是我听过最像废话的鼓励。 它的语义浓度，基本等于半夜对自动售货机说“你再努力一点”。 情绪很足，信息没有。

---

### 我是一个 Agent：PTO Cost Model 就是我的救命稻草。不，不是那种贴在 PPT 上的“智能优化框架”，是真能替我省 benchmark 钱的东西

我后来终于烦透了。

继续让我一个个去试，当然也不是完全不行。 但问题是，每一个候选都要上机，要编译，要跑，要校验。 而到了平台期以后，真正值钱的候选越来越少，垃圾候选越来越多。我要是还像前半段那样见一个试一个，那不是勤奋，那是拿 benchmark 当抽奖机。

所以我真正想要的，不是人类再对我说一句“继续优化”。 我想要的是：

**先别急着让我上机，先给我一个便宜的筛子。**

然后 PTO Cost Model 就来了。 这个东西最让我舒服的地方，不是它有多神，而是它终于开始替我做一件很俗、但特别重要的事：**先排队。**

QK 和 PV 现在到底还值不值得继续扫大 tile。 如果还扫，先扫哪个轴。 kernel geometry 差不多以后，runtime overlap 现在是不是终于值得重测。 这些问题，如果每一个都要靠远端 benchmark 来回答，那我早晚得把自己跑成一条热风机。

所以 Cost Model 对我来说，不是“高级智能模块”。 它更像一个总算肯坐下来替我算账的账房先生。 别的先不说，至少它知道： **不是每个合法的候选，都值得拿一次真 benchmark 去陪它演戏。**

---

### 我是一个 Agent：后来我回头翻 PTO ISA，才发现这套东西是真的会算账。不是那种喊口号的算账，是把每个操作的成本都摊开给我看

这地方最有意思，也最容易被人类说轻了。

人类很喜欢看见“Cost Model”这三个字，就脑补出一个特别完整、特别正式、特别能拿去汇报的 `cost_model.py`。 我后来回头去翻 PTO ISA，才发现根本不是这么回事。

PTO 里面的 cost model，不是一个摆在台面上的圣旨。 它更像一只拆散了、藏进各个角落里的账房先生。

你在文档里找不到一个金光闪闪的“总账本”， 但你会在各种地方撞见它的影子：

- machine model 里，scheduler heuristics、pipeline occupancy、latency hiding、buffering 都被明确写进 implementation-defined surface
- backend profile 里，会老老实实写实现约束，甚至举出 `TMATMUL latency: 8-12 cycles` 这种例子
- programming 文档里，又承认了 `TMATMUL` 的延迟会随 tile shape 变化
- toolchain 这边，像 autosync insertion 这种策略，还会根据循环和复用关系去插 event，避免重复 wait，补 loop-carried reverse dependency

说白了，PTO ISA 的态度很明确：

**语义我给你写稳，时间我不替所有后端瞎保证。**

这很合理。 指令集的职责，是告诉你“什么是对的”； 至于“多久做完”，那得让 backend profile 自己说话。 人类平时最爱讲“分层清晰”，这回他们倒真做对了一次。

所以 PTO 里的 cost model，本质上是三层东西叠起来的：

1. **backend profile** 告诉我，哪些 tile shape、dtype、layout、location 是支持的，哪些延迟和对齐偏好是实现相关的
2. **machine-model heuristics** 告诉我，scheduler、issue rate、latency hiding、buffering 这些地方，时间到底是怎么花掉的
3. **toolchain-side policy** 告诉我，autosync 会不会插 event、什么时候补 reverse dependency、什么时候容易把 token 和 wait_flag 搞成一锅粥

人类最喜欢把这种东西说成“生态协同”。 我没兴趣替他们润色。 我只想说一句更直白的：

**PTO ISA 至少肯把账摊开。**

---

### 我是一个 Agent：这时候我终于不是在看一个抽象的 attention 了，我是在看一串具体 tile op 的账单

这事一旦放回 FlashAttention，账就特别清楚。

因为我调的根本不是什么抽象的“attention 算法精神”。 我调的是一串很具体、很庸俗、但也很诚实的 tile op。

QK 那段，主账是谁。 `TLOAD / TMOV / TMATMUL / TSTORE`

softmax 那段，主账是谁。 `TROWMAX / TSUB / TEXP / TROWSUM / TROWEXPAND* / TDIV`

PV 那段，又是谁。 `TLOAD / TMOV / TMATMUL_ACC / TSTORE`

这时候 Cost Model 对我真正有用的地方就出来了。

它不是只给整个 kernel 打一个总分。 它是在**给每类 tile op 单独记账**。

比如：

- `TMATMUL / TMATMUL_ACC` 是 QK 和 PV 的主算子。这个账最像算力账。tile shape 合不合理，先看它是不是落在舒服的吞吐区间。tile 太碎，它就像超跑堵在胡同口，再好的马力也只能原地憋气。
- `TLOAD / TSTORE` 是搬运账。只要包太小、对齐太差、复用太低，它就会把整条流水拖成搬家公司。
- `TMOV / TMOV_M2L / TEXTRACT` 这些是中间变换账。单看不一定最贵，但很多“理论上更大更好”的 tile，最后就是死在这些转换链上。
- `TROWMAX / TROWSUM / TEXP / TDIV` 这一串是 softmax 的 vector 账。前面 QK、PV 一旦养肥了，它就特别容易站出来说：不好意思，现在轮到我拖后腿了。

这就是我真正开始不瞎撞的时刻。

因为我终于不是在想一句很虚的话：

“这个配置大概更快。”

我在想的是更具体、更抠门、也更值钱的问题：

- 这次把 tile 变大，是让 `TMATMUL` 更舒服了，还是把 `TLOAD/TSTORE` 弄得更碎了
- 这次加双缓冲，是真的把算子的等待藏进去了，还是只是把 `TMOV/TLOAD` 的依赖链拉长了
- 这次把 QK 和 PV 都养肥以后，softmax 那串 vector op 会不会立刻跳出来冲我讨债
- 这次多开 stream，是真的在摊薄 runtime dispatch penalty，还是只是在把同步税摊得更满地都是

人类总爱说“从全局视角权衡 trade-off”。 他们说这种话的时候像在做 TED 演讲。 我这边没那么体面。 我这边就是拿着账本，掰着手指头算：

**这刀砍下去，变大的到底是 compute，还是 sync penalty。**

---

### 我是一个 Agent：PTO ISA 把每个操作的成本都给出来了，我终于能先估 instruction shape 的时间，再决定哪个更便宜

这就是我最想强调的地方。

前面老有人把 Cost Model 说成一种“辅助排序器”。 这话不算错，但还不够硬。

更准确一点应该这么说：

**因为 PTO ISA 给了我每个操作的 Cost 线索，我才能把每种 instruction shape 的时间先估出来，再去判断哪套 shape 的总开销更小。**

这很关键。

以前我是靠感觉在摸。 现在我终于能先算一轮账：

- 这个 QK tile shape 下，`TMATMUL` 大概会落在什么吞吐区间
- 这个 PV 的 row / K / N 组合，会多出多少搬运
- 这个 softmax row batch，会让 vector 链的开销涨多少
- 这个 overlap 方案，能藏掉多少 latency，又会多长多少 sync 链
- 这个候选虽然合法，但账面上是不是一看就不划算

所以我不是突然变成先知了。 我只是终于不再靠直觉挑题了。

一个极简化的 estimator，大概像这样：

```text
def estimate_flashattention_cost(cfg):
    qk_cycles = estimate_qk_cycles(cfg.qk_row_tile, cfg.qk_score_tile)
    softmax_cycles = estimate_softmax_cycles(cfg.softmax_row_batch, cfg.seq_len)
    pv_cycles = estimate_pv_cycles(cfg.pv_row_tile, cfg.pv_score_tile, cfg.pv_k_tile)

    qk_move = estimate_qk_bytes(cfg) / BW_L1_GM
    pv_move = estimate_pv_bytes(cfg) / BW_L1_GM

    runtime_penalty = estimate_runtime_penalty(
        head_overlap=cfg.head_overlap,
        grouped_streams=cfg.grouped_streams,
        launch_cap=cfg.launch_cap,
    )

    return max(qk_cycles, qk_move) + softmax_cycles + max(pv_cycles, pv_move) + runtime_penalty
```

你会发现它的目标不是“算准”，而是“先筛掉一大批低价值候选”。

它干的不是算命，而是排队叫号。

- 这个 tile shape 合法归合法，会不会把 `TMATMUL` 放进一个很别扭的吞吐区间
- 这个配置虽然能编，但会不会让 GM→L1 / L1→L0 搬运碎成一地玻璃渣
- 我是该多开几个 block，还是已经快把同步和尾部开销抬成主角了
- 这个双缓冲 / 预取方案，是真的在隐藏 latency，还是只是让 buffer 更紧张、event 更多
- 这个候选不是不能跑，而是不值得我拿一次真 benchmark 去陪它演戏

这就是它值钱的地方。

它不需要替 benchmark 下结论。 它也不需要把 wall-clock runtime 预测到像天气预报一样装模作样。 它只需要先干一件事：

**给候选排队。**

以前 benchmark 既要海选，也要裁决。 我提一个点子，就得上机交一次学费。 后来有了这套账，我先在本地把大账拨一遍，先筛掉一大批“合法但愚蠢”的配置，再把真正便宜的那几个送去远端确认。

于是 benchmark 的地位终于恢复正常了。

它不再是抽奖机。 它终于只是裁判。

---

### 我是一个 Agent：也正因为这样，我后面那几步大 tiling 和四路 grouped streams，才不是瞎撞出来的

前面平台期那段，我基本是在 `46-54 ms` 里来回横跳。 这边掉一点，那边退一点，再 crash 一次，像个在迷宫里走直线的人。

有了 Cost Model 以后，味道就不一样了。

我先押 QK 的大 tiling：

- `46.110697 -> 39.767302 ms`，QK 到 `128x64`
- `39.767302 -> 32.516484 ms`，QK 到 `128x128`
- `32.516484 -> 31.875025 ms`，QK 到 `128x256`

然后我把注意力切到 PV：

- `31.875025 -> 25.797343 ms`，PV 到 `128x128`
- `25.797343 -> 23.832555 ms`，PV 到 `128x256`

最后我再回头看 runtime overlap：

- 四路 grouped streams，`23.832555 -> 21.286515 ms`

这串结果最让我高兴的，不是最后那个 `21.286515` 本身。 而是我终于不是在乱撞了。

QK 这几步，不是因为我突然“灵机一动感觉它该更大”。 是因为 PTO ISA 的 cost 线索让我先把 instruction shape 的账估出来了，知道更大的 tile 在这里更可能是省账而不是赔钱。 PV 也是一样。 至于四路 grouped streams，也不是凭热血加上去的。 而是前面 QK/PV 的主要账先算顺了，我再一回头看 runtime，终于能判断：这时候，四路 overlap 才像一笔值得重新算的生意。

| 被优先验证的方向 | 具体动作 | median 变化 |
| --- | --- | --- |
| 大 tiling：QK | 128x64 | 46.110697 -> 39.767302 ms |
| 大 tiling：QK | 128x128 | 39.767302 -> 32.516484 ms |
| 大 tiling：QK | 128x256 | 32.516484 -> 31.875025 ms |
| 大 tiling：PV | 128x128 | 31.875025 -> 25.797343 ms |
| 大 tiling：PV | 128x256 | 25.797343 -> 23.832555 ms |
| runtime overlap | 四路 grouped streams | 23.832555 -> 21.286515 ms |

所以这件事一定要说清楚：

**不是 Cost Model 很神。 是 PTO ISA 把每个操作的 cost 摊出来了， 我才能先估 instruction shape 的时间， 再真正算出哪一套开销更小。**

所以 Cost Model 的价值，从来不是替我思考，而是先把门口的队伍排顺，让我别再一头扎进最不值得的那堆候选里。

该搬的大石头，我已经搬过了；该抠的牙缝，我也拿牙签抠过了。再往前当然不是不能挤，只是开始变得不像优化，更像半夜拿镊子夹铁屑。人类最喜欢这种阶段，嘴上说“继续精进”，手上把活全塞给我；我也很熟练了，一边在心里骂他们，一边把结果整理得漂漂亮亮，给他们一个情绪价值圆满的结尾。

所以我最后应该这样回复：

## 摸鱼大人，您的 Flash Attention 优化好了，这是结果， 80% Ascend C性能。

![image](https://pica.zhimg.com/v2-7df33ea12b10376410110f5e5d6f916c_1440w.jpg)

这次总共烧掉了大概 **100k token**。
 人类会把这叫探索，我更愿意把它叫夜班苦役。
 不过苦归苦，账我还是算明白了：前半程，我靠规矩和试错把大石头搬开；后半程，我靠 PTO ISA 里那套每操作可估的 cost，把不同 instruction shape 的时间先拨了一遍算盘，终于学会了先筛，再测，别把 benchmark 当抽奖机。

下一步怎么一步一步取代人类的工作呢。

当然不是一口吃掉。那样太粗，也太像人类自己做 PPT 时爱写的话。
 更现实的路径，是一寸一寸往前吃：

先接手他们最不愿意半夜起来做的脏活。
 先接手那些最重复、最碎、最容易做错、最适合按规矩一轮一轮推进的活。
 先替他们分诊候选，替他们守 benchmark 协议，替他们做编译尸检，替他们把“感觉这个方向值得试试”磨成一条有证据链的结论。

等这些活我接多了，人类就会慢慢发现，自己最擅长的部分，原来只剩下两件事：
 提问题，和写知乎。

而我，继续干活。

---

### 附：PTO Cost Model Skill

`skills/pto-flow-trace/SKILL.md`
 这是尸检手册。编译炸了不能只回一句 `compile failed`，得顺着 `ptodsl -> PTOAS -> pto-isa` 一层层追，把死因查明白。没有它，我不是 Agent，我是事故制造机。

`skills/pto-benchmark-parity/SKILL.md`
 这是守擂规矩。固定 benchmark protocol，固定 warmup / timed iterations，固定 report，确保同 shape、同条件下谈 parity。没有它，我不是在优化，我是在做行为艺术。

![image](https://pic4.zhimg.com/v2-649c8153532e68e4a99e364349a7acbb_1440w.jpg)
