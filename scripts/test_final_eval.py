"""
模拟 final_decision_evaluator 的 LLM 调用方式
"""
import os
import json
from dotenv import load_dotenv

load_dotenv(".env")

from quantaalpha.llm.client import APIBackend

print("=== 模拟 final_decision_evaluator 的 API 调用 ===")
print(f"use_anthropic: {APIBackend().use_anthropic if hasattr(APIBackend(), 'use_anthropic') else 'N/A'}")

api = APIBackend()
api.chat_stream = False  # 子进程中可能是 False

user_prompt = """
Based on the following factor evaluation information, make a final decision.

Factor expression: -TS_MEAN(($high - $low) / ($close + 1e-8), 20) * TS_MEAN(SIGN($close - $open) * $volume, 5)
Execution feedback: Factor calculated successfully.
Value feedback: IC=0.03, RankIC=0.028.

Please return a JSON object with:
- "final_decision": true or false (whether this factor is good enough)
- "final_feedback": explanation
"""

system_prompt = "You are a quantitative researcher evaluating alpha factors. Respond in JSON."

try:
    result = api.build_messages_and_create_chat_completion(
        user_prompt=user_prompt,
        system_prompt=system_prompt,
        reasoning_flag=False,
        json_mode=True,
        seed=0,
    )
    print(f"\n✅ 调用成功!")
    print(f"回复: {result[:500]}")
    parsed = json.loads(result)
    print(f"解析后: {parsed}")
except Exception as e:
    print(f"\n❌ 调用失败!")
    print(f"异常类型: {type(e).__name__}")
    print(f"异常信息: {e}")
    import traceback
    traceback.print_exc()
