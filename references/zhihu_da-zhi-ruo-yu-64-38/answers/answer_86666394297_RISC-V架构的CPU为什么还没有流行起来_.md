---
type: "answer"
id: "86666394297"
title: "RISC-V架构的CPU为什么还没有流行起来？"
author: "乱序摸鱼"
created: "2025-01-25 11:38:32+0800"
updated: "2025-01-25 11:38:32+0800"
source_url: "https://www.zhihu.com/question/553376531/answer/86666394297"
content_need_truncated_in_detail: "False"
question_id: "553376531"
---

# RISC-V架构的CPU为什么还没有流行起来？

- 类型：回答
- 问题：RISC-V架构的CPU为什么还没有流行起来？
- 原文：[知乎回答](https://www.zhihu.com/question/553376531/answer/86666394297)

答案很简单，因为做一个高性能的RISC-V CPU是赔钱生意。

假如手机厂商投了几个亿，好不容易搞出来个RISC-V CPU, 最后发现性能和ARM核差不多，而且把整个手机生态都重置了。需要投入更多人进来开发软件，岂不是更大的一个钱窟窿？

RISC-V的设计，简单，开放，开源。但它只是拉低了普通玩家做CPU的门槛，各种阿猫阿狗都可以进来骗一骗投资，抄一抄概念。没有一个是真正想给RISC-V社区做贡献的。

我经常会去RISC-V的论坛上划水，发现RISC-V在2024年这些扩展设计，没有一个是国内玩家在参与讨论。也许是因为国内的同学英语不好？

![image](data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='1951' height='1019'></svg>)

RISCV后续的扩展，的确是在补齐之前的设计缺陷。

这尤其体现在RISCV作者Krste Asanovic这个人上。他在性格和能力上，都远远不如Linux的Linus Torvalds那么追求极致，那么技术宅。

![image](data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='460' height='460'></svg>)

Krste Asanovic

RISCV指令集一下子卷进来这么多人，大家提出来各种五花八门的指令扩展，最后整出来一堆碎片来，最后碎了一地。

做指令集，本质上是在做标准。做标准哪能通过民主的方式让大家七嘴八舌呢？

做指令集，反而需要一种中央集权的管理机制。我们都知道，ARM指令集的设计，就是Richard Grisenthwaite这个苏格兰老哥一个人说的算。

其他人，只需要给他提需求，讲痛点即可。过3个月后，R.G就可能从芬兰的冰天雪地那里发你一篇文档，把你的需求满足了。

![image](data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='320' height='320'></svg>)

ARM Fellow R.G.

## RISC-V指令集，能给CPU带来显著性能提升吗

其实，解题的思路也很简单。假如RISC-V指令集能够让其CPU的性能大幅超越ARM竞品，超越苹果M4大核CPU的50%~100%的性能的话，那么故事的逻辑就完全变了。大家肯定投入重金来使用。甚至重置生态都不是个问题。

但是，从现在RISC-V的指令设计来看，它注定只能依靠CPU的微架构设计和工艺演进提升其CPU的竞争力。指令集在性能能发挥的竞争力微乎其微。

因此，对于SiFive这种公司，只能盯着ARM，把核做成6发射，8发射，10发射进一步演进。

更何况，它的指令集设计，并不如ARM V8的水平。想达到ARM CPU相同的水平，还需要烧更多的钱卷微架构设计。

指令集不能设计的过于简单，否则就是一个Research Toy, 就是一个嵌入式场景的领域定制指令集。

**没有经过海量软件操过的指令集，被海量需求整成犬牙交错的指令集，没有迭代个十几个版本的指令集，就不是一款好的指令集**。
