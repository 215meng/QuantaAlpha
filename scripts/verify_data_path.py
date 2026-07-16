"""验证 factor.py 能正确计算数据路径"""
from pathlib import Path

# 模拟 factor.py 中的路径计算逻辑
_factor_py = Path(__file__).resolve().parent.parent / "factors" / "coder" / "factor.py"
_project_root = _factor_py.parent.parent.parent.parent
print(f"factor.py 位置: {_factor_py}")
print(f"项目根目录:   {_project_root}")
print()

# 模拟从 config 中取得的相对路径
data_folder_debug = "git_ignore_folder/factor_implementation_source_data_debug"
data_folder = "git_ignore_folder/factor_implementation_source_data"

source = _project_root / data_folder_debug
print(f"Debug 数据路径: {source}")
print(f"  存在: {source.exists()}")
print(f"  内容: {list(source.iterdir()) if source.exists() else 'N/A'}")
print()

source2 = _project_root / data_folder
print(f"正式 数据路径: {source2}")
print(f"  存在: {source2.exists()}")
if source2.exists():
    print(f"  内容: {[f.name for f in source2.iterdir()][:5]}")
