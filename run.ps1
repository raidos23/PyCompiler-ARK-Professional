# SPDX-License-Identifier: GPL-3.0-only
# PyCompiler Pro++ — High-grade launcher (Windows PowerShell)
# Author: Samuel Amen Ague
# Copyright (c) 2025 Samuel Amen Ague. All rights reserved.

[CmdletBinding(PositionalBinding=$false)]
Param(
  [switch]$Recreate,
  [switch]$SkipInstall,
  [switch]$NoUpgrade,
  [string]$VenvDir = 'venv',
  [string]$Requirements = 'requirements.txt',
  [string]$Python,
  [string]$MinPy = '3.10',
  [string[]]$PipArg,
  [switch]$Offline,
  [string]$Wheelhouse,
  [switch]$ForceInstall,
  [int]$MinFreeMB = 200,
  [switch]$NoColor,
  [string]$Log,
  [Parameter(ValueFromRemainingArguments=$true)][string[]]$AppArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Info($msg){ if ($NoColor) { Write-Host "[i] $msg" } else { Write-Host "ℹ️  $msg" -ForegroundColor Cyan } }
function Write-Ok($msg){ if ($NoColor) { Write-Host "[+] $msg" } else { Write-Host "✅ $msg" -ForegroundColor Green } }
function Write-Warn($msg){ if ($NoColor) { Write-Host "[!] $msg" } else { Write-Host "⚠️  $msg" -ForegroundColor Yellow } }
function Write-Err($msg){ if ($NoColor) { Write-Host "[x] $msg" } else { Write-Host "❌ $msg" -ForegroundColor Red } }

# Always run from the script directory
Set-Location -Path $PSScriptRoot

# Load .env if present
$EnvFile = Join-Path $PSScriptRoot '.env'
if (Test-Path -Path $EnvFile) {
  Get-Content $EnvFile | ForEach-Object {
    if ($_ -match '^\s*#') { return }
    if ($_ -match '^\s*$') { return }
    $kv = $_.Split('=',2)
    if ($kv.Count -eq 2) {
      $k = $kv[0].Trim(); $v = $kv[1].Trim()
      if ($k) { [System.Environment]::SetEnvironmentVariable($k, $v, 'Process') }
    }
  }
}

# Optional logging to file
$__TranscriptStarted = $false
if ($Log) {
  try {
    $dir = Split-Path -Parent $Log
    if ($dir) { New-Item -ItemType Directory -Force -ErrorAction SilentlyContinue -Path $dir | Out-Null }
    Start-Transcript -Path $Log -Append -NoClobber | Out-Null
    $__TranscriptStarted = $true
    Write-Info "Journal: $Log"
  } catch {}
}

# Helper to stop transcript safely
function Stop-TranscriptSafe {
  param()
  if ($__TranscriptStarted) {
    try { Stop-Transcript | Out-Null } catch {}
  }
}

# Pick a Python command if not provided
function Get-PythonCommand {
  if ($PSBoundParameters.ContainsKey('Python') -and $Python) { return ,@($Python) }
  if (Get-Command py -ErrorAction SilentlyContinue) { return ,@('py','-3') }
  elseif (Get-Command python -ErrorAction SilentlyContinue) { return ,@('python') }
  elseif (Get-Command python3 -ErrorAction SilentlyContinue) { return ,@('python3') }
  else { return $null }
}

$pyCmd = Get-PythonCommand
if (-not $pyCmd) { Write-Err 'Python introuvable dans le PATH.'; Stop-TranscriptSafe; exit 1 }
Write-Info "Python hôte: $(& $pyCmd[0] $pyCmd[1..($pyCmd.Count-1)] --version 2>&1)"

# Version check
$verCheck = & $pyCmd[0] $pyCmd[1..($pyCmd.Count-1)] - <<PY
import sys
minv = tuple(map(int, '$MinPy'.split('.')))
print('OK' if sys.version_info >= minv else 'KO')
PY
if ($verCheck -ne 'OK') {
  Write-Err "Version Python trop ancienne (min $MinPy). Trouvé: $(& $pyCmd[0] $pyCmd[1..($pyCmd.Count-1)] --version 2>&1)"
  Stop-TranscriptSafe; exit 1
}

# Disk free check
try {
  $drive = Get-PSDrive -Name ((Get-Item .).PSDrive.Name)
  if ($drive -and ($drive.Free/1MB) -lt $MinFreeMB) { Write-Err "Espace disque insuffisant: $([int]($drive.Free/1MB)) MiB < $MinFreeMB MiB requis"; Stop-TranscriptSafe; exit 1 }
} catch {}

# Recreate venv if requested
if ($Recreate -and (Test-Path -Path $VenvDir)) {
  Write-Info 'Recréation du venv'
  Remove-Item -Recurse -Force $VenvDir -ErrorAction SilentlyContinue
}

# Ensure venv exists
if (-not (Test-Path -Path $VenvDir)) {
  Write-Info 'Création du venv'
  & $pyCmd[0] $pyCmd[1..($pyCmd.Count-1)] -m venv $VenvDir
  if ($LASTEXITCODE -ne 0) { Write-Err "Échec de la création du venv."; Stop-TranscriptSafe; exit $LASTEXITCODE }
}

# venv python path (Windows)
$VENV_PY = Join-Path $VenvDir 'Scripts/python.exe'
if (-not (Test-Path -Path $VENV_PY)) { Write-Err "Python du venv introuvable: $VENV_PY"; Stop-TranscriptSafe; exit 1 }
Write-Info "Python venv: $(& $VENV_PY --version 2>&1) @ $VENV_PY"

# Upgrade pip unless disabled
if (-not $NoUpgrade) {
  Write-Info 'Mise à jour de pip'
  & $VENV_PY -m pip install --upgrade pip
  if ($LASTEXITCODE -ne 0) { Write-Err 'Échec mise à jour de pip'; Stop-TranscriptSafe; exit $LASTEXITCODE }
}

# Install dependencies unless skipped
if ($SkipInstall) {
  Write-Warn 'Installation des dépendances ignorée (-SkipInstall)'
} elseif (Test-Path -Path $Requirements) {
  # Cache de hash requirements
  $marker = Join-Path $VenvDir '.requirements.sha256'
  $hash = (Get-FileHash -Algorithm SHA256 -Path $Requirements).Hash
  $cur = if (Test-Path -Path $marker) { Get-Content -Path $marker -ErrorAction SilentlyContinue } else { '' }
  if (-not $ForceInstall -and $hash -eq $cur) {
    Write-Ok 'requirements.txt déjà installé (hash identique), saute l''installation'
  } else {
    Write-Info "Installation des dépendances ($Requirements)"
    $args = @('install')
    if ($Offline) {
      if (-not $Wheelhouse) { Write-Err '--Offline nécessite --Wheelhouse <dir>'; Stop-TranscriptSafe; exit 2 }
      $args += @('--no-index','--find-links', $Wheelhouse)
    }
    $args += @('-r', $Requirements)
    if ($PipArg) { $args += $PipArg }
    & $VENV_PY -m pip @args
    if ($LASTEXITCODE -ne 0) { Write-Err 'Échec installation des dépendances'; Stop-TranscriptSafe; exit $LASTEXITCODE }
    $hash | Set-Content -Path $marker -Encoding ascii -NoNewline
  }
} else {
  Write-Warn "Aucun fichier $Requirements trouvé — installation ignorée"
}

# Read app version (best-effort)
$APP_VERSION = (& $VENV_PY -c "import sys`ntry:`n import utils; print(getattr(utils,'__version__','?'))`nexcept Exception:`n print('?')" 2>$null)
Write-Host "`n—— Lancement de main.py (version $APP_VERSION) ——"

& $VENV_PY 'main.py' @AppArgs
if ($LASTEXITCODE -ne 0) {
  Write-Err "main.py s'est terminé avec un code d'erreur $LASTEXITCODE"
  Stop-TranscriptSafe; exit $LASTEXITCODE
}
Stop-TranscriptSafe
