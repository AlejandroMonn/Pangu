# Chaos-Triage — Arquitectura del Sistema

> Documento actualizado: Abril 2026  
> Versión del sistema: 1.0.0  
> Modelo por defecto: `qwen3:8b`

---

## 1. Visión General

Chaos-Triage es una herramienta de planificación 100% local que transforma una descarga mental desestructurada en un plan de acción organizado. El sistema combina inteligencia artificial local (Ollama) con una interfaz Kanban interactiva para convertir texto caótico en tareas priorizadas, filtradas por tema y ejecutables.

### Filosofía de diseño

El sistema se construye sobre dos principios fundamentales:

- **La IA genera estructura** — El modelo local analiza el texto del usuario, identifica tareas implícitas, asigna prioridades, estima tiempos y genera una guía de coaching personalizada.
- **El humano controla la ejecución** — Todas las tareas generadas comienzan en estado "Pendientes". El usuario decide cuándo empezar, reordenar, completar o eliminar cada tarea.

### Decisiones de producto clave

| Decisión | Justificación |
|----------|--------------|
| **Windows-first** | El usuario principal trabaja en Windows; los scripts de arranque priorizan esta plataforma |
| **Inferencia local** | Sin dependencia de APIs en la nube; la privacidad del usuario está garantizada |
| **Sin base de datos** | Estado persistido en `localStorage` del navegador; simplicidad sobre escalabilidad |
| **Sin build step** | Un solo archivo HTML con Tailwind CDN y SortableJS CDN; iteración rápida |
| **Frontend monolítico** | Todo el UI en `templates/index.html`; fácil de leer, depurar y modificar |
| **JSON estricto** | Contrato rígido entre backend y frontend para estabilidad ante drift del modelo |

---

## 2. Diagrama de Arquitectura

