import requests, time, json

HOST = "http://127.0.0.1:11434"

SYSTEM = """You are Chaos-Triage Planner. Convert a messy brain dump into strict JSON.
Return ONLY valid JSON with keys: summary, coach, topics, tasks.
tasks is an array of objects with: step_number, title, details, first_move, topic, urgency, energy_level, estimated_minutes, reason."""

USER = """Original brain dump:
clean the room, study math, reply emails

Pre-split task seeds in required order:
1. clean the room
2. study math
3. reply emails

Plan around these seeds."""

# Test qwen3:8b with format=json for triage
print("=== qwen3:8b triage test with format=json ===")
start = time.time()
try:
    res = requests.post(f"{HOST}/api/chat", json={
        "model": "qwen3:8b",
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": USER},
        ],
        "options": {"temperature": 0.2},
        "format": "json",
        "stream": False,
    }, timeout=120)
    elapsed = time.time() - start
    data = res.json()
    content = data.get("message", {}).get("content", "")
    print(f"  Time: {elapsed:.1f}s")
    print(f"  Response: {content[:500]}")
    # Try parsing
    parsed = json.loads(content)
    print(f"  Valid JSON: True, keys: {list(parsed.keys())}")
    if "tasks" in parsed:
        print(f"  Tasks count: {len(parsed['tasks'])}")
except requests.exceptions.Timeout:
    print(f"  TIMEOUT after {time.time()-start:.1f}s")
except json.JSONDecodeError as e:
    print(f"  JSON parse error: {e}")
except Exception as e:
    print(f"  ERROR: {e}")
