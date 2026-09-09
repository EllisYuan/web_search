param(
    [ValidateSet('ocr','read','all')][string]$Group = 'ocr',
    [string]$Name = 'baseline'
)
$ErrorActionPreference = 'Stop'
$prototypeRoot = Split-Path -Parent $PSScriptRoot
$worktreeRoot = Split-Path -Parent $prototypeRoot
Push-Location $worktreeRoot
try {
    if (-not (Test-Path '.venv/Scripts/python.exe')) {
        uv venv .venv --python 3.12
        if ($LASTEXITCODE -ne 0) { throw 'venv setup failed' }
    }
    uv pip sync --python .venv/Scripts/python.exe prototypes/cpu-web-read/requirements.lock
    if ($LASTEXITCODE -ne 0) { throw 'dependency installation failed' }
    $env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $worktreeRoot '.cache/ms-playwright'
    .venv/Scripts/python.exe -m playwright install chromium --only-shell
    if ($LASTEXITCODE -ne 0) { throw 'browser installation failed' }
    .venv/Scripts/python.exe prototypes/cpu-web-read/prepare.py
    if ($LASTEXITCODE -ne 0) { throw 'fixture generation failed' }
    .venv/Scripts/python.exe prototypes/cpu-web-read/download_samples.py
    if ($LASTEXITCODE -ne 0) { throw 'public sample preparation failed' }
    .venv/Scripts/python.exe prototypes/cpu-web-read/probe.py run --group $Group --name $Name
    if ($LASTEXITCODE -ne 0) { throw 'probe failed' }
} finally { Pop-Location }
