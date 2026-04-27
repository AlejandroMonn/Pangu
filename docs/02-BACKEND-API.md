# Chaos-Triage — Backend y API

> Documento actualizado: Abril 2026  
> Archivo principal: `main.py` (654 líneas)  
> Framework: FastAPI 1.0.0

---

## 1. Visión General del Backend

El backend de Chaos-Triage es un servidor FastAPI que actúa como puente inteligente entre la entrada del usuario y el modelo de IA local. Su responsabilidad va mucho más allá de simplemente reenviar texto a Ollama: implementa un pipeline completo de preprocesamiento, generación, reparación y normalización que garantiza respuestas estables incluso cuando el modelo produce output imperfecto.

### Responsabilidades principales

1. **Servir el frontend** — Entrega `templates/index.html` como respuesta estática
2. **Aceptar texto del usuario** — Parsea JSON o texto plano desde el body HTTP
3. **Extraer semillas de tareas** — Pipeline determinista comma-first de preextracción
4. **Construir prompts** — Formato dual: texto original + lista numerada de semillas
5. **Comunicarse con Ollama** — Doble path de transporte con fallback automático
6. **Recuperar output malformado** — Extracción JSON robusta + repair pass de emergencia
7. **Normalizar y validar** — Coerción de tipos, limpieza de campos, asignación de lanes
8. **Retornar JSON estable** — Contrato `TriageResponse` validado con Pydantic

---

## 2. Inicialización y Configuración

```python
# Archivo: main.py, líneas 1-24

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
os.environ.setdefault("OLLAMA_HOST", OLLAMA_HOST)

app = FastAPI(title="Chaos-Triage", version="1.0.0")
BASE_DIR = Path(__file__).resolve().parent
MODEL_NAME = os.getenv("OLLAMA_MODEL", "qwen3:8b").strip()
```

### Constantes de validación

```python
ALLOWED_URGENCY = {"low", "medium", "high"}
ALLOWED_ENERGY  = {"light", "medium", "deep"}
```

Cualquier valor fuera de estos sets se normaliza a `"medium"`.

---

## 3. Endpoints de la API

### `GET /` — Servir el Frontend

```python
@app.get("/")
async def home() -> FileResponse:
    return FileResponse(BASE_DIR / "templates" / "index.html")
```

Sirve el archivo HTML completo. No hay routing del lado del cliente ni build step.

---

### `GET /api/health` — Health Check

```python
@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "model": MODEL_NAME, "ollama_host": OLLAMA_HOST}
```

**Respuesta:**
```json
{
  "ok": true,
  "model": "qwen3:8b",
  "ollama_host": "http://127.0.0.1:11434"
}
```

Usado por:
- El launcher PowerShell para verificar que la app está lista
- Diagnóstico manual del usuario

---

### `POST /api/triage` — Procesar Brain Dump

Este es el endpoint principal de la aplicación.

**Request:**
```json
{
  "text": "limpiar cuarto, estudiar cálculo, ver un video"
}
```

También acepta `Content-Type: text/plain` con el texto directamente en el body.

**Response (`TriageResponse`):**
```json
{
  "summary": "Plan con 3 tareas organizadas por prioridad y energía.",
  "coach": {
    "intro": "Hoy no tienes que resolver toda la vida...",
    "focus": "Empieza por limpiar cuarto...",
    "caution": "Cuidado con saltar entre tareas...",
    "steps": ["Paso 1...", "Paso 2...", "Paso 3..."]
  },
  "topics": ["Casa", "Estudio", "Entretenimiento"],
  "tasks": [
    {
      "step_number": 1,
      "title": "Limpiar cuarto",
      "details": "Recoger ropa, barrer y organizar escritorio.",
      "first_move": "Recoger la ropa del suelo",
      "topic": "Casa",
      "urgency": "medium",
      "energy_level": "light",
      "estimated_minutes": 25,
      "reason": "Quick win para generar momentum.",
      "lane": "suggested"
    }
  ],
  "meta": {
    "model": "qwen3:8b",
    "generated_at": "2026-04-27T03:30:00+00:00",
    "transport": "requests_direct",
    "task_seeds": ["limpiar cuarto", "estudiar cálculo", "ver un video"]
  }
}
```

