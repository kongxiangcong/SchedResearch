---
type: "answer"
id: "82294489177"
title: "如何看待龙芯对外公开的 LoongArch 指令集？"
author: "乱序摸鱼"
created: "2025-01-19 01:36:16+0800"
updated: "2025-02-07 00:26:54+0800"
source_url: "https://www.zhihu.com/question/414069789/answer/82294489177"
content_need_truncated_in_detail: "False"
question_id: "414069789"
---

# 如何看待龙芯对外公开的 LoongArch 指令集？

- 类型：回答
- 问题：如何看待龙芯对外公开的 LoongArch 指令集？
- 原文：[知乎回答](https://www.zhihu.com/question/414069789/answer/82294489177)

临近过年，正好闲下来写点知乎~

**龙芯LoongArch指令集设计的到底好不好？**

本文从**指令集设计的技术**角度来分析龙芯指令集，指出其设计好的点和设计不好的点。其中龙芯指令集手册可从这里下载：[龙芯指令集手册](https://link.zhihu.com/?target=https%3A//github.com/loongson/LoongArch-Documentation/releases/latest/download/LoongArch-Vol1-v1.00-CN.pdf)

![image](data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='681' height='296'></svg>)

从指令集上，我们就可以看出设计者在面临众多限制下的设计权衡。

指令集的设计没有对和错，只有架构师面临众多变量时，他的选择是什么。

注：狂热的龙芯粉丝请绕路，这是你们胡老师的选择。自己的设计，自己买单哈。

**身正不怕影子斜，要是设计真的好，逻辑讲得通，就不用怕别人指指点点。**

某个同学给我发了个图，貌似是龙芯的吧主？很有自信，在此奉上衷心的祝福，希望LoongArch能够长盛不衰，应对未来50年的变化。

![image](data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='1068' height='326'></svg>)

## 龙芯指令设计特点1：复杂的指令编码格式

所谓指令编码格式，就是CPU在解析一条32bit二进制时，最小可以通过解析几bit，就可以将32bit进行断句，并传递给后级流水线做进一步解析。对于硬件来说，指令的解码格式越少，那么其解码复杂度就越低。

按照龙芯的描述，**LoongArch 有 9 种典型的指令编码格式，**但是在其新增的指令中，并不遵守指令编码格式的规范。从目前的手册来看，LoongArch 基础架构共有 **39 种不同指令的解码格式**。

![image](data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='997' height='1580'></svg>)

龙芯指令集的39种解码格式

复杂的解码格式，最大的问题是在高性能CPU的实现频率上，尤其是在高频8发射-12发射的大核CPU的实现中，我们往往需要进行预解码Pre-Decode或者几级解码才能真正把指令的信息获取出来。指令的解码格式为什么重要，下面展示了一个32bit指令通过6bit解码指令的电路。你可以看到，硬件解码一条指令需要多少级逻辑？

![image](data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='1420' height='1040'></svg>)

现代的CPU，往往是6发射到8发射的超标量处理器。它需要一个时钟周期内，尽可能把N条以上的指令连续解析出来。也就是上面的电路要级联起来，判断指令前后的寄存器依赖。如果解码足够复杂，CPU会引入MicroOP Cache, 将解码后的微码缓存，用来提供足够的解码带宽。

复杂解码格式引入额外的流水线或者带来的时序频率的损失。因此在设计权衡上来说，还不如将这些复杂的指令删除，保留更简单的指令解码格式。这一点，RISC-V的指令编码就是一种非常理想的编码格式了。16bit的Compress扩展除外。RISC-V的C扩展，无疑把简化版本的设计收益又抛弃掉了。

这里一点，高通就想带头把[RISC-V C扩展砍掉](https://link.zhihu.com/?target=https%3A//lists.riscv.org/g/tech-profiles/attachment/297/0/A%2520case%2520to%2520remove%2520the%2520C%2520extension%2520from%2520app%2520profiles%2520-%2520Profiltes%2520TG%252020230929.pdf)。。

![image](data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='1254' height='361'></svg>)

## 龙芯指令设计特点2：Opcode编码放在了指令字高位

龙芯指令集的设计者，选择仅支持小端（Little-endian）字节序，并将指令操作码Opcode放置在32bit的编码高位。这样做的问题是，在取指返回的第一个字节上，CPU无法获取到这个指令的任何信息。CPU必须缓存3个字节后，才能决定这个指令是什么指令。

这样做，完全放弃了16bit编码的任何扩展的可行性。因为CPU解析的第一个字节，无法用于解码后续的16bit的解码。当然，龙芯选择摒弃变长16bit的可能性，换取的是定长RISC指令的取指收益。但是这个收益，又被其复杂的指令编码格式给抵消掉了。

![image](data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='1245' height='696'></svg>)

龙芯的指令操作码，放在了bit 31-18

因此，龙芯指令集的这个设计选择，并不是最优解。

将指令编码限制在32bit以内，最大的问题是编码空间迟早有用完的时候。指令集扩展，如果囊括向量，矩阵，安全加解密等扩展后，32bit编码基本不太够用。

为什么编码空间32bit不够用呢？

举个简单的例子，最近AI比较火，大家喜欢卷新的数据格式。例如龙芯想出一个叫做LongFloat8的这种格式的浮点比较跳转。结果一发现，哦吼，竟然需要超过32bit的编码空间？：

BFEQ.LongFloat8 imm8, label (imm-16)

然后发现编码空间不够，那就不得不拆成了CMP + Branch这种格式。

## 龙芯指令设计特点3：超长的立即数编码，牺牲大量编码空间

可以看出龙芯指令集对**立即数的加载功能**，做出了非常多精巧且高效的设计。例如三条指令:

```text
lu12i.w 将 20 比特立即数 si20 最低位连接上 12 比特 0
lu32i.d 将 20 比特立即数 si20 符号扩展后的数据最低位连接上通用寄存器 rd 中[31:0]位数据
lu52i.d 将 12 比特立即数 si12 符号扩展后的数据最低位连接上通用寄存器 rj 中[51:0]位数据
```

这个设计的精妙之处在于将64bit的立即数，分成了[11:0], [31:12], [51:32], [63:52] 这12bit-20bit-20bit-12bit四个段。这四个段可和其他的指令，例如load/store进行组合，达到非常灵活多变的效果。

同时，龙芯也提供PC-Relative的加载符号的指令扩展，提供PIC的相对索引符号的方法。这个设计的确是现代指令集需要必备的功能。对于二进制特别大的APP来说，PC相对索引的索引效率大幅提升。

```text
pcaddi 将 20 比特立即数 si20 最低位连接上 2 比特 0 之后符号扩展，所得数据加上该指令的 PC
pcaddu12i 将 20 比特立即数 si20 最低位连接上 12 比特 0 之后符号扩展，所得数据加上该指令的 PC
pcaddu18i PCADDU18I 将 20 比特立即数 si20 最低位连接上 18 比特 0 之后符号扩展，所得数据加上该指令的 PC
pcalau12i 将 20 比特立即数 si20 最低位连接上 12 比特 0 之后符号扩展，所得数据加上该指令的 PC
```

![image](data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='1164' height='294'></svg>)

然而，为了支持20bit立即数的加载，LoongArch牺牲了接近1/32的编码空间。我注意到有一条指令ADDU16I.D, 这条指令将16bit的立即数，加一个通用寄存器，写入一个通用寄存器中：

![image](data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='1174' height='64'></svg>)

ADDUI16I.D编码

单单这条指令占用了宝贵的1/64的编码空间！然而它的作用，仅仅是用于加载GOT动态库的符号表，和LDPTR/STPTR组合使用。GOT符号表占整体执行时间能有多少呢？是不是让GOT的符号在L1 DCache上多Hit几次的收益会更大?

另外，所有的跳转指令，占用了13/64的编码空间。龙芯指令集的设计者发现，如果加上浮点的比较跳转，会占用更多更广的编码空间。于是就退而求其次，拆成了浮点比较+跳转的组合。

![image](data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='1171' height='538'></svg>)

**这样做到底值不值得呢？我认为是不值得的**。

对于32bit定长指令集来说，编码空间尤其重要。有人说，现在龙芯的指令集编码空间还剩下不少，还能扩展很多指令。但是我想说的是，如果龙芯想塞进更多指令扩展，它的解码格式就不再是39个了，可能是一百多个。很多空闲的编码空间，并不是为了塞指令，而是故意Reserve来简化编码格式的。因为每种指令的编码是不对称的。

从另外一个角度来说，加载立即数，在现代的CPU处理器上，并不是性能的瓶颈。RISC-V在其论文中做了非常详细的立即数范围评估。动态指令的立即数范围，往往都是具有局部性的，90%都可以编码在9bit范围内。对于这种大二进制，超长范围的跳转，基本都是冷代码，不经常执行。**为了剩下的10%牺牲巨大的编码空间，是得不偿失的**。

![image](data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='1242' height='643'></svg>)

就例如龙芯的ADDU16I.D指令来说，可能有12%的场景下，立即数是在12bit-16bit范围内。使用普通的ADDI无法编码。如果没有ADDU16I.D，CPU多执行几条指令会有性能损失吗？会有损失，但是仅仅在12%的场景下，损失了一点地址计算的时间。它并没有帮助CPU降低load/store的时延。最终的性能损失可能在0.5%左右

## 龙芯指令设计特点4：吸取了RISCV的优点，补齐了RISCV的短板

本人曾经经历过多次魔改RISC-V的相关工作，对RISCV的指令非常了解。

LoongArch大部分的标量指令，约有50%的指令和RISC-V基础指令重合。虽然说标量指令基本都长这样，无非就是add/load/store/branch这些指令。但是，龙芯的指令集，也有点太像RISC-V了。部分场景下，RISCV的设计缺陷，也被“借鉴”来了。

众所周知，RISC-V的指令集的最大缺点就是过于简单。

![image](data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='1353' height='167'></svg>)

这种简单，对于小型的MCU设计来说，可能重要。但是对于大型的通用乱序CPU来说，就有点过于简单，导致自断武功性能过差了。以至于平头哥不得不把这些复杂的指令再加回来。

举几个例子，RISC-V的**SLT (Set less than)**指令，就是一种简化的Compare指令。龙芯看起来完整的复制过来：

![image](data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='1254' height='836'></svg>)

指令集上，没必要在这里过于省空间，既然有Set Less Than, 那么Set Greater Than, Set Greater and Equal Than, Set Bitwise And etc这些常用的扩展为什么不加上去呢？

第二个例子，**RISCV的Load Link/Store Conditional指令**，分64bit和32bit宽度，龙芯直接借鉴过来，并且给这四条指令14bit的offset。

![image](data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='1156' height='170'></svg>)

其实，RISCV为了节省硬件复杂度，刻意省去了8bit, 16bit的原子操作，对于龙芯来说，没必要这么省吧？给原子操作增加offset，其实还不如给原子操作增加位宽。

第三个例子，**RISCV的LUI Load Upper Immediate指令和AUIPC add upper immediate to PC令**，这个设计有好有坏，被龙芯完整借鉴过来了。

这个设计的最大问题是，强行的把symbol按照高20bit，低12bit进行切分后，会对编译器的链接器复杂度造成较高的负担。让编译器复杂了以后，最大的问题就是编译器吐出来的代码，并不是最优的。

## TLDR; 龙芯指令集设计的到底如何？

分析了一大波以后，LoongArch指令集设计得到底如何呢？

我大体的感受是，**这个指令集是一种缝合怪**，MIPS和RISC-V的缝合版，另外加上了X86的基因

![image](data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='736' height='575'></svg>)

**缝合指令集**，作为一种大杂烩指令集，依然可以发挥其独特的优势。只是对编译器提出来更高的要求。要把各种优势都发挥出来，编译器需要把龙芯缝合来的技术点都要发挥出来。因此，在不同场合，很多龙芯的粉丝会针对编译器的不同扩展是否开启，跑分是否不同，引入了很多争执。

大杂烩指令集，号称300多条指令，但是因为编译器的适配问题，**往往经常使用的，就RISCV定义的那30条指令左右**。并不是指令越多越好，指令越多，软件，binutils，CPU指令验证的复杂度就越大。增加一条指令，在某个特定的场景获得了收益，但是在所有通用场景导致了负收益，这往往是得不偿失的。

另外，LoongArch指令集，在指令编码空间的安排，指令扩展Profile管理，不同硬件的指令集管理，ABI的定义上，展现出较为混乱的设计。这会导致**龙芯LoongArch指令集的根基不稳**。未来如果不断有新的指令加进去后，会导致底层架构的重新设计。对于指令集设计者来说，他最不希望的是指令集再重构一次(例如ARM V7到ARM V8的重构)。

## 对龙芯LoongArch指令集未来演进的建议

所谓的指令集架构，指令编码是次要的，更重要的是计算架构设计。龙芯指令集只是初步在指令编码上重新设计了一套，这样做的收益并不大。收益大的是对未来计算体系结构的设计和扩展。

在系统设计领域，以下才是指令集需要发力的方向：

1. CPU-加速器的接口，VMMA, IOMMU的定义和设计创新
2. Cache一致性，总线，互联的抽象设计，软件封装
3. 新的内存模型，新的Coherency和Consistency的设计实现。新的并行模型。
4. RAS，DFX，PMU等可靠性和可维可测的系统架构设计

然而这些设计，往往才是我们国内同行都不愿意做的事情。系统太复杂，收益不高，吃力不讨好。

但是这些设计，才是最卡我们脖子的领域
