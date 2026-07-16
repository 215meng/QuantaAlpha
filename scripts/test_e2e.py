"""端到端模拟因子代码写入、数据链接、执行"""
import os
import sys
from pathlib import Path

# 确保项目根在路径里
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 打 SSL 补丁
import ssl, certifi
ssl.create_default_context = lambda purpose=ssl.Purpose.SERVER_AUTH, cafile=None, capath=None, cadata=None: (
    ctx := ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
    setattr(ctx, 'minimum_version', ssl.TLSVersion.TLSv1_2),
    ctx.load_verify_locations(cafile=cafile or certifi.where(), capath=capath, cadata=cadata),
    ctx
)[-1] if False else None or (lambda: (
    (ctx := ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)),
    setattr(ctx, 'minimum_version', ssl.TLSVersion.TLSv1_2),
    ctx.load_verify_locations(cafile=certifi.where()),
    ctx
)[-1])()

print("=== 端到端因子执行模拟 ===\n")

# 1. 创建一个模拟 workspace
import tempfile
from quantaalpha.factors.coder.factor import FactorFBWorkspace, FactorTask

task = FactorTask(
    factor_name="TestFactor",
    factor_description="test factor",
    factor_formulation=None,
    factor_expression="TS_ZSCORE(($close - $open) * $volume / ($high - $low + 1e-8), 20)",
    factor_implementation=None,
    variables={},
)

ws = FactorFBWorkspace(task)
print(f"1. workspace 创建: {ws.workspace_path}")
print(f"   factor.py 存在: {(ws.workspace_path / 'factor.py').exists()}")

# 2. inject_code
ws.inject_code(**{"factor.py": """
import pandas as pd
import numpy as np
import os

def calculate_factor(df, name):
    expr = parse_expr(df)
    df[name] = expr
    result = df[name].astype(np.float64)
    result.to_hdf('result.h5', key='data')

if __name__ == '__main__':
    df = pd.read_hdf('./daily_pv.h5', key='data')
    df['test'] = df['$close'] * 2
    df['test'].to_hdf('result.h5', key='data')
"""})

factor_path = ws.workspace_path / "factor.py"
print(f"\n2. inject_code 后:")
print(f"   factor.py 存在: {factor_path.exists()}")

# 3. 尝试 execute（Debug 模式）
print(f"\n3. 执行 factor.py (Debug 模式)...")
try:
    feedback, result_df = ws.execute(data_type="Debug")
    print(f"   反馈: {feedback[:100]}")
    print(f"   result.h5 存在: {(ws.workspace_path / 'result.h5').exists()}")
    if result_df is not None:
        print(f"   因子值 shape: {result_df.shape}")
except Exception as e:
    print(f"   ❌ 执行失败: {type(e).__name__}: {str(e)[:200]}")
