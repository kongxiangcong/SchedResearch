---
type: "article"
id: "1988565015914107985"
title: "如何用PTO手写极致性能Flash Attention"
author: "乱序摸鱼"
created: "2025-12-29 16:09:56+0800"
updated: "2025-12-29 17:00:59+0800"
source_url: "https://zhuanlan.zhihu.com/p/1988565015914107985"
content_need_truncated_in_detail: "False"
---

# 如何用PTO手写极致性能Flash Attention

- 类型：文章
- 原文：[知乎文章](https://zhuanlan.zhihu.com/p/1988565015914107985)

**PTO (Parallel Tile Operation)**是昇腾CANN设计的一套跨平台高性能的虚拟指令集。

它可以跑在目前你能看到和未来看到的所有昇腾芯片上，也可以跑在CPU上。理论上适配得当的话，也可以跑在其他各种NPU上。

它是有架构约束力的，未来的昇腾芯片，会按照PTO定义的接口设计芯片，确保跨代兼容。(因为我们就是设计芯片的团队，没有中间商赚差价)。

它也可以是高性能的，本文教你如何用PTO Instruction手写一个高性能Flash Attention算子。如果你有昇腾卡，910B的话，照着我说的方法用PTO指令去写，可以写出个**150TFLOPS**的高性能的FA，自己测量一下是不是可以达到。910B已经是我们7年前设计的芯片了，难用是难用，但是有了PTO以后，感觉还行了。

**这个性能大概是用0.95x - 1.0x 的AscendC手写极致性能Kernel的水平，FA MFU在50%左右，但是你使用的代码行数只有AscendC的十分之一。**具体代码请参见：

[PTO-ISA 代码仓](https://link.zhihu.com/?target=https%3A//gitcode.com/cann/pto-isa/)

![image](https://picx.zhimg.com/v2-bd82076d3daacc9202dfcb49f77784a9_1440w.jpg)

## Flash Attention加速的难点

Flash Attention是Transformer架构中核心的算法，也是各个AI芯片军备竞赛的核心算法。听说英伟达的Blackwell B200就是因为FA性能不咋滴，才迅速推出的B300。

如果我们看FA的原始算法，已经是天然的Tile编程了。但是Tri Dao的Tiling，是基于GPU精心调配的。下面我们需要把它改一改，适配到昇腾芯片上。

Tile编程的好处是，控制适中，大小可调。把Tile调整到芯片SRAM的大小后，就天然享受到了片内存储的Locality收益。写一个FA的好的算法，就是如何调整这些Tile的控制流，编排出一套高效的集装箱集散港口。

![image](https://picx.zhimg.com/v2-39c7ad43b661947191c0289215bdda95_1440w.jpg)

![image](https://pic3.zhimg.com/v2-207d19760c1102872e98fd58d8445b06_1440w.jpg)

如上图所示，如果把上图的一个数据块当作规整的集装箱，那么你看到的就是一个一个集装箱在那里运转。你坐在调度中心，去指挥各个部件，把这一套系统运转起来。

![image](https://pic3.zhimg.com/v2-631398f998d2bc6001dbd704e2ed1c78_1440w.jpg)

## Flash Attention PTO初级写法：20%性能写法

如果用PTO指令的代码去写Flash Attention, 小白程序员会写成这个样子：

```cpp
    parallel_for (int b = 0; b < kB; ++b) {
        for (int h = 0; h < kH; ++h) {
            GlobalQ qGlobal(b, h, 0, 0, kH, kS, kD);
            GlobalK kGlobal(b, h, 0, 0, kH, kS, kD);
            GlobalV vGlobal(b, h, 0, 0, kH, kS, kD);
            GlobalO oGlobal(b, h, 0, 0, kH, kS, kD);
            //运入停车场
            TLOAD(qTile, qGlobal);
            TLOAD(kTile, kGlobal);
            TLOAD(vTile, vGlobal);
            TLOAD(oTile, oGlobal);
            //停车场卸货，集装箱拆成小箱子
            TEXRACT(qLeft, qTile);
            TTRANS(ktTile, kTile, kTile);
            TEXRACT(kRight, ktTile);
            //矩阵工厂运算QxK
            TMATMUL(scoresAcc, qLeft, kRight);
            TMOV(scores, scoresAcc);
            //向量工厂运算Softmax和global sum, global max
            TMULS(scores, scores, scale);
            TROWMAX(rowMax, scores, scores);
            TROWEXPANDSUB(scoresCentered, scores, rowMax);
            TEXP(expScores, scoresCentered);
            TROWSUM(rowSum, expScores, expScores);
            TROWEXPANDDIV(probs, expScores, rowSum);
            TMOV(pLeft, probs);
            //矩阵工厂运算PxV
            TMOV(vRight, vTile);
            TMATMUL(outAcc, pLeft, vRight);
            //运出停车场
            TSTORE(oGlobal, outAcc);
        }
    }
```

当然，如果你这样写了后，功能上能够跑通，但是性能会比较差。大概是目标性能的10%吧。为什么性能这么差？原因在与矩阵工厂和向量工厂没有并行起来。

![image](https://pica.zhimg.com/v2-d797b158296c001149e5afebe156e38c_1440w.jpg)

这个链条是一个非常串行的过程。另外芯片的CUBE工厂还比较珍贵，QxK和PxV还需要共享一个工厂，根本没法流水线起来。即使我们上了所谓的SPMD并行(Single-Program-Multiple-Data)，那么性能还是会很差的。这就是为什么我们说，SPMD只是用来保底，没法写出高性能算法的。

![image](https://pic2.zhimg.com/v2-1e2c70c6b3b0029e68f11f57495d48c3_1440w.jpg)

## Flash Attention PTO中级写法：80%性能写法

在910B上，我们有24个CUBE工厂，48个VEC工厂。这些工厂们的集装箱流动和调度效率，决定了我们的最终性能。那么我们怎么把他们调度起来呢？核间流水线并行！

![image](https://picx.zhimg.com/v2-cefc3e2e04d9d673a2e0df3c23091fb5_1440w.jpg)

这样我们在每个工厂那里加一个死循环，让这些工厂流水线起来，流水的中间数据放在910B的巨大的L2 Cache上，伪代码如下：

```text
      //步骤1 矩阵工厂流水线 QxK
      while(1) {
         //可并行
         parallel_for() {
            TLOAD(qTile, qGlobal);
            TLOAD(kTile, kGlobal);
            TLOAD(vTile, vGlobal);
            //停车场卸货，集装箱拆成小箱子
            TEXRACT(qLeft, qTile);
            TTRANS(ktTile, kTile, kTile);
            TEXRACT(kRight, ktTile);
            //矩阵工厂运算QxK
            TMATMUL(scoresAcc, qLeft, kRight);
            TMOV(scores, scoresAcc);
            //把Tile写入巨大的L2 Queue
            TPUSH(stage1, outAcc);
         }
      }
      //步骤2 向量工厂流水线 SOFTMAX
      while(1) {
         //可并行
         parallel_for() {
            //从上一个流水线获取一个Tile
            TPOP(scores, stage2);
            TMULS(scores, scores, scale);
            TROWEXPANDSUB(scoresCentered, scores, rowMax);
            TEXP(expScores, scoresCentered);
            TROWEXPANDDIV(probs, expScores, rowSum);
            //把Tile押入下个流水线
            TPUSH(probs, stage2);
        }
      }

      //步骤3 矩阵工厂流水线 PxV
      while(1) {
         //可并行
         parallel_for() {
            //矩阵工厂运算PxV
            TPOP(vTile, stage2)
            TMOV(vRight, vTile);
            TMATMUL(outAcc, pLeft, vRight);
             //运出停车场
            TSTORE(oGlobal, outAcc);
         }
      }
      //步骤4 向量工厂流水线 Global Update
      while(1) {
         //不可并行，Global Update
         for() {
            TPOP(stage1)
            TLOAD(expScores, globalScores);
            TROWSUM(rowSum, expScores, expScores);
            TROWEXPANDDIV(probs, expScores, rowSum);
            //全局累加
            TSTORE(expScores, globalScores);
        }
      }
```

![image](https://pic3.zhimg.com/v2-fd260124d23db0ce7d07d16725b94b1a_1440w.jpg)

如上所示，我们把Flash Attention分成4个步骤，这四个步骤流动的都是tile。这些tile暂存在910B的巨大L2 Cache里面。每个工厂，源源不断的从自己对应的L2 Cache里面TLOAD进来，进行相同的流程处理。

这个就是我们说的软流水技术（Decoupled Software Pipelining）技术。这个技术的好处就是让每个核处理相同的内容，指令的locality非常好，数据都变成了streaming in和streaming out。

上述讲的是伪代码，具体的代码请看我们的代码仓：[PTO-ISA 代码仓](https://link.zhihu.com/?target=https%3A//gitcode.com/cann/pto-isa/)

FA的代码写在kernels/manual/a2a3/flash_atten里面，欢迎试用。我们把上述四个步骤写在了三个函数里面，

让不同的核流水并行起来。他们之间pto_macro_fa_softmax.cpp, pto_macro_fa_gu.cpp, pto_macro_fa_matmul.cpp三个函数里面。

照着代码仓里面的写法，你可以学习如何把CUBE和VEC写成software pipeline的写法。后续PTO会增加核间同步的模板（SPMD，MPMD，PIPELINE）三种模板供大家比葫芦画瓢。

## Flash Attention PTO高级写法：100%性能写法

当然上面的代码，只能写出峰值性能的80%水平。下一步就是对PTO的代码进行Performance Tunring了。调优的手段在于这几个流水线的load balance。

**性能调优第一法：调旋钮**

![image](https://pic3.zhimg.com/v2-7b957a3b5ca9d87f529b366d97bc0c4a_1440w.jpg)

在PTO指令里面，调整旋钮是经常用的调优手段，也就是定义每个阶段数据的切分规则。

```cpp
//原始Tile，4KB Tile
Tile<Vec, 64, 64, int8_t> a;

//横着切，1KB Tile Array
Tile<Vec, 16, 64, int8_t> a[4];

//纵着切，1KB Tile Array
Tile<Vec, 64, 16, int8_t> a[4];

//全部切，256KB 二维 Tile Array
Tile<Vec, 16, 16, int8_t> a[4][4];
```

通过上述的代码，你可以写出各种奇形怪状的Tile，但是他们一定要对齐，一定要是512字节的2的次幂倍数。这样我们的编译器才不会脑残。

调整旋钮后，重新编译一下，就可以在卡上跑了，效率爆表。

如果你觉得人调起来很复杂，我们用AI Agent调整Tile旋钮，目前也可以跑起来。目前Cursor和Codex都能调的不错。

**性能调优第二法：合适位置加预取**

我们通过PTO performance monitor看到，第一个阶段的矩阵QxK阶段矩阵乘的利用率不高。怀疑是L2 Cache Miss所致。原因在于我们的CUBE速度过快了，SOC无法提前从HBM取数进来。

所以，为了进一步提升性能，我们在第一个阶段，增加一条预取的操作 PTO_PREFETCH。PTO的预取会调用底层芯片的SDMA加速器（Slave DMA），在矩阵乘在算当前Batch的时候，将下一层的矩阵乘Q和V预取进来。

这样终于把HBM的带宽给打满了，性能才到了100%。

这个是我们最后实测的性能数据，大家Ascend 910B的卡的同学，可以扒出来这段代码实测一下。

![image](https://pica.zhimg.com/v2-f3182cf2abfcca8c402102bb4d703214_1440w.jpg)

## 总结：PTO可以写出高性能算子吗？

我们从这次实际实测来看，PTO纯粹靠Tile编程，就可以达到Ascend C手写极致性能的效果。但是我们写这段代码，只用了一天的时间，Ascend C手撸汇编需要至少一个月的时间。这就能看出其中的效率差异。

欢迎大家把我们的代码拷贝过去，实现一版更骚气的流水排布出来。

极致的性能在于如何把并行度和局部性发挥出来。Tile编程只是让这个过程变得更容易一些。
