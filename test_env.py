import os
import requests
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

# 1. 加载环境变量验证
load_dotenv()
api_key = os.getenv("DASHSCOPE_API_KEY")
print("✅ 环境变量加载成功，API密钥已读取" if api_key else "❌ 环境变量加载失败，请检查.env文件")

# 2. Playwright环境验证
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://www.jd.com", timeout=10000)
        print("✅ Playwright环境正常，页面访问成功")
        browser.close()
except Exception as e:
    print(f"❌ Playwright环境异常：{e}")

# 3. 大模型API连通性验证
try:
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "qwen-turbo",
        "input": {"messages": [{"role": "user", "content": "你好，输出一句话测试连通性"}]},
        "parameters": {"result_format": "text"}
    }
    response = requests.post(url, headers=headers, json=payload, timeout=10)
    response.raise_for_status()
    print(f"✅ 大模型API连通正常，返回结果：{response.json()['output']['text']}")
except Exception as e:
    print(f"❌ 大模型API连通异常：{e}")

print("\n=== 环境验证完成 ===")