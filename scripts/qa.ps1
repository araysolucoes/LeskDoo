#requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$Install,
    [switch]$Coverage
)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$python = Join-Path (Get-Location) '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    Write-Error 'Virtual environment absent. Run: py -3.12 -m venv .venv'
    exit 1
}
function Invoke-Step([string]$Name, [string[]]$ArgList) {
    Write-Host "==> $Name" -ForegroundColor Cyan
    & $python @ArgList
    if ($LASTEXITCODE -ne 0) {
        Write-Error "$Name failed (exit $LASTEXITCODE)"
        exit $LASTEXITCODE
    }
}
if ($Install) {
    Invoke-Step 'Install test requirements' @('-m','pip','install','-r','requirements-dev.txt')
}
Invoke-Step 'Compile' @('-m','compileall','-q','leskdoo','tests','run.py')
Invoke-Step 'Critical lint' @('-m','ruff','check','--select','E4,E7,E9,F63,F7,F82','leskdoo','tests','run.py')
Invoke-Step 'YAML validation' @('scripts/check_yaml.py')
$tests = @('-m','pytest','-q')
if ($Coverage) { $tests += @('--cov=leskdoo','--cov-report=term-missing','--cov-report=xml') }
Invoke-Step 'Pytest' $tests
Write-Host 'QA local completed' -ForegroundColor Green
