# embeddings.py
import requests
import numpy as np

DEEPSEEK_EMBEDDING_API = "https://api.deepseek.com/v1/embeddings"
API_KEY = ""

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def get_embedding(text):
    try:
        payload = {
            "model": "deepseek-embedding",
            "input": text
        }
        response = requests.post(DEEPSEEK_EMBEDDING_API, headers=HEADERS, json=payload)
        if response.status_code == 200:
            data = response.json()
            return np.array(data["data"][0]["embedding"], dtype=np.float32)
        else:
            print("[Embedding Error]", response.text)
            return None
    except Exception as e:
        print("[Embedding Exception]", e)
        return None
