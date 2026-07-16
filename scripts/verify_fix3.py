import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
# 强制重新加载
if "quantaalpha.factors.coder.function_lib" in sys.modules:
    del sys.modules["quantaalpha.factors.coder.function_lib"]

import quantaalpha.factors.coder.function_lib as func_lib

# 检查混合大小写别名是否存在
checks = ["TS_RANK", "Ts_Rank", "ts_rank", "TS_MEAN", "Ts_Mean", "ts_mean",
           "DELAY", "Delay", "delay", "SIGN", "Sign", "sign"]
for name in checks:
    exists = hasattr(func_lib, name)
    obj = getattr(func_lib, name, None)
    print(f"  {name:15s} = {'✅' if exists else '❌'} {type(obj).__name__ if exists else ''}")
