# R12 Linux / tt-npe 环境

本轮使用独立 WSL2 发行版 `SchedResearch-R12`（Ubuntu 24.04.4 LTS，x86_64），仅服务本轮研究。固定 tt-npe commit 为 `341da058f0b65e51d3643fb36f011a0784abedff`。Linux 源码从本项目冻结副本 `git clone --no-hardlinks` 取得；编译产物放在 Linux 文件系统。

**实际验收：官方 library / Python API 已可用，C++ 45/45、pytest 10/10 通过；官方 CLI 存在已复现的上游字段错误，因此整体 `passed=false`，不能写成全部通过。** 最后完整运行编号为 `20260908T010242Z`，源码最终 `git status --porcelain` 为空。

## 路径与可重跑入口

| 内容 | 路径 |
|---|---|
| WSL 发行版 | `SchedResearch-R12` |
| 本轮 VHDX | Windows `research/r12/.wsl/`，由总任务创建 |
| Linux 源码 | `/opt/schedresearch-r12/tt-npe` |
| Linux CMake build | `/opt/schedresearch-r12/build/tt-npe` |
| Linux install | `/opt/schedresearch-r12/install/tt-npe` |
| Linux Python venv | `/opt/schedresearch-r12/venv-npe` |
| 设置脚本 | [setup_linux.sh](setup_linux.sh) |
| Python 依赖锁 | [requirements-npe.lock.txt](requirements-npe.lock.txt) |
| 结构化环境与验收回执 | [artifacts/npe_environment.json](artifacts/npe_environment.json) |
| 逐阶段日志和历史回执 | `artifacts/logs/npe_*`、`artifacts/npe/environment_<run_id>.json` |

从 Windows PowerShell 运行：

```powershell
research/r12/.venv/Scripts/python.exe -X utf8 research/r12/prepare_npe_sources.py
wsl -d SchedResearch-R12 -u root -- bash /mnt/d/dsh-proj/SchedResarch/research/r12/setup_linux.sh
```

第一个命令从 GitHub 官方 tag 下载第三方归档并记录 URL / tag / SHA256；Boost 递归依赖从相同 tag 的 CMakeLists 提取。Linux 脚本安装 Ubuntu 官方包，确认本地源码 commit/clean 状态，设置独立 venv，校验归档哈希并解压到 `/opt/schedresearch-r12/download_sources`，使用上游 CMake 工程进行 out-of-source configure/build/install，然后执行官方 Python API example、CLI、C++ 测试和 pytest。每次运行保留独立日志；不删除源码、build、install 或发行版。不要在脚本运行期间编辑正在执行的 shell 文件。

## 已验证的工具配置

`gcc-12` / `g++-12` 为 **12.4.0**，CMake **3.28.3**，Ninja **1.11.1**，Linux Python **3.12.3**。安装了 `python3-dev`、`python3-venv`、git、ca-certificates、curl、libc++ / libc++abi dev、pkg-config、zlib dev。Python 依赖首先按上游 `requirements.txt` 安装 pytest / orjson，随后冻结全部实际版本；`pip check` 已通过。

