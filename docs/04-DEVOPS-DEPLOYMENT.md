# Chaos-Triage — DevOps y Deployment

> Documento actualizado: Abril 2026  
> Plataforma principal: Windows 10/11  
> Alternativa: WSL/Linux

---

## 1. Visión General del Deployment

Chaos-Triage es una aplicación 100% local que no requiere servicios en la nube, contenedores ni orquestación. El deployment consiste en asegurar que tres componentes estén corriendo en la máquina del usuario:

1. **Ollama** — Servidor de modelos de IA local
2. **Modelo LLM** — `qwen3:8b` descargado y disponible
3. **FastAPI + Uvicorn** — Servidor de aplicación en Python

El sistema de scripts automatiza completamente este proceso para Windows.

---

## 2. Estructura de Scripts

```
scripts/
├── start-chaos-triage.cmd            # Entry point Windows (doble click)
├── start-chaos-triage.ps1            # Bootstrap PowerShell completo
├── start-chaos-triage-wsl.sh         # Launcher para WSL/Linux
└── install-chaos-triage-startup.ps1  # Crear shortcut de inicio automático
```

---

## 3. `start-chaos-triage.cmd` — Entry Point

**Propósito:** Punto de entrada de un solo click para usuarios Windows.

```batch
@echo off
setlocal
if /I "%~1"=="--no-browser" (
  powershell.exe -ExecutionPolicy Bypass -File "%~dp0start-chaos-triage.ps1" -NoBrowser
) else (
  powershell.exe -ExecutionPolicy Bypass -File "%~dp0start-chaos-triage.ps1"
)
```

**Características:**
- Ejecuta el script PowerShell con `ExecutionPolicy Bypass` (evita restricciones)
- Soporta flag `--no-browser` para arranque headless
- Resuelve paths relativos con `%~dp0`

**Uso:**
```bash
# Doble click en el explorador
scripts\start-chaos-triage.cmd

# Desde terminal sin abrir browser
scripts\start-chaos-triage.cmd --no-browser
```

---

## 4. `start-chaos-triage.ps1` — Bootstrap Completo

Este es el corazón del sistema de arranque. Orquesta toda la secuencia de inicialización.

### 4.1 Configuración Inicial

```powershell
param([switch]$NoBrowser)
$ErrorActionPreference = "Stop"

$Model = if ($env:CHAOS_TRIAGE_MODEL) { $env:CHAOS_TRIAGE_MODEL.Trim() } else { "qwen3:8b" }
$OllamaExe = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
```

**Variables clave:**

| Variable | Propósito |
|----------|-----------|
| `$ProjectWin` | Directorio raíz del proyecto |
| `$Model` | Modelo a usar (`CHAOS_TRIAGE_MODEL` o `qwen3:8b`) |
| `$OllamaExe` | Path al ejecutable de Ollama |
| `$RequirementsPath` | Path a `requirements.txt` |
| `$InstallStamp` | Archivo de marca de instalación |
| `$PidFile` | `.chaos-triage.pid` — PID del servidor |
| `$StdoutLog` / `$StderrLog` | Logs de salida del servidor |

### 4.2 Detección de Python — `Get-BootstrapPython`

Busca Python en el orden:

```powershell
$PythonCandidates = @(
  (Join-Path $env:LOCALAPPDATA "Programs\Python\Python314\python.exe"),
  (Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe"),
  (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe")
)
```

Retorna el primer candidato que exista. Si ninguno existe, lanza error:
> `"Windows Python was not found. Install Python 3.13+ for the current user."`

### 4.3 Instalación de Dependencias — `Ensure-WindowsPythonDeps`

**Estrategia de instalación inteligente:**

```
1. ¿Existe el stamp file?
   └─ NO → instalar
   └─ SÍ → ¿requirements.txt es más nuevo que el stamp?
            └─ SÍ → reinstalar
            └─ NO → verificar imports
                     └─ import falla → reinstalar
                     └─ import ok → skip
```

**Comandos ejecutados al instalar:**
```powershell
python -m pip install --user --upgrade pip
python -m pip install --user -r requirements.txt
```

**Stamp file:** `.windows-python-requirements-installed` — contiene la fecha ISO del último install exitoso.

### 4.4 Limpieza de Servidor Previo — `Stop-PreviousServer`

Busca procesos Python que matcheen:
```powershell
Get-CimInstance Win32_Process | Where-Object {
  $_.Name -eq "python.exe" -and
  $_.CommandLine -like "*-m uvicorn main:app*--port 8000*"
}
```

