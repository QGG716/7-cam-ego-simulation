param([switch]$Render,[switch]$View)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$python=Join-Path $projectRoot '.venv/Scripts/python.exe'
if (Test-Path config/environment.local.json) { $python=(Get-Content -Raw config/environment.local.json | ConvertFrom-Json).local_python }
if ($Render) {
    & $python scripts/render_fov_figure_remote.py
    if ($LASTEXITCODE -ne 0) { throw 'External figure rendering failed; inspect reports/step2_1b.' }
}
& $python scripts/build_fov_figure.py
if ($LASTEXITCODE -ne 0) { throw 'Figure generation or baseline check failed.' }
if ($View) { Invoke-Item outputs/step2_1b/fov_overview_wearer.png }
