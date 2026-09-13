# Enable the isolated Python environment for this infrastructure directory.
# Usage (Git Bash):  source scripts/env.sh
INFRA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_SITE="C:/Users/72449/AppData/Roaming/Python/Python314/site-packages"

export PYTHONPATH="$INFRA_DIR/src;$USER_SITE"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUTF8=1

python --version
python -c "import numpy, onnx, pytest; print('numpy', numpy.__version__, '| onnx', onnx.__version__, '| pytest', pytest.__version__)"
