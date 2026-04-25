import json
import os
import re
import subprocess
from base64 import b64encode
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Must be set before importing ollama so ollama.chat uses this host.
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
os.environ.setdefault("OLLAMA_HOST", OLLAMA_HOST)

import ollama
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="Chaos-Triage", version="1.0.0")
BASE_DIR = Path(__file__).resolve().parent

MODEL_NAME = os.getenv("OLLAMA_MODEL", "qwen3:8b").strip()
ALLOWED_URGENCY = {"low", "medium", "high"}
ALLOWED_ENERGY = {"light", "medium", "deep"}

SYSTEM_PROMPT = """
You are Chaos-Triage Planner.
You must convert a messy brain dump into a strict JSON action plan.
The input may include a pre-split task seed list. Respect that seed list carefully.

Return ONLY valid JSON. No markdown. No code fences. No commentary.

Required JSON schema:
{
  "summary": "short plain-text summary",
  "coach": {
    "intro": "short human opening",
    "focus": "what to start with in a direct and supportive tone",
    "caution": "one pacing warning or anti-distraction note",
    "steps": ["short step 1", "short step 2", "short step 3"]
  },
  "topics": ["short theme 1", "short theme 2"],
  "tasks": [
    {
      "step_number": 1,
      "title": "short actionable task",
      "details": "1-2 lines with concrete next action",
      "first_move": "very short first physical or digital action",
      "topic": "short readable theme",
      "urgency": "low|medium|high",
      "energy_level": "light|medium|deep",
      "estimated_minutes": 25,
      "reason": "why this step is in this order"
    }
  ]
}

Task extraction and categorization rules:
- Commas are the main task boundary. Treat each comma-separated seed as a separate task candidate.
- Preserve seed order unless one seed clearly contains multiple obvious actions that must be split.
- Only split obvious internal chains such as "deploy then test", "clean room and wash dishes", or "estudiar y entregar".
- Do not aggressively split descriptive phrases that are really one task.
- Keep each task medium-detail: concise title, short explanation, and one clear first_move.
- Generate topics freely from the actual brain dump.
- Each task must have exactly one short topic in the topic field.
- Topics must be readable, useful as filters, and grounded in the user's text.
- Avoid duplicate topics or tiny wording variations for the same theme.
- topics must list the unique topics used across tasks.

Ordering rules (critical):
- Put the tasks in a practical execution order based on blockers, effort, momentum, and usefulness.
- Front-load clear wins or unblockers when appropriate.
- Keep the suggested order realistic for one day.

Output constraints:
- Include all meaningful tasks inferred from user text.
- Try to keep a 1:1 mapping with the provided task seeds unless a seed obviously contains two separate actions.
- step_number values must start at 1 and be continuous without gaps.
- Keep titles concise and imperative.
- estimated_minutes must be an integer between 5 and 180.
- first_move must be short, practical, and easy to start right now.
- coach must sound like a helpful daily guide in mixed Spanish and English.
- coach.steps must contain exactly 3 short lines.
- topic values should usually be 1-3 words.
- If nothing actionable exists, return one low-urgency task asking user to clarify priorities.
""".strip()

REPAIR_PROMPT = """
You fix malformed model outputs.
Convert the provided text into valid JSON that matches the requested schema exactly.
Return ONLY valid JSON.
Do not include markdown, code fences, notes, or explanation.
If the input already contains valid task information, preserve it.
""".strip()

TRIAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "coach": {
            "type": "object",
            "properties": {
                "intro": {"type": "string"},
                "focus": {"type": "string"},
                "caution": {"type": "string"},
                "steps": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["intro", "focus", "caution", "steps"],
        },
        "topics": {"type": "array", "items": {"type": "string"}},
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "step_number": {"type": "integer"},
                    "title": {"type": "string"},
                    "details": {"type": "string"},
                    "first_move": {"type": "string"},
                    "topic": {"type": "string"},
                    "urgency": {"type": "string", "enum": sorted(ALLOWED_URGENCY)},
                    "energy_level": {"type": "string", "enum": sorted(ALLOWED_ENERGY)},
                    "estimated_minutes": {"type": "integer"},
                    "reason": {"type": "string"},
                },
                "required": [
                    "step_number",
                    "title",
                    "details",
                    "first_move",
                    "topic",
                    "urgency",
                    "energy_level",
                    "estimated_minutes",
                    "reason",
                ],
            },
        },
    },
    "required": ["summary", "coach", "topics", "tasks"],
}


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


