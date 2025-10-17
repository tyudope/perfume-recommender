import os, httpx, json
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("LLM_API_KEY")
print("Using key prefix:", key[:10], "...")

headers = {"Authorization": f"Bearer {key}"}
payload = {
    "model": "gpt-4o-mini",
    "messages": [
        {"role": "user", "content": "Say hello if you can read this."}
    ]
}

r = httpx.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
print("Status:", r.status_code)
print("Response:", r.json()["choices"][0]["message"]["content"])