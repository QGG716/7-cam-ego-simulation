param()
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot\..
& .venv\Scripts\python.exe scripts\run_fov_figure_v3.py
if ($LASTEXITCODE -ne 0) { throw 'Step 2.1b-v3 reproduction failed' }