**Códigos de error:**

| Código | Situación |
|--------|-----------|
| 400 | Body JSON inválido o texto vacío |
| 503 | Ollama no disponible o modelo no encontrado |
| 422 | Output del modelo no parseable ni tras reparación |

---

## 4. Modelos Pydantic

```python
class TriageCoach(BaseModel):
    intro: str
    focus: str
    caution: str
    steps: list[str]

class TriageTask(BaseModel):
    step_number: int
    title: str
    details: str
    first_move: str
    topic: str
    urgency: str
    energy_level: str
    estimated_minutes: int
    reason: str
    lane: str

class TriageResponse(BaseModel):
    summary: str
    coach: TriageCoach
    topics: list[str]
    tasks: list[TriageTask]
    meta: dict[str, Any]
```

Estos modelos definen el contrato exacto entre backend y frontend. Cualquier respuesta que no pueda construir un `TriageResponse` válido será rechazada con HTTP 422.

---

## 5. Pipeline de Extracción de Tareas

La extracción de semillas de tareas es **determinista** — ocurre antes de cualquier contacto con la IA. Esto permite que el usuario tenga control predecible sobre los límites de sus tareas.

### Paso 1: Split por comas — `_split_primary_seeds(text)`

```
"limpiar cuarto, deploy then test, ver video"
→ ["limpiar cuarto", "deploy then test", "ver video"]
```

**Regla fundamental:** cada coma es un límite de tarea.

### Paso 2: Split de compuestos obvios — `_split_obvious_compound_seed(seed)`

Solo split intra-semilla si hay conectores claros con frases de acción:

**Conectores soportados:** `then`, `y luego`, `y despues`, `and then`, `y`, `and`

**Palabras de acción (EN):** `clean`, `wash`, `study`, `deploy`, `test`, `fix`, `write`, `read`, `watch`...  
**Palabras de acción (ES):** `estudiar`, `entregar`, `limpiar`, `lavar`, `ordenar`, `revisar`, `leer`...

```
"deploy then test" → ["deploy", "test"]
"clean room and wash dishes" → ["clean room", "wash dishes"]
"estudiar y entregar" → ["estudiar", "entregar"]
```

### Paso 3: Guard — `_should_split_connector(left, right)`

Evita splits agresivos:
- Ambos lados deben ser no-vacíos
- Cada lado debe tener ≤ 8 palabras
- Al menos un lado debe empezar con una palabra de acción

### Paso 4: Consolidación — `_extract_task_seeds(text)`

```python
def _extract_task_seeds(text: str) -> list[str]:
    seeds: list[str] = []
    for chunk in _split_primary_seeds(text):
        split_chunk = _split_obvious_compound_seed(chunk)
        seeds.extend(split_chunk or [chunk])
    return seeds or [text.strip()]
```

Si no sobrevive ninguna semilla, retorna el texto original completo como una sola semilla.

---

## 6. Construcción del Prompt

### System Prompt (`SYSTEM_PROMPT`)

El prompt de sistema define:

- **Esquema JSON requerido** — estructura exacta de la respuesta
- **Reglas de extracción** — respetar comas como límites, preservar orden de semillas
- **Reglas de ordenamiento** — priorizar por bloqueos, esfuerzo, momentum y utilidad
- **Restricciones de output** — step_number continuo desde 1, títulos concisos, minutos entre 5-180
- **Tono del coach** — mezcla español/inglés, directo y de apoyo
- **Topics dinámicos** — generar temas desde el texto real del usuario, no categorías fijas

### User Prompt — `_build_user_prompt(original_text, task_seeds)`

```
Original brain dump:
<texto completo del usuario>

Pre-split task seeds in required order:
1. limpiar cuarto
2. deploy
3. test
4. ver video

Plan around these seeds. Preserve their order unless one seed
obviously contains two separate actions.
```

