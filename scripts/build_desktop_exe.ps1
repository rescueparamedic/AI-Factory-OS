[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$repositoryRoot = [System.IO.Path]::GetFullPath((
    Join-Path -Path $PSScriptRoot -ChildPath '..'
))
$specPath = Join-Path $repositoryRoot 'packaging\ai_factory_desktop.spec'
$buildPath = Join-Path $repositoryRoot 'build'
$distPath = Join-Path $repositoryRoot 'dist'
$expectedExe = Join-Path $distPath 'AI Factory Desktop\AI Factory Desktop.exe'

function Remove-RepositoryBuildDirectory {
    param([Parameter(Mandatory)][string]$Path)

    $resolved = [System.IO.Path]::GetFullPath($Path)
    $separator = [System.IO.Path]::DirectorySeparatorChar
    $rootPrefix = $repositoryRoot.TrimEnd($separator) + $separator
    if (-not $resolved.StartsWith(
        $rootPrefix, [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw ('Refusing to remove a path outside the repository: ' + $resolved)
    }
    if ($resolved -notin @($buildPath, $distPath)) {
        throw ('Refusing to remove an unexpected repository path: ' + $resolved)
    }
    if (Test-Path -LiteralPath $resolved) {
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}

if (-not (Test-Path -LiteralPath $specPath -PathType Leaf)) {
    throw ('PyInstaller spec was not found: ' + $specPath)
}

& python -c 'import PyInstaller'
if ($LASTEXITCODE -ne 0) {
    throw 'PyInstaller is unavailable. Install requirements-packaging.txt.'
}

Remove-RepositoryBuildDirectory -Path $buildPath
Remove-RepositoryBuildDirectory -Path $distPath

$pyInstallerArguments = @(
    '-m',
    'PyInstaller',
    '--noconfirm',
    '--workpath',
    $buildPath,
    '--distpath',
    $distPath,
    $specPath
)
Push-Location $repositoryRoot
try {
    & python @pyInstallerArguments
    if ($LASTEXITCODE -ne 0) {
        throw ('PyInstaller failed with exit code ' + $LASTEXITCODE)
    }
}
finally {
    Pop-Location
}

if (-not (Test-Path -LiteralPath $expectedExe -PathType Leaf)) {
    throw ('Expected executable was not created: ' + $expectedExe)
}

Write-Output ('AI Factory Desktop executable: ' + $expectedExe)
