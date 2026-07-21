"""
合成 BTC_ETH_EQ benchmark 数据。

读取 BTC 和 ETH 的 bin 数据，计算等权平均，输出到 crypto_50/features/btc_eth_eq/。
同时在 instruments/crypto_50.txt 追加 BTC_ETH_EQ。
"""

import struct
import numpy as np
from pathlib import Path

CRYPTO_DIR = Path(__file__).resolve().parent.parent / "data" / "qlib" / "crypto_50"
FIELDS = [
    "adjclose", "amount", "change", "close", "factor",
    "high", "low", "open", "volume", "vwap"
]

def read_bin(path: Path) -> np.ndarray:
    """读取 bin 文件，返回 float32 数组"""
    return np.fromfile(str(path), dtype=np.float32)

def write_bin(path: Path, data: np.ndarray):
    """写入 bin 文件"""
    path.parent.mkdir(parents=True, exist_ok=True)
    data.astype(np.float32).tofile(str(path))

def write_txt(path: Path, count: int, start_date: str):
    """写入 txt 索引文件"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(path), "w") as f:
        f.write(f"{count}\n{start_date}\n")

def main():
    btc_dir = CRYPTO_DIR / "features" / "btcusdt"
    eth_dir = CRYPTO_DIR / "features" / "ethusdt"
    out_dir = CRYPTO_DIR / "features" / "btc_eth_eq"

    if not btc_dir.exists() or not eth_dir.exists():
        print(f"ERROR: BTC or ETH data not found")
        print(f"  BTC: {btc_dir}")
        print(f"  ETH: {eth_dir}")
        return

    # 获取起始日期（从 close.day.txt 读取）
    btc_txt = btc_dir / "close.day.txt"
    with open(str(btc_txt)) as f:
        lines = f.read().strip().split("\n")
        start_date = lines[1] if len(lines) > 1 else "2019-12-14"

    print(f"Start date: {start_date}")
    print(f"Output dir: {out_dir}")

    for field in FIELDS:
        btc_data = read_bin(btc_dir / f"{field}.day.bin")
        eth_data = read_bin(eth_dir / f"{field}.day.bin")

        # 等权平均
        min_len = min(len(btc_data), len(eth_data))
        eq_data = 0.5 * btc_data[:min_len] + 0.5 * eth_data[:min_len]

        write_bin(out_dir / f"{field}.day.bin", eq_data)
        write_txt(out_dir / f"{field}.day.txt", min_len, start_date)
        print(f"  {field}: {min_len} records")

    # 追加到 instruments/crypto_50.txt
    inst_file = CRYPTO_DIR / "instruments" / "crypto_50.txt"
    with open(str(inst_file), "r") as f:
        content = f.read()

    if "BTC_ETH_EQ" not in content:
        with open(str(inst_file), "a") as f:
            f.write(f"BTC_ETH_EQ\t2019-12-14\t2025-08-29\n")
        print(f"\nAppended BTC_ETH_EQ to {inst_file}")
    else:
        print(f"\nBTC_ETH_EQ already exists in {inst_file}")

    print("\nDone!")

if __name__ == "__main__":
    main()
