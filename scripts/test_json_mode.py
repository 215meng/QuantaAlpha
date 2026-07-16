"""
测试 JSON 模式的完整行为 - 验证 thinking disabled 后能否正常返回 JSON
"""
import os
import json
from dotenv import load_dotenv

load_dotenv(".env")
from quantaalpha.llm.client import APIBackend

api = APIBackend()
api.chat_stream = False

print("=== 测试 JSON 模式（带 thinking disabled） ===")

# 测试 1: 简单 prompt + 大 max_tokens
print("\n[测试 1: 简单 prompt, max_tokens=500]")
try:
    result = api.build_messages_and_create_chat_completion(
        user_prompt='Return a JSON object with key "greeting" and value "hello".',
        system_prompt="",
        reasoning_flag=False,
        json_mode=True,
        seed=0,
        max_tokens=500,
    )
    print(f"  结果: {result}")
    parsed = json.loads(result)
    print(f"  解析: {parsed}")
except Exception as e:
    print(f"  ❌ 失败: {e}")

# 测试 2: 使用 seed=None 避免缓存
print("\n[测试 2: 真实评估 prompt]")
try:
    result2 = api.build_messages_and_create_chat_completion(
        user_prompt='Factor evaluation: IC=0.03. Return JSON with keys "decision" (true/false) and "reason".',
        system_prompt="You are a quant. Always respond in JSON.",
        reasoning_flag=False,
        json_mode=True,
        seed=42,
        max_tokens=500,
    )
    print(f"  结果: {result2}")
    parsed2 = json.loads(result2)
    print(f"  解析: {parsed2}")
except Exception as e:
    print(f"  ❌ 失败: {e}")

print("\n=== 完成 ===")
