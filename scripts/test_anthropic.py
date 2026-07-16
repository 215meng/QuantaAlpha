"""
测试 Anthropic 后端的 DeepSeek API 调用（通过标准调用路径）
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv(".env")

print("=" * 60)
print("QuantaAlpha Anthropic 后端测试")
print("=" * 60)

# 1. 检查环境变量
from quantaalpha.llm.config import LLM_SETTINGS
print(f"\n[配置检查]")
print(f"  use_anthropic: {LLM_SETTINGS.use_anthropic}")
print(f"  base_url:      {LLM_SETTINGS.openai_base_url}")
print(f"  chat_model:    {LLM_SETTINGS.chat_model}")
print(f"  api_key set:   {'yes' if LLM_SETTINGS.openai_api_key else 'no'}")

# 2. 初始化客户端
print(f"\n[客户端初始化]")
from quantaalpha.llm.client import APIBackend
client = APIBackend()
print(f"  ✅ APIBackend 创建成功 (type: {type(client.chat_client).__name__})")

# 3. 通过标准路径测试对话
print(f"\n[测试 1: 标准路径对话 (build_messages_and_create_chat_completion)]")
try:
    client.chat_stream = False
    resp = client.build_messages_and_create_chat_completion(
        user_prompt="Hello! Please say 'API working' if you can hear me.",
        system_prompt="You are a helpful assistant. Reply briefly.",
    )
    print(f"  ✅ 调用成功!")
    print(f"  回复: {resp[:300]}")
except Exception as e:
    print(f"  ❌ 调用失败: {e}")
    import traceback
    traceback.print_exc()

# 4. 测试 JSON 模式
print(f"\n[测试 2: JSON 模式 (build_chat_session + build_chat_completion)]")
try:
    session = client.build_chat_session()
    resp_json = session.build_chat_completion(
        user_prompt='Return a JSON object with key "status" and value "ok".',
    )
    print(f"  ✅ JSON 模式调用成功!")
    print(f"  回复: {resp_json[:300]}")
except Exception as e:
    print(f"  ❌ JSON 模式调用失败: {e}")
    import traceback
    traceback.print_exc()

# 5. 测试流式
print(f"\n[测试 3: 流式调用]")
try:
    client.chat_stream = True
    resp_stream = client.build_messages_and_create_chat_completion(
        user_prompt="Count to 5 in one sentence.",
        system_prompt="",
    )
    print(f"  ✅ 流式调用成功!")
    print(f"  回复: {resp_stream[:300]}")
except Exception as e:
    print(f"  ❌ 流式调用失败: {e}")
    import traceback
    traceback.print_exc()

# 6. 消息转换
print(f"\n[测试 4: 消息格式转换]")
try:
    converted = client._convert_messages_to_anthropic([
        {"role": "system", "content": "You are a quant expert."},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": "Help with alpha factors."},
    ])
    print(f"  ✅ system: {converted['system']}")
    print(f"  ✅ messages({len(converted['messages'])}): " + ", ".join(m['role'] for m in converted['messages']))
except Exception as e:
    print(f"  ❌ 转换失败: {e}")

print(f"\n{'=' * 60}")
print("测试完成")
print("=" * 60)
