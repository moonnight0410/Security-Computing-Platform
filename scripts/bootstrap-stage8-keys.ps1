$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$configDir = Join-Path $root "workspace\config"
$publicDir = Join-Path $configDir "keys\public"
$privateDir = Join-Path $configDir "keys\private"

New-Item -ItemType Directory -Force -Path $publicDir | Out-Null
New-Item -ItemType Directory -Force -Path $privateDir | Out-Null

function New-RsaKeyPair {
    param(
        [string]$PrivateKeyPath,
        [string]$PublicKeyPath
    )

    if (-not (Test-Path $PrivateKeyPath)) {
        & openssl genrsa -out $PrivateKeyPath 2048 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "生成私钥失败：$PrivateKeyPath"
        }
    }
    if (-not (Test-Path $PublicKeyPath)) {
        & openssl rsa -in $PrivateKeyPath -pubout -out $PublicKeyPath | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "导出公钥失败：$PublicKeyPath"
        }
    }
}

$cityPrivate = Join-Path $privateDir "city-rule-center-private.pem"
$cityPublic = Join-Path $publicDir "city-rule-center-public.pem"
$govPrivate = Join-Path $privateDir "governance-office-private.pem"
$govPublic = Join-Path $publicDir "governance-office-public.pem"
$archivePrivate = Join-Path $privateDir "archive-sealer-private.pem"
$archivePublic = Join-Path $publicDir "archive-sealer-public.pem"

New-RsaKeyPair -PrivateKeyPath $cityPrivate -PublicKeyPath $cityPublic
New-RsaKeyPair -PrivateKeyPath $govPrivate -PublicKeyPath $govPublic
New-RsaKeyPair -PrivateKeyPath $archivePrivate -PublicKeyPath $archivePublic

$trustedSigners = @(
    [ordered]@{
        signer_name = "市级规则中心"
        key_type = "rsa-public-key"
        signature_ref = "SIG-CENTER-RSA-001"
        status = "active"
        public_key_path = "workspace/config/keys/public/city-rule-center-public.pem"
        private_key_path = "workspace/config/keys/private/city-rule-center-private.pem"
        description = "市级规则中心离线 RSA 密钥"
    }
    [ordered]@{
        signer_name = "数据治理办公室"
        key_type = "rsa-public-key"
        signature_ref = "SIG-GOV-RSA-002"
        status = "active"
        public_key_path = "workspace/config/keys/public/governance-office-public.pem"
        private_key_path = "workspace/config/keys/private/governance-office-private.pem"
        description = "数据治理办公室离线 RSA 密钥"
    }
)
$trustedSigners | ConvertTo-Json -Depth 10 | Set-Content -Path (Join-Path $configDir "trusted-signers.json") -Encoding UTF8

$archiveSigner = [ordered]@{
    signer_name = "本域归档封存中心"
    key_type = "rsa-key-pair"
    signature_ref = "ARCHIVE-SEAL-RSA-001"
    status = "active"
    private_key_path = "workspace/config/keys/private/archive-sealer-private.pem"
    public_key_path = "workspace/config/keys/public/archive-sealer-public.pem"
    description = "本域归档封存中心离线 RSA 密钥对"
}
$archiveSigner | ConvertTo-Json -Depth 10 | Set-Content -Path (Join-Path $configDir "archive-signer.json") -Encoding UTF8

Write-Output "Stage 8 key bootstrap completed."
