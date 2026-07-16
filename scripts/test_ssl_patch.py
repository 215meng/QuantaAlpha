"""
验证 SSL 补丁：模拟 cli.py 的修复逻辑后，aiohttp 是否能正常导入
"""
import os
import ssl

print("[1] 导入 certifi 并打补丁")
import certifi
cert_path = certifi.where()
os.environ["SSL_CERT_FILE"] = cert_path
os.environ["REQUESTS_CA_BUNDLE"] = cert_path
print(f"  certifi 路径: {cert_path}")

_orig = ssl.create_default_context

def _patched(purpose=ssl.Purpose.SERVER_AUTH, cafile=None, capath=None, cadata=None):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_verify_locations(cafile=cafile or cert_path, capath=capath, cadata=cadata)
    return ctx

ssl.create_default_context = _patched
print("  ✅ ssl.create_default_context 已打补丁")

print("\n[2] 测试 ssl.create_default_context()")
try:
    ctx = ssl.create_default_context()
    print(f"  ✅ 上下文创建成功 (protocol={ctx.protocol})")
except Exception as e:
    print(f"  ❌ 失败: {e}")

print("\n[3] 尝试导入 litellm (触发 aiohttp)")
try:
    import litellm
    print(f"  ✅ litellm 导入成功 (v{litellm.__version__})")
except Exception as e:
    print(f"  ❌ 导入失败: {type(e).__name__}: {str(e)[:100]}")

print("\n[4] 尝试导入 quantaalpha.factors.experiment (完整链路)")
try:
    from quantaalpha.factors.experiment import FactorExperiment
    print(f"  ✅ FactorExperiment 导入成功")
except Exception as e:
    print(f"  ❌ 导入失败: {type(e).__name__}: {str(e)[:100]}")

print("\n" + "=" * 40)
print("测试完成")
