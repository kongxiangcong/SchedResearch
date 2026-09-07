import importlib.util
import json
import sys

names = ['numpy', 'onnx', 'onnxruntime', 'torch', 'openvino', 'tvm', 'vai_q_onnx', 'npu', 'pyxrt', 'pytest']
print(json.dumps({'python': sys.executable, 'version': sys.version,
                  'packages': {n: (spec.origin if (spec := importlib.util.find_spec(n)) else None)
                               for n in names}}, indent=2))
