import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
import quantaalpha.factors.coder.function_lib as func_lib

# 检查 TS_RANK 和 Ts_Rank
print("TS_RANK in dir:", "TS_RANK" in dir(func_lib))
print("Ts_Rank in dir:", "Ts_Rank" in dir(func_lib))
print("ts_rank in dir:", "ts_rank" in dir(func_lib))

# 检查 parse_expression 做了什么
from quantaalpha.factors.coder.expr_parser import parse_expression
import io

test_cases = [
    "Ts_Rank($volume, 5)",
    "TS_RANK($volume, 5)",
    "TsRank($volume, 5)",
    "TSRANK($volume, 5)",
]

for tc in test_cases:
    old_stdout = sys.stdout; sys.stdout = io.StringIO()
    try:
        result = parse_expression(tc)
    finally:
        sys.stdout = old_stdout
    print(f"  {tc:30s} → {result}")
