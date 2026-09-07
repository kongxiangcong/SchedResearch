# R7 Phoenix 计算 kernel 来源与可执行合同

日期：2026-09-05。结论：**获得了来源完整、可独立验算的 Phoenix INT8 单 GEMM 候选；本文件的来源侧工作没有运行设备。** 本机已安装 BF16 GEMM 的数值合同仍未建立。实际兼容性与设备数值结果由 R7 主实验单独报告，不从目录名、来源版本或 CPU fixture 推定。

## 问题、假设与停止门

- 问题：当前 driver 10.1109.8.110 / XRT 2.17.0 能否复用早期 Phoenix 公开示例，使单次算术 kernel 的输入、布局、指令和 oracle 全部固定？
- 假设：AMD 的早期 Phoenix `qlinear_2` 具有比现代 DynamicDispatch 更贴近当前栈的可运行二进制和完整 host 合同，可以通过本机 XRT 执行；兼容性必须用本机加载、完成状态、全输出比对判断。
- 强基线：原厂静态 INT8 GEMM 配置、原厂 `WgtMatrix` 权重排列、原厂 superkernel 参数、原厂 shape-specific microcode。输入仅替换为固定可精确验算的数据；未添加调度动作或背景。
- 判别实验：先以原厂 C++ headers 独立核对 Python 的 200 B 参数序列、4 MiB 权重排列与 2048 个输出 oracle，再以原厂调用 ABI 完成一次本机单 GEMM 并全量精确比较；通过后方可重复 elapsed 筛查。
- 停止门：若 CPU 合同不一致，禁止设备测试；若本机加载/等待失败或任何输出不相等，停止重复运行并保留错误。无已定义 compute-active/实际 bytes/request 观测时只准 host elapsed 筛查，不打开 R5 机制门。

## 1. 可复用的完整 INT8 路径