**Diseño dual:** el modelo recibe dos vistas del input:
1. El texto original freeform (contexto completo)
2. Las semillas pre-extraídas (scaffolding determinista)

---

## 7. Integración con Ollama

### Path Primario: HTTP directo via `requests`

```python
def _generate_with_ollama(user_prompt: str) -> tuple[str, str]:
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "options": {"temperature": 0.2},
        "format": "json",
        "stream": False,
    }
    resp = requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=3600)
```

**¿Por qué `requests` directo?** Es el path más limpio y directo. Funciona cuando Python puede alcanzar la instancia de Ollama directamente.

### Path Fallback: PowerShell Bridge

```python
def _chat_via_windows_ollama(system_prompt, user_text, fmt=None) -> str:
```

**¿Por qué existe?** En entornos mixtos Windows + WSL, Python corriendo bajo Linux puede no alcanzar directamente el Ollama de Windows.

**Flujo:**
1. Construir payload JSON para Ollama
2. Codificar en Base64
3. Ejecutar PowerShell como subproceso
4. Decodificar dentro de PowerShell
5. Llamar `Invoke-RestMethod` contra la API de Ollama
6. Retornar el contenido del modelo a Python

**Detalle crítico:** el bridge fuerza encoding UTF-8 en PowerShell para evitar corrupción de caracteres.

### Metadata de transporte

El backend incluye en `meta.transport` el path usado:
- `requests_direct` — HTTP directo exitoso
- `windows_ollama_bridge` — fallback PowerShell
- `requests_direct+repair` — directo + paso de reparación
- `windows_ollama_bridge+repair` — bridge + reparación

---

## 8. Parsing y Reparación de Output

### Extracción JSON — `_extract_first_json_object(raw)`

Los modelos locales frecuentemente producen output con:
- Code fences de Markdown
- Comentarios antes/después del JSON
- Texto extra fuera del objeto

**Estrategia de extracción:**
1. Limpiar whitespace
2. Remover code fences si están presentes
3. Intentar `json.loads()` directo
4. Si falla, escanear el texto buscando `{`
5. Trackear profundidad de objetos respetando strings y escapes
6. Intentar parsear candidatos hasta encontrar un JSON válido

### Repair Pass — `_repair_content(raw_content)`

Si la extracción o validación falla, el backend ejecuta **un segundo paso de reparación**:

```python
REPAIR_PROMPT = """
You fix malformed model outputs.
Convert the provided text into valid JSON that matches the requested schema exactly.
Return ONLY valid JSON.
"""
```

El contenido malformado se envía de vuelta al modelo con instrucciones de reparación. Esto da una segunda oportunidad antes de fallar con HTTP 422.

---

## 9. Normalización y Validación — `_coerce_and_validate(data, original_text)`

### Coerción de campos de tareas

| Campo | Fallback chain | Límite |
|-------|---------------|--------|
| `title` | `title` → `task` → `name` → `"Untitled task"` | 140 chars |
| `details` | `details` → `description` → `"Take the next concrete action."` | 400 chars |
| `first_move` | `first_move` → `next_action` → `title` | 160 chars |
| `reason` | `reason` → `"Placed to maintain momentum."` | 300 chars |
| `topic` | `topic` → `category` → `theme` → `"General"` | 48 chars |

### Normalización de enums

```python
# Urgency: cualquier valor inválido → "medium"
urgency = str(task.get("urgency", "medium")).strip().lower()
if urgency not in ALLOWED_URGENCY:
    urgency = "medium"

# Energy: cualquier valor inválido → "medium"
energy_level = str(task.get("energy_level", "medium")).strip().lower()
if energy_level not in ALLOWED_ENERGY:
    energy_level = "medium"
```

### Estimaciones de tiempo

```python
estimated = max(5, min(180, estimated))  # Clamped entre 5 y 180 minutos
```

### Ordering final

Las tareas se ordenan por `(step_number, topic, title)` y luego se renumeran secuencialmente desde 1.

---