También limpia archivos temporales:
- `.chaos-triage.pid`
- `py-stdout.log`
- `py-stderr.log`

Esto previene que procesos stale sirvan código desactualizado.

### 4.5 Arranque de Ollama

```powershell
if (-not (Get-Process -Name ollama -ErrorAction SilentlyContinue)) {
  Start-Process -FilePath $OllamaExe -ArgumentList "serve" -WindowStyle Hidden
}
```

Solo inicia Ollama si no está corriendo. Corre en modo hidden.

### 4.6 Verificación de Disponibilidad — `Wait-Http`

```powershell
function Wait-Http {
  param([string]$Url, [int]$Attempts = 30)
  for ($i = 0; $i -lt $Attempts; $i++) {
    try {
      Invoke-RestMethod -Uri $Url -TimeoutSec 2 | Out-Null
      return $true
    } catch {
      Start-Sleep -Seconds 2
    }
  }
  return $false
}
```

**Parámetros:** 30 intentos × 2 segundos = **60 segundos máximo de espera**.

Se usa para verificar:
1. `http://127.0.0.1:11434/api/tags` — Ollama está listo
2. `http://127.0.0.1:8000/api/health` — La app está lista

### 4.7 Verificación del Modelo — `Ensure-OllamaModelAvailable`

```powershell
$Tags = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 10
$InstalledModels = $Tags.models | ForEach-Object { $_.name }
if ($InstalledModels -notcontains $ModelName) {
  throw "El modelo '$ModelName' no está disponible en Ollama. Ejecuta: ollama pull $ModelName"
}
```

Si el modelo no está instalado, el launcher falla con un mensaje claro indicando cómo obtenerlo.

### 4.8 Warm-Up del Modelo

```powershell
$WarmPayload = @{
  model = $Model
  prompt = "Warm up the model. Reply with OK."
  stream = $false
  keep_alive = "30m"
} | ConvertTo-Json -Compress
```

El warm-up se ejecuta en **background** (proceso PowerShell separado) para no bloquear el arranque. Esto pre-carga los pesos del modelo en memoria, reduciendo la latencia de la primera petición real.

`keep_alive = "30m"` mantiene el modelo en memoria por 30 minutos.

### 4.9 Arranque del Servidor

```powershell
$env:OLLAMA_MODEL = $Model
$ServerProcess = Start-Process `
  -FilePath $WindowsPython `
  -ArgumentList @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000") `
  -WorkingDirectory $ProjectWin `
  -WindowStyle Hidden `
  -RedirectStandardOutput $StdoutLog `
  -RedirectStandardError $StderrLog `
  -PassThru
Set-Content -Path $PidFile -Value $ServerProcess.Id
```

El servidor se ejecuta:
- En modo hidden (sin ventana)
- Con output redirigido a logs
- PID guardado en `.chaos-triage.pid`

### 4.10 Apertura del Browser

```powershell
if (-not $NoBrowser) {
  Start-Process "http://127.0.0.1:8000"
}
Write-Host "Chaos-Triage is ready on http://127.0.0.1:8000"
```

Solo después de que el health check confirme que la app está lista.

---

## 5. Secuencia Completa de Arranque

```
┌──────────────────────────────────────────────────────────┐
│ 1. Verificar que Ollama existe en el sistema             │
│ 2. Detectar Windows Python (3.14 → 3.13 → 3.12)         │
│ 3. Instalar/verificar dependencias Python                │
│ 4. Matar procesos Uvicorn previos en puerto 8000         │
│ 5. Iniciar Ollama serve (si no está corriendo)           │
│ 6. Esperar que Ollama responda (/api/tags) — max 60s     │
│ 7. Verificar que el modelo está instalado                │
│ 8. Warm-up del modelo en background                      │
│ 9. Iniciar FastAPI/Uvicorn en puerto 8000                │
│ 10. Esperar que la app responda (/api/health) — max 60s  │
│ 11. Abrir el navegador (si no es --no-browser)           │
│ 12. Imprimir "Chaos-Triage is ready"                     │
└──────────────────────────────────────────────────────────┘
```

---

## 6. `start-chaos-triage-wsl.sh` — Launcher WSL/Linux

Para entornos donde Python corre bajo WSL pero Ollama corre en Windows:

```bash
#!/usr/bin/env bash
set -euo pipefail

MODEL="${1:-qwen3:8b}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

