$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $root "frontend"
$logs = Join-Path $root "workspace\logs"

New-Item -ItemType Directory -Force -Path $logs | Out-Null

$existing = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($pidValue in $existing) {
    Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue
}

Start-Process -FilePath "npm.cmd" `
    -ArgumentList "run","dev" `
    -WorkingDirectory $frontend `
    -RedirectStandardOutput (Join-Path $logs "frontend.out.log") `
    -RedirectStandardError (Join-Path $logs "frontend.err.log") `
    -WindowStyle Hidden

Start-Sleep -Seconds 3
Write-Output "Frontend started: http://127.0.0.1:5173"
