"""
端到端测试：用完全未改的 GitHub 原始代码，定位 factor.py 执行失败的真实原因
"""
import os
import sys
import platform
from pathlib import Path

# SSL 补丁（仅此项是非改不可的 Windows 兼容修复）
import ssl as _ssl
import certifi as _certifi
_ssl.create_default_context = lambda purpose=_ssl.Purpose.SERVER_AUTH, cafile=None, capath=None, cadata=None: (
    (ctx := _ssl.SSLContext(_ssl.PROTOCOL_TLS_CLIENT)),
    setattr(ctx, 'minimum_version', _ssl.TLSVersion.TLSv1_2),
    ctx.load_verify_locations(cafile=cafile or _certifi.where()),
    ctx
)[-1]

# ========== 复现原始代码中的路径计算 ==========
print("=== 复现原始 windows 分支代码的路径计算 ===\n")

# 模拟 rdagent 的 workspace_path 结构
# run.sh 设置 WORKSPACE_PATH = data/results/workspace_exp_XXXX
# RDagent 在 WORKSPACE_PATH 下创建 <uuid>
workspace_path = Path("data/results/workspace_exp_test/1c8a404e92fe468b90ed631d960080c9").resolve()

print(f"workspace_path: {workspace_path}")
print(f"workspace_path.is_absolute(): {workspace_path.is_absolute()}")
print(f"  parent:           {workspace_path.parent}")
print(f"  parent.parent:    {workspace_path.parent.parent}")
print(f"  parent.parent.parent: {workspace_path.parent.parent.parent}")
print()

# 原始代码中的 source_data_path 计算
data_folder_debug = "git_ignore_folder/factor_implementation_source_data_debug"
source_data_path_orig = workspace_path.parent.parent.parent / data_folder_debug
print(f"原始代码 source_data_path: {source_data_path_orig}")
print(f"  存在: {source_data_path_orig.exists()}")

# 正确的项目根目录应该在哪个层级？
# 数据文件实际位于: <项目根>/git_ignore_folder/factor_implementation_source_data_debug
# 实际存在于此路径
actual_data = Path("git_ignore_folder/factor_implementation_source_data_debug").resolve()
print(f"\n实际数据路径: {actual_data}")
print(f"  存在: {actual_data.exists()}")

# 反向推算 workspace_path 应该是什么结构才能使 parent.parent.parent 指向正确位置
# parent.parent.parent = 项目根 → workspace_path = 项目根/x/y/z
# 但实际是: workspace_path = data/results/workspace_exp_xxx/<uuid>
# parent.parent.parent = data/
# parent.parent.parent.parent = 项目根 ✅ 这才是正确的！

print(f"\n结论: 原始代码的 parent.parent.parent 是错误的！")
print(f"  parent.parent.parent = {workspace_path.parent.parent.parent}")
print(f"  项目根 (parent.parent.parent.parent) = {workspace_path.parent.parent.parent.parent}")
print(f"  == 包含 git_ignore_folder: {(workspace_path.parent.parent.parent.parent / 'git_ignore_folder').exists()}")

# ========== 子进程执行路径测试（原版代码） ==========
print(f"\n=== 原版代码子进程执行路径测试 ===\n")

# 原始代码: execution_code_path = self.workspace_path / "factor.py"
code_path_orig = Path(workspace_path) / "factor.py"
print(f"code_path (Path 对象): {code_path_orig}")
print(f"  str():     {str(code_path_orig)}")
print(f"  是绝对路径:  {code_path_orig.is_absolute()}")
print()

# subprocess.check_output 中 str(Path) 的行为
cmd_orig = f"python {code_path_orig}"
print(f"原始代码拼接的命令:")
print(f"  {cmd_orig[:80]}...")
print()

# 当 shell=True, cwd=workspace_path 时:
# cmd.exe 看到: python data\results\workspace_exp_test\xxx\factor.py
# 如果 code_path 是绝对路径，cmd.exe 正确使用它
# 如果 code_path 是相对路径，cmd.exe 将相对于 cwd 解析 → 路径重复

print(f"code_path 在 subprocess 命令中的类型:")
print(f"  type: {type(code_path_orig)}")
print(f"  str(code_path_orig): {str(code_path_orig)}")
print(f"  is_absolute: {code_path_orig.is_absolute()}")

if not code_path_orig.is_absolute():
    print(f"\n  ⚠️  code_path 是相对路径！在 shell=True + cwd 时会导致路径重复！")
    resolved_by_cmd = Path(str(workspace_path)) / str(code_path_orig)
    print(f"  cmd.exe 会解析为: {resolved_by_cmd}")
else:
    print(f"\n  ✅ code_path 是绝对路径，cmd.exe 会正确使用")