def _split_primary_seeds(text: str) -> list[str]:
    return [chunk.strip(" \n\t.;:-") for chunk in text.split(",") if chunk.strip(" \n\t.;:-")]


def _should_split_connector(left: str, right: str) -> bool:
    left = left.strip()
    right = right.strip()
    if not left or not right:
        return False
    if len(left.split()) > 8 or len(right.split()) > 8:
        return False

    action_words = (
        "clean",
        "wash",
        "tidy",
        "study",
        "finish",
        "submit",
        "review",
        "deploy",
        "test",
        "fix",
        "write",
        "read",
        "watch",
        "catch up",
        "organize",
        "reply",
        "send",
        "prepare",
        "estudiar",
        "entregar",
        "limpiar",
        "lavar",
        "ordenar",
        "revisar",
        "leer",
        "ver",
        "terminar",
        "hacer",
    )
    left_lower = left.lower()
    right_lower = right.lower()
    return any(left_lower.startswith(word) or right_lower.startswith(word) for word in action_words)


def _split_obvious_compound_seed(seed: str) -> list[str]:
    working = re.sub(r"\s+", " ", seed.strip())
    if not working:
        return []

    parts = [working]
    connectors = (
        r"\bthen\b",
        r"\by luego\b",
        r"\by despues\b",
        r"\band then\b",
        r"\by\b",
        r"\band\b",
    )

    for connector in connectors:
        next_parts: list[str] = []
        for part in parts:
            split_parts = re.split(connector, part, flags=re.IGNORECASE)
            if len(split_parts) == 2 and _should_split_connector(split_parts[0], split_parts[1]):
                next_parts.extend(piece.strip(" \n\t.;:-") for piece in split_parts if piece.strip(" \n\t.;:-"))
            else:
                next_parts.append(part.strip())
        parts = next_parts

    return [part for part in parts if part]


def _extract_task_seeds(text: str) -> list[str]:
    seeds: list[str] = []
    for chunk in _split_primary_seeds(text):
        split_chunk = _split_obvious_compound_seed(chunk)
        seeds.extend(split_chunk or [chunk])
    return seeds or [text.strip()]


def _build_user_prompt(original_text: str, task_seeds: list[str]) -> str:
    seed_lines = "\n".join(f"{idx}. {seed}" for idx, seed in enumerate(task_seeds, start=1))
    return (
        "Original brain dump:\n"
        f"{original_text.strip()}\n\n"
        "Pre-split task seeds in required order:\n"
        f"{seed_lines}\n\n"
        "Plan around these seeds. Preserve their order unless one seed obviously contains two separate actions."
    )


def _extract_input_text(content_type: str, raw_body: bytes) -> str:
    body = raw_body.decode("utf-8", errors="replace").strip()
    if not body:
        return ""

    if "application/json" in content_type:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

        if isinstance(payload, dict):
            return str(payload.get("text", "")).strip()
        if isinstance(payload, str):
            return payload.strip()
        return ""

    return body


def _extract_first_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()

    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start_indices = [i for i, ch in enumerate(text) if ch == "{"]
    for start in start_indices:
        depth = 0
        in_string = False
        escaped = False

        for i in range(start, len(text)):
            ch = text[i]

            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue

            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        parsed = json.loads(candidate)
                        if isinstance(parsed, dict):
                            return parsed
                    except json.JSONDecodeError:
                        break

    raise ValueError("No valid JSON object found in model response")


def _lane_for_task(task: dict[str, Any], index: int, total: int) -> str:
    if index == 0:
        return "suggested"
    if task["urgency"] == "high":
        return "suggested"
    if total > 1 and index >= total - 2 and task["urgency"] == "low":
        return "done_later"
    return "suggested"

def _normalize_topic(raw_topic: Any) -> str:
    text = str(raw_topic or "").strip()
    if not text:
        return "General"
    text = re.sub(r"\s+", " ", text)
    text = text.strip(" \n\t.;:-_")
    if not text:
        return "General"
    return text[:48]


