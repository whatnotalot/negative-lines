# Launch the Negative Lines ML & BO studio: .\run_app.ps1 [-Port 8501] [-Rebuild]
param([int]$Port = 8501, [switch]$Rebuild)
. "$PSScriptRoot\scripts\project-env.ps1"
if ($Rebuild -or -not (Test-Path "$PSScriptRoot\results\replay\summary.csv")) {
    & $env:NEGLINES_PYTHON scripts\run_cv.py --workers 8
    & $env:NEGLINES_PYTHON scripts\run_replay.py --workers 16
}
& $env:NEGLINES_PYTHON -m streamlit run app\streamlit_app.py --server.port $Port
