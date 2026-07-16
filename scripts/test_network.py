"""
测试 API 网络连通性
"""
import os
import socket
import urllib.request
import urllib.error
from dotenv import load_dotenv

load_dotenv(".env")

base = os.environ.get("OPENAI_BASE_URL", "")

# 解析主机名
from urllib.parse import urlparse
parsed = urlparse(base)
host = parsed.hostname
port = parsed.port or (443 if parsed.scheme == "https" else 80)

print(f"目标: {base}")
print(f"主机: {host}")
print(f"端口: {port}")
print("---")

# 1. DNS 解析
try:
    ip = socket.gethostbyname(host)
    print(f"✅ DNS 解析: {host} → {ip}")
except Exception as e:
    print(f"❌ DNS 解析失败: {e}")

# 2. TCP 连接
try:
    sock = socket.create_connection((host, port), timeout=10)
    sock.close()
    print(f"✅ TCP 连接: {host}:{port} 连通")
except Exception as e:
    print(f"❌ TCP 连接失败: {e}")

# 3. HTTPS 请求（带错误响应）
try:
    req = urllib.request.Request(base, method="GET")
    resp = urllib.request.urlopen(req, timeout=10)
    print(f"✅ HTTPS 响应: {resp.status}")
except urllib.error.HTTPError as e:
    print(f"⚠️  HTTP 错误: {e.code}（主机可达，服务端返回错误）")
except urllib.error.URLError as e:
    print(f"❌ HTTPS 失败: {e.reason}")
except Exception as e:
    print(f"❌ HTTPS 失败: {e}")

# 4. 也测试 deepseek.com 主站
print("\n--- 主站 ---")
try:
    req2 = urllib.request.Request("https://api.deepseek.com")
    resp2 = urllib.request.urlopen(req2, timeout=10)
    print(f"✅ api.deepseek.com: {resp2.status}")
except urllib.error.HTTPError as e:
    print(f"⚠️  api.deepseek.com: {e.code}")
except Exception as e:
    print(f"❌ api.deepseek.com: {e}")
