"""
测试 DeepSeek /anthropic 端点的 thinking 模式控制
"""
import os
import json
import httpx
from dotenv import load_dotenv

load_dotenv(".env")
key = os.environ.get("OPENAI_API_KEY", "").strip()
base = os.environ.get("OPENAI_BASE_URL", "").strip()
model = os.environ.get("CHAT_MODEL", "")

url = base + "/messages"
payload = {
    "model": model,
    "max_tokens": 100,
    "messages": [{"role": "user", "content": "Say hi in one sentence."}],
}

# 测试 1: 默认（不传 thinking）
print("[测试 1: 默认（不传 thinking）]")
r = httpx.post(url, headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}, json=payload, timeout=10)
print(f"  status: {r.status_code}")
resp = r.json()
content_types = [c.get("type") for c in resp.get("content", [])]
print(f"  content types: {content_types}")
for c in resp.get("content", []):
    if c.get("type") == "text":
        print(f"  text: {c['text'][:100]}")
    elif c.get("type") == "thinking":
        print(f"  thinking: {c['thinking'][:60]}...")

# 测试 2: thinking = {"type": "disabled", "budget_tokens": 0}
print("\n[测试 2: thinking disabled]")
payload2 = {**payload, "thinking": {"type": "disabled", "budget_tokens": 0}}
r2 = httpx.post(url, headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}, json=payload2, timeout=10)
print(f"  status: {r2.status_code}")
resp2 = r2.json()
content_types2 = [c.get("type") for c in resp2.get("content", [])]
print(f"  content types: {content_types2}")
for c in resp2.get("content", []):
    if c.get("type") == "text":
        print(f"  text: {c['text'][:100]}")

# 测试 3: 带 tool_choice 但不传 thinking
print("\n[测试 3: tool_choice + 默认 thinking]")
payload3 = {
    **payload,
    "tools": [{"name": "output_json", "description": "output json", "input_schema": {"type": "object", "properties": {}}}],
    "tool_choice": {"type": "tool", "name": "output_json"},
}
r3 = httpx.post(url, headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}, json=payload3, timeout=10)
print(f"  status: {r3.status_code}")
print(f"  response: {r3.text[:300]}")

# 测试 4: 带 tool_choice + thinking disabled
print("\n[测试 4: tool_choice + thinking disabled]")
payload4 = {
    **payload3,
    "thinking": {"type": "disabled", "budget_tokens": 0},
}
r4 = httpx.post(url, headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}, json=payload4, timeout=10)
print(f"  status: {r4.status_code}")
resp4 = r4.json()
content_types4 = [c.get("type") for c in resp4.get("content", [])]
print(f"  content types: {content_types4}")
for c in resp4.get("content", []):
    if c.get("type") == "text":
        print(f"  text: {c['text'][:200]}")

# 测试 5: JSON mode 的标准做法 - 不传 tool_choice 而是 system prompt 引导
print("\n[测试 5: system prompt 引导 JSON（不用 tool_choice）]")
payload5 = {
    "model": model,
    "max_tokens": 200,
    "messages": [{"role": "user", "content": 'Return JSON: {"status":"ok"}'}],
    "system": "You always respond with valid JSON only. No other text.",
}
r5 = httpx.post(url, headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}, json=payload5, timeout=10)
print(f"  status: {r5.status_code}")
resp5 = r5.json()
for c in resp5.get("content", []):
    if c.get("type") == "text":
        print(f"  text: {c['text'][:200]}")
