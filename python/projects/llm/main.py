import requests
from memory_store import MemoryStore

API_URL = "https://api.deepseek.com/v1/chat/completions"
API_KEY = ""

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

system_prompt = {
    "role": "system",
    "content": (
        "你是一位专业的心理陪护机器人，擅长认知行为疗法（CBT）、情绪识别和情感共情，"
        "你的任务是帮助用户识别情绪、接受自己、构建健康心态。你会结合用户的过去经历给出个性化回应。"
    )
}

store = MemoryStore()

print("🧠 欢迎使用心理陪护机器人（含记忆系统）")

while True:
    user_input = input("你：")
    if user_input.strip().lower() in {"exit", "quit"}:
        break

    # 添加到记忆库
    store.add(user_input)

    # 查询最相关的历史对话片段
    related_memories = store.query(user_input, k=3)
    memory_context = "\n".join([f"过去你曾说过：{m['text']}" for m in related_memories])

    # 构建消息上下文
    messages = [system_prompt]
    if memory_context:
        messages.append({"role": "system", "content": memory_context})
    messages.append({"role": "user", "content": user_input})

    # 请求 DeepSeek 聊天模型
    payload = {
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": 0.8,
        "max_tokens": 2048
    }

    try:
        response = requests.post(API_URL, headers=HEADERS, json=payload)
        if response.status_code == 200:
            reply = response.json()["choices"][0]["message"]["content"]
        else:
            reply = f"[错误] {response.status_code} - {response.text}"
    except Exception as e:
        reply = f"[异常] {e}"

    print("\n🤖 陪护机器人：", reply, "\n")
