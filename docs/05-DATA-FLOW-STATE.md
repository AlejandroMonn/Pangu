# Chaos-Triage — Flujo de Datos y Gestión de Estado

> Documento actualizado: Abril 2026  
> Scope: End-to-end data flow, estado del frontend, persistencia y ciclo de vida

---

## 1. Visión General

El flujo de datos de Chaos-Triage atraviesa cuatro capas en un ciclo completo:

```
Usuario → Frontend → Backend → Ollama → Backend → Frontend → localStorage
```

Este documento describe cómo los datos se transforman en cada paso, cómo se gestiona el estado en el frontend, y cómo la persistencia mantiene el workspace del usuario entre sesiones.

---

## 2. Flujo End-to-End Detallado

### Fase 1: Entrada del Usuario

```
┌──────────────────────────────────────────────────┐
│ Input:                                            │
│ "limpiar cuarto, deploy then test, ver un video" │
└──────────────────────────┬───────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────┐
│ Frontend: runTriage()                             │
│                                                    │
│ 1. Lee textarea value                             │
│ 2. Valida que no esté vacío                       │
│ 3. clearError() + setLoading(true)                │
│ 4. fetch('/api/triage', {                         │
│      method: 'POST',                              │
│      headers: {'Content-Type': 'application/json'},│
│      body: JSON.stringify({ text })               │
│    })                                              │
└──────────────────────────┬───────────────────────┘
                           │ HTTP POST
                           ▼
```

### Fase 2: Procesamiento Backend

```
┌──────────────────────────────────────────────────┐
│ Backend: POST /api/triage                         │
│                                                    │
│ Step 1: _extract_input_text()                     │
│   Raw bytes → UTF-8 string → JSON parse → "text" │
│   Resultado: "limpiar cuarto, deploy then test,   │
│               ver un video"                        │
│                                                    │
│ Step 2: _extract_task_seeds()                     │
│   Split por comas:                                 │
│     ["limpiar cuarto",                             │
│      "deploy then test",                           │
│      "ver un video"]                               │
│   Split compuestos:                                │
│     ["limpiar cuarto",                             │
│      "deploy", "test",                             │
│      "ver un video"]                               │
│                                                    │
│ Step 3: _build_user_prompt()                      │
│   "Original brain dump:\n..."                      │
│   "Pre-split task seeds:\n1. limpiar cuarto\n..."  │
│                                                    │
│ Step 4: _generate_with_ollama()                   │
│   → POST http://127.0.0.1:11434/api/chat          │
│   ← JSON content string                           │
│   Transport: "requests_direct"                     │
│                                                    │
│ Step 5: _extract_first_json_object()              │
│   Raw LLM output → parsed dict                    │
│                                                    │
│ Step 6: _coerce_and_validate()                    │
│   → Normalizar campos                             │
│   → Clamp valores                                  │
│   → Asignar lanes                                  │
│   → Renumerar step_numbers                         │
│   → Generar meta                                   │
│                                                    │
│ Step 7: TriageResponse(**normalized)              │
│   Validación Pydantic final                        │
└──────────────────────────┬───────────────────────┘
                           │ HTTP 200 JSON
                           ▼
```

### Fase 3: Aplicación en el Frontend

```
┌──────────────────────────────────────────────────┐
│ Frontend: applyPlan(data)                         │
│                                                    │
│ 1. hydratePlan(data)                              │
│    → Normaliza cada tarea con hydrateTask()       │
│    → Genera client_id si no existe                │
│    → Normaliza topics                              │
│                                                    │
│ 2. currentPlan = hydratedPlan                     │
│ 3. initialCoach = hydratedPlan.coach              │
│ 4. setTaskMap(tasks) — Map<id, task>              │
│ 5. loadPersistedState(tasks)                      │
│    → Restaura boardState de localStorage          │
│    → O crea defaultBoard (todo en backlog)        │
│                                                    │
│ 6. summaryText.textContent = plan.summary         │
│ 7. modelTag.textContent = "Modelo: ..."           │
│ 8. persistWorkspace()                             │
│ 9. renderPlan()                                    │
│    → renderCoach()                                 │
│    → renderFilters()                               │
│    → renderBoard()                                 │
│       → renderColumn('backlog', ...)               │
│       → renderColumn('in_progress', ...)           │
│       → renderColumn('done', ...)                  │
│       → attachCardActions()                        │
│       → initSortables()                            │
│                                                    │
│ 10. resultsSection.classList.remove('hidden')      │
│ 11. scrollIntoView({ behavior: 'smooth' })        │
└──────────────────────────────────────────────────┘
```

