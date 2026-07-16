import sys, io
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import numpy as np
from quantaalpha.factors.coder.expr_parser import parse_expression, parse_symbol
import quantaalpha.factors.coder.function_lib as func_lib

h5_path = PROJECT_ROOT / "git_ignore_folder/factor_implementation_source_data/daily_pv.h5"
df = pd.read_hdf(str(h5_path), key="data")

# 测试混合大小写函数名
test_exprs = [
    "-1 * Ts_Rank($volume, 5)",
    "Ts_Rank($close, 10)",
    "-1 * Ts_Rank($volume, 5) + Ts_Mean($close, 20)",
]

exec_globals = {'df': df, 'np': np, 'pd': pd}
for name in dir(func_lib):
    if not name.startswith('_'):
        obj = getattr(func_lib, name)
        if callable(obj):
            exec_globals[name.upper()] = obj  # 修复：统一大写注册

for expr in test_exprs:
    expr1 = parse_symbol(expr, df.columns)
    old_stdout = sys.stdout; sys.stdout = io.StringIO()
    try: expr2 = parse_expression(expr1)
    finally: sys.stdout = old_stdout
    for col in df.columns:
        if col.startswith("$"):
            expr2 = expr2.replace(col[1:], f"df['{col}']")
    try:
        result = eval(expr2, exec_globals)
        print(f"✅ {expr:50s} → len={len(result) if hasattr(result,'__len__') else '?'}")
    except Exception as e:
        print(f"❌ {expr:50s} → {e}")
