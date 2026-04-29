$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$python = Join-Path $backend ".venv\Scripts\python.exe"
$logs = Join-Path $root "workspace\logs"

New-Item -ItemType Directory -Force -Path $logs | Out-Null

if (-not (Test-Path $python)) {
    Write-Error "Backend virtualenv not found. Install dependencies as described in README first."
}

$existing = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($pidValue in $existing) {
    Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue
}

Start-Process -FilePath $python `
    -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8000" `
    -WorkingDirectory $backend `
    -RedirectStandardOutput (Join-Path $logs "backend.out.log") `
    -RedirectStandardError (Join-Path $logs "backend.err.log") `
    -WindowStyle Hidden

Start-Sleep -Seconds 3
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health"
