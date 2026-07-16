"""快速复现实验中的 API 调用"""
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(".env")
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=os.environ["OPENAI_BASE_URL"])
try:
    r = client.chat.completions.create(
        model=os.environ["CHAT_MODEL"],
        messages=[{"role":"user","content":"Say hi"}],
        max_tokens=10,
    )
    print(f"OK: {r.choices[0].message.content}")
except Exception as e:
    print(f"FAIL: {type(e).__name__}: {e}")
