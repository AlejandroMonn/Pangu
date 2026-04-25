import requests
import json
import time

OLLAMA_HOST = "http://127.0.0.1:11434"

try:
    print("Fetching models...")
    res = requests.get(f"{OLLAMA_HOST}/api/tags")
    models = res.json()
    model_name = models['models'][0]['name'] if models.get('models') else "qwen2.5:14b"
    print(f"Using model: {model_name}")
except Exception as e:
    print("Error fetching models:", e)
    model_name = "qwen2.5:14b"

payload_json = {
    "model": model_name,
    "messages": [
        {"role": "user", "content": "generate a triage plan for 'clean the room'"}
    ],
    "stream": False,
    "format": "json"
}

print("Testing format='json' completion...")
start = time.time()
try:
    res = requests.post(f"{OLLAMA_HOST}/api/chat", json=payload_json, timeout=30)
    print(f"Took {time.time()-start:.2f}s. Response: {res.text[:100]}")
except requests.exceptions.Timeout:
    print("Timeout on json completion!")
except Exception as e:
    print("Error:", e)
