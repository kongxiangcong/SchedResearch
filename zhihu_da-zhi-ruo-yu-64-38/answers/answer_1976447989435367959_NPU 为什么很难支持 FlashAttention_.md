---
type: "answer"
id: "1976447989435367959"
title: "NPU 为什么很难支持 FlashAttention?"
author: "乱序摸鱼"
created: "2025-11-25 00:32:01+0800"
updated: "2025-12-05 23:26:19+0800"
source_url: "https://www.zhihu.com/question/1964791844773822881/answer/1976447989435367959"
content_need_truncated_in_detail: "False"
question_id: "1964791844773822881"
---

# NPU 为什么很难支持 FlashAttention?

- 类型：回答
- 问题：NPU 为什么很难支持 FlashAttention?
- 原文：[知乎回答](https://www.zhihu.com/question/1964791844773822881/answer/1976447989435367959)

从目前看来，无论是NPU还是GPGPU，对Flash Attention的支持都是差了那么一点意思。

有些时候我就比较纳闷，为啥业界到现在都没有Flash Attention的硬化加速器?

目前好像只有Systolic Attention这一片文章。

FlashAttention最大的问题就是，**矩阵乘和向量计算的配比是随着SequenceLength动态浮动的**。

FA这个算法简单来说：

Q在Sequence Length维度被切分为TR个Tile，KV切分为TC个Tile。然后TR和TC计算一组矩阵乘。然后对结果进行local max, sum, scaling操作，更新一下全局的max，做subexp最后global sum再拧一下广播给矩阵乘。

FA的内层循环，从矩阵乘到向量计算的数据流，就是一个基本串行的过程，并行度并不高。NPU需要靠多个内层循环并行起来才能把MAC利用率打满。

但是Sequence Length越长，矩阵乘的配比就越大，否则向量的配比就越大。(感谢评论区，更准确的说法应该是切块后的QxK的数据量，这些链条就变得头重脚轻了)

下面这个图实际上就是FA数据流全展开的样子。

但是大模型上，sequence length和用户的输入有关，永远是一个动态值，那么在一个算力配比固定的核内，永远都会遇到矩阵算力不够，或者向量算力不够的窘态。

有些时候最佳的切分算力的方法是把local max和scale切给矩阵去算。那么Vector就去做reduce了。最后的global update，也是需要把多个内层循环迭代汇聚起来，做一个全局的reduce。

面多了加水，水多了加面，我们要么卡在矩阵上，要么卡在向量上。

![image](data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='695' height='536'></svg>)

那么什么样才能是最佳的性能呢？

我们需要动态的调整TileSize，能够让矩阵的计算和向量的计算在计算时间上大体相等，那么我们就可以让矩阵和向量的单元都不那么空闲，这样就可以把矩阵和向量的单元都利用起来。当然这里需要保证矩阵和向量都共享一套buffer，他们之间的通路有随路计算的功能(micro scaling 1/sqrt，on-the-fly max and sum etc)

但是NPU最大的问题就是这个动态调度上，它不能像GPGPU一样，例化的warp个数和输入的problem size相关。

对于华为昇腾来说，PTO框架利用一个CPU来解决动态调度的问题，把NPU的这个短板补齐了。它的原理是Code Specialization, 也就是CPU动态选择了一个预先排布好的NPU流水。

那么GPU就万事大吉了吗？并不是，GPU最大的问题就在Softmax的reduce上。有些时候需要4个warp协作做warp-level的reduce，有些时候需要8个warp做warp-level和thread level的reduce。如果wrap-level的reduce走SM的同步，那么warp同步的开销会非常大，影响总体性能。 本来GPU的SIMT架构做reduce就是一件非常头疼的事情。当然NV的GPU里面增加了SHUFFLE.Bufferfly这样的操作，让SIMT变得更SIMD一点，但也没解决动态的warp level reduce问题。

总而言之，如果你把整个Flash Attention的数据流展开并可视化的话，**它其实就是一个拧来拧去的Dataflow Graph**。这个拧的自由度和sequence length相关，每次图都是变动的，无法固化。

那么有什么架构更适合Flash Attention吗？

感觉也就乱序的OOO Tile-based CPU算更合适了?

链条A: TMA>矩阵乘->随路->向量累加->矩阵乘->TMA

链条B: TMA>矩阵乘->随路->向量累加->矩阵乘->TMA

通过合理的切分，把每一步的执行时间做到差不多，然后去拍流水，利用pipeline并行。

Flash Attention is not a solved problem.
