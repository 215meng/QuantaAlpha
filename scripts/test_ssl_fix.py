"""
诊断并修复 SSL 连接问题
逐步排查：系统证书 → 代理 → SSL 验证绕过测试
"""
import os
import ssl
import certifi
import urllib.request
import httpx

print("=" * 60)
print("SSL 连接诊断")
print("=" * 60)

# 检查 1: SSL 环境
print("\n[检查 1: SSL 环境]")
print(f"  OpenSSL 版本: {ssl.OPENSSL_VERSION}")
print(f"  SSL_CERT_FILE: {os.environ.get('SSL_CERT_FILE', '(未设置)')}")
print(f"  REQUESTS_CA_BUNDLE: {os.environ.get('REQUESTS_CA_BUNDLE', '(未设置)')}")
print(f"  HTTPS_PROXY: {os.environ.get('HTTPS_PROXY', '(未设置)')}")
print(f"  HTTP_PROXY: {os.environ.get('HTTP_PROXY', '(未设置)')}")
print(f"  certifi 路径: {certifi.where()}")

# 检查 2: 直接 httpx 测试（各种 SSL 模式）
print("\n[检查 2: httpx 连接测试]")

url = "https://api.deepseek.com/anthropic"
headers = {
    "x-api-key": os.environ.get("OPENAI_API_KEY", ""),
    "anthropic-version": "2023-06-01",
    "content-type": "application/json",
}
payload = {
    "model": "deepseek-v4-flash",
    "max_tokens": 10,
    "messages": [{"role": "user", "content": "hi"}],
}

# 2a: 默认 ssl 验证
try:
    client = httpx.Client(timeout=10)
    resp = client.post(url, headers=headers, json=payload)
    print(f"  2a) 默认 SSL: {resp.status_code} - {resp.text[:100]}")
    client.close()
except Exception as e:
    print(f"  2a) 默认 SSL: ❌ {type(e).__name__}: {str(e)[:80]}")

# 2b: 禁用 ssl 验证
try:
    client2 = httpx.Client(timeout=10, verify=False)
    resp2 = client2.post(url, headers=headers, json=payload)
    print(f"  2b) 禁用验证: {resp2.status_code} - {resp2.text[:100]}")
    client2.close()
except Exception as e:
    print(f"  2b) 禁用验证: ❌ {type(e).__name__}: {str(e)[:80]}")

# 2c: 使用 certifi 证书
try:
    client3 = httpx.Client(timeout=10, verify=certifi.where())
    resp3 = client3.post(url, headers=headers, json=payload)
    print(f"  2c) certifi验证: {resp3.status_code} - {resp3.text[:100]}")
    client3.close()
except Exception as e:
    print(f"  2c) certifi验证: ❌ {type(e).__name__}: {str(e)[:80]}")

# 2d: 使用系统自定义 SSL_CERT_FILE
cert_file = r"G:\miniconda\Library\ssl\cacert.pem"
if os.path.exists(cert_file):
    try:
        client4 = httpx.Client(timeout=10, verify=cert_file)
        resp4 = client4.post(url, headers=headers, json=payload)
        print(f"  2d) conda cacert: {resp4.status_code} - {resp4.text[:100]}")
        client4.close()
    except Exception as e:
        print(f"  2d) conda cacert: ❌ {type(e).__name__}: {str(e)[:80]}")

# 检查 3: 测试其他 HTTPS 站点（确认是全局问题还是 deepseek 特例）
print("\n[检查 3: 对比站点连通性]")
import httpx
for test_url in ["https://www.baidu.com", "https://api.openai.com", "https://api.anthropic.com"]:
    try:
        c = httpx.Client(timeout=5)
        r = c.get(test_url)
        print(f"  ✅ {test_url}: {r.status_code}")
        c.close()
    except Exception as e:
        print(f"  ❌ {test_url}: {type(e).__name__}: {str(e)[:60]}")

print("\n" + "=" * 60)