编译显式选择 GCC12，使用 `-DENABLE_LIBCXX=OFF`，避免混用 Clang 的 libc++ ABI。此选择直接受上游 `CHECK_COMPILERS()` 的 GCC>=12 条件支持；GCC12 是该检查标记的 tested 版本。上游还支持 Clang17/20，但本环境没有为了默认自动发现逻辑额外引入 LLVM 私有源。[固定 compiler checks](https://github.com/tenstorrent/tt-npe/blob/341da058f0b65e51d3643fb36f011a0784abedff/cmake/compilers.cmake)、[CMake 构建入口](https://github.com/tenstorrent/tt-npe/blob/341da058f0b65e51d3643fb36f011a0784abedff/CMakeLists.txt)。

本轮直接调用上游 CMake 接口：`cmake -S ... -B ...`、`cmake --build ... --parallel 4`、`cmake --install ...`。没有调用会先删除 install 的 `build-npe.sh`，也没有 source 会自动运行 uv 安装和检查 moving main 的 `ENV_SETUP`；所需 PATH / PYTHONPATH / LD_LIBRARY_PATH 仅在本轮进程里显式设置。[上游 build 脚本](https://github.com/tenstorrent/tt-npe/blob/341da058f0b65e51d3643fb36f011a0784abedff/build-npe.sh)、[ENV_SETUP](https://github.com/tenstorrent/tt-npe/blob/341da058f0b65e51d3643fb36f011a0784abedff/ENV_SETUP)。

上游 CPM / FetchContent 会获取第三方源码；[dependencies.cmake](https://github.com/tenstorrent/tt-npe/blob/341da058f0b65e51d3643fb36f011a0784abedff/cmake/dependencies.cmake)固定 zstd 1.5.5、GoogleTest 1.16.0、reflect 1.1.1、magic_enum 0.9.6、fmt 11.1.4、nlohmann/json 3.12.0、simdjson 3.12.3、yaml-cpp 0.8.0、pybind11 2.13.6；[Boost 获取逻辑](https://github.com/tenstorrent/tt-npe/blob/341da058f0b65e51d3643fb36f011a0784abedff/cmake/fetch_boost.cmake)使用 Boost 1.87.0。实际取得的 Git dependency commits 和安装文件 SHA256 写入结构化回执。

## 运行证据与边界

| 实际运行阶段 | 结果 |
|---|---|
| CMake configure / Ninja build / install | 全部 exit 0，158 个构建步骤完成 |
| 官方 C++ tests | 6 个 suite，45 tests，0 failure / error / skipped；14.026 s |
| 官方 pytest | 10 tests，0 failure / error / skipped；12.63 s |
| 官方 `example_wl.json` 经 Python API | PASS；真实安装目录的 `tt_npe_pybind` 返回 `Stats` |
| 官方 CLI | FAIL / exit 1：`tt_npe.py:166` 的 `Stats.wallclock_runtime_us` 不存在 |
| 固定源码最终状态 | commit 匹配且 clean |
| 结构化状态 | `ready_for_coarse_api_use=true`、`upstream_tests_passed=true`、`official_cli_passed=false`、`passed=false` |

测试 XML 分别为 [C++ 回执](artifacts/npe/cpp_tests_20260908T010242Z.xml) 与 [pytest 回执](artifacts/npe/python_tests_20260908T010242Z.xml)；[API 回执](artifacts/npe/example_api_20260908T010242Z.json)和[CLI 原始错误](artifacts/logs/npe_example_cli_20260908T010242Z.log)均保留。脚本最终返回 1 是对已知 CLI 验收失败的显式报告，并不否定前面成功的 library、API 与测试阶段。脚本不会把任何实际测试失败改成成功。

该 CLI 先成功获取 `Stats`，随后打印时访问旧的全局字段；固定绑定只在 `DeviceStats` 上暴露 `wallclock_runtime_us`，顶层 `Stats` 暴露 `per_device_stats`。本轮直接使用受支持的 Python API，未修改 upstream，也未做字段 fallback。[CLI 固定源码](https://github.com/tenstorrent/tt-npe/blob/341da058f0b65e51d3643fb36f011a0784abedff/tt_npe/py/pycli/tt_npe.py#L156-L168)、[绑定定义](https://github.com/tenstorrent/tt-npe/blob/341da058f0b65e51d3643fb36f011a0784abedff/tt_npe/cpp/pybind/bindings.cpp#L171-L183)。

API example 使用 `wormhole_b0 / fast / 32 cycles per timestep / infer injection rate=true`。device `0` 返回 `completed=true`、`estimated_cycles=437`、`estimated_cong_free_cycles=437`，输入自带 `golden_cycles=450`，工具计算误差为 −2.8889%；这里的 golden 不是本轮设备测量，不能据此声称误差校准通过。完整结果也保留 API 的 `-1` 字典项，以及每控制器 DRAM / NoC / NIU 字段。输入 SHA256 为 `6dd385b68704b180508b21ec7d10ca2f7161c857eea72611d06cfb6c5c99ff1c`。

官方 example 缺少三个 transfer 的 `noc_event_type`，固定 parser 发出警告后继续；C++ trace fixture 测试也打印缺少 fabric 字段的诊断但全部断言通过。这些日志不能当作完成/可见性语义已覆盖的证据。源码位置：[parser](https://github.com/tenstorrent/tt-npe/blob/341da058f0b65e51d3643fb36f011a0784abedff/tt_npe/cpp/src/npeWorkloadIngest.cpp#L185-L202)。

仅复跑可用的官方 API example，无须重装：

```powershell
wsl -d SchedResearch-R12 -u root -- bash -lc 'cd /opt/schedresearch-r12/runs && PYTHONPATH=/opt/schedresearch-r12/install/tt-npe/lib LD_LIBRARY_PATH=/opt/schedresearch-r12/install/tt-npe/lib /opt/schedresearch-r12/venv-npe/bin/python /mnt/d/dsh-proj/SchedResarch/research/r12/npe_smoke.py --output /opt/schedresearch-r12/runs/example_api_manual.json'
```

WSL 的 GitHub git clone 吞吐明显低于 Windows。构建使用 CPM 0.40.2 自带的 `CPM_<name>_SOURCE` 和 CMake 的 `FETCHCONTENT_SOURCE_DIR_PYBIND11` 本地目录覆盖接口，源码内容来自上游指定的同一 tag；没有更换版本或编辑 upstream。归档的 URL、大小、SHA256 在 `artifacts/npe_downloads/manifest.json` 和环境回执中，覆盖配置保存在 Linux `download_sources/sources.cmake`。zstd 1.5.5 和 CPM 本身由原始上游下载路径取得，哈希也保留。

43 项归档已冻结为 [npe_source_archives.json](npe_source_archives.json)；再次运行下载脚本必须匹配这里的 SHA256，并验证 Boost 依赖闭包没有漏项。本轮实际复核全部 43 项通过，日志为 `artifacts/logs/npe_archive_lock_verification.log`。本地 source 接口有[CPM 0.40.2 实现](https://github.com/cpm-cmake/CPM.cmake/blob/v0.40.2/cmake/CPM.cmake#L689-L706)和[CMake 3.28 文档](https://cmake.org/cmake/help/v3.28/module/FetchContent.html#variable:FETCHCONTENT_SOURCE_DIR_%3CuppercaseName%3E)支持。

构建、测试与 example 状态以本轮最后的 `npe_environment.json` 为准，不把源码下载或包安装成功记为 build PASS。C++ 测试直接执行上游 `tt_npe_ut`，pytest 使用固定源码 `tt_npe/pytest.ini`，都保留 XML，入口与[上游 run_ut.sh](https://github.com/tenstorrent/tt-npe/blob/341da058f0b65e51d3643fb36f011a0784abedff/tt_npe/scripts/run_ut.sh)相同。

官方 CLI 与 Python API 结果分别记录。`npe_smoke.py` 使用上游 `example_wl.json` 和公开 `Config / createWorkloadFromJSON / InitAPI / runNPE`，要求返回真实 `Stats`，每个 device 完成且 estimated cycles 为正；不以进程返回 0 代替 API 合同检查。[官方示例/API 文档](https://github.com/tenstorrent/tt-npe/blob/341da058f0b65e51d3643fb36f011a0784abedff/README.md)、[绑定字段](https://github.com/tenstorrent/tt-npe/blob/341da058f0b65e51d3643fb36f011a0784abedff/tt_npe/cpp/pybind/bindings.cpp)。

所有 NPE 数值均为固定 coarse estimator 输出。本轮没有 Tenstorrent 设备测量，没有校准完整 DFG elapsed，也没有独立验证示例中的 golden cycles。NPE 可以筛选网络争用候选，不能单独准入本轮 G0/G1/G2 或证明新方法收益。

## 过程中的失败保留

首个 setup run `20260908T004524Z` 已完成系统包、源码 clone 和 Python 依赖安装，但本轮 shell 脚本在执行中被补写超时参数，改变了 bash 后续读取位置，错误为 `clone: command not found`。这是本轮 setup wrapper 的操作错误，不是 NPE 源码或平台错误；完整回执已保存在 `artifacts/npe/environment_20260908T004524Z.json`。脚本随后经 `bash -n` 检查后重新执行，没有删除失败证据或改动 upstream。

第二个 run `20260908T005053Z` 在 WSL GitHub clone 阶段持续缓慢；本轮主动停止该 configure 及其下载子进程，保留 configure exit 137 和完整日志，再改用 Windows 下载同 tag 官方归档。它是主动中止的网络获取尝试，不是 NPE 编译失败。第三个 run 完成所有阶段，唯一最终失败为前述上游 CLI 字段错误。构建日志另保留 GCC / pybind11 的 LTO 和 `-Wstringop-overread` 警告，未修改警告策略或关闭测试。
