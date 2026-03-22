import requests

API_KEY = ""
API_URL = "https://api.deepseek.com/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

messages = [
    {"role": "system", "content": "你是一个代码专家。"},
    {"role": "user", "content": "请用Python实现快速排序。"}
]

data = {
    "model": "deepseek-chat",
    "messages": messages,
    "temperature": 0.7,
    "max_tokens": 1024
}

response = requests.post(API_URL, headers=headers, json=data)

print(response.json())
