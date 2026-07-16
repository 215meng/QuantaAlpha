import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from quantaalpha.backtest.custom_factor_calculator import CustomFactorCalculator

calc = CustomFactorCalculator(config={"config_path": str(PROJECT_ROOT / "configs" / "backtest.yaml")})

# 测试混合大小写函数名
test_cases = [
    ("Ts_Rank_Test", "-1 * Ts_Rank($volume, 5)"),
    ("TS_RANK_Test", "-1 * TS_RANK($volume, 5)"),
    ("Mixed_Case", "-1 * Ts_Rank($volume, 5) + Ts_Mean($close, 20)"),
]

for name, expr in test_cases:
    result = calc.calculate_factor(name, expr)
    if result is not None and len(result) > 0:
        print(f"✅ {name:20s} ({expr[:40]}...) → 正常")
    else:
        print(f"❌ {name:20s} → result={result}")
