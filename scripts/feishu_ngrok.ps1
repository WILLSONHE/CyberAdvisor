# Feishu Bot tunnel: ngrok http 8765 (launched by feishu_bot.bat)
$ErrorActionPreference = 'Continue'
Write-Host '>>> ngrok http 8765 (Feishu Bot tunnel)' -ForegroundColor Cyan
Write-Host ''

if (-not (Get-Command ngrok -ErrorAction SilentlyContinue)) {
    Write-Host '[ERROR] ngrok not found in PATH' -ForegroundColor Red
    Read-Host 'Press Enter to close'
    exit 1
}

& ngrok http 8765

Write-Host ''
if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] ngrok exit code: $LASTEXITCODE" -ForegroundColor Red
}
Read-Host 'Press Enter to close'
