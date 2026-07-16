"""
QuantaAlpha 数据下载脚本
从 HuggingFace 下载 QuantaAlpha/qlib_csi300 数据集
"""

import os
import sys
from huggingface_hub import hf_hub_download

REPO_ID = "QuantaAlpha/qlib_csi300"
REPO_TYPE = "dataset"
LOCAL_DIR = "./hf_data"

# 需要下载的文件（排除 README 和 .gitattributes）
FILES = [
    ("cn_data.zip", 492_502_328, "Qlib 行情数据（A 股 2016-2025）"),
    ("daily_pv.h5", 398_130_836, "预计算价量数据"),
    ("daily_pv_debug.h5", 1_407_056, "调试子集"),
]

def format_size(size_mb):
    if size_mb >= 1024:
        return f"{size_mb/1024:.1f} GB"
    return f"{size_mb:.1f} MB"

def main():
    print("=" * 60)
    print("QuantaAlpha 数据下载")
    print(f"来源: https://huggingface.co/datasets/{REPO_ID}")
    print(f"目标: {os.path.abspath(LOCAL_DIR)}")
    print("=" * 60)

    for filename, expected_size, description in FILES:
        filepath = os.path.join(LOCAL_DIR, filename)
        size_mb = expected_size / (1024 * 1024)

        # 检查是否已存在且大小匹配
        if os.path.exists(filepath):
            actual_size = os.path.getsize(filepath)
            if actual_size == expected_size:
                print(f"\n✅ [已存在] {filename} ({format_size(size_mb)}) — 跳过")
                continue
            else:
                print(f"\n⚠️  [不完整] {filename} 大小不匹配，重新下载...")

        print(f"\n📥 正在下载: {filename}")
        print(f"   大小: {format_size(size_mb)} | 说明: {description}")

        try:
            hf_hub_download(
                repo_id=REPO_ID,
                repo_type=REPO_TYPE,
                filename=filename,
                local_dir=LOCAL_DIR,
                local_dir_use_symlinks=False,
            )
            print(f"   ✅ 下载完成")
        except Exception as e:
            print(f"   ❌ 下载失败: {e}")
            print(f"   提示: 可能是网络问题，可重新运行本脚本继续")
            sys.exit(1)

    print("\n" + "=" * 60)
    print("✅ 所有文件下载完成！")
    print("=" * 60)

if __name__ == "__main__":
    main()