---

## 3. Transformación de Datos por Capa

### 3.1 Texto → Semillas (Backend)

```
Input:  "limpiar cuarto, deploy then test, ver un video"

Paso 1 (comma split):
  ["limpiar cuarto", "deploy then test", "ver un video"]

Paso 2 (compound split):
  ["limpiar cuarto", "deploy", "test", "ver un video"]
```

### 3.2 Semillas → Prompt (Backend)

```
Input: seeds = ["limpiar cuarto", "deploy", "test", "ver un video"]

Output:
  "Original brain dump:
   limpiar cuarto, deploy then test, ver un video

   Pre-split task seeds in required order:
   1. limpiar cuarto
   2. deploy
   3. test
   4. ver un video

   Plan around these seeds. Preserve their order..."
```

### 3.3 Prompt → LLM Response (Ollama)

```json
{
  "summary": "Plan de 4 tareas organizadas...",
  "coach": {
    "intro": "Hoy no tienes que resolver toda la vida...",
    "focus": "Empieza por limpiar cuarto...",
    "caution": "Cuidado con saltar entre tareas...",
    "steps": ["Primero...", "Luego...", "Después..."]
  },
  "topics": ["Casa", "Trabajo", "Entretenimiento"],
  "tasks": [
    {
      "step_number": 1,
      "title": "Limpiar cuarto",
      "topic": "Casa",
      "urgency": "medium",
      "energy_level": "light",
      "estimated_minutes": 25,
      ...
    }
  ]
}
```

### 3.4 LLM Response → Normalized Response (Backend)

Transformaciones aplicadas por `_coerce_and_validate()`:

| Campo | Transformación |
|-------|---------------|
| `title` | Truncado a 140 chars, fallback chain |
| `details` | Truncado a 400 chars |
| `first_move` | Truncado a 160 chars |
| `urgency` | Validado contra `{low, medium, high}` |
| `energy_level` | Validado contra `{light, medium, deep}` |
| `estimated_minutes` | Clamped `[5, 180]` |
| `topic` | Normalizado, truncado a 48 chars |
| `step_number` | Renumerado secuencialmente |
| `lane` | Calculado por `_lane_for_task()` |

### 3.5 API Response → Hydrated Plan (Frontend)

`hydratePlan()` + `hydrateTask()` aplican:

| Campo | Transformación |
|-------|---------------|
| `task_id` | Preservado o `null` |
| `client_id` | Generado si no existe (`crypto.randomUUID()`) |
| `step_number` | Coercionado a número |
| `title` | Trim, fallback a `"Tarea N"` |
| `details` | Fallback a title |
| `first_move` | Fallback a title |
| `topic` | Normalizado a texto limpio |
| `estimated_minutes` | `Math.max(5, ...)` |

---

## 4. Modelo de Estado del Frontend

### 4.1 Variables de Estado Global

```javascript
let currentPlan = null;       // Plan completo actual (TriageResponse hidratado)
let initialCoach = null;      // Coach del AI (antes de interacción)
let taskMap = new Map();      // Map<taskId, taskObject> para lookup rápido
let boardState = {            // IDs de tareas por columna
  backlog: [],
  in_progress: [],
  done: []
};
let taskStatus = {};          // Map<taskId, columnName> derivado
let currentFilter = 'all';   // Topic filter activo
let hasInteracted = false;    // ¿El usuario ha movido/filtrado algo?
let sortables = [];           // Instancias SortableJS activas
let activeDropColumn = null;  // Columna target durante drag
let localTaskCounter = 0;     // Contador para IDs de tareas manuales
```

### 4.2 Identidad de Tareas

```javascript
function taskId(task) {
  return String(task.task_id || task.client_id || `${task.step_number}-${task.title}`);
}
```

**Cadena de prioridad:** `task_id` → `client_id` → `step_number-title`

