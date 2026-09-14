> 历史环境记录，非实时状态；当前使用方法见[infra README](../README.md)，能力见[实验能力线](../../../docs/progress/experimental-capabilities.md)。

# 环境

## 主机

| 项 | 值 |
|---|---|
| OS | Windows（win32） |
| Shell | PowerShell 7（首选）；Git Bash 用于部分工具 |
| Python | `C:\Python314\python.exe`，3.14.0 |
| numpy / onnx / pyyaml / pytest | 2.3.5 / 1.20.0 / 6.0.3 / 9.0.2 |
| 编译器 | MinGW g++（`E:\compiler\mingw-posix-sjlj\mingw64\bin\g++`） |
| cmake | **无** |
| conan | **无** |
| WSL2 | **被主机安全策略拉黑**（`wsl.exe` 在 Program Blacklist） |

## 为什么不建 venv

`scripts/setup_env.ps1` 会创建独立 venv 并 `pip install -r requirements.txt`，
**但在本机必然失败**：`files.pythonhosted.org` 被网络过滤替换成 HTML 拦截页。

验证过程【执行】：

```
curl -k https://files.pythonhosted.org/.../pyyaml-6.0.3-cp313-cp313-win_amd64.whl
→ 81042 bytes，首字节 b'<!DOCTYPE html><!-- STATUS OK -->'
```

因此本轮改用主机已有的用户级 site-packages：

```
C:\Users\72449\AppData\Roaming\Python\Python314\site-packages
```

通过 `PYTHONPATH` 启用（`scripts/env.ps1` / `scripts/env.sh`）。这是**隔离的用户级依赖**，
不写入全局 site-packages，也不污染系统 Python。

## 网络状态（实测）

| 目标 | 状态 |
|---|---|
| `files.pythonhosted.org` | 被替换为 HTML 拦截页 |
| `api.github.com`、`raw.githubusercontent.com` | 可达，偶发 TLS 重置，重试可用 |
| `codeload.github.com` | 可达，但大归档在约 8.7 MB 处截断 |
| `github.com/.../releases/download/...` | Empty reply from server |
| 代理 | `127.0.0.1:51780`，提供不受信任的证书 |

## 顺带说明

`requirements.txt` 中的版本号是本轮实际使用的版本（numpy 2.3.5 等），用于在新环境复现；
它描述的是**已验证可用的组合**，不是本机通过 pip 安装得到的。
