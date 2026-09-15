$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$env:TEMP = "S:\.tooling\tmp"
$env:TMP = "S:\.tooling\tmp"
$ffmpegBin = "S:\tools\ffmpeg-9.0.1-essentials_build\bin"
if (Test-Path $ffmpegBin) {
  $env:PATH = "$ffmpegBin;$env:PATH"
}

Write-Host "== API ruff =="
Push-Location apps\api
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m ruff format --check src tests
Write-Host "== API mypy =="
.\.venv\Scripts\python.exe -m mypy src\anything_download
Write-Host "== API pytest =="
.\.venv\Scripts\python.exe -m pytest -q -m "not external and not browser"
Pop-Location

Write-Host "== Web lint/typecheck/build =="
pnpm --filter @anything-download/web lint
pnpm --filter @anything-download/web typecheck
pnpm --filter @anything-download/web build

Write-Host "Quality gate commands finished."
