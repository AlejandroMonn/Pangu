import asyncio
from main import _generate_with_ollama
import traceback

user_prompt = "Hidratacion, Postura, Desayuno,Organizar Cuarto, Entreno completo, Limpieza, BOT TELEGRAM -> 3. PROVEEDORES -> 4. ESQUEMA MEMORIA, Refinar souls de hermes agent, Mandar set de pruebas de la dian, Enviar Factura electronica elecciones, Refinar UX Kinetiq, Refinar Frames de UI, Refinar chaos triage app"

print("Calling _generate_with_ollama...")
try:
    content, transport = _generate_with_ollama(user_prompt)
    print("Success:", transport)
    print("Content preview:", content[:200])
except Exception as e:
    print("Error calling _generate_with_ollama:")
    traceback.print_exc()
