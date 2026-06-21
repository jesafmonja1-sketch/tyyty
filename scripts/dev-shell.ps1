$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$srcPath = Join-Path $repoRoot "src"

if (-not (Test-Path -LiteralPath $srcPath)) {
    throw "src directory not found: $srcPath"
}

$env:PYTHONPATH = $srcPath
$env:WCI_DATABASE_URL = "sqlite:///C:/Users/Administrator/Documents/球赛/data/world-cup-intel.db"
$env:WCI_EMAIL_SMTP_HOST = "placeholder"
$env:WCI_EMAIL_SMTP_PORT = "465"
$env:WCI_EMAIL_USERNAME = "placeholder"
$env:WCI_EMAIL_PASSWORD = "placeholder"
$env:WCI_EMAIL_RECIPIENT = "placeholder"

Write-Host "World Cup Intel shell is ready."
Write-Host "Repo root: $repoRoot"
Write-Host "PYTHONPATH: $($env:PYTHONPATH)"
Write-Host "WCI_DATABASE_URL: $($env:WCI_DATABASE_URL)"
Write-Host ""
Write-Host "Next commands:"
Write-Host "  python -m world_cup_intel.cli --help"
Write-Host "  python -X utf8 -m world_cup_intel.cli analyze-match 49"