def _collect_topics(tasks: list[dict[str, Any]], raw_topics: Any) -> list[str]:
    topics: list[str] = []
    seen: set[str] = set()

    if isinstance(raw_topics, list):
        for topic in raw_topics:
            normalized = _normalize_topic(topic)
            key = normalized.casefold()
            if key not in seen:
                seen.add(key)
                topics.append(normalized)

    for task in tasks:
        normalized = _normalize_topic(task.get("topic"))
        key = normalized.casefold()
        if key not in seen:
            seen.add(key)
            topics.append(normalized)

    return topics or ["General"]


def _build_default_coach(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    first = tasks[0]
    second = tasks[1] if len(tasks) > 1 else None
    third = tasks[2] if len(tasks) > 2 else None

    steps = [
        f"Primero, start con {first['title']} y no mires mas lejos que el primer movimiento.",
        (
            f"Luego pasa a {second['title']} sin cambiar mucho de contexto."
            if second
            else "Luego revisa el backlog y elige el siguiente bloque sin sobrepensarlo."
        ),
        (
            f"Despues entra a {third['title']} y cierra ese bloque antes de abrir otra cosa."
            if third
            else "Despues haz una pausa corta y sigue con el siguiente bloque del backlog."
        ),
    ]

    return {
        "intro": "Hoy no tienes que resolver toda la vida; solo necesitas una secuencia clara para bajar el caos.",
        "focus": f"Empieza por {first['title']} y usa este arranque: {first['first_move']}.",
        "caution": "Cuidado con saltar entre tareas; hoy te conviene trabajar por bloques y no por impulsos.",
        "steps": steps,
    }


def _normalize_coach(raw_coach: Any, tasks: list[dict[str, Any]]) -> dict[str, Any]:
    fallback = _build_default_coach(tasks)
    if not isinstance(raw_coach, dict):
        return fallback

    steps_raw = raw_coach.get("steps", [])
    cleaned_steps = []
    if isinstance(steps_raw, list):
        cleaned_steps = [str(step).strip()[:180] for step in steps_raw if str(step).strip()]

    while len(cleaned_steps) < 3:
        cleaned_steps.append(fallback["steps"][len(cleaned_steps)])

    return {
        "intro": str(raw_coach.get("intro", "")).strip()[:220] or fallback["intro"],
        "focus": str(raw_coach.get("focus", "")).strip()[:220] or fallback["focus"],
        "caution": str(raw_coach.get("caution", "")).strip()[:220] or fallback["caution"],
        "steps": cleaned_steps[:3],
    }


def _coerce_and_validate(data: dict[str, Any], original_text: str) -> dict[str, Any]:
    summary = str(data.get("summary", "")).strip() or "Action plan generated from your brain dump."
    tasks_raw = data.get("tasks") or data.get("plan") or data.get("items") or []
    if isinstance(data, list):
        tasks_raw = data

    if not isinstance(tasks_raw, list) or not tasks_raw:
        raise ValueError("Model response does not contain a non-empty tasks array")

    cleaned_tasks: list[dict[str, Any]] = []
    for task in tasks_raw:
        if not isinstance(task, dict):
            continue

        title = (
            str(task.get("title") or task.get("task") or task.get("name") or "Untitled task").strip()[:140]
            or "Untitled task"
        )
        details = (
            str(task.get("details") or task.get("description") or "").strip()[:400]
            or "Take the next concrete action."
        )
        first_move = (
            str(task.get("first_move") or task.get("next_action") or title).strip()[:160]
            or title
        )
        topic = _normalize_topic(task.get("topic") or task.get("category") or task.get("theme"))

        urgency = str(task.get("urgency", "medium")).strip().lower()
        if urgency not in ALLOWED_URGENCY:
            urgency = "medium"

        energy_level = str(task.get("energy_level", "medium")).strip().lower()
        if energy_level not in ALLOWED_ENERGY:
            energy_level = "medium"

        try:
            estimated = int(task.get("estimated_minutes", 25))
        except (TypeError, ValueError):
            estimated = 25
        estimated = max(5, min(180, estimated))

        cleaned_tasks.append(
            {
                "step_number": int(task.get("step_number", len(cleaned_tasks) + 1)),
                "title": title,
                "details": details,
                "first_move": first_move,
                "topic": topic,
                "urgency": urgency,
                "energy_level": energy_level,
                "estimated_minutes": estimated,
                "reason": str(task.get("reason", "Placed to maintain momentum.")).strip()[:300]
                or "Placed to maintain momentum.",
            }
        )

    if not cleaned_tasks:
        raise ValueError("No valid tasks after normalization")

    cleaned_tasks.sort(key=lambda t: (t["step_number"], t["topic"].casefold(), t["title"].casefold()))
    for idx, task in enumerate(cleaned_tasks, start=1):
        task["step_number"] = idx
        task["lane"] = _lane_for_task(task, idx - 1, len(cleaned_tasks))

    return {
        "summary": summary,
        "coach": _normalize_coach(data.get("coach"), cleaned_tasks),
        "topics": _collect_topics(cleaned_tasks, data.get("topics")),
        "tasks": cleaned_tasks,
        "meta": {
            "model": MODEL_NAME,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def _extract_content(chat_response: Any) -> str:
    if isinstance(chat_response, dict):
        return str(chat_response.get("message", {}).get("content", "")).strip()

    message = getattr(chat_response, "message", None)
    if message is not None:
        return str(getattr(message, "content", "")).strip()

    return ""


def _chat_via_windows_ollama(system_prompt: str, user_text: str, fmt: dict[str, Any] | None = None) -> str:
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        "options": {"temperature": 0.2},
        "stream": False,
    }
    if fmt:
        payload["format"] = fmt
    payload_b64 = b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")

    ps_script = f"""
$OutputEncoding = [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$payload = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('{payload_b64}'))
$response = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/chat' -Method Post -ContentType 'application/json' -Body $payload -TimeoutSec 180
if ($null -eq $response.message -or [string]::IsNullOrWhiteSpace($response.message.content)) {{
  throw 'Windows Ollama returned no content'
}}
$response.message.content
""".strip()

    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", ps_script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=220,
        check=False,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(stderr or "PowerShell/Ollama bridge failed")

    output = (result.stdout or "").strip()
    if not output:
        raise RuntimeError("PowerShell/Ollama bridge returned empty output")
    return output


def _repair_content(raw_content: str) -> str:
    repaired = _chat_via_windows_ollama(REPAIR_PROMPT, raw_content, TRIAGE_SCHEMA)
    if not repaired:
        raise RuntimeError("Repair pass returned empty output")
    return repaired


def _generate_with_ollama(user_prompt: str) -> tuple[str, str]:
    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            options={"temperature": 0.2},
            format=TRIAGE_SCHEMA,
        )
        content = _extract_content(response)
        if not content:
            raise RuntimeError("Model returned empty content")
        return content, "python_ollama"
    except Exception:
        fallback_content = _chat_via_windows_ollama(SYSTEM_PROMPT, user_prompt, TRIAGE_SCHEMA)
        return fallback_content, "windows_ollama_bridge"


@app.get("/")
async def home() -> FileResponse:
    return FileResponse(BASE_DIR / "templates" / "index.html")


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "model": MODEL_NAME, "ollama_host": OLLAMA_HOST}


