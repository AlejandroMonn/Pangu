import requests
import time

OLLAMA_HOST = "http://127.0.0.1:11434"
model_name = "qwen3.5:9b"

payload = {
    "model": model_name,
    "messages": [
        {"role": "user", "content": "generate a triage plan for 'clean the room'"}
    ],
    "stream": False
}

print(f"Testing completion without format using {model_name}...")
start = time.time()
try:
    res = requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=60)
    print(f"Took {time.time()-start:.2f}s.")
    print("Response:", res.text[:200])
except Exception as e:
    print("Error:", e)
