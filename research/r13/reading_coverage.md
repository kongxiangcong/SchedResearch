# R13 接续阅读与运行覆盖

2026-09-08。范围为用户指定的研究记录、关联代码/合同/结果和固定的公开来源。没有使用仓库其他proposal初稿、演示或解析副本。此表区分当前团队的实际阅读、源码/结果核查和实际执行；旧报告中的PASS不等于本轮复跑。

| 材料 / 位置 | 本轮覆盖 | 用途与边界 |
|---|---|---|
| `research/research_progress.md` | 全文，分段读取 | 接续R1–R12证据链、R13模型路线及R12需求纠错。未重跑R1–R11性能实验。 |
| `research/analysis/r1_r10_research_retrospective.md` | 全文，包含末尾追加 | 区分历史候选、已关闭和未验证判断，不把过去投入排序当作当前限制。 |
| `research/analysis/r13_model_contract_redteam.md` | 全文，补读截断尾部 | 有限buffer、完成事件和强基线反解释。 |
| `research/literature/model_based_evaluation_20260908.md` | 全文 | 读取上一轮公开论文方法核查；本次执行未新增文献检索，不把模型方法认可当作本模型验证。 |
| `research/r13/proposal_contract.md` | 全文 | 当前M0/M1/M2、无板卡路线、完整MLP及P0能力合同。 |
| `SchedResearch_reassessment_evidence_20260907/proposal_contract.md` | 全文 | 原proposal历史边界，native前置已由R13取代。 |
| 同目录 `evidence_ledger.md` | 全文 | 项目与公开依据及未验证事项。 |
| 同目录 `evidence_manifest.json` | 全文 | 证据包文件与来源登记。 |
| 同目录 `bound_witness.py` | 全文 | 旧解析见证是下界算术，不升级为完整协议周期模拟。 |
| 同目录 `bound_witness_result.json` | 全文 | 核查保存的旧见证结果；本次不改写。 |
| 同目录 `sha256.json` | 全文及字节核对 | 保留原包文件完整性。 |
| `research/r12/README.md`、`dependencies.json`、`preregistration.json`、`experiment_report.md` | 全文 | 复用固定版本与环境；原native门仅为历史，依赖未升级。 |
| `research/r12/qualification.py` | 前150行及代理定向查阅的相关需求/基线部分 | 96种空间/路由种子、物理地址和原始需求纠错；不称全文逐行审计。 |
| `research/r12/linux_environment.md`、`npe_smoke.py` | 环境/路径及API调用相关部分 | 定位既有WSL/NPE；本轮真实调用受拒，未重新安装或完成NPE对照。 |
| 固定 `tt-isa-documentation` 的 `NoC/README.md`、`RoutingPaths.md`、`Ordering.md`、`Counters.md`、`TensixTile/L1.md`、`DRAMTile/README.md` | 团队全文读取；根代理重点复核NoC/路由及DRAM前75行 | 10×12物理路由、flit、buffer、独立L1口/共享bank、channel alias与完成语义。源码文档不等于设备测量。 |
| 固定 `tt-npe` 的 `wormhole_b0.hpp` 路由/DRAM映射、Python绑定及programmatic example | 定向源码核查 | 按device,row,col解释坐标；区分API transaction投影和逐flit完整协议。 |
| 固定STREAM/TETRA的scheduler、allocator、路径/源图处理与GSCIP调用 | 基线代理定向源码审计及真实调用 | 导出原选择与求解状态，具名目标IO/路径适配继承原约束；不是全文审计整个依赖仓库。 |
| 原始2conv ONNX、实际IR/SVG和affine map | 需求代理按原访问关系/轴基向量独立核查并实际运行 | 49152-bit/384必要界仅属于对齐halo所有权；全复制2048界是另一合同。 |
| `research/r13` 新实现 | 主作者实现；独立代理分别审查builder算术、tick执行、16B值/epoch、TETRA移植与实验方法 | 审查覆盖及实际结果各自引用具名回执，不以代理报告替代未运行门。 |

本轮实际执行包括CPU完整数值资格、需求回归、真实STREAM/TETRA及GSCIP、主DES、独立tick检查器、数据trace审计、非法变异、有限集成例，以及新小图实验。最终数量和门判决由 `experiment_report.md` 与紧凑JSON登记。没有板卡、固件、native kernel、RTL/PPA测量；没有完整MLP性能模拟。

不能访问的运行能力是当前会话下的既有WSL服务，因此NPE共同投影的跨工具趋势尚缺。固定依赖的源码仍可读取；不将这个执行限制补成已完成事实。没有把无法打开的外部会话附件推断为已读；本次所需原附件已在指定证据目录按文件读取。
