---
type: "article"
id: "2035830474866733912"
title: "pyCircuit：给硬件元编程套上 MLIR 的缰绳"
author: "乱序摸鱼"
created: "2026-05-07 21:18:46+0800"
updated: "2026-05-07 21:55:55+0800"
source_url: "https://zhuanlan.zhihu.com/p/2035830474866733912"
content_need_truncated_in_detail: "False"
---

# pyCircuit：给硬件元编程套上 MLIR 的缰绳

- 类型：文章
- 原文：[知乎文章](https://zhuanlan.zhihu.com/p/2035830474866733912)

## Chisel 让硬件会生成，pyCircuit 想让生成器别裸奔

有人问：**pyCircuit 是不是 Python 版 Chisel？**

我一听这个问题，心里咯噔一下。

这就像问：乌龟是不是带壳的鱼？
都在水里混过，都能扑腾两下，但祖宗不一样，活法也不一样。你非要把它们关一个缸里，也不是不行。只是最后是共生、互食，还是各自在角落里假装没看见对方，就要看生态位了。

![image](https://pic1.zhimg.com/v2-dbd0ff7acf90cccf93b73c1ed1375936_1440w.jpg)

我这个人一贯没有什么鲜明立场。俗称：和稀泥。
Verilog 存在即有理。Chisel 存在即有理。SpinalHDL 存在即有理。CIRCT 存在即有理。pyCircuit 也不是从石头缝里蹦出来的。

但我更关心的不是“谁先进、谁落后”，而是：

**它为什么在这个时候出现？它到底想解决哪一类问题？**

如果只是为了把 Verilog 换一种语法写一遍，那不如洗洗睡。
如果只是为了证明 Python 也能写硬件，那也没多大意思。Python 能干的事太多了，能写网页，能训模型，能爬虫，能画图，能写胶水，能写出一坨 nobody understands 的 generator。光说“用 Python 写硬件”，这句话既不能让电路变快，也不能让时序变好，更不能让 debug 的人少掉几根头发。

所以 pyCircuit 真正值得聊的地方，不在 Python。

而在它想回答一个更麻烦的问题：

**硬件元编程之后，谁来治理生成物？**

---

## 一、Verilog 为什么四十年不死？

先别急着骂 Verilog。

Verilog 这东西，像老小区门口的兰州拉面。装修不新，桌子有点粘，菜单几十年没怎么变，但你真饿了，还是得进去吃一碗。

你说它不好？
确实不好。

你说它不能用？
那就有点不讲武德了。

Verilog 从 1980 年代一路活到今天，不是因为硬件工程师没有想象力，也不是因为全行业都迷恋 `always_ff` 和 `assign`。这个世界没那么多傻子。几十年里，想提高硬件描述抽象层的人一茬又一茬。只是大部分时候，这笔账没算赢。

软件语言的抽象升级，通常是在扩大生产者。

C 之后有 C++，有 Java，有 Python，有 Go，有 Rust。每升一层抽象，可能牺牲一点性能，但换来更多开发者、更快迭代、更大生态。抽象的损耗，常常被硬件进步、编译器优化、业务规模掩盖掉。说到底，无论面向对象，还是面向函数，最后都得面向 money。

硬件不一样。

硬件语言每升一层抽象，首先不是扩大生产者，而是增加一层责任链。

软件错了，可以发版。
芯片错了，可能就是一片硅上的墓志铭。

软件有 bug，凌晨三点回滚。
芯片有 bug，凌晨三点看波形，早上九点开复盘，中午十二点开始讨论谁来背锅。

所以一个新的硬件抽象层要成立，不能只说“我更优雅”。它得证明：

省下的设计成本，是否大于新增工具链成本？
省下的验证成本，是否大于新增语义不确定性？
带来的复用收益，是否大于 debug 和 QoR 风险？
吸引来的新开发者，是否真的能转化为芯片交付能力？

这个等式如果不成立，大家宁可继续抱着 Verilog 这把旧锤子。

旧是旧，至少砸过很多钉子。

所以看硬件语言，不要只看语法。
语法是脸。
工具链是骨头。
验证是内脏。
能不能流片，是命。

---

## 二、Chisel 的价值，不是少写几行 Verilog

所以讨论 Chisel，也不能用“Verilog 五行，Chisel 五十行”这种标准。

如果 Verilog 五行写一个固定电路，Chisel 五十行也写同一个固定电路，那确实像“用 Java 干汇编的活”。不是不能干，只是让人看了想问一句：兄弟，你图什么？

但如果 Chisel 五十行能生成五十种 cache、五十种 issue queue、五十种 NoC 拓扑、五十种流水线配置，那账就完全不一样了。

这时候它不是啰嗦。
它是在搞自动化养殖。

硬件设计里有一个词，DSE：design space exploration。翻译成人话就是：这个设计还没定，先把各种姿势都试一遍。

bank 几个？
lane 几条？
流水几级？
队列多深？
端口几个？
cache 几路？
crossbar 几入几出？
NoC 是 mesh、ring，还是自己发明一个看起来很优雅、最后 timing 很悲伤的新拓扑？

这种活让 Verilog 手写，就像拿菜刀雕航母。

能雕。
但不建议。

Chisel 的真正价值，不是“Scala 写 RTL”。
它的真正价值，是 generator。

它让硬件不只是被写出来，而是被生成出来。

这一步很重要。现代芯片越来越像“设计族”，不是一个孤零零的固定点。CPU、NPU、NoC、cache、互连、调度器、队列、bank、tile、lane，都有大量参数化空间。如果没有 generator，工程师就会在复制粘贴和宏地狱里慢慢修炼成赛博苦行僧。

所以 Chisel 没错。

Chisel 的问题不在于它提出了 generator。
问题在于：**generator 一旦强起来，复杂性就换了地方藏。**

---

## 三、Chisel 的槽点，其实是元编程的老毛病

很多人吐槽 Chisel，说 Scala 太灵活，弄不好就是群魔乱舞。有人说刚开始把它当 Verilog 写，代码很工整；等真正学会了 Scala 和 SpinalHDL/Chisel 的参数化抽象，顶层代码是漂亮了，但封装背后的东西，初学者完全看不懂。这个味道很真实。用户提供的材料里也保留了类似评论：初学时当 Verilog/VHDL 用很工整，熟练后发挥参数化配置能力，就容易出现所谓“群魔乱舞”。

这不是 Chisel 独有的问题。

这是所有元编程都会有的问题。

什么叫元编程？

简单说，就是你写的程序，不是最终干活的程序，而是生成最终结构的程序。

C++ template 就是前史。

C++ template 一开始只是泛型工具。大家只是想写个 `vector<T>`，让它既能装 int，又能装 float，还能装一些奇奇怪怪的对象。结果后来发现，这玩意儿不得了。它可以在编译期递归，可以做类型选择，可以搞 SFINAE，可以开坛做法，可以炼丹飞升，最后甚至能玩出图灵完备。

于是 C++ 编译器不只是编译器了。

它变成一台结构生成机器。

写模板的人觉得自己羽化登仙。
看模板报错的人觉得自己误入克苏鲁。

Chisel 也是这个路数。

它不是“Scala 代码等于电路”。
它是“Scala 程序运行后生成硬件图”。

这和 C++ template 的精神是一致的：用一套更强的宿主语言，去生成另一套结构。

好处显而易见：抽象强，复用强，生成能力强，参数化能力强。
坏处也显而易见：难读，难追，难 debug，错误链条长，源代码和生成物之间隔着一层雾。

顶层代码可以很漂亮，像精装修样板间。
真正的结构藏在 Scala 抽象、隐式规则、参数展开、库封装后面，像样板间后面的下水管。

作者看着是生产力。
维护者看着是密室逃脱。

所以元编程从来不是消灭复杂性，而是转移复杂性。

Verilog 把复杂性摊在 RTL 里，脏乱但看得见。
Chisel 把复杂性藏在 generator 里，优雅但难追踪。

前者像工地，一地钢筋水泥，灰尘扑面。
后者像魔法阵，地面干干净净，但你不知道哪条咒语召唤出了那堵墙。

---

## 四、高级 HDL 最怕的不是不能生成，而是生成之后没人管

高级 HDL 最容易让人兴奋的地方，是“我能生成”。

能生成 Verilog。
能生成模块。
能生成参数化结构。
能生成一族设计点。

这当然重要。

但大规模硬件设计真正难的，不是“能不能生成”。而是：

生成之后，谁来管？

生成出来的结构是否合法？
组合环有没有藏在 instance 边界后面？
logic depth 有没有被层次结构低估？
reset 语义在 C++ 仿真和 Verilog 后端里是否一致？
memory read-during-write 是 old-data 还是 new-data？
trace 采样在 tick 前还是 transfer 后？
probe 名字是否稳定？
这次生成和下次生成，信号身份还对得上吗？
C++ simulator 跑出来的行为，和 Verilator/RTL 是否一致？
出了 bug，能不能顺着 hierarchy、probe、trace 找回设计意图？

这才是高级 HDL 的硬骨头。

如果 generator 只是把复杂性从 RTL 搬到宿主语言，然后把一大坨 Verilog 扔给后端，那它只是换了一个地方制造混乱。

前端写得很优雅，后端查得很痛苦。
作者抽象得很开心，验证波形看得很沉默。

所以 pyCircuit 如果只是“Python 版 Chisel”，意义不大。

Python 也能写出灾难级 generator。
Python 也能生成一坨 nobody understands 的 Verilog。
Python 也能让前端自由飞翔，让后端痛苦埋单。

pyCircuit 真正有意思的地方，是它意识到：

**元编程本身不是答案。元编程之后的治理，才是答案。**

---

## 五、pyCircuit 不是再造一个 Chisel

现在回到 pyCircuit。

很多人看到 pyCircuit，会先注意两个东西：

第一，它用 Python。
第二，它有 cycle-aware API。

这两个都很亮眼，但都不是根。

如果说 pyCircuit 的核心是 Python，那就说浅了。
如果说 pyCircuit 的核心是 cycle-aware，那也说偏了。

cycle-aware 很香，但不能把它当 pyCircuit 的祖宗牌位。它更像厨房里一把好刀，不是整个饭店的商业模式。

它能让某些流水线写起来像分镜脚本：第 0 拍做什么，第 1 拍做什么，第 2 拍做什么。这当然好。硬件里很多 bug 不是算错，而是对齐错。能把 cycle relation 在前端暴露出来，很有价值。

**Python 只是笔，MLIR 才是法。**

Python 负责写得爽。
MLIR 负责不让你爽过头。

这话听着像段子，但其实很严肃。

pyCircuit 的基本路径是：

```text
Python frontend
  -> pyc MLIR dialect / passes / verifiers
  -> C++ functional simulator
  -> Verilog / Verilator integration
```

pyCircuit 不是“Python 拼 Verilog 字符串”的工具，而是把硬件构造、IR 语义、编译检查、C++ 功能仿真、Verilog 发射和 DFX/trace 基础设施放在同一条流水线里的系统。

这才是关键。

它不是只问：怎么写得更像 Python？
它问的是：Python 写出来以后，如何进入一个严肃的硬件编译器秩序？

---

## 六、MLIR 在 pyCircuit 里不是装饰品，而是法庭

为什么一定要 MLIR？

因为高级前端太自由。

Python 太自由。
Scala 也太自由。
C++ template 更不用说，那是上古黑魔法。

自由是生产力。
自由也是事故源。

一个 Python `if` 是不是硬件 mux？
一个 Python `for` 是不是静态展开？
动态 index 能不能进入硬件 IR？
复杂类型能不能 flatten？
helper function 是 inline，还是保留层次？
模块边界经过 pass 后还能不能存在？
某个语义是前端约定，还是后端补丁，还是 IR contract？

这些问题不能让各个后端自己猜。

否则会发生什么？

C++ 后端补一刀。
Verilog 后端缝一针。
testbench 里贴膏药。
trace 工具再包一层纱布。

最后这不是工具链，这是中医推拿馆。

pyCircuit 的原则很硬：**不能 backend-only semantic fixes。**
语义不能只在某个后端里偷偷修。语义必须进入 dialect、pass 或 verifier。否则 C++ 仿真和 Verilog 发射迟早分叉。

所有实现必须由 MLIR-level verifiers/passes gating，不能引入 backend drift；并且要求“add gate first, then implement”，禁止 backend-only fixes，语义属于 dialect + passes。

这就是 MLIR 的意义。

谁能进硬件 IR？
谁必须被 lower 掉？
谁违反 static hardware contract？
谁残留动态控制流？
谁类型不合法？
谁跨 instance 藏了组合环？
谁 logic depth 被低估？

这些都要判。

没有这层法，Python generator 再好写，也可能只是把 Verilog 的混乱换成 Python 的混乱。

---

## 七、pyCircuit 解决的是“元编程治理问题”

所以 pyCircuit 和 Chisel 的区别，不是 Python vs Scala。

这点一定要讲清楚。

Python 不天然高贵。
Scala 也不天然有罪。

Scala 的抽象能力很强，类型系统很强，函数式和面向对象能力都强。Chisel 借 Scala 拿到了强大的 generator 能力，这没有问题。

Python 的优势是亲民、生态广、脚本能力强、测试和工具胶水方便，也更适合 AI Agent 和架构探索。但 Python 也很容易失控。你不给它上规矩，它能把一个电路生成器写成玄幻小说。

所以 pyCircuit 真正要做的，不是“换一种宿主语言”。

而是把硬件 generator 带进 compiler-governed 时代。

Chisel 问的是：

**硬件结构能不能由高级语言生成？**

pyCircuit 继续往后问：

**高级语言生成的硬件，如何被审判、仿真、观测、追责？**

这不是同一道题。

Chisel 像预制构件厂，负责把墙、梁、柱批量造出来。
pyCircuit 更像工地总控系统：图纸要审，构件要编号，施工要留痕，出了事故能查监控，最后 C++ 仿真和 Verilog 还得对账。

前者解决“怎么生”。
后者关心“生出来以后归谁管”。

这就是 pyCircuit 的存在逻辑。

---

## 八、module instance 不是审美，是案发现场的门牌号

pyCircuit 还有一个很重要的设计：模块实例对应 C++ SimObject。

小设计可以拍平。
大设计不能拍成肉饼。

为什么？

因为大设计需要层次。
层次不是美学。层次是案发现场的门牌号。

你查 bug 的时候，不是只想知道“某个信号错了”。你想知道它在哪个 instance，哪个模块，哪个 cycle，哪个 phase，哪个 probe，哪个路径下错了。

这很重要。

因为生成 Verilog 只是第一步。
生成以后还能不能定位、观测、仿真、回放，才是大设计的命门。

模块边界如果只是源码里的组织结构，经过 pass 一搅就没了，那 debug 的时候就像城市没有门牌号。你知道案子发生了，但不知道警车往哪开。

pyCircuit 的做法是把模块边界变成 runtime 结构。

`@module` instance 不只是语法边界。
它是 C++ SimObject。
它拥有状态。
它对应 probe path。
它进入 trace 体系。
它在 DFX 里有身份。

这就是工程味。

---

## 九、tick / transfer：别让软件顺序执行偷走硬件时间

C++ functional simulation 还有一个坑：软件是顺序执行的，硬件是并行发生的。

如果你不小心，仿真模型里 A 模块先跑，B 模块后跑，B 就可能读到 A 在“同一拍”刚写出来的新状态。

软件里这叫执行顺序。
硬件里这叫时序污染。

所以 pyCircuit 的 SimObject 有 `tick()` 和 `transfer()` 两阶段。

`tick()` 计算组合逻辑和 next-state。
`transfer()` 提交寄存器和内存状态。

这个模型不花哨，但很关键。

它等价于告诉 simulator：

这一拍，大家都看 current state；
这一拍，大家都算 next state；
到拍边界，再统一提交。

这和同步硬件的精神一致，也和很多 cycle-level simulator 里的 Work/Xfer 模型一致。

如果没有这个分离，C++ 仿真很容易变成“看起来跑了硬件，实际上跑了一个有顺序污染的软件程序”。

pyCircuit 把 C++ functional simulator 放到一等位置，就必须把这个问题回答清楚。

这也是它不是普通 Verilog generator 的原因。

---

## 十、DFX / probe / trace：别等楼塌了才想起装摄像头

很多工具是楼盖完了才想起来装监控。

先把 RTL 生成出来。
先把仿真跑起来。
先把 demo 做出来。
等出 bug 了，再说能不能加个 probe。
等波形太大了，再说能不能搞 trace。
等信号名变了，再说能不能稳定 path。
等 C++ 和 Verilog 对不上了，再说能不能 cosim。

这就像楼都入住了，才想起没装消防通道。

pyCircuit 的思路不一样。

它把 DFX、probe、trace 很早就纳入系统设计。

统一 probe 概念。
central ProbeRegistry。
hierarchical path。
probe_id。
hash64。
pre-transfer/post-transfer sampling。
binary trace event stream。
phase timestamp。
schema version。
cosim mismatch dump。

这些词看起来很烦，像一群项目管理文档里的妖怪。但在大规模硬件设计里，它们都是救命绳。

因为 bug 发生时，你不能只说“我觉得它应该对”。

你要能回答：

哪个模块？
哪个实例？
哪个周期？
哪个阶段？
哪个 probe？
哪个值变化？
这次构建和上次构建是不是同一个身份？
C++ sim 和 Verilog 后端有没有对账？

pyCircuit 想把这些东西从“事后补丁”变成“先天器官”。

这就是 DFX-first。

不是出事以后再装摄像头，而是在施工前就把门牌、探头、巡检路线、事故录像格式都定好。

---

## 十一、pyCircuit 的重，不是缺点，是选择

有人可能会说：写个 counter 而已，要 Python、MLIR、C++ sim、Verilog、DFX、trace、gate，至于吗？

确实，写个 counter 不至于。

小电路怕重。
大设计怕虚。

如果你的目标只是写一个固定模块，Verilog 五行搞定，那 pyCircuit 显得像拿大炮打蚊子。

但一旦进入 CPU、NPU、流水线、issue queue、ROB、scoreboard、bypass network、tile scheduler、memory ordering、cosim、trace、LinxCore 这类设计，事情就不一样了。

这类设计需要的不只是短代码。

它们需要：

稳定层次；
显式状态归属；
可追踪 probe；
可复现 trace；
C++ cycle-level simulator；
Verilog/Verilator integration；
reset/memory 语义一致；
跨模块组合环检查；
logic depth 早期代理；
generator/DSE 后仍然可验证；
多个后端行为不漂移。

这不是语法糖能解决的。

这需要基础设施。

所以 pyCircuit 的“重”，不是误伤。
它本来就不是为了只写一个 counter。

它是为大规模硬件元编程准备的缰绳、马鞍、马厩、兽医和赛道裁判。

野马可以跑。
但不能裸奔。

---

## 十二、抽象可以飞，但必须落地

所以，我不会说 pyCircuit 已经赢了 Chisel。

这话太早，也太油。

Chisel 有自己的历史、生态、战绩和方法论。它证明了硬件 generator 的价值。Rocket Chip、Chipyard 这类生态并不是 PPT 里的幻觉，而是真实推动过开源硬件复杂系统的工具链路线。

pyCircuit 还年轻。它需要真实大设计验证，需要后端成熟，需要 pass/gate 体系不断补强，需要 C++ sim 和 Verilog 长期对账，需要在复杂模块里证明自己不是“看起来很美”。

但 pyCircuit 有一个很清醒的判断：

**高级 HDL 的下一步，不只是更强的 generator，而是更强的治理系统。**

Chisel 让硬件会生成。
pyCircuit 想让生成器别裸奔。

Verilog 时代，工程师是在写电路。
Chisel 时代，工程师是在写生成电路的程序。
pyCircuit 想推进的是第三步：

**工程师仍然写生成器，但生成出来的东西必须进入一套可验证、可观测、可追踪、可审判的编译器秩序。**

这就是从 programming，到 meta-programming，再到 governed meta-programming。

C++ template 告诉我们，元编程能解放生产力，也能制造黑魔法。
Chisel 告诉我们，硬件生成器能救工程效率，也能把 debug 变成考古。
pyCircuit 如果有价值，就在于它不迷信元编程本身，而是试图给元编程套上 MLIR 的缰绳。

抽象可以飞，但必须落地。
generator 可以施法，但施完法以后，得有人查消防、验结构、看监控、对账本。

所以 pyCircuit 的意义，不是“Python 写硬件真香”。

它真正想说的是：

**硬件元编程可以继续浪，但不能继续裸奔。**