Las tareas generadas por la API usan `step_number-title`.  
Las tareas manuales usan `client_id` (UUID del browser).

### 4.3 Identidad de Plan

```javascript
function planKey(tasks) {
  return `chaos-triage:${tasks.map(task => taskId(task)).join('|')}`;
}
```

El plan key es un hash determinista basado en todas las tareas. Esto permite:
- Scopear la persistencia por plan específico
- Restaurar estado cuando se regenera el mismo plan
- Evitar conflictos entre planes distintos

---

## 5. Sistema de Persistencia

### 5.1 Persistencia por Plan (`localStorage`)

Cada plan tiene su propio namespace en `localStorage`:

```javascript
function storageKey(suffix) {
  return `${planKey(currentPlan.tasks)}:${suffix}`;
}
```

**Claves persistidas:**

| Sufijo | Contenido | Tipo |
|--------|-----------|------|
| `columns` | `{ backlog: [...ids], in_progress: [...ids], done: [...ids] }` | JSON |
| `status` | `{ taskId: "column", ... }` | JSON |
| `filter` | `"all"` o nombre de topic | String |

### 5.2 Persistencia del Workspace

Además de la persistencia por plan, existe un snapshot global del workspace:

```javascript
const WORKSPACE_STORAGE_KEY = 'chaos-triage:workspace:v1';

function persistWorkspace() {
  const snapshot = {
    currentPlan,
    initialCoach,
    boardState,
    currentFilter,
    hasInteracted,
    brainDump: brainDump.value || ''
  };
  localStorage.setItem(WORKSPACE_STORAGE_KEY, JSON.stringify(snapshot));
}
```

**El workspace se restaura al cargar la página** — `restoreWorkspace()` se ejecuta al final del script.

Esto permite:
- Mantener el tablero entre recargas
- Preservar el texto del textarea
- Restaurar el estado completo sin re-ejecutar la IA

### 5.3 Restauración del Estado — `loadPersistedState(tasks)`

```
1. Crear board default (todas las tareas en backlog)
2. Cargar columns guardadas en localStorage
3. Cargar status guardado
4. Cargar filtro guardado
5. Reconstruir boardState:
   a. Para cada columna guardada, restaurar IDs conocidos
   b. Para IDs no encontrados en ninguna columna,
      ponerlos en su columna guardada o en backlog
6. Derivar taskStatus de las columnas
7. Detectar si hubo interacción previa (boardChanged || filter != 'all')
```

### 5.4 Flujo de Persistencia

```
Interacción del usuario (drag, click, filter)
  ↓
Actualizar boardState / taskStatus / currentFilter
  ↓
hasInteracted = true
  ↓
persistState()
  ├── localStorage.setItem(storageKey('columns'), boardState)
  ├── localStorage.setItem(storageKey('status'), taskStatus)
  ├── localStorage.setItem(storageKey('filter'), currentFilter)
  └── persistWorkspace()
        └── localStorage.setItem(WORKSPACE_STORAGE_KEY, snapshot)
```

---

## 6. Ciclo de Vida del Board State

### 6.1 Creación (Plan Nuevo)

```javascript
function defaultBoard(tasks) {
  return {
    backlog: tasks.sort(by step_number).map(taskId),
    in_progress: [],
    done: []
  };
}
```

**Regla fundamental:** Todas las tareas empiezan en `backlog`. Nunca se auto-asigna `in_progress` ni `done`.

### 6.2 Movimiento por Drag & Drop

```javascript
function handleSortEnd(evt) {
  const source = evt.from.dataset.column;
  const target = evt.to.dataset.column;
  const movedId = evt.item.dataset.taskId;

  if (source === target) {
    // Reorder dentro de la misma columna
    boardState[source] = mergeVisibleOrder(boardState[source], domTaskIds(evt.to));
  } else {
    // Mover entre columnas
    boardState[source] = mergeVisibleOrder(
      boardState[source].filter(id => id !== movedId),
      domTaskIds(evt.from)
    );
    boardState[target] = mergeVisibleOrder(
      boardState[target].filter(id => id !== movedId),
      domTaskIds(evt.to)
    );
  }

  deriveStatusFromColumns();
  hasInteracted = true;
  persistState();
  renderPlan();
}
```

