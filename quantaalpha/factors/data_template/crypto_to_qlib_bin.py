"""
crypto_to_qlib_bin.py
将 others/50币/ 下的 1h CSV 转换为 Qlib 能识别的 bin 目录结构。

Qlib 0.9.7 bin 文件命名规则：{freq}.{field}.bin
例如：$close.day.bin, $open.day.bin

输出目录：data/qlib/crypto_50/
├── calendars/calendar_day.txt
├── instruments/crypto_50.txt
└── features/{BTCUSDT,ETHUSDT,...}/
    ├── $close.day.bin  (+ .day.txt)
    ├── $open.day.bin   (+ .day.txt)
    ├── $high.day.bin   (+ .day.txt)
    ├── $low.day.bin    (+ .day.txt)
    ├── $volume.day.bin (+ .day.txt)
    ├── $factor.day.bin (+ .day.txt)     crypto 无复权，全 1.0
    ├── $change.day.bin (+ .day.txt)     crypto 无涨跌停，全 0.0
    ├── adjclose.day.bin                 = $close（crypto 不复权）
    ├── amount.day.bin                   = $close * $volume（成交额）
    └── vwap.day.bin                     = 需要小时级数据重新聚合

.txt 文件是 Qlib 的日历索引，格式：第一行 n_days，第二行起始日期。
"""

import numpy as np
import pandas as pd
from pathlib import Path

# ── 路径配置 ──────────────────────────────────────────────
CSV_DIR = Path(r"E:\py\github_QuantaAlpha\others\50币\50币\前 50 种加密货币历史（2020-2025 每小时）")
OUTPUT_DIR = Path(r"E:\py\github_QuantaAlpha\QuantaAlpha\data\qlib\crypto_50")

# 跳过的币种
SKIP = {"HOTUSDT"}

# 日线和小时线都要保留，用于 vwap 计算
FREQ = "day"


def csv_to_daily(csv_path: str | Path):
    """读取 CSV，返回日线和小时线 DataFrame。"""
    df = pd.read_csv(csv_path, parse_dates=["timestamp"])
    df = df.rename(columns={"timestamp": "datetime"})
    df = df.set_index("datetime").sort_index()

    hourly = df.copy()

    daily = pd.DataFrame({
        "$open":    df["open"].resample("D").first(),
        "$close":   df["close"].resample("D").last(),
        "$high":    df["high"].resample("D").max(),
        "$low":     df["low"].resample("D").min(),
        "$volume":  df["volume_from"].resample("D").sum(),
    })

    # amount = close * volume（近似成交额）
    daily["amount"] = daily["$close"] * daily["$volume"]

    # vwap：用小时级加权平均
    df["amount_hour"] = df["close"] * df["volume_from"]
    df["vol_hour"] = df["volume_from"]
    vwap = (df["amount_hour"].resample("D").sum()
            / df["vol_hour"].resample("D").sum())
    daily["vwap"] = vwap

    # 清除无效行
    daily = daily.dropna(subset=["$open", "$close"])

    return daily


def write_bin(data: np.ndarray, path: Path):
    """写入 float32 二进制文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    data.astype(np.float32).tofile(str(path))


def write_txt(n_days: int, start_date: str, path: Path):
    """写入 Qlib 日历索引文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{n_days}\n{start_date}\n", encoding="utf-8")


