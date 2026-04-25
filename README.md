# Chaos-Triage

Chaos-Triage is a Windows-first, 100% local planning tool that turns a messy brain dump into a clear, actionable day plan.

Paste your thoughts, tasks, worries, and reminders into a single input box, and the app will organize them into:

- a structured task plan
- a human-style coach summary
- a draggable Kanban board
- a topic-filtered execution view

Everything runs locally with FastAPI + Ollama. No cloud API is required.

## Why It Exists

Most task apps assume you already know what your tasks are.

Chaos-Triage is for the moment before that: when your head is full, your notes are chaotic, and you need help turning unstructured text into something you can actually work through.

The app is built around two ideas:

- AI helps create structure
- you stay in control of execution

That is why the generated plan always starts with every task in `Pendientes`. Nothing is auto-marked as `En Progreso` or `Completadas`.

## Core Features

- Local AI triage using Ollama and `qwen3.5:9b`
- Comma-first task extraction for more predictable task boundaries
- Strict JSON output contract for stable backend parsing
- Human-friendly coach panel for the day plan
- Draggable Kanban board with:
  - `Pendientes`
  - `En Progreso`
  - `Completadas`
- Quick mouse actions to move tasks between states without opening details
- Topic filters generated dynamically by the AI for each plan
- Persistent browser state per generated plan
- Windows launcher scripts for one-click startup

## How It Works

High-level flow:

1. You paste a brain dump into the textarea.
2. The backend pre-splits the text into task seeds.
3. Each comma is treated as a primary task boundary.
4. Very obvious multi-action phrases can be split further.
5. The backend sends both:
   - the original text
   - the ordered task seed list
   to the local Ollama model.
6. The model returns structured JSON.
7. The backend normalizes, validates, and repairs the response if needed.
8. The frontend renders a coach plan, dynamic topic filters, and a draggable board.

## Task Extraction Rules

Chaos-Triage uses a deterministic first pass before the LLM:

- every comma is treated as a new task seed
- empty comma chunks are ignored
- obvious internal chains can be split further

Examples:

- `deploy then test`
- `clean room and wash dishes`
- `estudiar y entregar la tarea`

The splitter is intentionally conservative. It tries to make tasks more detailed without turning every sentence into fragments.

## Topics Instead of Fixed Categories

PANGU no longer relies on a fixed taxonomy like business, university, personal, or consumption.

Instead:

- the AI generates short topics dynamically for each plan
- every task receives one main `topic`
- the filter bar is built from those discovered topics
- topics change depending on the actual brain dump

This makes the board more flexible and more faithful to what the user actually wrote.

## Tech Stack

- Python
- FastAPI
- Uvicorn
- Ollama Python library
- Gemma via local Ollama
- Tailwind CSS via CDN
- SortableJS via CDN

## Project Structure

```text
.
├── LICENSE
├── README.md
├── SECURITY.md
├── DOCUMENTATION.md
├── main.py
├── requirements.txt
├── templates/
│   └── index.html
└── scripts/
    ├── start-chaos-triage.cmd
    ├── start-chaos-triage.ps1
    ├── start-chaos-triage-wsl.sh
    └── install-chaos-triage-startup.ps1
```

## Requirements

Before running the app, install:

- Windows Python 3.12 or newer
- [Ollama](https://ollama.com/)
- the local model `qwen3.5:9b`

Pull the model:

```bash
ollama pull qwen3.5:9b
```

## Running the App

### Recommended Windows startup

Use the provided launcher:

```bat
scripts\start-chaos-triage.cmd
```

That launcher will:

- locate Windows Python
- install Python dependencies if needed
- start Ollama if needed
- verify that the selected model is installed
- warm the selected model
- start FastAPI on `127.0.0.1:8000`
- open the browser automatically

### Manual run

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Start the server:

```bash
uvicorn main:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

## Environment Variables

Optional environment variables:

- `OLLAMA_MODEL`
  - default: `qwen3.5:9b`
- `CHAOS_TRIAGE_MODEL`
  - Windows launcher override for the startup script
- `OLLAMA_HOST`
  - default: `http://127.0.0.1:11434`

Example:

```bash
set OLLAMA_MODEL=qwen3.5:9b
uvicorn main:app --host 127.0.0.1 --port 8000
```

## API

### `GET /`

Serves the frontend.

### `GET /api/health`

Returns backend health information.

### `POST /api/triage`

Accepts:

```json
{
  "text": "clean room, deploy then test, watch a video"
}
```

Returns:

- `summary`
- `coach`
- `topics`
- `tasks`
- `meta`

## Privacy and Public Repo Safety

This project is designed for local inference, but if you publish the repository you still need normal Git hygiene.

Do not commit:

- `.env` files
- API keys or access tokens
- virtual environments
- logs
- PID files
- local install stamps
- personal notes or raw brain dumps

The included `.gitignore` is set up to exclude the common local-only files used by this project.

Before pushing publicly, always review:

```bash
git status
git diff --cached
```

## Documentation

Detailed technical documentation is available in:

- [DOCUMENTATION.md](./DOCUMENTATION.md)

That file covers:

- backend architecture
- prompt contract
- Ollama transport paths
- parsing and repair logic
- frontend state model
- drag/drop behavior
- local persistence
- Windows launcher behavior

If the launcher says the model is missing, install it with:

```bash
ollama pull qwen3.5:9b
```

## Recommended Public Repo Contents

Good files to include:

- `main.py`
- `templates/index.html`
- `requirements.txt`
- `README.md`
- `.gitignore`
- `SECURITY.md`
- `DOCUMENTATION.md`
- `scripts/`
- `LICENSE`

Do not include:

- `.venv/`
- `.venv-win/`
- `.venv-win-test/`
- `__pycache__/`
- `*.log`
- `.chaos-triage.pid`
- `.windows-python-requirements-installed`
- `.env*`

## GitHub Setup Notes

If this project is being added to an existing GitHub repository that already contains a `LICENSE`, the safest flow is:

```bash
git fetch origin
git pull --rebase origin main
git add .
git status
git commit -m "Add Chaos-Triage project files"
git push -u origin main
```

This avoids overwriting the remote history and keeps the existing license commit intact.

## License

This project is released under the MIT License. See [LICENSE](./LICENSE).
