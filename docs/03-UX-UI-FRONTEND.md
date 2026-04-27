# Chaos-Triage — UX/UI y Frontend

> Documento actualizado: Abril 2026  
> Archivo principal: `templates/index.html` (1135 líneas)  
> Stack: HTML5 + Tailwind CSS (CDN) + SortableJS + JavaScript Vanilla

---

## 1. Filosofía de Diseño UX

Chaos-Triage está diseñado para un momento muy específico: cuando el usuario tiene la cabeza llena de tareas, preocupaciones y pendientes desordenados, y necesita convertir ese caos en algo ejecutable.

### Principios de diseño

| Principio | Implementación |
|-----------|---------------|
| **Reducir fricción** | Un solo campo de entrada, un solo botón, resultado inmediato |
| **Control del usuario** | La IA sugiere, el humano ejecuta — nada se auto-marca |
| **Privacidad visual** | Estética oscura, sin logos corporativos, se siente personal y privado |
| **Momentum visual** | Las victorias completadas permanecen visibles para reforzar el progreso |
| **Interacción mínima** | Drag & drop + botones de acción rápida; sin formularios complejos |

### User Flow Principal

```
1. El usuario abre la app (http://127.0.0.1:8000)
2. Pega su descarga mental en el textarea
3. Presiona "Organizar Mi Caos" (o Ctrl+Enter)
4. Espera mientras la IA procesa (~10-60 segundos)
5. Ve el panel de coaching con la estrategia del día
6. Ve el tablero Kanban con sus tareas organizadas
7. Arrastra tareas entre columnas según avanza
8. Agrega tareas nuevas sin re-ejecutar el plan
9. El estado se persiste automáticamente en el navegador
```

---

## 2. Estética Visual

### Paleta de colores

La interfaz usa una estética **dark glassmorphism** con acentos de color vivos:

