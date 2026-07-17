"""
generate_crypto.py
将 others/50币/ 下的 1h CSV 转换为日线 h5，供因子挖掘侧使用。

输出：
  - daily_pv_all.h5   : 全量 49 币（HOTUSDT 因数据脏被跳过）
  - daily_pv_debug.h5: 前 10 币（用于 CoSTEER 快速调试）

h5 格式：
  MultiIndex(instrument, datetime)
  columns: $open, $close, $high, $low, $volume, $return
"""

import pandas as pd
from pathlib import Path

# ── 路径配置 ──────────────────────────────────────────────
CSV_DIR = Path(r"E:\py\github_QuantaAlpha\others\50币\50币\前 50 种加密货币历史（2020-2025 每小时）")
OUTPUT_DIR = Path(__file__).parent  # data_template/

# 跳过的币种（数据质量差）
SKIP = {"HOTUSDT"}


def csv_to_daily(csv_path: str | Path) -> pd.DataFrame:
    """将单个 1h CSV 聚合为日线 DataFrame。"""
    df = pd.read_csv(csv_path, parse_dates=["timestamp"])
    df = df.rename(columns={"timestamp": "datetime"})
    df = df.set_index("datetime").sort_index()

    # 按日聚合 OHLCV
    daily = pd.DataFrame({
        "$open":   df["open"].resample("D").first(),
        "$close":  df["close"].resample("D").last(),
        "$high":   df["high"].resample("D").max(),
        "$low":    df["low"].resample("D").min(),
        "$volume": df["volume_from"].resample("D").sum(),
    })

    # 日收益率
    daily["$return"] = daily["$close"].pct_change().fillna(0)

    # 去掉全 NaN 的行（新币上线前没有数据）
    daily = daily.dropna(subset=["$open", "$close"])

    return daily


# ── 主流程 ────────────────────────────────────────────────
def main():
    csv_files = sorted(CSV_DIR.glob("*USDT_1h.csv"))
    print(f"找到 {len(csv_files)} 个 CSV 文件")

    all_dfs = []
    for csv_path in csv_files:
        coin = csv_path.name.replace("_1h.csv", "")
        if coin in SKIP:
            print(f"  跳过 {coin}（数据脏）")
            continue
        daily = csv_to_daily(csv_path)
        daily["instrument"] = coin
        daily = daily.set_index("instrument", append=True)
        all_dfs.append(daily)
        print(f"  处理 {coin}: {len(daily)} 天")

    # 合并成 MultiIndex
    full = pd.concat(all_dfs)
    full = full.reorder_levels(["instrument", "datetime"]).sort_index()
    print(f"\n全量数据: {full.index.get_level_values('instrument').nunique()} 币, "
          f"{full.index.get_level_values('datetime').nunique()} 天, "
          f"共 {len(full)} 行")

    # 保存全量
    all_h5 = OUTPUT_DIR / "daily_pv_all.h5"
    full.to_hdf(all_h5, key="data")
    print(f"已保存: {all_h5}")

    # 保存 debug 子集（前 10 币）
    debug_n = 10
    debug_instruments = full.index.get_level_values("instrument").unique()[:debug_n]
    debug = full.loc[debug_instruments]
    debug_h5 = OUTPUT_DIR / "daily_pv_debug.h5"
    debug.to_hdf(debug_h5, key="data")
    print(f"已保存: {debug_h5} ({debug_n} 币)")


if __name__ == "__main__":
    main()
