import sys, io, os
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import numpy as np
from quantaalpha.factors.coder.expr_parser import parse_expression, parse_symbol
import quantaalpha.factors.coder.function_lib as func_lib

h5_path = PROJECT_ROOT / "git_ignore_folder/factor_implementation_source_data/daily_pv.h5"
print(f"[1] daily_pv.h5 exists: {h5_path.exists()}")

if h5_path.exists():
    df = pd.read_hdf(str(h5_path), key="data")
    print(f"[2] df shape: {df.shape}, index: {df.index.names}, cols: {list(df.columns[:8])}")

    # 测试 LLM 生成的 expression
    expr = "(DELAY($close, 5) / DELAY($close, 1) - 1) * SIGN(DELAY($volume, 1) - (TS_MEAN($volume, 20) + 1.5 * TS_STD($volume, 20)))"
    name = "Short_Term_Reversal_Volume_Spike_5D"

    print(f"[3] Raw expr: {expr}")

    # parse_symbol
    expr1 = parse_symbol(expr, df.columns)
    print(f"[4] After parse_symbol: {expr1}")

    # parse_expression
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        expr2 = parse_expression(expr1)
    finally:
        sys.stdout = old_stdout
    print(f"[5] After parse_expression: {expr2}")

    # 替换 $var → df['$var']
    for col in df.columns:
        if col.startswith("$"):
            expr2 = expr2.replace(col[1:], f"df['{col}']")
    print(f"[6] After var replace: {expr2[:200]}...")

    # 构造 exec 环境
    exec_globals = {"df": df, "np": np, "pd": pd}
    for fname in dir(func_lib):
        if not fname.startswith("_"):
            obj = getattr(func_lib, fname)
            if callable(obj):
                exec_globals[fname] = obj

    print(f"[7] exec environment keys sample: {list(exec_globals.keys())[:15]}")

    try:
        result = eval(expr2, exec_globals)
        print(f"[8] ✅ Eval SUCCESS: type={type(result)}, ", end="")
        if isinstance(result, pd.Series):
            print(f"len={len(result)}, name={result.name}, NaN%={result.isna().mean()*100:.2f}%")
        elif isinstance(result, pd.DataFrame):
            print(f"shape={result.shape}")
        else:
            print(f"value={result}")
    except Exception as e:
        print(f"[8] ❌ Eval FAILED: {e}")

    # 测试简单的对照 expression
    simple_expr = "-1 * Ts_Rank($volume, 5)"
    print(f"\n[Test B] Simple expr: {simple_expr}")
    expr1b = parse_symbol(simple_expr, df.columns)
    old_stdout = sys.stdout; sys.stdout = io.StringIO()
    try: expr2b = parse_expression(expr1b)
    finally: sys.stdout = old_stdout
    for col in df.columns:
        if col.startswith("$"):
            expr2b = expr2b.replace(col[1:], f"df['{col}']")
    try:
        result_b = eval(expr2b, exec_globals)
        if isinstance(result_b, pd.Series):
            print(f"  ✅ Simple eval OK: len={len(result_b)}, NaN%={result_b.isna().mean()*100:.2f}%")
        else:
            print(f"  ⚠️ Result type: {type(result_b)}")
    except Exception as e:
        print(f"  ❌ Simple eval FAILED: {e}")

    # 检查 function_lib 中有哪些 TS_ 函数
    ts_funcs = [n for n in dir(func_lib) if n.startswith("TS_")]
    print(f"\n[Info] TS_ functions in lib: {ts_funcs}")
    
    # 检查 SIGN 是否存在
    print(f"[Info] SIGN exists: {'SIGN' in dir(func_lib)}")
else:
    print("[!] daily_pv.h5 not found, listing dir:")
    for f in (PROJECT_ROOT / "git_ignore_folder/factor_implementation_source_data").iterdir():
        print(f"  {f.name} ({f.stat().st_size/1e6:.1f} MB)")
