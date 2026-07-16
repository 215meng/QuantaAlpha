"""
直接生成一个测试因子写入因子库，用于验证回测管线。
使用表达式：-1 * Ts_Rank($volume, 5)  （经典的价量类因子）
"""
import json
import hashlib
import os
import sys
from datetime import datetime
from pathlib import Path

# 确保项目根目录在路径中
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from quantaalpha.backtest.custom_factor_calculator import CustomFactorCalculator


def add_factor_to_library(
    factor_name: str,
    factor_expression: str,
    factor_description: str,
    factor_formulation: str,
    library_path: str,
):
    """计算因子值并写入因子库 JSON。"""
    lib_path = Path(library_path)
    lib_path.parent.mkdir(parents=True, exist_ok=True)

    # 加载或创建 library
    if lib_path.exists():
        with open(lib_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "total_factors": 0,
                "version": "1.0",
            },
            "factors": {},
        }

    # 计算因子值
    config_path = PROJECT_ROOT / "configs" / "backtest.yaml"
    calc = CustomFactorCalculator(config={"config_path": str(config_path)})

    print(f"正在计算因子: {factor_name}")
    print(f"  表达式: {factor_expression}")

    result = calc.calculate_factor(factor_name, factor_expression)

    if result is None or result.empty:
        print("  ❌ 因子计算失败")
        return False

    print(f"  ✅ 因子计算成功: {len(result)} 条数据")

    # 保存 result.h5 到 workspace 目录
    ws_path = PROJECT_ROOT / "data" / "results" / "workspace_manual" / factor_name
    ws_path.mkdir(parents=True, exist_ok=True)
    result_h5 = ws_path / "result.h5"
    result.to_hdf(str(result_h5), key="data")
    print(f"  保存因子值到: {result_h5}")

    # 同步到 MD5 缓存
    md5_key = hashlib.md5(factor_expression.encode()).hexdigest()
    cache_dir = PROJECT_ROOT / "data" / "results" / "factor_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    pkl_file = cache_dir / f"{md5_key}.pkl"
    result.to_pickle(str(pkl_file))
    print(f"  同步缓存到: {pkl_file}")

    # 构造因子条目
    factor_id = hashlib.md5(f"{factor_name}_{factor_expression}".encode()).hexdigest()[:16]

    factor_entry = {
        "factor_id": factor_id,
        "factor_name": factor_name,
        "factor_expression": factor_expression,
        "factor_implementation_code": "",
        "factor_description": factor_description,
        "factor_formulation": factor_formulation,
        "cache_location": {
            "workspace_suffix": "manual",
            "workspace_path": str(ws_path.parent),
            "factor_dir": factor_name,
            "result_h5_path": str(result_h5),
        },
        "metadata": {
            "experiment_id": "manual_test",
            "round_number": 0,
            "evolution_phase": "manual",
            "trajectory_id": "",
            "parent_trajectory_ids": [],
            "hypothesis": "手动生成的测试因子",
            "initial_direction": "价量因子测试",
            "planning_direction": "",
            "created_at": datetime.now().isoformat(),
        },
        "backtest_results": {},
        "feedback": {},
    }

    data["factors"][factor_id] = factor_entry

    data["metadata"]["last_updated"] = datetime.now().isoformat()
    data["metadata"]["total_factors"] = len(data["factors"])

    with open(lib_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n✅ 因子已写入库: {lib_path}")
    print(f"   因子总数: {len(data['factors'])}")
    return True


if __name__ == "__main__":
    # 使用一条经典的 Alpha158 风格因子（保证表达式解析器能处理）
    test_factors = [
        {
            "name": "Volume_Reversal_5D",
            "expression": "-1 * Ts_Rank($volume, 5)",
            "description": "短期成交量反转因子：过去5天成交量的横截面排名取负",
            "formulation": "-1 * Ts_Rank(volume, 5)",
        },
    ]

    library_path = PROJECT_ROOT / "data" / "factorlib" / "all_factors_library.json"

    for factor in test_factors:
        add_factor_to_library(
            factor_name=factor["name"],
            factor_expression=factor["expression"],
            factor_description=factor["description"],
            factor_formulation=factor["formulation"],
            library_path=str(library_path),
        )