## 10. Sistema de Topics

Chaos-Triage **no usa categorías fijas**. Los topics se generan dinámicamente para cada plan.

### Normalización — `_normalize_topic(raw_topic)`

- Limpia whitespace y caracteres de puntuación
- Retorna `"General"` si el resultado está vacío
- Trunca a 48 caracteres

### Recolección — `_collect_topics(tasks, raw_topics)`

1. Procesa la lista `topics` del modelo (si existe)
2. Añade topics de tareas individuales
3. Deduplica case-insensitively
4. Retorna `["General"]` si no hay topics válidos

---

## 11. Asignación de Lanes — `_lane_for_task(task, index, total)`

Los lanes son **recomendaciones**, no estados reales.

| Condición | Lane asignado |
|-----------|--------------|
| Primera tarea | `suggested` |
| Urgencia `high` | `suggested` |
| Últimas 2 tareas con urgencia `low` | `done_later` |
| Default | `suggested` |

El frontend **ignora** los lanes para el estado inicial: todas las tareas empiezan en `Pendientes`.

---

## 12. Coach Generation

### Default Coach — `_build_default_coach(tasks)`

Se genera cuando el modelo no retorna un coach válido:

```python
{
    "intro": "Hoy no tienes que resolver toda la vida...",
    "focus": f"Empieza por {first['title']}...",
    "caution": "Cuidado con saltar entre tareas...",
    "steps": [
        f"Primero, start con {first['title']}...",
        f"Luego pasa a {second['title']}...",
        f"Despues entra a {third['title']}..."
    ]
}
```

### Normalización — `_normalize_coach(raw_coach, tasks)`

- Valida que el coach sea un dict
- Limpia y trunca cada campo
- Rellena steps faltantes desde el fallback
- Garantiza exactamente 3 steps

---

## 13. Flujo de Request Completo

```
1. POST /api/triage con {"text": "..."}
2. _extract_input_text() → texto limpio
3. Si texto vacío → HTTP 400
4. _extract_task_seeds() → lista de semillas
5. _build_user_prompt() → prompt formateado
6. _generate_with_ollama() → (content, transport)
   └─ try: requests POST → Ollama
   └─ except: _chat_via_windows_ollama() → PowerShell bridge
7. Si Ollama falla completamente → HTTP 503
8. _extract_first_json_object() → parsed dict
9. _coerce_and_validate() → normalized dict
10. Si falla:
    └─ _repair_content() → second attempt
    └─ _extract_first_json_object() → parsed
    └─ _coerce_and_validate() → normalized
11. Si sigue fallando → HTTP 422 con preview del raw
12. Construir TriageResponse → JSON response
```

---

## 14. Esquema JSON del Modelo (`TRIAGE_SCHEMA`)

El esquema enviado a Ollama como constraint de formato:

```json
{
  "type": "object",
  "required": ["summary", "coach", "topics", "tasks"],
  "properties": {
    "summary": { "type": "string" },
    "coach": {
      "type": "object",
      "required": ["intro", "focus", "caution", "steps"],
      "properties": {
        "intro": { "type": "string" },
        "focus": { "type": "string" },
        "caution": { "type": "string" },
        "steps": { "type": "array", "items": { "type": "string" } }
      }
    },
    "topics": { "type": "array", "items": { "type": "string" } },
    "tasks": {
      "type": "array",
      "items": {
        "type": "object",
        "required": [
          "step_number", "title", "details", "first_move",
          "topic", "urgency", "energy_level",
          "estimated_minutes", "reason"
        ],
        "properties": {
          "step_number": { "type": "integer" },
          "title": { "type": "string" },
          "details": { "type": "string" },
          "first_move": { "type": "string" },
          "topic": { "type": "string" },
          "urgency": { "type": "string", "enum": ["high", "low", "medium"] },
          "energy_level": { "type": "string", "enum": ["deep", "light", "medium"] },
          "estimated_minutes": { "type": "integer" },
          "reason": { "type": "string" }
        }
      }
    }
  }
}
```
