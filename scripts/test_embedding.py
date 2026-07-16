import os, httpx
from dotenv import load_dotenv
load_dotenv(".env")
key = os.environ.get("OPENAI_API_KEY", "")

# 测试 1: Anthropic 风格的 embedding endpoint
url1 = "https://api.deepseek.com/anthropic/v1/embeddings"
r1 = httpx.post(url1,
    headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
    json={"model": "deepseek-v4-flash", "input": ["hello"]}, timeout=10)
print(f"[1] anthropic/v1/embeddings: {r1.status_code}")
print(f"    {r1.text[:200]}")

# 测试 2: DeepSeek 原生 embedding endpoint
url2 = "https://api.deepseek.com/v1/embeddings"
r2 = httpx.post(url2,
    headers={"Authorization": f"Bearer {key}", "content-type": "application/json"},
    json={"model": "deepseek-embedding", "input": ["hello world test"]}, timeout=10)
print(f"\n[2] /v1/embeddings (Bearer): {r2.status_code}")
print(f"    {r2.text[:300]}")

# 测试 3: text-embedding-3-small (OpenAI)
url3 = "https://api.deepseek.com/v1/embeddings"
r3 = httpx.post(url3,
    headers={"Authorization": f"Bearer {key}", "content-type": "application/json"},
    json={"model": "text-embedding-3-small", "input": ["hello world test"]}, timeout=10)
print(f"\n[3] text-embedding-3-small: {r3.status_code}")
print(f"    {r3.text[:300]}")
