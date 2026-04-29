$ports = @(8000, 5173)

foreach ($port in $ports) {
    $existing = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($pidValue in $existing) {
        Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue
    }
}

Write-Output "Local services stopped."