冻结官方 `amd/RyzenAI-SW` 的 `1.0` 分支到 `a3d163c81e4d0b21667c05f614c1d79be14c3fa1`。该 revision 的 `qlinear_2.hpp` 直接使用 XRT，明确将 INT8×INT8 矩阵乘送到 AIE。它加载 `xclbin/phx/gemm_4x4.xclbin`，为 M=1,K=N=2048 选择 `dll/phx/qlinear_2/mc_code_1_2k_2k.txt`。官方 unit test 对同一 shape 使用独立三重循环参考并逐元素要求零误差。[官方 host](https://github.com/amd/RyzenAI-SW/blob/a3d163c81e4d0b21667c05f614c1d79be14c3fa1/example/transformers/ops/cpp/qlinear_2/qlinear_2.hpp)、[官方 exact oracle](https://github.com/amd/RyzenAI-SW/blob/a3d163c81e4d0b21667c05f614c1d79be14c3fa1/example/transformers/tests/cpp/test_qlinear_2.cpp)

完整字节下载已冻结在 [kernel_access/ryzenai](sources/kernel_access/ryzenai/)，URL、revision、大小、SHA256 与下载失败均在 [source_manifest.json](sources/kernel_access/source_manifest.json)。`gemm_4x4.xclbin` 是 2,375,756 B 的真实 `xclbin2` 文件；microcode 文本是 46,360 B，解析为 1663 个 little-endian uint32，即 6652 B。二者均非 Git LFS pointer。

固定调用为 `DPU(1, A, W, C, dummy1, instructions, 1663, dummy2)`，但必须遵守 scalar 的实际类型：

| arg | 类型/用途 | 固定 BO 大小 | 原厂 group/flag |
| --- | --- | ---: | --- |
| 0 | uint64 opcode=1 | — | scalar |
| 1 | IFM，2048 B row-major INT8 A + 200 B superkernel序列 | 2248 B | group_id(1), HOST_ONLY |
| 2 | 重排后的INT8 W，逻辑2048×2048 | 4,194,304 B | group_id(2), HOST_ONLY |
| 3 | row-major INT32 C，逻辑1×2048 | 8192 B | group_id(3), HOST_ONLY |
| 4 | inter dummy | 16 B | group_id(4), HOST_ONLY |
| 5 | uint32 microcode序列 | 6652 B | group_id(5), CACHEABLE |
| 6 | uint32 instruction word count=1663 | — | scalar |
| 7 | mc dummy | 16 B | group_id(7), HOST_ONLY |

这些参数也由该 xclbin 的 DPU embedded XML 交叉核对：arg0 `uint64_t`/8 B；arg6 `uint32_t`/4 B；其余为64-bit buffer pointers。文件另有名为 `vadd` 的 XML 描述，不能把它误当作本次调用的计算合同。[冻结提取 XML](sources/kernel_access/gemm_4x4_embedded_0.xml)、[提取程序](sources/kernel_access/inspect_binary.py)

原厂顺序是 input/instructions/weights sync 到设备后 `kernel_` 调用→`wait2`，随后 C sync 回 host，最后拷出结果。原厂 `run_aie_time_` 是 host launch→wait2 区间；同步、格式化、权重初始化、CPU分块累加都另计。此次 shape 无外层 K/N 分块累加。这个调用本身不提供 compute-active、物理总线 bytes 或 request 上限。[原厂 run_aie](https://github.com/amd/RyzenAI-SW/blob/a3d163c81e4d0b21667c05f614c1d79be14c3fa1/example/transformers/ops/cpp/qlinear_2/qlinear_2.hpp#L485)

### 固定 fixture 与独立检查

[generate_int8_fixture.py](sources/kernel_access/generate_int8_fixture.py) 仅在 CPU 生成数据，不加载 XRT。它冻结 A 与逻辑 W 的全部原始字节，再将 W 按官方 `WgtMatrix` 映射重排；对4,194,304个位置检查映射为双射。oracle 从未重排的逻辑 W 按 signed INT64/整数语义求和，输出可安全放入 INT32。输入值位于[-3,3]，全部2048个输出范围[-575,691]，694个不同结果，包含正负与抵消。[官方 WgtMatrix](https://github.com/amd/RyzenAI-SW/blob/a3d163c81e4d0b21667c05f614c1d79be14c3fa1/example/transformers/ops/cpp/utils/wgt_matrix.h)

superkernel 参数依次为 `MLKernelParams` 默认构造、`update_params(32,128,64,8,8,16)`、`out_32=1`，`GemmSeq` 长200 B。参数中 unused/padding 被显式置零，避免继承原厂初始化器未写字段的任意 host 内容。M=1 的 IFM 仍只保存一行；原厂 microcode负责相应 pad，不能把 A 按32行自行扩成不同合同。[super_instr.h](https://github.com/amd/RyzenAI-SW/blob/a3d163c81e4d0b21667c05f614c1d79be14c3fa1/example/transformers/ops/cpp/utils/super_instr.h)、[ml_params.h](https://github.com/amd/RyzenAI-SW/blob/a3d163c81e4d0b21667c05f614c1d79be14c3fa1/example/transformers/ops/cpp/utils/ml_params.h)

交付文件位于 [int8_fixture/](sources/kernel_access/int8_fixture/)，大小与 hash 见 [fixture_manifest.json](sources/kernel_access/int8_fixture/fixture_manifest.json)：`a_with_super_sequence.bin`、`weights_packed_int8.bin`、`instructions_uint32.bin`、`expected_rowmajor_int32.bin`；原始 A/W 和单独 super_sequence 也保存。[verify_fixture.cpp](sources/kernel_access/verify_fixture.cpp) 直接包含冻结的原厂 C++ helper，逐byte核对 Python 序列与重排结果，并以 C++ INT64 再验全部2048个 golden 输出。SDK 子任务使用 MSVC C++17编译并实际执行后全部通过：`MLKernelParams=40, GemmInstr=60, GemmSeq=200, packed_weight_bytes=4194304, exact_oracle_outputs=2048`。[真实CPU检查输出](sdk/fixture_verification_output.txt)、[构建回执](sdk/build_receipt.json)。这只认证CPU fixture与原厂host布局相符，仍不是设备正确性证据。

## 2. 版本和可移植性边界

该早期示例自带 headers/libraries，但其 `version.h`/`version.json` 明确为 XRT **2.14.0@6c6a8bddd007847d8125213c91c2f13ae61cf4ca**，不是当前2.17.0。R7 应以当前 XRT 的精确headers和已安装DLL构建 host，不能将发现旧SDK称为找到版本匹配SDK；本机是否接受早期 xclbin仍须执行验证。[冻结版本头](sources/kernel_access/ryzenai/example/transformers/third_party/xrt-ipu/xrt/include/version.h)、[版本JSON](sources/kernel_access/ryzenai/example/transformers/third_party/xrt-ipu/xrt/version.json)

有一个有限但具体的年代关联证据：同一官方revision的 `aieml_gemm_vm_phx_4x4.xclbin` 与本机已安装同名文件逐byte SHA256一致，均为 `d8b16adf18172cb3a5bfdd57328b49b05fa5ebc1e8ae9c86517920533c7bc032`。这只证明旧示例资产与安装栈有重叠，**不证明不同的 `gemm_4x4.xclbin` 已兼容或已执行**。[本地资产记录](sources/kernel_access/local_installed_assets.json)

Riallto v1.0 精确revision `8e73ab69daf2f04f1341baf6181a8d2ab478848d` 的 README要求driver `.100`，R6冻结v1.1要求`.128`；本机`.110`夹在二者之间并不构成兼容声明。v1.0 的确有 prebuilt vision xclbin/sequence和应用元数据，另有 plus1源码，但本轮没有发现可直接替换为自定义小plus1的已构建三件套。其安装脚本会创建/改动环境与系统PATH，本轮未执行。[Riallto v1.0](https://github.com/AMDResearch/Riallto/blob/8e73ab69daf2f04f1341baf6181a8d2ab478848d/README.md)、[冻结安装脚本](sources/kernel_access/riallto/scripts/utils/setup_runtime.ps1)

现代 `amd/DynamicDispatch@b3051f03e20aab237cda3bbe4cd2081f76b72b06` README明确其当前栈只支持 STX，并要求 STRIX B0、IPU-MCDM driver。不能因其提供 BF16/MatMul代码就将 transaction、ABI或binary代入Phoenix。README的transaction细节链接还指向AMD内网，本轮没有访问该内网。[冻结官方 README](https://github.com/amd/DynamicDispatch/blob/b3051f03e20aab237cda3bbe4cd2081f76b72b06/README.md)

## 3. 已安装 BF16 GEMM 的具体缺口

本机 `aieml_gemm_vm_phx_4x4_bf16.xclbin`/`.json` 分别为1,491,595 B和46,094 B。JSON是 AIE graph/tile/port metadata，包括4列partition与图位置；它没有独立给出可执行shape的 buffer重排、microcode、数值舍入合同和oracle。[冻结 metadata](sources/kernel_access/installed_bf16_aie_metadata.json)、[hash记录](sources/kernel_access/local_installed_assets.json)

旧RyzenAI-SW还包含同名 BF16 的 **TVM target configuration**，仅3364 B，与已安装46,094 B AIE metadata是不同文档。它描述instruction字段、BD granularity与superkernel选择，不是一份具体矩阵shape的可执行序列。该revision的另一条 `qlinear` 通过 `tvm::runtime::Module::LoadFromFile` 加载编译后的shared library并取PackedFunc运行，不能把INT8 `qlinear_2` 的原厂WgtMatrix和superkernel参数直接套到BF16文件。[TVM配置](https://github.com/amd/RyzenAI-SW/blob/a3d163c81e4d0b21667c05f614c1d79be14c3fa1/example/transformers/third_party/.tvm/aie/aieml_gemm_vm_phx_4x4_bf16.json)、[qlinear runtime](https://github.com/amd/RyzenAI-SW/blob/a3d163c81e4d0b21667c05f614c1d79be14c3fa1/example/transformers/ops/cpp/qlinear/qlinear.hpp)

因此BF16候选的最小补件仍是该binary匹配的已生成算子模块/指令、host布局和golden数值；不能用“文件已安装”验收浮点算术。INT8单GEMM若通过只补足“真实单compute可执行/可验算”的能力，不补足Qwen GDN的BF16/FP32合同、跨层state驻留或动态收益证据。

## 4. 来源完整性与下一决定

官方 GitHub API tree 的3次请求均因403 rate limit失败；后改用浅层、无checkout、禁LFS自动smudge的source-only clone取得文件路径和固定revision，并以固定raw URL下载选定资产。三个 `*_repo/.git` 仅是来源检索缓存；权威交付为显式冻结文件与manifest，不应把检索缓存当研究结果。未安装任何系统包、未升级driver、未使用外部账号/内网。

**Refine→执行原厂静态单compute合同。** 若 CPU helper核对、本机加载、全量数值全部通过，再测固定BO/输入/binary的elapsed边界及instrumentation成本。仍须另行解决计数器资格与强静态可调空间，才能决定Phoenix是否能承担R5研究门；本来源任务不改变R5否定结论。
