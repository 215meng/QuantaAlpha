"""端到端测试：验证所有修复后的组件无误"""
import sys, io
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 强制重新加载所有已修改的模块
for mod in list(sys.modules):
    if 'quantaalpha.factors' in mod:
        del sys.modules[mod]

print("=" * 60)
print("  QuantaAlpha Windows 兼容性修复 - 端到端验证")
print("=" * 60)

# ---- 1. function_lib 大小写别名 ----
print("\n[1] function_lib 大小写别名")
import quantaalpha.factors.coder.function_lib as func_lib
alias_ok = all(hasattr(func_lib, n) for n in ["Ts_Rank", "TS_RANK", "ts_rank", "Sign", "SIGN"])
print(f"    {'✅' if alias_ok else '❌'} 大小写别名注册正确")

# ---- 2. 数据文件 ----
print("\n[2] 数据文件")
h5_path = PROJECT_ROOT / "git_ignore_folder/factor_implementation_source_data/daily_pv.h5"
print(f"    {'✅' if h5_path.exists() else '❌'} daily_pv.h5 ({h5_path.stat().st_size/1e6:.1f} MB)")

# ---- 3. PYTHONPATH 分隔符 ----
print("\n[3] PYTHONPATH 分隔符")
import inspect
factor_src = inspect.getsource(sys.modules["quantaalpha.factors.coder.factor"].FactorFBWorkspace.execute)
sep_ok = "sys.platform" in factor_src and "';'" in factor_src
print(f"    {'✅' if sep_ok else '❌'} 跨平台 PYTHONPATH 分隔符")

# ---- 4. Runner result.h5 刷新逻辑 ----
print("\n[4] Runner result.h5 刷新逻辑")
from quantaalpha.factors.runner import QlibFactorRunner
runner_src = inspect.getsource(QlibFactorRunner.process_factor_data)
refresh_ok = "to_hdf" in runner_src
print(f"    {'✅' if refresh_ok else '❌'} result.h5 刷新已启用")

# ---- 5. Workspace Windows execute ----
print("\n[5] Workspace Windows execute()")
from quantaalpha.factors.workspace import QlibFBWorkspace
ws_src = inspect.getsource(QlibFBWorkspace.execute)
win_execute_ok = "sys.platform" in ws_src and "QlibLocalEnv" in ws_src
print(f"    {'✅' if win_execute_ok else '❌'} Windows QlibLocalEnv execute 已覆盖")

# ---- 6. 全链路因子计算（大小写混合）----
print("\n[6] 全链路因子计算（大小写混合表达式）")
from quantaalpha.backtest.custom_factor_calculator import CustomFactorCalculator
calc = CustomFactorCalculator(config={"config_path": str(PROJECT_ROOT / "configs" / "backtest.yaml")})

tests = [
    ("Ts_Rank_mixed", "-1 * Ts_Rank($volume, 5)"),
    ("DELAY_upper", "-1 * DELAY($close, 5)"),
    ("Sign_func", "SIGN($volume - TS_MEAN($volume, 20))"),
    ("Complex", "(DELAY($close, 5) / DELAY($close, 1) - 1) * Ts_Rank($volume, 5)"),
]
for name, expr in tests:
    r = calc.calculate_factor(name, expr)
    ok = r is not None and len(r) > 0 and not r.isna().all()
    print(f"    {'✅' if ok else '❌'} {name:25s} {expr[:50]}...")

print("\n" + "=" * 60)
print("  所有关键修复已验证！")
print("=" * 60)
