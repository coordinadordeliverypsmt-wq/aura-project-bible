# Instalacion del stack real de AURA en Windows (local-first — acta D24). PowerShell.
$ErrorActionPreference = "Stop"
$Model = if ($env:AURA_LLM_MODEL) { $env:AURA_LLM_MODEL } else { "qwen2.5:3b" }
$Here  = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "==> AURA :: instalacion de stack (Windows)"

Write-Host "==> 1/4 Python venv + dependencias"
python -m venv "$Here\..\.venv"
& "$Here\..\.venv\Scripts\python.exe" -m pip install --upgrade pip -q
& "$Here\..\.venv\Scripts\pip.exe" install -q -r "$Here\requirements-stack.txt"

Write-Host "==> 2/4 NATS server (winget o descarga manual)"
if (-not (Get-Command nats-server -ErrorAction SilentlyContinue)) {
  try { winget install -e --id Synadia.NATS.Server --accept-source-agreements --accept-package-agreements } catch {
    Write-Host "   winget no disponible: descarga nats-server de https://github.com/nats-io/nats-server/releases y agregalo al PATH." }
}

Write-Host "==> 3/4 Ollama (ADR-0010)"
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
  try { winget install -e --id Ollama.Ollama --accept-source-agreements --accept-package-agreements } catch {
    Write-Host "   Descarga Ollama de https://ollama.com/download/windows e instalalo." }
}

Write-Host "==> 4/4 Modelo LLM: $Model"
ollama pull $Model
Write-Host "==> LISTO. Verifica con: powershell -File $Here\verify-stack.ps1"
