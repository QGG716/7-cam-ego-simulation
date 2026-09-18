param([switch]$Render,[switch]$View,[switch]$OpenScene)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$config=Get-Content -Raw config/environment.local.json | ConvertFrom-Json
if ($Render) {
    & $config.local_python scripts/run_remote_indoor_wearer.py
    if ($LASTEXITCODE -ne 0) { throw 'Indoor rendering or transfer failed; inspect reports/step2_1.' }
}
if (Test-Path outputs/step2_1/occlusion_summary.json) {
    & $config.local_python scripts/finalize_indoor_wearer.py
    if ($LASTEXITCODE -ne 0) { throw 'Indoor artifact validation failed.' }
}
if ($View) {
    Invoke-Item outputs/step2_1/front_trio.png
    Invoke-Item outputs/step2_1/surround_four.png
    Invoke-Item outputs/step2_1/worn_full
}
if ($OpenScene) {
    $scene=Join-Path $projectRoot 'scenes/step2_1/indoor_wearer.usda'
    if (!(Test-Path $scene)) { throw 'Run -Render first.' }
    Invoke-Item $scene
    Write-Output 'Open in Isaac Sim 6.0.1.0; generic USD viewers may not support the verified camera backends.'
}
