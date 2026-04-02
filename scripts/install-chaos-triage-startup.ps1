param(
  [switch]$OpenOnLogin
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$StartupDir = [Environment]::GetFolderPath("Startup")
$ShortcutPath = Join-Path $StartupDir "Chaos-Triage.lnk"
$LauncherPath = Join-Path $ScriptDir "start-chaos-triage.cmd"
$Arguments = if ($OpenOnLogin) {
  "/c `"$LauncherPath`""
} else {
  "/c `"$LauncherPath`" --no-browser"
}

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "cmd.exe"
$Shortcut.Arguments = $Arguments
$Shortcut.WorkingDirectory = $ScriptDir
$Shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,220"
$Shortcut.Save()

Write-Host "Startup shortcut created at $ShortcutPath"
