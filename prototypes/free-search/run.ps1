param([string]$Window = (Get-Date -Format 'yyyyMMdd-HHmmss'))
# THROWAWAY: requires Python/uv and a running Docker Desktop Linux daemon.
$ErrorActionPreference = 'Stop'
$imageRef = 'searxng/searxng@sha256:3547509b419cd6a67333d6d68bd1ffad8d46d3669d82e7a7bd538f7b45827432'
$containerName = 'web-search-prototype-searxng'
$pythonPath = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    uv venv (Join-Path $PSScriptRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'uv venv failed' }
}
uv pip sync --python $pythonPath (Join-Path $PSScriptRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
$existing = docker ps -a --filter "name=^/$containerName$" --format '{{.Names}}'
if ($LASTEXITCODE -ne 0) { throw 'Docker daemon unavailable' }
if ($existing -eq $containerName) {
    $actualImage = docker inspect $containerName --format '{{.Config.Image}}'
    if ($actualImage -ne $imageRef) { throw 'Container name is occupied by a different image' }
    docker start $containerName | Out-Null
} else {
    $settingsPath = Join-Path $PSScriptRoot 'settings.yml'
    docker run --detach --name $containerName --publish '127.0.0.1:18888:8080' --mount "type=bind,source=$settingsPath,target=/etc/searxng/settings.yml,readonly" $imageRef | Out-Null
}
if ($LASTEXITCODE -ne 0) { throw 'Container start failed' }
$ready = $false
for ($attempt = 0; $attempt -lt 15; $attempt++) {
    try {
        Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:18888/healthz' -TimeoutSec 2 | Out-Null
        $ready = $true
        break
    } catch { Start-Sleep -Seconds 1 }
}
if (-not $ready) { throw 'SearXNG health check failed' }
& $pythonPath (Join-Path $PSScriptRoot 'probe.py') --window $Window
if ($LASTEXITCODE -ne 0) { throw 'Probe failed; inspect saved partial observations' }
Write-Output "Observations: $PSScriptRoot/runs/$Window"
Write-Output "Stop the temporary service when finished: docker stop $containerName"
