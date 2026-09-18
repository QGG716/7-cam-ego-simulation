param([switch]$Render)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$config = Get-Content -Raw config/environment.local.json | ConvertFrom-Json
& $config.local_python scripts/build_step1.py
if ($LASTEXITCODE -ne 0) { throw 'Artifact generation failed.' }
& $config.local_python tests/test_offline.py
if ($LASTEXITCODE -ne 0) { throw 'Offline checks failed.' }
if ($Render) {
    & $config.local_python scripts/run_remote_step1.py
    if ($LASTEXITCODE -ne 0) { throw 'Remote Step 1 failed. Inspect reports/isaac_all.log.' }
    & $config.local_python scripts/finalize_step1.py
    if ($LASTEXITCODE -ne 0) { throw 'Downloaded artifact checks failed.' }
}