| Elemento | Color/Estilo |
|----------|-------------|
| **Fondo principal** | `bg-slate-950` (#020617) |
| **Paneles** | `bg-white/5` con `backdrop-blur-xl` — glassmorphism |
| **Bordes** | `border-white/10` — líneas sutiles semi-transparentes |
| **Acento primario** | Cyan (`cyan-300`, `cyan-400`) — botones, highlights, labels |
| **Acento de precaución** | Orange (`orange-300`) — panel de caution del coach |
| **Urgencia alta** | Rose (`rose-500/15`) |
| **Urgencia media** | Amber (`amber-500/15`) |
| **Urgencia baja** | Emerald (`emerald-500/15`) |
| **Glow decorativo** | Esferas blur en cyan, orange y emerald (`blur-3xl`) |

### Efectos de fondo (Background Glow)

```html
<div class="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
  <div class="absolute -top-36 left-1/2 h-[28rem] w-[28rem]
    -translate-x-1/2 rounded-full bg-cyan-500/20 blur-3xl"></div>
  <div class="absolute bottom-0 right-0 h-80 w-80
    rounded-full bg-orange-500/10 blur-3xl"></div>
  <div class="absolute left-0 top-1/2 h-72 w-72
    rounded-full bg-emerald-500/10 blur-3xl"></div>
</div>
```

Tres esferas difuminadas dan profundidad y calidez sin distraer del contenido.

### Tipografía

- **Fuente:** Sora (Google Fonts)
- **Pesos usados:** 300 (light), 400 (regular), 500 (medium), 600 (semibold), 700 (bold)
- **Estilo:** Geométrica, moderna, limpia — ideal para interfaces de productividad

### Sombras y bordes

```javascript
// Tailwind config extendido
boxShadow: {
  glow: '0 0 0 1px rgba(255,255,255,0.08), 0 10px 35px rgba(0,0,0,0.45)'
}
```

Los paneles principales usan `shadow-glow` para un efecto elevado sutil.

### Animaciones

```javascript
keyframes: {
  fadeUp: {
    '0%': { opacity: '0', transform: 'translateY(14px)' },
    '100%': { opacity: '1', transform: 'translateY(0px)' }
  }
},
animation: {
  fadeUp: 'fadeUp 450ms ease-out both'
}
```

Las secciones principales se animan con `animate-fadeUp` al aparecer.

---

## 3. Componentes de Interfaz

### 3.1 Input Card — Zona de Entrada

La primera interacción del usuario es con el campo de texto principal.

**Elementos:**
- Label `PANGU` en cyan (branding del sistema)
- Título principal: *"Convierte tu descarga mental en un plan claro para hoy"*
- Badge `Local + Privado` — refuerza la privacidad
- Textarea con 10 filas, placeholder descriptivo con ejemplos
- Botón `Organizar Mi Caos` con spinner de carga
- Tip sobre el uso de comas

**Comportamiento del botón:**
- Estado normal: fondo cyan, texto oscuro, `hover:bg-cyan-300`
- Estado loading: disabled, spinner SVG animado, texto cambia a "Organizando..."
- Keyboard shortcut: `Ctrl+Enter` o `Cmd+Enter`

**Zona de error:**
```html
<p id="errorMsg" class="hidden rounded-lg border border-rose-500/30
  bg-rose-500/10 px-3 py-2 text-sm text-rose-200"></p>
```

---

### 3.2 Results Section — Zona de Resultados

Se revela con `classList.remove('hidden')` tras recibir la respuesta de la API. Se anima con `animate-fadeUp`.

**Sub-componentes:**
1. Summary Strip (resumen + modelo usado)
2. Coach Panel (guía de coaching)
3. Quick Capture (captura rápida de tareas)
4. Topic Filters (filtros dinámicos)
5. Kanban Board (tablero de ejecución)

---

### 3.3 Coach Panel — Panel de Coaching

Muestra la guía personalizada del día. Tiene **dos modos:**

| Modo | Cuándo se usa | Fuente |
|------|--------------|--------|
| **AI Coach** | Plan recién generado, filtro `all`, sin interacción | `data.coach` del backend |
| **Live Coach** | Tras mover tarjetas, cambiar filtros o interactuar | `buildLiveCoach()` del frontend |

**Layout:**

```
┌─────────────────────────────────────────────────┐
│  Plan Humano            [Estrategia]             │
│  "Hoy no tienes que resolver toda la vida..."    │
│                                                   │
│  ┌──────────────────┐  ┌──────────────────┐      │
│  │ Empieza por esto │  │    Cuidado       │      │
│  │ (cyan gradient)  │  │  (orange accent) │      │
│  │ Focus text...    │  │  Caution text... │      │
│  └──────────────────┘  └──────────────────┘      │
│                                                   │
│  ┌───────────────────────────────────────────┐   │
│  │          Pasos Sugeridos                   │   │
│  │  1. Empieza con...                         │   │
│  │  2. Luego mueve...                         │   │
│  │  3. Después entra a...                     │   │
│  └───────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

**Live Coach Logic (`buildLiveCoach()`):**
- Prioriza tareas visibles del backlog filtrado
- Cae back a tareas en progreso o completadas
- Cambia el tono según si ya hay algo en progreso
- Advierte contra mover tareas de baja prioridad demasiado pronto

---

### 3.4 Quick Capture — Captura Rápida

Permite agregar tareas nuevas sin re-ejecutar la IA.

```
┌─────────────────────────────────────────────────────┐
│  Captura Rápida                 [Se guarda localmente]│
│  Cuando aparezca una tarea nueva...                   │
│                                                       │
│  [  Input text...                 ] [Agregar al tablero]│
│                                                       │
│  ✓ "Tarea agregada al tablero sin rerun del plan."    │
└─────────────────────────────────────────────────────────┘
```

**Comportamiento:**
- Split por comas (igual que la extracción principal)
- Cada fragmento se convierte en una tarea manual
- Topic inferido: si hay un filtro activo, usa ese topic; si no, usa `"Nuevas ideas"`
- Las tareas se insertan al **inicio** del backlog
- Estado se persiste inmediatamente
- Keyboard shortcut: `Enter` para agregar

**Creación de tareas manuales (`createManualTask()`):**
```javascript
{
  client_id: nextLocalTaskId(),  // UUID generado en el browser
  step_number: highestStep + offset + 1,
  title: cleanTitle,             // Capitalizado automáticamente
  urgency: "medium",
  energy_level: "medium",
  estimated_minutes: 20,
  reason: "Añadida manualmente durante el día.",
  lane: "suggested"
}
```

---

### 3.5 Topic Filters — Filtros por Tema

Los filtros se generan dinámicamente desde los topics del plan actual.

```
[Todos los temas] [Casa] [Estudio] [Trabajo] [Entretenimiento]
```

**Comportamiento:**
- `Todos los temas` siempre presente
- Solo muestra topics que existen en el plan actual
- Filtro activo resaltado con `bg-cyan-300 text-slate-950`
- Filtro inactivo con `bg-white/5 text-slate-300`
- Cambiar filtro actualiza inmediatamente:
  - Coach panel (cambia a Live Coach)
  - Tarjetas visibles en cada columna
  - Board hint text
- Filtrar **no destruye** la posición de tarjetas ocultas

---

### 3.6 Kanban Board — Tablero Principal

Tres columnas con drag & drop entre ellas:

| Columna | Color border | Semántica |
|---------|-------------|-----------|
| **Pendientes** | `cyan-300/20` | Tareas sugeridas por la IA, ordenadas |
| **En Progreso** | `amber-300/20` | Solo lo que el usuario movió intencionalmente |
| **Completadas** | `emerald-300/20` | Victorias visibles para mantener momentum |

**Estado inicial:** Todas las tareas empiezan en **Pendientes**. Nunca se auto-asigna En Progreso o Completadas.

---

### 3.7 Task Cards — Tarjetas de Tarea

Cada tarea se renderiza como una tarjeta compacta:

```
┌──────────────────────────────────────────────┐
│ ⋮⋮ Arrastrar                                 │
│   Pendiente #1                                │
│   Limpiar cuarto                              │
│                                               │
│   [Casa] [25 min] [light energía]             │
│                                               │
│   [Empezar] [Completar] [Eliminar]            │
└──────────────────────────────────────────────┘
```

**Elementos de cada tarjeta:**
- Handle de arrastre con icono `⋮⋮`
- Label de posición (Pendiente #N / En progreso / Completada)
- Título (truncado con `truncate`)
- Pills de metadatos: topic (color por hash), minutos estimados, nivel de energía
- Botones de acción contextual según la columna

**Acciones por columna:**

| Columna | Acciones disponibles |
|---------|---------------------|
| Pendientes | Empezar, Completar, Eliminar |
| En Progreso | Volver, Completar, Eliminar |
| Completadas | Reabrir, Eliminar |

**Estilo de topic pills:**

6 paletas de color asignadas por hash del nombre del topic:
- Cyan, Emerald, Amber, Fuchsia, Orange, Sky

```javascript
const TOPIC_STYLE_PALETTE = [
  { border: 'border-cyan-300/30', pill: 'bg-cyan-400/15 text-cyan-100' },
  { border: 'border-emerald-300/30', pill: 'bg-emerald-400/15 text-emerald-100' },
  { border: 'border-amber-300/30', pill: 'bg-amber-400/15 text-amber-100' },
  { border: 'border-fuchsia-300/30', pill: 'bg-fuchsia-400/15 text-fuchsia-100' },
  { border: 'border-orange-300/30', pill: 'bg-orange-400/15 text-orange-100' },
  { border: 'border-sky-300/30', pill: 'bg-sky-400/15 text-sky-100' }
];
```

---

## 4. Drag & Drop System

### Configuración de SortableJS

```javascript
Sortable.create(element, {
  group: 'chaos-board',          // Grupo compartido entre 3 columnas
  animation: 170,                // Duración de animación (ms)
  draggable: '.task-card',       // Selector de elementos arrastrables
  delayOnTouchOnly: true,        // Delay solo en touch (no mouse)
  delay: 80,                     // Delay antes de iniciar drag
  emptyInsertThreshold: 28,      // Zona sensible para columnas vacías
  filter: 'button,[data-no-drag]', // Elementos que NO inician drag
  preventOnFilter: false,        // Permitir click en filtered elements
  ghostClass: 'sortable-ghost',  // Clase del ghost (opacity: 0.22)
  chosenClass: 'sortable-chosen', // Clase al seleccionar
  dragClass: 'sortable-drag'     // Clase durante el drag
});
```

### Feedback visual durante drag

**Al iniciar drag (`onStart`):**
- Se remueven empty states
- Todas las columnas reciben `is-drop-ready` (borde dashed sutil)

**Al mover sobre columna (`onMove`):**
- La columna target recibe `is-drop-target`:
  - Borde dashed cyan brillante
  - Gradiente de fondo destacado
  - Sombra glow
  - Transform `translateY(-2px)`

**Al soltar (`onEnd`):**
- Se limpian todos los estilos de drop target
- Se ejecuta `handleSortEnd()` para actualizar el estado

### CSS de drag states

```css
.task-card.sortable-ghost   { opacity: 0.22; }
.task-card.sortable-chosen  { border-color: rgba(103, 232, 249, 0.65);
                              box-shadow: 0 0 0 1px rgba(103, 232, 249, 0.28),
                                          0 16px 40px rgba(6, 182, 212, 0.22); }
.task-card.sortable-drag    { opacity: 0.95 !important;
                              transform: rotate(1deg) scale(1.02);
                              box-shadow: 0 24px 48px rgba(2, 132, 199, 0.28); }
```

### Hover effects en tarjetas

```css
.task-card {
  transition: transform 160ms ease, box-shadow 160ms ease,
              border-color 160ms ease, opacity 160ms ease;
}
.task-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 18px 42px rgba(8, 145, 178, 0.14);
}
```

---

## 5. Reordenamiento con Filtros Activos

**Problema:** Cuando un filtro está activo, solo algunas tarjetas son visibles. Si el usuario arrastra tarjetas visibles, las tarjetas ocultas no deben perderse ni corromperse.

**Solución:** `mergeVisibleOrder(fullIds, visibleIds)`

```javascript
function mergeVisibleOrder(fullIds, visibleIds) {
  const visibleSet = new Set(fullIds.filter(id => taskMatchesFilterId(id)));
  // Intercalar el nuevo orden visible con las tarjetas ocultas
  // preservando la posición relativa de los elementos ocultos
}
```

Esto garantiza que:
- Solo el subconjunto visible cambia de orden
- Las tarjetas ocultas permanecen en su posición
- El tablero es coherente cuando se remueve el filtro

---

## 6. Empty States

Cada columna tiene un mensaje cuando está vacía:

| Columna | Mensaje |
|---------|---------|
| Pendientes | "No hay tareas pendientes con este filtro." |
| En Progreso | "Arrastra una tarjeta aquí cuando realmente la empieces." |
| Completadas | "Las tareas terminadas aparecerán aquí." |

Los empty states se implementan con `data-empty-state="true"` y se eliminan al iniciar un drag.

---

## 7. Eliminación de Tareas

**Flujo:**
1. Usuario hace click en "Eliminar"
2. `window.confirm()` pide confirmación con el título de la tarea
3. La tarea se remueve del plan, taskMap y boardState
4. Los topics se recalculan
5. Si el filtro activo ya no tiene tareas, se resetea a `all`
6. Si no quedan tareas, se muestra un coach de "tablero en cero"
7. Estado se persiste y se re-renderiza

---

## 8. Responsiveness

La interfaz es responsive por defecto via Tailwind:

| Breakpoint | Layout del board |
|------------|-----------------|
| Mobile (< 1280px) | Columnas apiladas verticalmente |
| Desktop (≥ 1280px) | Grid de 3 columnas (`xl:grid-cols-3`) |

Otros ajustes responsive:
- Coach panel: `lg:grid-cols-[1.1fr_0.9fr]` para focus/caution
- Quick capture: `lg:flex-row` para input + botón
- Padding adaptativo: `px-4 sm:px-6 lg:px-8`
- Ancho máximo: `max-w-7xl` (board), `max-w-4xl` (input)