# ── 主流程 ────────────────────────────────────────────────
def main():
    csv_files = sorted(CSV_DIR.glob("*USDT_1h.csv"))
    print(f"找到 {len(csv_files)} 个 CSV 文件")

    # 1. 读取所有币的日线数据
    coin_daily = {}
    for csv_path in csv_files:
        coin = csv_path.name.replace("_1h.csv", "")
        if coin in SKIP:
            print(f"  跳过 {coin}")
            continue
        daily = csv_to_daily(csv_path)
        coin_daily[coin] = daily
        print(f"  读取 {coin}: {len(daily)} 天")

    # 2. 构建统一日历（所有币的日期并集，排序）
    all_dates = sorted(set().union(*(set(df.index) for df in coin_daily.values())))
    n_days = len(all_dates)
    start_date = all_dates[0].strftime("%Y-%m-%d")
    print(f"\n统一日历: {n_days} 天, 起始 {start_date}")

    # 3. 写 calendars/day.txt（Qlib 从文件名推断频率，必须叫 day.txt）
    cal_dir = OUTPUT_DIR / "calendars"
    cal_dir.mkdir(parents=True, exist_ok=True)
    cal_file = cal_dir / "day.txt"
    cal_file.write_text("\n".join(d.strftime("%Y-%m-%d") for d in all_dates) + "\n", encoding="utf-8")
    print(f"已保存: {cal_file}")

    # 4. 写 instruments/crypto_50.txt（Qlib 格式：symbol\tstart_time\tend_time，TSV）
    inst_dir = OUTPUT_DIR / "instruments"
    inst_dir.mkdir(parents=True, exist_ok=True)
    inst_file = inst_dir / "crypto_50.txt"
    coins = sorted(coin_daily.keys())
    end_date = all_dates[-1].strftime("%Y-%m-%d")
    with open(inst_file, "w", encoding="utf-8") as f:
        for coin in coins:
            start = coin_daily[coin].index[0].strftime("%Y-%m-%d")
            f.write(f"{coin}\t{start}\t{end_date}\n")
    print(f"已保存: {inst_file} ({len(coins)} 币, TSV 三列格式)")

    print(f"\n开始写 bin 文件...")

    # 5. 写 features/{coin}/*.day.bin
    feats_dir = OUTPUT_DIR / "features"
    feats_dir.mkdir(parents=True, exist_ok=True)

    for coin in coins:
        daily = coin_daily[coin]
        # Qlib 把 instrument lower() 作为目录名，所以必须用小写
        coin_dir = feats_dir / coin.lower()
        coin_dir.mkdir(parents=True, exist_ok=True)

        # 对齐到统一日历（缺失日期补 NaN）
        aligned = daily.reindex(all_dates)
        first_valid_idx = all_dates.index(daily.index[0]) if daily.index[0] in all_dates else 0

        def _prep(values, fill_nan_before=None):
            arr = values.values.astype(np.float32).copy()
            if fill_nan_before is not None and first_valid_idx > 0:
                arr[:first_valid_idx] = np.nan
            return arr

        # 5a. 写 7 个字段 + adjclose + amount + vwap
        # Qlib 内部会把 instrument 和 field 都 lower()，所以目录名和文件名必须小写
        fields = {
            "$open":     _prep(aligned["$open"]),
            "$close":    _prep(aligned["$close"]),
            "$high":     _prep(aligned["$high"]),
            "$low":      _prep(aligned["$low"]),
            "$volume":   _prep(aligned["$volume"]),
            "$factor":   np.where(np.arange(n_days) < first_valid_idx, np.nan, 1.0).astype(np.float32),
            "$change":   np.where(np.arange(n_days) < first_valid_idx, np.nan, 0.0).astype(np.float32),
            "adjclose":  _prep(aligned["$close"]),
            "amount":    _prep(aligned["amount"]),
            "vwap":      _prep(aligned["vwap"]),
        }

        for field_name, arr in fields.items():
            # Qlib 读取时会去掉 field 的第一个字符（$）再 lower()
            # 所以 $close → close, $open → open, $factor → factor
            clean_name = field_name[1:] if field_name.startswith("$") else field_name
            fname = f"{clean_name.lower()}.{FREQ.lower()}"
            write_bin(arr, coin_dir / f"{fname}.bin")
            write_txt(n_days, start_date, coin_dir / f"{fname}.txt")

        print(f"  写入 {coin} 的 {len(fields)} 个字段（含 .txt 索引）")

    print(f"\n全部完成！输出目录: {OUTPUT_DIR}")

    # 6. 输出一个文件树示例
    sample_dir = feats_dir / coins[0]
    print(f"\n示例：{coins[0]} 的文件列表：")
    for f in sorted(sample_dir.iterdir()):
        size = f.stat().st_size
        print(f"  {f.name:28s} {size:>10,} bytes")


if __name__ == "__main__":
    main()
