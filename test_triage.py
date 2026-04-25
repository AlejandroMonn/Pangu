import asyncio
from main import _generate_with_ollama

print("Testing python ollama package call with format='json' (which is now in main.py)...")
try:
    response, transport = _generate_with_ollama("clean the room")
    print("Transport:", transport)
    print("Response:", response[:100])
except Exception as e:
    print("Error:", e)
