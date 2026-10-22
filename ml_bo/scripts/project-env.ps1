$ErrorActionPreference = 'Stop'
# Dot-source this: . .\scripts\project-env.ps1
# Uses NEGLINES_PYTHON if set, else the gibo env if present, else `python` on PATH.
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$env:NEGLINES_ROOT = $ProjectRoot
if (-not $env:NEGLINES_PYTHON) {
    $gibo = 'C:\Users\mmuthyala\envs\gibo\Scripts\python.exe'
    $env:NEGLINES_PYTHON = if (Test-Path $gibo) { $gibo } else { (Get-Command python).Source }
}
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:STREAMLIT_BROWSER_GATHER_USAGE_STATS = 'false'
Set-Location -LiteralPath $ProjectRoot