pkill -f "uvicorn main:app --host 0.0.0.0 --port 8000" >/dev/null 2>&1 || true
source "$HOME/.venvs/manager/bin/activate"
cd "$PROJECT_DIR"
nohup env OLLAMA_MODEL="$MODEL" uvicorn main:app --host 0.0.0.0 --port 8000 \
  >/tmp/chaos-triage.log 2>&1 < /dev/null &
```

**Diferencias con el launcher Windows:**
- Host `0.0.0.0` en lugar de `127.0.0.1` (accesible desde Windows host)
- Virtual environment en `$HOME/.venvs/manager/`
- Ejecución con `nohup` en background
- El modelo acepta como primer argumento

---

## 7. `install-chaos-triage-startup.ps1` — Auto-Start

Crea un shortcut en la carpeta Startup de Windows para arranque automático:

```powershell
$StartupDir = [Environment]::GetFolderPath("Startup")
$ShortcutPath = Join-Path $StartupDir "Chaos-Triage.lnk"

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "cmd.exe"
$Shortcut.Arguments = $Arguments
$Shortcut.WorkingDirectory = $ScriptDir
$Shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,220"
$Shortcut.Save()
```

**Modos:**
- `install-chaos-triage-startup.ps1` — Inicia sin abrir browser
- `install-chaos-triage-startup.ps1 -OpenOnLogin` — Inicia y abre browser

---

## 8. Archivos de Runtime

| Archivo | Propósito | En `.gitignore` |
|---------|-----------|-----------------|
| `.chaos-triage.pid` | PID del proceso Uvicorn activo | ✅ |
| `py-stdout.log` | Output estándar del servidor | ✅ |
| `py-stderr.log` | Errores del servidor | ✅ |
| `.windows-python-requirements-installed` | Stamp de última instalación | ✅ |

---

## 9. `.gitignore` Configurado

```gitignore
# Python
__pycache__/
*.py[cod]

# Virtual environments
.venv/
.venv-win/
.venv-win-test/

# Logs and runtime
*.log
.chaos-triage.pid
.windows-python-requirements-installed

# Editors
.vscode/
.idea/

# Environment
.env
.env.*

# OS
.DS_Store
Thumbs.db
```

---

## 10. Seguridad y Privacidad

### Lo que NUNCA debe commitearse

| Archivo/Patrón | Razón |
|----------------|-------|
| `.env` / `.env.*` | Variables de entorno con posibles secretos |
| API keys / tokens | Credenciales de acceso |
| `*.log` | Pueden contener brain dumps del usuario |
| `.chaos-triage.pid` | Estado local de runtime |
| Virtual environments | Dependencias pesadas, específicas de máquina |
| `__pycache__/` | Bytecode compilado |

### Verificación pre-push

```bash
git status
git diff --cached
```

### Modelo de privacidad

- Todo el procesamiento de texto ocurre localmente
- Ollama no envía datos a servidores externos
- Los brain dumps del usuario nunca salen de la máquina
- La persistencia del browser es solo `localStorage` (no cookies, no telemetría)

---

## 11. Troubleshooting

### Problema: "Failed to fetch"

**Causa:** El browser no puede alcanzar el backend.

**Verificaciones:**
1. ¿El launcher corrió exitosamente?
2. ¿El puerto 8000 está en uso por otro proceso?
3. ¿`http://127.0.0.1:8000/api/health` responde?

### Problema: "Model output could not be parsed"

**Causa:** El modelo produjo output demasiado malformado.

**Verificaciones:**
1. ¿El modelo es `qwen3:8b`?
2. ¿Ollama está saludable? → `http://127.0.0.1:11434/api/tags`
3. ¿El prompt fue modificado manualmente?

### Problema: Modelo no encontrado

**Solución:**
```bash
ollama pull qwen3:8b
```

### Problema: Board se ve stale

**Solución:**
1. Refrescar la página
2. Si persiste, regenerar el plan
3. La persistencia es local y por plan; el estado viejo se restaura legítimamente

### Problema: Python no encontrado

**Solución:** Instalar Python 3.12+ desde python.org con la opción "Install for current user".

---

## 12. Ejecución Manual (sin launcher)

Si se prefiere no usar el launcher:

```bash
# 1. Instalar dependencias
python -m pip install -r requirements.txt

# 2. Asegurarse de que Ollama esté corriendo
ollama serve

# 3. Descargar el modelo (si no existe)
ollama pull qwen3:8b

# 4. Iniciar el servidor
uvicorn main:app --host 127.0.0.1 --port 8000

# 5. Abrir en el browser
# http://127.0.0.1:8000
```
