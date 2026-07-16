"""
测试 DeepSeek /anthropic 端点的认证方式
核心假设：DeepSeek /anthropic 使用 x-api-key header（非 Bearer）
"""
import os
import httpx
from dotenv import load_dotenv

load_dotenv(".env")
key = os.environ.get("OPENAI_API_KEY", "").strip()
base = os.environ.get("OPENAI_BASE_URL", "").strip()
model = os.environ.get("CHAT_MODEL", "")

print(f"Key: {key[:10]}...{key[-4:]}")
print(f"Base URL: {base}")
print(f"Model: {model}")
print("=" * 60)

url = base + "/messages" if not base.endswith("/messages") else base
payload = {
    "model": model,
    "max_tokens": 20,
    "messages": [{"role": "user", "content": "Say hi"}],
}

# 测试 1: x-api-key header (Anthropic 原生格式)
print("\n[测试 1: x-api-key header (Anthropic 原生)]")
try:
    resp = httpx.post(url, headers={
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }, json=payload, timeout=10)
    print(f"  状态: {resp.status_code}")
    print(f"  响应: {resp.text[:300]}")
except Exception as e:
    print(f"  ❌ 异常: {e}")

# 测试 2: Authorization Bearer <REDACTED> (OpenAI 格式)
print("\n[测试 2: Authorization Bearer <REDACTED> (OpenAI 格式)]")
try:
    resp = httpx.post(url, headers={
        "Authorization": f"Bearer {key}",
        "content-type": "application/json",
    }, json=payload, timeout=10)
    print(f"  状态: {resp.status_code}")
    print(f"  响应: {resp.text[:300]}")
except Exception as e:
    print(f"  ❌ 异常: {e}")

# 测试 3: Anthropic SDK (自动使用 x-api-key)
print("\n[测试 3: Anthropic SDK (x-api-key)]")
try:
    import anthropic
    client = anthropic.Anthropic(api_key=key, base_url=base)
    msg = client.messages.create(
        model=model,
        max_tokens=20,
        messages=[{"role": "user", "content": "Say hi"}],
    )
    print(f"  ✅ 成功! 回复: {msg.content[0].text}")
    print(f"  model: {msg.model}, stop_reason: {msg.stop_reason}")
except Exception as e:
    print(f"  ❌ 异常: {type(e).__name__}: {str(e)[:200]}")

print("\n" + "=" * 60)