### 6.3 Movimiento por Botones

```javascript
function moveTaskToColumn(id, targetColumn) {
  // Remover de todas las columnas
  Object.keys(boardState).forEach(col => {
    boardState[col] = boardState[col].filter(key => key !== id);
  });

  // Insertar en la columna target
  if (targetColumn === 'backlog')     boardState.backlog.push(id);      // Al final
  if (targetColumn === 'in_progress') boardState.in_progress.unshift(id); // Al inicio
  if (targetColumn === 'done')        boardState.done.unshift(id);        // Al inicio
}
```

**Lógica de inserción:**
- `backlog` → al final (mantener orden sugerido arriba)
- `in_progress` → al inicio (la tarea activa es la más visible)
- `done` → al inicio (la victoria más reciente primero)

### 6.4 Eliminación de Tareas

```javascript
function deleteTask(id) {
  // 1. Confirmar con el usuario
  // 2. Remover del plan
  currentPlan.tasks = currentPlan.tasks.filter(item => taskId(item) !== id);
  // 3. Recalcular topics
  currentPlan.topics = uniqueTopics(currentPlan.tasks.map(t => t.topic));
  // 4. Actualizar taskMap
  setTaskMap(currentPlan.tasks);
  // 5. Remover del board
  Object.keys(boardState).forEach(col => {
    boardState[col] = boardState[col].filter(key => key !== id);
  });
  // 6. Reset filtro si topic eliminado
  if (currentFilter !== 'all' && !currentPlan.topics.includes(currentFilter)) {
    currentFilter = 'all';
  }
  // 7. Si vacío, mostrar coach de reset
}
```

### 6.5 Adición de Tareas Manuales (Quick Capture)

```javascript
function addQuickTasks() {
  // 1. Split por comas
  // 2. Crear tareas manuales con client_id
  // 3. Insertar al INICIO del plan y backlog
  currentPlan.tasks = [...newTasks, ...currentPlan.tasks];
  boardState.backlog = dedupe([...newIds, ...boardState.backlog]);
  // 4. Actualizar topics
  // 5. Persistir y re-renderizar
}
```

---

## 7. Sistema de Coaching Dual

### 7.1 Selección de Modo

```javascript
function renderCoach() {
  const coach = (!hasInteracted && currentFilter === 'all' && initialCoach)
    ? initialCoach   // AI Coach
    : buildLiveCoach(); // Live Coach
}
```

| Condición | Modo |
|-----------|------|
| Plan recién generado + filtro `all` + sin interacción | **AI Coach** |
| Cualquier movimiento, cambio de filtro o restauración | **Live Coach** |

### 7.2 Live Coach — Generación Reactiva

```javascript
function buildLiveCoach() {
  const backlog = getFilteredColumnTasks('backlog');
  const doing = getFilteredColumnTasks('in_progress');
  const done = getFilteredColumnTasks('done');

  // Prioridad: backlog visible → in_progress → done → plan original
  const first = backlog[0] || doing[0] || done[0] || currentPlan.tasks[0];

  return {
    intro: doing.length
      ? `Vas bien. Ya moviste ${doing[0].title} a En Progreso...`
      : 'Hoy no necesitas hacerlo todo de golpe...',
    focus: backlog.length
      ? `Empieza por ${backlog[0].title}...`
      : `Si no hay tareas visibles en Pendientes...`,
    caution: hasLowPriorityTail
      ? 'Ojo: deja las tareas de baja prioridad para más tarde...'
      : 'Ojo con cambiar de contexto demasiado rápido...',
    steps: [...]
  };
}
```

---

## 8. Sistema de Filtrado

### 8.1 Rendering de Filtros

```javascript
function renderFilters() {
  const topics = ['all', ...planTopics()];
  // Si el filtro actual no existe, reset a 'all'
  if (!topics.includes(currentFilter)) currentFilter = 'all';
  // Generar botones
}
```

### 8.2 Efecto del Filtrado

| Lo que cambia | Cómo |
|---------------|------|
| Tarjetas visibles | `getFilteredColumnTasks()` filtra por topic |
| Coach | Cambia a Live Coach con tareas filtradas |
| Board hint | Muestra el filtro activo |
| Orden de tarjetas | `mergeVisibleOrder()` preserva ocultas |

