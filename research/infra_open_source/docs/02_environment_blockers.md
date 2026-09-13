# 环境阻断记录（ONNXim 无法在本机构建/运行）

本文只记录**本轮实际执行过的命令与真实错误**，用于把"环境阻断"与"能力不匹配"分开。
所有结论都能用下面的命令复现。

## 结论摘要

ONNXim 本轮**没有构建、没有运行**。原因有两层，互相独立，不可合并成一句"环境不行"：

| 层次 | 结论 | 是否本轮可解 |
|---|---|---|
| 环境阻断 | 主机上没有 cmake、没有 conan；PyPI 被网络过滤替换成 HTML 拦截页；大文件下载被截断 | 否 |
| 能力阻断 | 即使能构建，跨算子驻留、核间通信、整层屏障三项与研究需求直接冲突 | 否（需重写执行/存储/路由） |

## 1. WSL2 不可用（非技术原因）

```
wsl.exe -l -v
→ PROGRAM BLOCKED BY SECURITY POLICY: wsl.exe (C:\Windows\system32\wsl.exe)
  is on the configured Program Blacklist.
```

本轮因此完全在 Windows 原生环境开发（PowerShell 7 / Git Bash）。

## 2. pip 无法安装任何包

```
pip install numpy
→ ERROR: THESE PACKAGES DO NOT MATCH THE HASHES FROM THE REQUIREMENTS FILE
    numpy ... Expected sha256 451a9b80... Got 6685043d...
（重复执行，Got 值每次都不同：6685043d / caacf93e）
```

用 curl 直接取件验证，发现返回的不是文件而是 HTML：

```
curl -k https://files.pythonhosted.org/.../pyyaml-6.0.3-cp313-cp313-win_amd64.whl
→ 81042 bytes, 首字节: b'<!DOCTYPE html><!-- STATUS OK --><html ...>'
```

即 `files.pythonhosted.org` 被替换为网络拦截页。已尝试 `--trusted-host pypi.org
--trusted-host files.pythonhosted.org`（绕过证书校验）与 `--no-cache-dir`
+ `pip cache purge`（排除缓存污染），均无效：内容本身被替换，不是证书问题。

**绕过方式**：本机 `C:\Users\72449\AppData\Roaming\Python\Python314\site-packages`
已有 numpy 2.3.5 / onnx 1.20.0 / pyyaml / pytest，通过 `PYTHONPATH` 启用即可，
本轮 Python 依赖问题因此解决。但 cmake 与 conan 都不在其中。

## 3. 大文件下载被截断

```
git clone --depth 1 https://github.com/PSAL-POSTECH/ONNXim.git
→ error: RPC failed; curl 56 schannel: server closed abruptly (missing close_notify)
  fatal: early EOF / fetch-pack: invalid index-pack output   （约 11 分钟后失败）

curl codeload.github.com/.../ONNXim/tar.gz/refs/heads/master
→ 下载到 8,724,934 字节后：gzip: stdin: unexpected end of file
  重试用 -C - 断点续传 25 次，大小始终停在 8,724,934（服务端不支持 Range）
```

**绕过方式（成功）**：`git clone --depth 1 --filter=blob:none --no-checkout` 只取
提交与目录树，再用 `git sparse-checkout set src configs example tests scripts` 按需
取 blob，6 秒完成。因此**源码审计得以执行**，但构建仍不可行（见下）。

## 4. 构建工具缺失

| 工具 | 状态 |
|---|---|
| g++ (MinGW, E:\compiler\mingw-posix-sjlj) | 有 |
| git 2.55 | 有 |
| cmake（要求 >= 3.22.1） | **全盘搜索无 cmake.exe**（Program Files / Program Files (x86) / E:\compiler / mingw64 / anaconda） |
| conan == 1.57.0 | 无，且 PyPI 不可达 |
| Python 包（torch / onnxruntime） | torch 与 onnxruntime 均不在本机 site-packages |

ONNXim 的 `CMakeLists.txt` 还要求 5 个 git 子模块：`extern/onnx`、`extern/protobuf`、
`extern/booksim`、`extern/ramulator2`、`extern/torch2timeloop`，其中 onnx + protobuf
体积在 GB 量级，在当前会截断大文件的代理下无法取得。

## 5. 因此本轮没有做的事

- 没有构建 ONNXim，没有运行 `build/bin/Simulator`。
- 没有运行自带示例（`configs/systolic_ws_128x128_c4_simple_noc_tpuv4.json` +
  `example/models_list.json`）或 `tests/` 下的 GoogleTest。
- 没有用任何"假执行器"输出通过。计划合法性检查只检查计划本身，不产生 cycles。

## 6. 已执行的替代工作

- ONNXim 固定 commit 的**源码级能力审计**（见
  `runs/2026-09-09T16-51-02Z_backend-audit/onnxim_source_audit.json`）。
- 不依赖后端的部分：有来源 workload、计划 IR、合法性检查器、CPU 数值参考，
  均已实际运行并通过（见 `report.md`）。
