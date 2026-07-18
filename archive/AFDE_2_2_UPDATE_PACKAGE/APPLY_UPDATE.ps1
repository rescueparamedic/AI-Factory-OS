$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PatchRoot = Join-Path $ProjectRoot "patch"
$TargetRoot = Split-Path -Parent $ProjectRoot

Write-Host "[AFDE-2.2] Applying update to: $TargetRoot" -ForegroundColor Cyan
Copy-Item (Join-Path $PatchRoot "afde\task_runner.py") (Join-Path $TargetRoot "afde\task_runner.py") -Force
Copy-Item (Join-Path $PatchRoot "afde\cli.py") (Join-Path $TargetRoot "afde\cli.py") -Force
Copy-Item (Join-Path $PatchRoot "tests\test_afde_cli_runtime.py") (Join-Path $TargetRoot "tests\test_afde_cli_runtime.py") -Force
Write-Host "[AFDE-2.2] Update applied." -ForegroundColor Green
Write-Host "Run: python -m pytest -q" -ForegroundColor Yellow
