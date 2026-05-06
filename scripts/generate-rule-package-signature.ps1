param(
    [Parameter(Mandatory = $true)]
    [string]$Name,
    [Parameter(Mandatory = $true)]
    [string]$Purpose,
    [Parameter(Mandatory = $true)]
    [string]$SignerName,
    [Parameter(Mandatory = $true)]
    [string]$SignatureRef,
    [Parameter(Mandatory = $true)]
    [string]$RulesJson,
    [string]$Version = "0.1.0"
)

$root = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $root "workspace\config\trusted-signers.json"
if (-not (Test-Path $configPath)) {
    throw "未找到 trusted-signers.json，请先执行 scripts/bootstrap-stage8-keys.ps1"
}

$signers = Get-Content -Path $configPath -Encoding UTF8 | ConvertFrom-Json
$signer = $signers | Where-Object { $_.signer_name -eq $SignerName } | Select-Object -First 1
if (-not $signer) {
    throw "未知签名人：$SignerName"
}
if ($signer.signature_ref -ne $SignatureRef) {
    throw "签名引用与签名人配置不一致"
}

$privateKeyPath = Join-Path $root ($signer.private_key_path -replace '/', '\')
if (-not (Test-Path $privateKeyPath)) {
    throw "未找到私钥文件：$privateKeyPath"
}

$rules = $RulesJson | ConvertFrom-Json
$payloadObject = [ordered]@{
    name = $Name
    purpose = $Purpose
    rules = $rules
    signature_ref = $SignatureRef
    signer_name = $SignerName
    version = $Version
}
$payloadJson = $payloadObject | ConvertTo-Json -Depth 20 -Compress

$tempDir = Join-Path $env:TEMP ("rule-sign-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tempDir | Out-Null
try {
    $payloadPath = Join-Path $tempDir "payload.json"
    $signaturePath = Join-Path $tempDir "payload.sig"
    [System.IO.File]::WriteAllText($payloadPath, $payloadJson, [System.Text.Encoding]::UTF8)
    & openssl dgst -sha256 -sign $privateKeyPath -out $signaturePath $payloadPath | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "OpenSSL 签名失败"
    }
    [Convert]::ToBase64String([System.IO.File]::ReadAllBytes($signaturePath))
}
finally {
    Remove-Item -LiteralPath $tempDir -Recurse -Force -ErrorAction SilentlyContinue
}
