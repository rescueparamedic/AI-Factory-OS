$ErrorActionPreference = 'Stop'

Write-Host '=== AI Factory OS / AFDE-2.2 Source Export ===' -ForegroundColor Cyan

$root = (Get-Location).Path
if (-not (Test-Path (Join-Path $root '.git'))) {
    throw 'Git repository root에서 실행해야 합니다. (.git 폴더가 없습니다.)'
}

$branch = (git branch --show-current).Trim()
if ($branch -ne 'develop') {
    throw "현재 브랜치가 '$branch' 입니다. develop 브랜치에서 실행하세요."
}

$required = @(
    'afde',
    'tests',
    'pyproject.toml',
    'pytest.ini',
    'requirements.txt',
    'README.md'
)

$stage = Join-Path $env:TEMP 'AI_FACTORY_OS_AFDE_2_2_SOURCE'
$zip = Join-Path $root 'AI_FACTORY_OS_AFDE_2_2_SOURCE.zip'

if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Path $stage | Out-Null

foreach ($item in $required) {
    $source = Join-Path $root $item
    if (Test-Path $source) {
        Copy-Item $source $stage -Recurse -Force
    }
}

$gitInfo = @{
    branch = $branch
    head = (git rev-parse HEAD).Trim()
    status = (git status --short | Out-String).Trim()
    remote = (git remote -v | Out-String).Trim()
    exported_at = (Get-Date).ToString('o')
}
$gitInfo | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $stage 'GIT_SNAPSHOT.json') -Encoding UTF8

if (-not (Test-Path (Join-Path $stage 'afde'))) {
    throw 'afde 폴더를 찾지 못했습니다. 프로젝트 루트가 맞는지 확인하세요.'
}

if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zip -CompressionLevel Optimal

Write-Host "완료: $zip" -ForegroundColor Green
Write-Host '이 ZIP 파일을 현재 대화에 첨부하세요.' -ForegroundColor Yellow
