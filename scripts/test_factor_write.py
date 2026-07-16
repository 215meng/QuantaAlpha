"""
模拟因子代码写入与执行，定位 factor.py 为什么没被创建
"""
import os
import tempfile
from pathlib import Path

# 测试 1: 模拟 QlibFBWorkspace.inject_code()
print("=== 测试 inject_code ===")
from quantaalpha.factors.workspace import QlibFBWorkspace

ws = QlibFBWorkspace()
ws.prepare()
print(f"workspace_path: {ws.workspace_path}")
print(f"exists: {ws.workspace_path.exists()}")

factor_code = """
import pandas as pd
def calculate_factor(expr, name):
    df = pd.read_hdf('./daily_pv.h5', key='data')
    df[name] = df['$close'] * 2
    result = df[name].astype('float64')
    result.to_hdf('result.h5', key='data')

if __name__ == '__main__':
    expr = "test"
    name = "test_factor"
    calculate_factor(expr, name)
"""

ws.inject_code(**{"factor.py": factor_code})

factor_path = ws.workspace_path / "factor.py"
print(f"factor.py 存在: {factor_path.exists()}")

if not factor_path.exists():
    # 列出 workspace 所有文件
    print("workspace 内容:")
    for f in ws.workspace_path.rglob("*"):
        print(f"  {f.relative_to(ws.workspace_path)}")

# 测试 2: 尝试 execute（不带实际数据，只测试代码是否能被找到）
print("\n=== 测试 execute 执行路径 ===")
try:
    # 不实际 execute，只检查 injected 文件
    injected = ws.get_factor_py_code()
    print(f"get_factor_py_code 返回: {injected[:100] if injected else None}")
except Exception as e:
    print(f"get_factor_py_code 错误: {e}")
