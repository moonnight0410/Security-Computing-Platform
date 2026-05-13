$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendPython = Join-Path $repoRoot "backend\.venv\Scripts\python.exe"
$frontendDir = Join-Path $repoRoot "frontend"

Write-Host "[Stage12] Backend compile check"
& $backendPython -m compileall (Join-Path $repoRoot "backend\app")

Write-Host "[Stage12] Frontend build check"
Push-Location $frontendDir
try {
  npm.cmd run build
}
finally {
  Pop-Location
}

Write-Host "[Stage12] Checks completed"
