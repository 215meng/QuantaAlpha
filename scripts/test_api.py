"""
测试 DeepSeek API 连通性
"""
import os
from dotenv import load_dotenv

load_dotenv(".env")

key = os.environ.get("OPENAI_API_KEY", "")
base = os.environ.get("OPENAI_BASE_URL", "")
model = os.environ.get("CHAT_MODEL", "")

print(f"BASE_URL: {base}")
print(f"MODEL:    {model}")
print(f"KEY:      {key[:8]}...{key[-4:]}")
print("---")

from openai import OpenAI

client = OpenAI(api_key=key, base_url=base)

try:
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Say hello in one word"}],
        max_tokens=10,
    )
    print(f"✅ API 调用成功！回复: {resp.choices[0].message.content}")
except Exception as e:
    print(f"❌ API 调用失败: {e}")
