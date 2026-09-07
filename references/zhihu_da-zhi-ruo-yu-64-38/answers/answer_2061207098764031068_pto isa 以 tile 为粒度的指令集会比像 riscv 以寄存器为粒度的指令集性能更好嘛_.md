---
type: "answer"
id: "2061207098764031068"
title: "pto isa 以 tile 为粒度的指令集会比像 riscv 以寄存器为粒度的指令集性能更好嘛？"
author: "乱序摸鱼"
created: "2026-07-16 21:54:27+0800"
updated: "2026-07-16 21:54:27+0800"
source_url: "https://www.zhihu.com/question/2060745202143432920/answer/2061207098764031068"
content_need_truncated_in_detail: "False"
question_id: "2060745202143432920"
---

# pto isa 以 tile 为粒度的指令集会比像 riscv 以寄存器为粒度的指令集性能更好嘛？

- 类型：回答
- 问题：pto isa 以 tile 为粒度的指令集会比像 riscv 以寄存器为粒度的指令集性能更好嘛？
- 原文：[知乎回答](https://www.zhihu.com/question/2060745202143432920/answer/2061207098764031068)

感觉像是菊厂同学问的问题，正好借这个问题把PTO ISA指令集设计理念系统性讲一下。

Tile 是指令集对软件暴露的架构粒度，却不必成为硬件内部唯一的数据准备和执行粒度，因此一条 PTO 指令操作一个 Tile，并不意味着硬件必须等几千字节的数据全部到齐，再整整齐齐地拍一张全家福，随后才允许 Cube 或 Vector 单元开始工作；只要微架构愿意增加分块状态跟踪、部分结果转发和内部流水，一个 Tile 完全可以被拆成若干 block、slice 或 beat，当其中一部分数据准备完成以后，执行单元就可以开始消费，而尚未准备好的部分继续由 Load 单元或前级计算单元在后台生产。

反过来也一样，RVV 在 ISA 中使用向量寄存器，并不意味着依赖指令天然就能在第一个元素到达时启动，因为这种能力依赖的不是助记符里写了 Vector 还是 Tile，而是微架构是否实现了 vector chaining、分段唤醒、寄存器 bank 管理、部分写回和生产者到消费者的旁路网络；如果这些机制没有实现，那么一条 RVV 指令同样可能要等整个向量寄存器 ready 才能启动，如果这些机制实现得足够好，那么 PTO ISA 也同样可以在一个 Tile 内部进行链式执行。

### PTO ISA 对标的已经不是 PTX

经过半年左右的设计和验证，PTO ISA 已经逐步演进成一套相对完备的 NPU 物理指令集，它现在对标的不再是 PTX 这种仍然需要由驱动和编译器继续翻译的虚拟 ISA，而是 x86 AVX、Arm SVE 和 RISC-V RVV 这类能够被处理器前端直接取指、译码和执行的物理 ISA，因此 PTO ISA 不只是提供一套供编译器调用的高层接口，而是定义了自己的指令编码、架构状态、寄存器语义和依赖关系，使得 NPU 前端能够直接解析 PTO 指令，并把它们调度到 Load、Store、Vector、Cube 和通信单元。

我个人认为，这套指令集设计得还是很漂亮的，因为它没有先造一个通用处理器，再想办法给矩阵乘打一个扩展补丁，而是从 LLM 的核心数据流出发，让矩阵乘、向量运算、归约、广播、量化、反量化、布局变换和数据搬运共享同一套 Tile 抽象，从而使原本分散在不同执行单元、不同寄存器类型和不同软件接口中的操作，可以围绕同一套数据对象组织起来。

在同等工艺、矩阵吞吐和片上存储容量的条件下，基于 PTO ISA 设计的 NPU 有机会在 PPA，也就是性能、功耗和面积上，明显优于用通用 RISC-V 向量核堆出来的方案，因为通用向量核需要使用大量细粒度指令、寄存器项和乱序资源来描述矩阵数据流，而 PTO ISA 可以使用更少的架构指令覆盖更多计算，并让 Tile 的形状、位宽和布局直接匹配 NPU 的物理数据通路。

### Tile 是寄存器，而不是一块临时内存

PTO ISA 的全称是 Parallel Tile Operation Instruction Set Architecture，它是一套围绕 Tile 定义的 SIMD 指令集，其中所谓的 Tile，不只是某段地址连续的存储空间，而是一块同时具有数据类型、逻辑形状、数据布局、有效区域和物理容量的数据对象，并且在 PTO ISA 中，这个数据对象被进一步提升为架构寄存器，因此硬件可以像管理普通寄存器一样，对它进行依赖跟踪、重命名、分配和回收。

Tile 寄存器本身并不是新概念，x86 AMX 定义了八个最大为 4KB 的 Tile 寄存器，Arm SME 也定义了用于矩阵外积和累加的 ZA 存储区，但这些 Tile 更多是原有标量和向量架构旁边增加的矩阵扩展，老房子没有改，只是在院子里搭了一间矩阵乘健身房；PTO ISA 的做法更加激进，因为它把 Tile 放到了架构状态的核心位置，在保留三十二个标量 GPR 的同时，不再继续维护一套传统浮点寄存器，而是定义六十四个架构 Tile 寄存器，因此每个 Tile 寄存器 ID 需要六个比特编码，而每一条 PTO 指令所描述的，也都是这些 Tile 寄存器之间的输入、输出和变换。

这些 Tile 可以承载整数、FP64、FP32、BF16、FP16、FP8、INT8 和 INT4 等不同类型的数据，所以它不是“专门给矩阵乘准备的一块大数组”，而是整个 NPU 数据通路共同使用的基本操作数；当矩阵乘产生高精度累加结果，量化把浮点数据压缩成低位宽格式，归约把二维 Tile 压缩成一行或一列，广播再把一行或一列扩展回二维 Tile 时，变化的只是 Tile 的数据类型、形状和容量，而不是突然切换到另一套完全不同的寄存器体系。

传统 SIMD 编程之所以经常不如 SIMT 舒服，真正麻烦的地方并不是加法或者乘法本身，而是数据位宽和循环迭代被绑定到了固定宽度的寄存器上；当编译器需要把多次循环迭代的数据塞进 256bit 或者512bit 的 SIMD 寄存器时，只要输入和输出精度相同，事情还算规整，但当 FP32 被量化成 FP16，或者 FP16 被压缩成 INT8，原来占满寄存器的数据突然只需要一半甚至四分之一的空间，编译器就不得不考虑 pack、unpack、interleave 和 shuffle，最后算术指令可能只需要一个周期，整理数据却像搬家一样忙了半天。

SIMT 看起来更舒服，是因为程序员表达的是每个线程处理一个元素，至于线程如何组合由硬件负责，但当每个 32bit lane 最终只产生一个 16bit 或者8bit 结果时，寄存器中没有使用的部分仍然存在，只不过 GPU 通常选择用更多寄存器把这个问题盖住；如果后续还要对这些数据进行归约，再把结果广播回每个元素，那么原本简单的 per-lane 表达也会出现额外的线程通信和数据重组，因此 SIMD 和 SIMT 并不是一个聪明、一个笨，它们只是把复杂度放在了不同的位置，天下没有免费的午餐，最多只是有人先替你买了单。

### 可变大小 Tile 把数据位宽问题交给硬件

PTO ISA 在这里稍微偷了一个懒，既然软件和编译器很难把不同位宽、不同形状的数据高效塞进同一种固定宽度的寄存器，那么就不再要求所有寄存器一样大，而是把物理容量分配和空间整理交给微架构，通过寄存器重命名完成动态管理。

一个 PTO Tile 寄存器既不是固定 256bit 或者512bit 的传统 SIMD 寄存器，也不是每个线程固定 32bit 的 SIMT GPR，而是一块大小为 2 的整数次幂的物理存储空间；按照当前 Superscalar NPU 的 Tile 分配设计，其容量可以从 128B 逐步增加到 256B、512B、1KB、2KB、4KB 和 8KB，其中最小的 128B 刚好对应三十二个 lane 乘以 32bit，最大的 8KB 则能够容纳低精度矩阵乘之后的高精度累加分块。

例如：

```text
TADD T0, T1 -> T2<256B>
```

这条指令在产生 T2 时，同时告诉硬件目标 Tile 需要 256B 的物理空间；如果同一条运算需要处理更大的数据，也可以写成：

```text
TADD T0, T1 -> T2<512B>
```

此时，硬件就会为 T2 分配 512B，而不是让所有数据不分高矮胖瘦地穿同一个尺码的公司团建服。

可变大小的 Tile 还使下面这种汇编表达成为可能：

```text
TADD    T0, T1 -> T2<256B>
TADD    T2, T3 -> T4<256B>
TCONCAT T2, T4 -> T5<512B>
```

前两条指令分别产生两个 256B Tile，第三条指令则把它们拼接成一个 512B Tile，这种操作在传统定长 SIMD 或者按线程定宽的 SIMT 体系中并非不能实现，但软件必须显式表达寄存器拼接、数据搬移和布局变化，而在 PTO ISA 中，它可以直接成为寄存器语义的一部分。

![image](data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='1672' height='941'></svg>)

之所以一定要支持不同大小的 Tile，核心原因还是矩阵乘，因为低精度矩阵乘的左右输入和累加输出在物理存储容量上天然不同，例如一个 4bit 矩阵乘可以写成：

```text
TMATMUL
    T0<M×K×4bit>,
    T1<K×N×4bit>
 -> T2<M×N×32bit>
```

输入只有 4bit，累加结果却通常需要 32bit，即使输入和输出的逻辑元素数量接近，物理存储容量也可能相差八倍；如果采用累加形式，原有的高精度 Acc Tile 还需要继续参与下一轮计算：

```text
TMATMUL_ACC
    T0<M×K×4bit>,
    T1<K×N×4bit>,
    T2<M×N×32bit>
 -> T2<M×N×32bit>
```

到了 MXFP4 这类带 block scale 的低精度格式，除了左右两个低精度矩阵，还需要传入左右两侧各自的 scale Tile，因此同一条矩阵指令的几个输入在数据类型、形状和容量上可能完全不同；如果硬件只提供一套定长定宽寄存器，软件就必须提前把这些数据全部排好，理论上当然可以，图灵完备嘛，算盘也能算大模型，问题只是程序员什么时候下班。

PTO ISA 还把 Layout 放进了 Tile 的寄存器语义，因为两个容量同样为 4KB 的 Tile，在物理字节数上虽然完全一致，但一个可能表示 M×K 的 RowMajor 矩阵，另一个可能表示 K×M 的 ColMajor 矩阵，后续执行单元的取数顺序、bank 映射和数据解释都会不同；因此 Tile 不只有 size，还需要表达 shape、dtype、layout、有效行列、padding 和所在的存储层次，这些信息并不是给寄存器贴一张装饰性标签，而是让 Load、Vector、Cube 和数据重排单元能够在同一套数据语义下衔接，从而避免编译器每隔三条指令就重新证明一次这块数据到底是横着放还是竖着放。

### Tile 的架构粒度和执行粒度并不相同

回到最初的问题，如果一个 Tile 有 512B，那么硬件是否必须等到这 512B 数据全部准备好，才能把下一条指令发射出去，取决于微架构如何实现，而不是由 PTO ISA 使用 Tile 作为操作数这件事情直接决定。

从架构状态来看，一个 Tile 是一个寄存器，一条 `TADD` 或者 `TMATMUL` 是一条完整指令，这一层负责定义架构依赖、指令编码、异常恢复和提交语义；进入微架构以后，一个 Tile 可以被拆成多个 block，Scoreboard 或 ready table 也可以按 block 记录数据是否准备完成，例如一个 512B Tile 可以被拆成四个 128B block，当第一个 block 已经由 Load 单元返回，而后面的 block 仍然在访问存储系统时，只要 Vector 或 Cube 单元支持 block 级取数，消费者就可以先处理已经准备好的部分，而不必等整个 Tile 全部完成。

生产者和消费者之间也可以进行部分结果转发，当前级 Vector 指令刚刚产生 Tile 的第一个 block 时，后级指令可以通过旁路网络直接取得这部分结果，后面的 block 则继续按照流水线节拍依次传递；从软件角度看，这仍然是两条存在完整 Tile 依赖的指令，从执行单元角度看，它们已经形成了一条 block 级流水，因此 PTO ISA 完全可以实现与 RVV vector chaining 类似的效果，只是架构层面对外表达的是更大的一块数据。

当然，Tile 内部流水并不是免费的，因为硬件如果希望在整个 Tile 尚未 ready 时提前启动消费者，就需要增加 block 级 ready bitmap、更细粒度的 Scoreboard、分 bank 的物理寄存器文件、部分写回状态、数据旁路以及更加复杂的 replay 和异常恢复机制，所以 PTO ISA 并没有凭空消灭复杂度，而是把一部分复杂度从软件、指令前端和大规模乱序窗口，搬到了物理寄存器管理和后端数据通路。

对于以矩阵乘和规则 Tile 数据流为主的 LLM，这种复杂度搬迁通常是值得的，因为 Tile 内部各个 block 的生产顺序、消费顺序和生命周期相对规则，硬件可以用有限的状态完成流水；如果工作负载充满随机访存、复杂分支和细粒度数据依赖，那么 Tile 的利用率会下降，Tile 内部的 ready 跟踪也可能变得很难看，因此 PTO ISA 的优势并不是无条件成立的，ISA 不是许愿池，往里面扔一个 Tile，PPA 不会自己浮上来。

### Tile 寄存器的重命名，答案藏在 2048 里

可变大小 Tile 还会带来一个非常现实的问题，也就是物理寄存器文件的碎片化，因为今天申请一个 128B Tile，明天申请一个 2KB Tile，后天又申请一个 512B Tile，最后整个寄存器文件可能看起来像搬家以后没有收拾的客厅，空间似乎还有不少，但就是放不下一张完整的桌子。

这个问题不能简单交给软件静态安排，因为编译器无法准确知道运行时每条指令什么时候真正完成，也很难提前预测 Cache Miss、执行冲突、通信延迟和流水线停顿，如果让软件为每个 Tile 预先安排固定物理位置，最后往往只能得到一个理论上很整齐、实际上一跑就变形的方案。

![image](data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='728' height='1092'></svg>)

我们的一个启发来自 2048 这个小游戏，因为不同大小的方块可以通过控制分配顺序和生命周期完成合并，从而避免空间被切得过碎；顺便说一句，2048 的原始作者之一正好是我们读博士期间组里的同学，学术界的缘分就是这样，当年摸鱼玩的游戏，很多年后突然出现在寄存器分配器里。

另外一种启发来自 Clockhands 一类生命周期分配方法，它可以按照寄存器的预期生命周期组织不同的分配队列，使短生命周期、中等生命周期和长生命周期的数据进入不同的 FIFO 或物理区域，例如编译器可以提供如下提示：

```text
TADD    T0, T1 -> T2.Fast<256B>
TADD    T2, T3 -> T4.Medium<256B>
TCONCAT T2, T4 -> T5.Slow<512B>
```

![image](data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='1536' height='1024'></svg>)

编译器不需要精确指定每个 Tile 的物理地址，只需要告诉硬件这份数据大概会存活多久，硬件再根据运行时状态完成真正的物理空间分配和回收，这种设计让编译器提供全局视野，让硬件处理动态变化，避免双方互相指导工作。

### 较大的 Tile 为什么反而可能提高性能

当然可以把 PTO ISA 中的每个 Tile 都固定成 128B，这样 PTO ISA 的执行粒度会非常接近传统向量指令，但当程序被切得非常细，每一小块 Load、Compute、Reduce 和 Expand 都变成独立指令时，为了暴露足够多的并行性，处理器就需要更大的 ROB、Issue Queue、Scoreboard 和重命名表，同时还需要更高的取指、译码和提交带宽，甚至需要通过多线程才能覆盖访存延迟。

![image](data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='1536' height='1024'></svg>)

ROB 中的每一个 entry 都需要付出面积、功耗和时序代价，一个 256-entry ROB 听起来很威风，真正摆到芯片上，每一个 entry 都会提醒你天下没有免费的乱序执行；如果把每条指令处理的数据从 128B 提高到 512B，那么同样数量的 ROB entry 就可能覆盖四倍的数据和计算，Load 可以在更早的时间以更大的粒度发出，Cube 和 Vector 单元也更容易保持忙碌，而前端每取出、译码和重命名一条指令所获得的有效工作量都会增加。

从这个角度看，增大 Tile 粒度相当于在不线性放大 ROB 的情况下扩大了有效指令窗口，它并不是让一条加法指令神奇地算得更快，而是让同样规模的控制电路管理更多的数据和计算，这也是 PTO ISA 有机会获得高 PPA 的核心原因。

但是，Tile 不能无限增大，因为当一个 Tile 被做到 32KB，硬件中能够同时在飞的独立 Tile 数量会下降，生产者与消费者之间的距离会变长，物理寄存器分配压力也会增加，原本希望节省的前端开销可能被 Tile 内部同步和并行度下降重新吃掉；如果沿着“Tile 越大越好”的逻辑继续推演，最终就会得到一条指令执行整个大模型的设计，芯片第二天可以发布，只是大概率跑不起来。

因此，一个合理的 NPU，其最佳 Tile 粒度应该大于 GPU 单线程或者单 warp 的寄存器操作粒度，又小于传统 NPU 那种“一个算子就是一条巨型指令”的粒度，而具体的大小需要随着数据类型、算子形态和执行单元动态变化，因为矩阵乘、Attention、卷积、量化和不规则访存所需要的并行度与数据复用完全不同。

### 所以 PTO ISA 和 RISC-V RVV 谁会更快

如果只比较 ISA 名字，这个问题没有意义，因为一个专门围绕矩阵数据流设计的 PTO NPU 和一个强调通用性的 RISC-V 向量核，本来就不在完全相同的设计点上；真正公平的比较必须固定工艺、频率、矩阵吞吐、片上存储、外部带宽、软件成熟度、功耗和面积约束，然后观察哪一种 ISA 能够用更少的控制状态维持相同的执行单元利用率。

在以矩阵乘为核心，并混合大量量化、归约、广播和数据重排的 LLM 工作负载中，PTO ISA 可以用更少的指令覆盖更大的数据范围，并通过可变大小 Tile 匹配低精度输入、高精度累加和 block scale 的容量差异，同时把 Shape、Layout 和有效区域纳入寄存器语义，因此它比通用 RISC-V 向量 ISA 更有机会做出高 PPA 的 NPU；这个判断并不是因为 Tile 这个词听起来比较高级，而是因为 PTO ISA 把指令表达、寄存器容量、数据布局和矩阵数据流放进了同一个架构模型里。

至于最终能不能真的更快，仍然取决于 Tile 大小是否合理、Tile 内部 chaining 是否有效、物理寄存器分配是否稳定、Load 能否充分提前，以及编译器能否把这些能力真正用起来，因为 ISA 负责把路修宽，微架构和编译器负责别把车开进沟里。

## PTO ISA指令列表

逐元素双目运算包括算术类的 `TADD`、`TSUB`、`TMUL`、`TMAX` 和 `TMIN`，以及逻辑、移位、比较和选择类的 `TAND`、`TOR`、`TXOR`、`TSHL`、`TSHR`、`TCMP` 和 `TSEL`；逐元素单目运算包括 `TABS`、`TNOT`、`TNEG` 和 `TRELU`，逐元素超越函数及复杂算术包括 `TDIV`、`TREM`、`TSQRT`、`TLOG`、`TRECIP`、`TEXP` 和 `TRSQRT`。

![image](data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='1672' height='941'></svg>)

逐元素与标量运算包含 `TADDS`、`TAXPY`、`TSUBS`、`TMULS`、`TDIVS`、`TMINS`、`TMAXS`、`TREMS`、`TANDS`、`TORS`、`TXORS`、`TCMPS`、`TSELS`、`TSHLS` 和 `TSHRS`；

归约运算中，沿列方向归约并为每一行产生一个结果的指令包括 `TROWSUM`、`TROWPROD`、`TROWMAX`、`TROWMIN`、`TROWARGMAX` 和 `TROWARGMIN`，

![image](data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='1672' height='941'></svg>)

沿行方向归约并为每一列产生一个结果的指令则包括 `TCOLSUM`、`TCOLPROD`、`TCOLMAX`、`TCOLMIN`、`TCOLARGMAX` 和 `TCOLARGMIN`。

![image](data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='1672' height='941'></svg>)

广播运算中，按行广播的指令包括 `TROWEXPAND`、`TROWEXPANDADD`、`TROWEXPANDSUB`、`TROWEXPANDMUL`、`TROWEXPANDDIV`、`TROWEXPANDMAX`、`TROWEXPANDMIN` 和 `TROWEXPANDEXPDIF`，

![image](data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='1672' height='941'></svg>)

按列广播的指令包括 `TCOLEXPAND`、`TCOLEXPANDADD`、`TCOLEXPANDSUB`、`TCOLEXPANDMUL`、`TCOLEXPANDDIV`、`TCOLEXPANDMAX`、`TCOLEXPANDMIN` 和 `TCOLEXPANDEXPDIF`。

矩阵运算由矩阵乘矩阵和矩阵乘向量两部分组成，其中前者包含 `TMATMUL`、`TMATMUL_BIAS`、`TMATMUL_ACC` 和 `TMATMUL_MX`，后者包含 `TGEMV`、`TGEMV_BIAS`、`TGEMV_ACC` 和 `TGEMV_MX`；数据搬运与访存指令包括规则访存使用的 `TLOAD`、`TSTORE` 和 `TPREFETCH`，以及不规则访存使用的 `MGATHER` 和 `MSCATTER`。

复杂变换计算覆盖初始化、类型转换、布局变换、排序和部分计算，其中初始化相关指令包括 `TEXPANDS`、`TCI`、`TTRI`、`TRANDOM` 和 `TFILLPAD`，数据类型转换指令包括 `TCVT`、`TQUANT` 和 `TDEQUANT`，布局与数据变换指令包括 `TEXTRACT`、`TINSERT`、`TGATHER`、`TSCATTER`、`TCONCAT`、`TTRANS`、`TIMG2COL`、`TMOV`、`TGATHERB`、`TDEINTERLEAVE`、`TINTERLEAVE` 和 `TRESHAPE`，排序相关指令包括 `TSORT32`、`TMRGSORT` 和 `THISTOGRAM`

Written by ChatGPT Sol 5.6
