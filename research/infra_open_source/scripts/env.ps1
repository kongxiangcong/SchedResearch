# Enable the isolated Python environment for this infrastructure directory.
# No pip is required on this host: the user-level site-packages already carry
# numpy / onnx / pyyaml / pytest, and PyPI is unreachable here.
# Usage (PowerShell 7):  . .\scripts\env.ps1

$ErrorActionPreference = "Stop"
$InfraDir = Split-Path -Parent $PSScriptRoot
$UserSite = "C:\Users\72449\AppData\Roaming\Python\Python314\site-packages"

$env:PYTHONPATH = "$InfraDir\src;$UserSite"
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:PYTHONUTF8 = "1"

"PYTHONPATH = $env:PYTHONPATH"
python --version
python -c "import numpy, onnx, pytest; print('numpy', numpy.__version__, '| onnx', onnx.__version__, '| pytest', pytest.__version__)"
