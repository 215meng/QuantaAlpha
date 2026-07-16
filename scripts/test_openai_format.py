"""测试 DeepSeek OpenAI 兼容格式"""
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(".env")

key = os.environ.get("OPENAI_API_KEY", "")
base = os.environ.get("OPENAI_BASE_URL", "")
model = os.environ.get("CHAT_MODEL", "")

print(f"Key: {key[:10]}...{key[-4:]}")
print(f"Base URL: {base}")
print(f"Model: {model}")
print()

client = OpenAI(api_key=key, base_url=base)

# 测试 1: 聊天（deepseek-chat）
print("[测试 1: 聊天 completion]")
try:
    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": "Say 'API working' in one sentence."}],
        max_tokens=50,
    )
    print(f"  ✅ 回复: {resp.choices[0].message.content}")
except Exception as e:
    print(f"  ❌ 错误: {e}")

# 测试 2: Embedding (尝试多种模型名)
print("\n[测试 2: Embedding]")
for emb_model in ["deepseek-embedding", "deepseek-embed", "text-embedding-3-small", "text-embedding-ada-002"]:
    try:
        resp_e = client.embeddings.create(
            model=emb_model,
            input=["测试文本"],
        )
        vec = resp_e.data[0].embedding
        print(f"  ✅ {emb_model}: 维度={len(vec)}, 前3个={vec[:3]}")
        break
    except Exception as e:
        print(f"  ❌ {emb_model}: {type(e).__name__}: {str(e)[:80]}")

# 测试 3: JSON 模式
print("\n[测试 3: JSON 模式]")
try:
    resp_json = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "user", "content": 'Return JSON: {"status": "ok", "value": 42}'}
        ],
        max_tokens=50,
        response_format={"type": "json_object"},
    )
    print(f"  ✅ 回复: {resp_json.choices[0].message.content}")
except Exception as e:
    print(f"  ❌ 错误: {type(e).__name__}: {str(e)[:150]}")
