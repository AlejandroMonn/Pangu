param(
  [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectWin = Split-Path -Parent $ScriptDir
$Model = if ($env:CHAOS_TRIAGE_MODEL) { $env:CHAOS_TRIAGE_MODEL.Trim() } else { "qwen3:8b" }
$OllamaExe = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
$RequirementsPath = Join-Path $ProjectWin "requirements.txt"
$InstallStamp = Join-Path $ProjectWin ".windows-python-requirements-installed"
$PidFile = Join-Path $ProjectWin ".chaos-triage.pid"
$StdoutLog = Join-Path $ProjectWin "py-stdout.log"
$StderrLog = Join-Path $ProjectWin "py-stderr.log"
$PythonCandidates = @(
  (Join-Path $env:LOCALAPPDATA "Programs\Python\Python314\python.exe"),
  (Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe"),
  (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe")
)

function Wait-Http {
  param(
    [string]$Url,
    [int]$Attempts = 30
  )

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

function Get-BootstrapPython {
  foreach ($Candidate in $PythonCandidates) {
    if (Test-Path $Candidate) {
      return $Candidate
    }
  }

  throw "Windows Python was not found. Install Python 3.13+ for the current user."
}

function Invoke-PythonChecked {
  param(
    [string]$PythonExe,
    [string[]]$Arguments
  )

  $Process = Start-Process -FilePath $PythonExe -ArgumentList $Arguments -Wait -PassThru -WindowStyle Hidden
  if ($Process.ExitCode -ne 0) {
    throw "Python command failed: $PythonExe $($Arguments -join ' ')"
  }
}

function Ensure-WindowsPythonDeps {
  param(
    [string]$PythonExe
  )

  $NeedsInstall = -not (Test-Path $InstallStamp)
  if ((Test-Path $InstallStamp) -and (Test-Path $RequirementsPath)) {
    $NeedsInstall = (Get-Item $RequirementsPath).LastWriteTimeUtc -gt (Get-Item $InstallStamp).LastWriteTimeUtc
  }

  if (-not $NeedsInstall) {
    $ImportCheck = Start-Process `
      -FilePath $PythonExe `
      -ArgumentList @("-c", "import fastapi, uvicorn, ollama") `
      -Wait `
      -PassThru `
      -WindowStyle Hidden
    $NeedsInstall = $ImportCheck.ExitCode -ne 0
  }

  if ($NeedsInstall) {
    Invoke-PythonChecked -PythonExe $PythonExe -Arguments @("-m", "pip", "install", "--user", "--upgrade", "pip")
    Invoke-PythonChecked -PythonExe $PythonExe -Arguments @("-m", "pip", "install", "--user", "-r", $RequirementsPath)
    Set-Content -Path $InstallStamp -Value (Get-Date).ToString("o")
  }
}

function Stop-PreviousServer {
  $Matches = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -eq "python.exe" -and $_.CommandLine -like "*-m uvicorn main:app*--port 8000*"
  }

  foreach ($Match in $Matches) {
    Stop-Process -Id $Match.ProcessId -Force -ErrorAction SilentlyContinue
  }

  if (Test-Path $PidFile) {
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
  }

  if (Test-Path $StdoutLog) {
    Remove-Item $StdoutLog -Force -ErrorAction SilentlyContinue
  }

  if (Test-Path $StderrLog) {
    Remove-Item $StderrLog -Force -ErrorAction SilentlyContinue
  }
}

if (-not (Test-Path $OllamaExe)) {
  throw "Ollama was not found at $OllamaExe"
}

$WindowsPython = Get-BootstrapPython
Ensure-WindowsPythonDeps -PythonExe $WindowsPython
Stop-PreviousServer

if (-not (Get-Process -Name ollama -ErrorAction SilentlyContinue)) {
  Start-Process -FilePath $OllamaExe -ArgumentList "serve" -WindowStyle Hidden | Out-Null
}

if (-not (Wait-Http -Url "http://127.0.0.1:11434/api/tags")) {
  throw "Ollama did not become ready on http://127.0.0.1:11434"
}

$WarmPayload = @{
  model = $Model
  prompt = "Warm up the model. Reply with OK."
  stream = $false
  keep_alive = "30m"
} | ConvertTo-Json -Compress
$WarmCommand = "try { Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/generate' -Method Post -ContentType 'application/json' -Body '$($WarmPayload.Replace("'", "''"))' -TimeoutSec 180 | Out-Null } catch {}"
Start-Process -FilePath "powershell.exe" -WindowStyle Hidden -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $WarmCommand | Out-Null

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
Start-Sleep -Seconds 2

if (-not (Wait-Http -Url "http://127.0.0.1:8000/api/health")) {
  $stderrPreview = ""
  if (Test-Path $StderrLog) {
    $stderrPreview = (Get-Content $StderrLog -Raw -ErrorAction SilentlyContinue).Trim()
  }

  if ([string]::IsNullOrWhiteSpace($stderrPreview)) {
    throw "Chaos-Triage did not become ready on http://127.0.0.1:8000"
  }

  throw "Chaos-Triage did not become ready on http://127.0.0.1:8000`n`nBackend stderr:`n$stderrPreview"
}

if (-not $NoBrowser) {
  Start-Process "http://127.0.0.1:8000"
}

Write-Host "Chaos-Triage is ready on http://127.0.0.1:8000"
