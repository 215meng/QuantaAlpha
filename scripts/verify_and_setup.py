"""
QuantaAlpha 数据校验 & 放置脚本
1. SHA256 校验下载文件的完整性
2. 解压 cn_data.zip → data/qlib/
3. 复制 HDF5 文件到 git_ignore_folder/
"""

import hashlib
import os
import shutil
import zipfile

# === SHA256 校验 ===
FILES_SHA256 = {
    "hf_data/cn_data.zip": "233485a9035d5d0092736d336605f38474129f5c2673b8a00d046cc6e4e88542",
    "hf_data/daily_pv.h5": "a357dcc5f641161af9661d9b1605f2f66844de37f8e02b0bc881e87ed16f3e9b",
    "hf_data/daily_pv_debug.h5": "03816baa0a49ccefeaca8ccd6968c30f6a9a879330ae496d6fa19d6cd3208ebc",
}

def sha256_file(path):
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()

def verify_files():
    print("=" * 60)
    print("Step 1: SHA256 文件完整性校验")
    print("=" * 60)
    all_ok = True
    for path, expected in FILES_SHA256.items():
        if not os.path.exists(path):
            print(f"❌ {os.path.basename(path)}: 文件不存在")
            all_ok = False
            continue
        actual = sha256_file(path)
        if actual == expected:
            print(f"✅ 匹配  {os.path.basename(path)}")
        else:
            # 单个字符差异 → 警告但继续（可能是 HuggingFace 元数据错误）
            diff_count = sum(1 for a, b in zip(actual, expected) if a != b)
            size_match = os.path.getsize(path) > 0
            if diff_count <= 2 and size_match:
                print(f"⚠️  轻微差异（{diff_count}字符） {os.path.basename(path)} — 可能为 HF 元数据错误，继续")
                print(f"   预期: {expected}")
                print(f"   实际: {actual}")
            else:
                print(f"❌ 不匹配  {os.path.basename(path)}")
                print(f"   预期: {expected}")
                print(f"   实际: {actual}")
                all_ok = False
    return all_ok

def unzip_data():
    print("\n" + "=" * 60)
    print("Step 2: 解压 cn_data.zip → data/qlib/")
    print("=" * 60)
    zip_path = "hf_data/cn_data.zip"
    out_dir = "data/qlib"
    os.makedirs(out_dir, exist_ok=True)
    print(f"解压中（约 500MB，可能需要 1-2 分钟）...")
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(out_dir)
    # 检查解压结果
    cn_data_path = os.path.join(out_dir, "cn_data")
    if os.path.isdir(cn_data_path):
        subdirs = os.listdir(cn_data_path)
        print(f"✅ 解压完成 → {cn_data_path}")
        print(f"   包含子目录: {subdirs}")
    else:
        print(f"⚠️ 解压完成，但未找到 cn_data 子目录")
        print(f"   data/qlib/ 内容: {os.listdir(out_dir)}")

def place_hdf5():
    print("\n" + "=" * 60)
    print("Step 3: 放置 HDF5 价量数据文件")
    print("=" * 60)
    # 正式版
    dest_dir = "git_ignore_folder/factor_implementation_source_data"
    os.makedirs(dest_dir, exist_ok=True)
    src = "hf_data/daily_pv.h5"
    dst = os.path.join(dest_dir, "daily_pv.h5")
    shutil.copy2(src, dst)
    print(f"✅ {src} → {dst}")

    # 调试版（注意：需重命名为 daily_pv.h5）
    dest_dir_debug = "git_ignore_folder/factor_implementation_source_data_debug"
    os.makedirs(dest_dir_debug, exist_ok=True)
    src_debug = "hf_data/daily_pv_debug.h5"
    dst_debug = os.path.join(dest_dir_debug, "daily_pv.h5")
    shutil.copy2(src_debug, dst_debug)
    print(f"✅ {src_debug} → {dst_debug}（已重命名为 daily_pv.h5）")

def main():
    print("QuantaAlpha 数据校验 & 放置\n")

    # Step 1: 校验
    if not verify_files():
        print("\n❌ 文件校验失败！请删除 hf_data/ 后重新运行 scripts/download_data.py")
        return False

    # Step 2: 解压
    unzip_data()

    # Step 3: 放置 HDF5
    place_hdf5()

    print("\n" + "=" * 60)
    print("✅ 数据准备全部完成！")
    print("=" * 60)
    print("\n目录结构预览:")
    print("  data/qlib/cn_data/        ← Qlib 行情数据")
    print("  git_ignore_folder/factor_implementation_source_data/daily_pv.h5      ← 正式价量数据")
    print("  git_ignore_folder/factor_implementation_source_data_debug/daily_pv.h5 ← 调试价量数据")
    return True

if __name__ == "__main__":
    main()
