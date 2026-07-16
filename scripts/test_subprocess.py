"""测试子进程执行 factor.py"""
import os
import subprocess
from pathlib import Path

# 创建测试目录和文件
ws = Path("data/results/workspace/test_subprocess")
ws.mkdir(parents=True, exist_ok=True)
(ws / "factor.py").write_text("""
import pandas as pd
print("factor.py started!")
df = pd.read_hdf('./daily_pv.h5', key='data')
print(f"Loaded data: {df.shape}")
df['test'] = df['$close'] * 2
df['test'].to_hdf('result.h5', key='data')
print("Done!")
""")

# 检查源数据
src = Path("git_ignore_folder/factor_implementation_source_data_debug")
print(f"源数据目录: {src.absolute()}")
print(f"源数据存在: {src.exists()}")

# 硬链接数据文件到 workspace
import platform
for f in src.iterdir():
    dest = ws / f.name
    if dest.exists():
        dest.unlink()
    if platform.system() == "Windows":
        os.link(f, dest)
    else:
        os.symlink(f, dest)
    print(f"链接: {f.name} -> {dest} (存在: {dest.exists()})")

# 测试执行
cmd = f"python {(ws / 'factor.py').absolute()}"
print(f"\n执行命令: {cmd}")
print(f"cwd: {ws}")
try:
    result = subprocess.check_output(
        cmd,
        shell=True,
        cwd=str(ws),
        stderr=subprocess.STDOUT,
        env=os.environ.copy(),
        timeout=30,
    )
    print(f"输出: {result.decode()[:500]}")
except subprocess.CalledProcessError as e:
    print(f"执行失败! 退出码: {e.returncode}")
    print(f"输出: {e.output.decode()[:500]}")
except Exception as e:
    print(f"异常: {type(e).__name__}: {e}")
