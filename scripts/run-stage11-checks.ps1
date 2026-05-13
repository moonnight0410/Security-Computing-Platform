$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command,
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

Push-Location $root
Invoke-Checked { python -m compileall backend\app } "backend compile"
Pop-Location

Push-Location (Join-Path $root "backend")
Invoke-Checked { .\.venv\Scripts\python.exe -m unittest discover -s tests } "backend unit tests"
Pop-Location

Push-Location (Join-Path $root "frontend")
Invoke-Checked { npx tsc --noEmit } "frontend typecheck"
Invoke-Checked { npm run build } "frontend build"
Pop-Location

Write-Output "Stage 11 local checks completed."
