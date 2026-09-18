$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$config = Get-Content -Raw (Join-Path $projectRoot 'config/environment.local.json') | ConvertFrom-Json
$archive = Join-Path $projectRoot '七目相机IMU_仿真结构与模型包_SIM-V0.1.zip'
$baseline = Join-Path $projectRoot 'assets/baseline/seven_camera_sim_layout_v01'
Write-Output "Project: $projectRoot"
Write-Output "OS: $([Environment]::OSVersion.VersionString)"
Write-Output "Archive exists: $(Test-Path -LiteralPath $archive)"
Write-Output "Extracted baseline exists: $(Test-Path -LiteralPath $baseline)"
& $config.local_python -c "import sys; print(sys.version); print(sys.executable)"
if ($LASTEXITCODE -ne 0) { throw 'Local Python check failed.' }
if (!(Test-Path -LiteralPath $archive) -and !(Test-Path -LiteralPath $baseline)) {
    Write-Output 'BLOCKED: baseline missing. No simulation or rendering has run.'
    exit 2
}
Write-Output 'Baseline path exists; content verification is still required before simulation.'
