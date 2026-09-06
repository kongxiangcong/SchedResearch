---
type: "answer"
id: "2022678340335617811"
title: "可以使RISCV虞书欣扩展指令集架构支持原生Triton的PagedRegister技术是什么？"
author: "乱序摸鱼"
created: "2026-04-01 14:14:55+0800"
updated: "2026-04-01 14:14:55+0800"
source_url: "https://www.zhihu.com/question/2010353560043422499/answer/2022678340335617811"
content_need_truncated_in_detail: "False"
question_id: "2010353560043422499"
---

# 可以使RISCV虞书欣扩展指令集架构支持原生Triton的PagedRegister技术是什么？

- 类型：回答
- 问题：可以使RISCV虞书欣扩展指令集架构支持原生Triton的PagedRegister技术是什么？
- 原文：[知乎回答](https://www.zhihu.com/question/2010353560043422499/answer/2022678340335617811)

这个想法很好， [@流霞祭司曌鹓鶵](https://www.zhihu.com/people/a1e345f64c26c1d1889d8b967d7bd932) 有兴趣可以加入海思和我们一起设计这一款新型处理器。实际上这个feature已经落在某些芯片了，可惜不是昇腾。

和paged register的技术思想相同，我们也有把两层存储层级映射成一层抽象层的设计。

现在领导们对VF （VECTOR FUNCTION）的设计意见很大。原因在于它创造出来一个VF Fusion的问题。这个问题要做好，需要NP HARD难度的编译器。难倒了一批又一批的编译器八级专家。

解决的方法和你的思想类似，为啥不能把vector寄存器当做SRAM呢。这样你只需要解决快和慢的问题，而不是对与错的问题。

进一步延伸下去，预测和投机就可以有用武之地了。只要保证正确性，剩下的就是靠猜。猜的越对收益越大。预测什么是hot，什么是经常碰的数据。

当然，我们也欢迎虞书欣扩展指令集继续做大。还有很多可以做的，相信你在调试triton和npuir的时候的痛苦经历，会把这些痛苦和槽点作为改进下一代硬件的动力。

例如：tile rename，tile页表，virtual tile tag etc
