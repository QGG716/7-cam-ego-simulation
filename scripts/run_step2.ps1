param([switch]$Render,[switch]$Reanalyze)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$config=Get-Content -Raw config/environment.local.json | ConvertFrom-Json
if ($Reanalyze -or !(Test-Path outputs/step2/camera_occlusion_summary.json)) {
    & $config.local_python scripts/analyze_step2.py
    if ($LASTEXITCODE -ne 0) { throw 'Analytic analysis failed.' }
}
if ($Render) {
    & $config.local_python scripts/run_remote_step2.py
    if ($LASTEXITCODE -ne 0) { throw 'Remote Step 2 failed.' }
}
& $config.local_python tests/test_step2.py
if ($LASTEXITCODE -ne 0) { throw 'Step 2 regression failed.' }
if (Test-Path outputs/step2/render_status.json) {
    & $config.local_python scripts/finalize_step2.py
    if ($LASTEXITCODE -ne 0) { throw 'Artifact comparison failed.' }
    & $config.local_python scripts/report_step2.py
    if ($LASTEXITCODE -ne 0) { throw 'Report generation failed.' }
}
