$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$config = Get-Content -Raw (Join-Path $projectRoot 'config/environment.local.json') | ConvertFrom-Json
$probePath = Join-Path $PSScriptRoot 'probe_remote.py'
$encoded = [Convert]::ToBase64String([IO.File]::ReadAllBytes($probePath))
# Base64 alphabet and the configured absolute executable path are passed to the remote shell.
if ($config.remote_python -notmatch '^/[A-Za-z0-9_./-]+$') { throw 'Invalid remote Python path.' }
$remoteCommand = 'echo ' + $encoded + ' | base64 -d | ' + $config.remote_python
New-Item -ItemType Directory -Force (Join-Path $projectRoot '.ssh') | Out-Null
$knownHosts = Join-Path $projectRoot '.ssh/known_hosts'
$result = & ssh -p $config.ssh_port -o ConnectTimeout=15 -o StrictHostKeyChecking=accept-new -o "UserKnownHostsFile=$knownHosts" "$($config.ssh_user)@$($config.ssh_host)" $remoteCommand
if ($LASTEXITCODE -ne 0) { throw "Remote inventory failed: $LASTEXITCODE" }
$json = $result -join "`n"
$null = $json | ConvertFrom-Json
New-Item -ItemType Directory -Force (Join-Path $projectRoot 'reports') | Out-Null
[IO.File]::WriteAllText((Join-Path $projectRoot 'reports/remote_environment.json'), $json, (New-Object Text.UTF8Encoding($false)))
Write-Output 'Saved reports/remote_environment.json. Isaac was not started.'