| Lo que NO cambia |
|-------------------|
| Posición de tarjetas ocultas |
| Estado (columna) de tarjetas ocultas |
| Plan original |

### 8.3 Topic Matching

```javascript
function taskMatchesFilterId(id) {
  if (currentFilter === 'all') return true;
  const task = taskMap.get(id);
  return Boolean(task && task.topic === currentFilter);
}
```

Match exacto por nombre de topic (case-sensitive).

---

## 9. Derivación de Estado

### `deriveStatusFromColumns()`

Reconstruye `taskStatus` desde `boardState`:

```javascript
function deriveStatusFromColumns() {
  const next = {};
  Object.entries(boardState).forEach(([column, ids]) => {
    ids.forEach(id => { next[id] = column; });
  });
  taskStatus = next;
}
```

Esta función se llama después de cada cambio al boardState para mantener consistencia.

---

## 10. Deduplicación

```javascript
function dedupe(ids) {
  const seen = new Set();
  return ids.filter(id => {
    if (seen.has(id)) return false;
    seen.add(id);
    return true;
  });
}
```

Se usa en:
- `mergeVisibleOrder()` — después de intercalar visible/oculto
- `addQuickTasks()` — al insertar nuevos IDs en backlog
- `loadPersistedState()` — implícitamente via seen set

---

## 11. Ciclo de Renderizado

Cada interacción del usuario dispara un **rerender completo** del plan:

```javascript
function renderPlan() {
  if (!currentPlan) return;
  renderCoach();    // 1. Actualizar panel de coaching
  renderFilters();  // 2. Actualizar botones de filtro
  renderBoard();    // 3. Actualizar columnas, tarjetas, sortables
}
```

`renderBoard()` a su vez:
1. Renderiza cada columna con tarjetas filtradas
2. Actualiza el board hint
3. Attaches event listeners a botones de acción
4. Destruye e inicializa SortableJS

**Este enfoque "rerender everything"** es simple y correcto para el tamaño actual de la aplicación. Con ~20 tareas máximo por plan, no hay problema de performance.

---

## 12. Diagrama de Estado Completo

```
                    ┌─────────────┐
                    │  Página se  │
                    │   carga     │
                    └──────┬──────┘
                           │
                    restoreWorkspace()
                           │
                    ┌──────┴──────┐
                    │  ¿Hay plan  │
                    │  guardado?  │
                    └──────┬──────┘
                     SÍ    │    NO
                    ┌──────┘    └──────┐
                    │                   │
              renderPlan()        Esperar input
                    │                   │
                    │            runTriage() ←── Ctrl+Enter
                    │                   │
                    │             applyPlan()
                    │                   │
                    ├───────────────────┘
                    │
              ┌─────┴─────┐
              │ Board activo│
              └─────┬──────┘
                    │
        ┌───────────┼───────────┬───────────┐
        │           │           │           │
    Drag/Drop   Button     Filter      Quick Add
        │       click      change      task(s)
        │           │           │           │
        ▼           ▼           ▼           ▼
   handleSort  moveTask   currentFilter  addQuick
   End()       ToColumn()  = topic      Tasks()
        │           │           │           │
        └───────────┴───────────┴───────────┘
                         │
                  hasInteracted = true
                         │
                  persistState()
                         │
                  renderPlan()
```

---

## 13. Limitaciones Conocidas

| Limitación | Impacto | Mitigación posible |
|-----------|---------|-------------------|
| Task ID basado en título | Colisiones si dos tareas tienen mismo título y step | UUIDs generados por el backend |
| Sin base de datos | Estado solo en el browser local | Export/import de planes |
| Sin multi-dispositivo | No hay sync entre máquinas | API de sync o cloud storage |
| Sin autenticación | Herramienta personal, un solo usuario | N/A para el caso de uso actual |
| Frontend monolítico | Mantenibilidad a largo plazo | Separar en módulos ES |
| Rerender completo | O(n) por interacción | Virtual DOM o patch selectivo |
| localStorage limitado | ~5-10MB según browser | IndexedDB para planes grandes |