@app.post("/api/triage", response_model=TriageResponse)
async def triage(request: Request) -> TriageResponse:
    content_type = request.headers.get("content-type", "").lower()
    raw_body = await request.body()
    text = _extract_input_text(content_type, raw_body)
    if not text:
        raise HTTPException(status_code=400, detail="Input text cannot be empty")
    task_seeds = _extract_task_seeds(text)
    user_prompt = _build_user_prompt(text, task_seeds)

    try:
        content, transport = _generate_with_ollama(user_prompt)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Failed to contact Ollama at '{OLLAMA_HOST}' with model '{MODEL_NAME}'. "
                "Ensure Ollama is running and the model is available."
            ),
        ) from exc

    try:
        parsed = _extract_first_json_object(content)
        normalized = _coerce_and_validate(parsed, text)
        normalized["meta"]["transport"] = transport
        normalized["meta"]["task_seeds"] = task_seeds
        return TriageResponse(**normalized)
    except Exception:
        try:
            repaired_content = _repair_content(content)
            parsed = _extract_first_json_object(repaired_content)
            normalized = _coerce_and_validate(parsed, text)
            normalized["meta"]["transport"] = f"{transport}+repair"
            normalized["meta"]["task_seeds"] = task_seeds
            return TriageResponse(**normalized)
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Model output could not be parsed into valid task JSON",
                    "raw_preview": content[:1200],
                    "error": str(exc),
                },
            ) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