```
┌──────────────────────────────────────────────────────────────────────┐
│                        USUARIO (Navegador)                          │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │
│  │  Input Card  │  │ Coach Panel  │  │    Kanban Board           │   │
│  │  (textarea)  │  │ (AI/Live)    │  │  [Pendientes|En Prog|OK] │   │
│  └──────┬───────┘  └──────────────┘  └──────────────────────────┘   │
│         │              ▲                       ▲                     │
│         │              │                       │                     │
│         ▼              │         localStorage  │                     │
│  ┌──────────────┐      │        ┌──────────────┤                    │
│  │ fetch()      │      │        │ Persistencia │                    │
│  │ POST /triage │      │        │ por plan     │                    │
│  └──────┬───────┘      │        └──────────────┘                    │
└─────────┼──────────────┼────────────────────────────────────────────┘
          │              │
          ▼              │
┌─────────────────────────────────────────────────────────────────────┐
│                    BACKEND (FastAPI + Uvicorn)                       │
│                                                                      │
│  ┌────────────────┐  ┌──────────────┐  ┌────────────────────────┐   │
│  │ Input Parser   │  │ Seed Extract │  │ Prompt Builder         │   │
│  │ JSON/PlainText │→ │ Comma-first  │→ │ System + User prompt   │   │
│  └────────────────┘  └──────────────┘  └───────────┬────────────┘   │
│                                                     │                │
│                                                     ▼                │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                    Ollama Integration                          │  │
│  │  ┌──────────────────┐    ┌──────────────────────────────────┐ │  │
│  │  │ Primary Path:    │    │ Fallback Path:                   │ │  │
│  │  │ requests (HTTP)  │    │ PowerShell Bridge (subprocess)   │ │  │
│  │  └────────┬─────────┘    └───────────────┬──────────────────┘ │  │
│  └───────────┼──────────────────────────────┼────────────────────┘  │
│              │                              │                        │
│              ▼                              ▼                        │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                    Post-Processing Pipeline                    │  │
│  │  JSON Extract → Repair Pass (si falla) → Normalize → Validate │  │
│  └───────────────────────────────────────────┬───────────────────┘  │
│                                               │                      │
│                                               ▼                      │
│                                     TriageResponse JSON              │
└──────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      OLLAMA (Local LLM Server)                       │
│                                                                      │
│  Modelo: qwen3:8b                                                    │
│  Host:   http://127.0.0.1:11434                                      │
│  API:    /api/chat (inferencia) | /api/tags (health) | /api/generate │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. Stack Tecnológico

### Backend

| Componente | Tecnología | Versión / Notas |
|------------|------------|-----------------|
| Framework HTTP | FastAPI | Async, tipado estricto con Pydantic |
| Servidor ASGI | Uvicorn | Auto-reload en desarrollo |
| Cliente LLM | `ollama` (Python) + `requests` | Doble path de transporte |
| Validación | Pydantic BaseModel | `TriageResponse`, `TriageTask`, `TriageCoach` |
| Lenguaje | Python 3.12+ | Type hints modernos (`dict[str, Any]`, `list[str]`) |

### Frontend

| Componente | Tecnología | Notas |
|------------|------------|-------|
| Estructura | HTML5 semántico | `<main>`, `<section>`, `<article>` |
| Estilos | Tailwind CSS v3+ (CDN) | Configuración extendida inline con `tailwind.config` |
| Tipografía | Google Fonts — Sora | Pesos: 300, 400, 500, 600, 700 |
| Drag & Drop | SortableJS v1.15.2 (CDN) | Grupo compartido `chaos-board` |
| Lógica | JavaScript Vanilla (ES6+) | Sin framework, sin bundler |
| Persistencia | `localStorage` | Scopeado por plan generado |

### Infraestructura

| Componente | Tecnología | Notas |
|------------|------------|-------|
| LLM Local | Ollama | Sirve modelos en `127.0.0.1:11434` |
| Modelo | `qwen3:8b` | Configurable via `OLLAMA_MODEL` |
| Launcher | PowerShell + CMD | Bootstrap completo de dependencias y servicios |
| WSL Support | Bash script | Path alternativo para entornos Linux/WSL |

---

## 4. Estructura del Proyecto

```
d:\Manager\
├── main.py                              # Backend FastAPI (654 líneas)
├── requirements.txt                     # Dependencias Python: fastapi, uvicorn, ollama
├── templates/
│   └── index.html                       # Frontend completo (1135 líneas)
├── scripts/
│   ├── start-chaos-triage.cmd           # Entry point Windows (doble click)
│   ├── start-chaos-triage.ps1           # Bootstrap PowerShell completo
│   ├── start-chaos-triage-wsl.sh        # Launcher para WSL/Linux
│   └── install-chaos-triage-startup.ps1 # Instalar shortcut de arranque automático
├── docs/                                # Documentación del sistema (este directorio)
│   ├── 01-ARCHITECTURE.md               # Este archivo
│   ├── 02-BACKEND-API.md                # Backend y API detallados
│   ├── 03-UX-UI-FRONTEND.md            # Diseño visual y frontend
│   ├── 04-DEVOPS-DEPLOYMENT.md          # Scripts de arranque y despliegue
│   └── 05-DATA-FLOW-STATE.md           # Flujo de datos y gestión de estado
├── LICENSE                              # MIT License
├── README.md                            # Overview del proyecto
├── SECURITY.md                          # Guía de seguridad y privacidad
├── DOCUMENTATION.md                     # Documentación técnica legacy (completa)
└── .gitignore                           # Exclusiones de Git configuradas
```

---

## 5. Capas del Sistema

### Capa 1: Presentación (Frontend)
- Interfaz Kanban con 3 columnas: **Pendientes**, **En Progreso**, **Completadas**
- Panel de coaching con dos modos: AI Coach (inicial) y Live Coach (reactivo)
- Filtros dinámicos por tema generados por la IA
- Captura rápida de tareas sin re-ejecutar el plan
- Persistencia local en `localStorage`

### Capa 2: Lógica de Negocio (Backend)
- Extracción determinista de semillas de tareas (comma-first)
- Construcción de prompts con contexto dual (texto original + semillas)
- Integración con Ollama via doble path de transporte
- Pipeline de post-procesamiento: extracción JSON → reparación → normalización → validación
- Contrato de respuesta estricto con Pydantic

### Capa 3: Inteligencia Artificial (Ollama)
- Modelo local `qwen3:8b` ejecutándose en la máquina del usuario
- Sin conexión a la nube; toda la inferencia es local
- Prompt de sistema estricto con esquema JSON obligatorio
- Temperatura baja (0.2) para respuestas consistentes

### Capa 4: Infraestructura (Scripts)
- Bootstrap automatizado: detección de Python, instalación de dependencias, arranque de Ollama
- Warm-up del modelo para reducir latencia en la primera petición
- Limpieza de procesos Uvicorn previos
- Health checks con reintentos para Ollama y la app

---

## 6. Comunicación entre Capas

| Origen → Destino | Protocolo | Formato | Endpoint |
|-------------------|-----------|---------|----------|
| Browser → FastAPI | HTTP POST | JSON `{text: "..."}` | `/api/triage` |
| Browser → FastAPI | HTTP GET | — | `/`, `/api/health` |
| FastAPI → Ollama | HTTP POST | JSON (payload Ollama) | `/api/chat` |
| FastAPI → Ollama (fallback) | subprocess → PowerShell → HTTP | Base64-encoded JSON | `/api/chat` |
| FastAPI → Browser | HTTP Response | JSON `TriageResponse` | `/api/triage` |
| Browser ↔ localStorage | JavaScript API | JSON serializado | Claves por plan |

---

## 7. Variables de Entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Host del servidor Ollama |
| `OLLAMA_MODEL` | `qwen3:8b` | Modelo a usar para inferencia |
| `CHAOS_TRIAGE_MODEL` | — | Override del modelo para el launcher Windows |

---

## 8. Dependencias del Sistema

### Requisitos previos

- **Python 3.12+** instalado en Windows (user install)
- **Ollama** instalado en `%LOCALAPPDATA%\Programs\Ollama\`
- **Modelo `qwen3:8b`** descargado: `ollama pull qwen3:8b`

### Dependencias Python (`requirements.txt`)

```
fastapi
uvicorn
ollama
```

### Dependencias Frontend (CDN, no requieren instalación)

- Tailwind CSS (`cdn.tailwindcss.com`)
- SortableJS v1.15.2 (`cdn.jsdelivr.net`)
- Google Fonts — Sora (`fonts.googleapis.com`)
