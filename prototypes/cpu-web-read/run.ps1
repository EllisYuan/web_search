param(
    [ValidateSet('ocr','read','all')][string]$Group = 'ocr',
    [string]$Name = 'baseline',
    [switch]$Constrained
)
$ErrorActionPreference = 'Stop'
$prototypeRoot = Split-Path -Parent $PSScriptRoot
$worktreeRoot = Split-Path -Parent $prototypeRoot
$venvDir = Join-Path $worktreeRoot '.venv-system'
$python = Join-Path $venvDir 'Scripts/python.exe'
Push-Location $worktreeRoot
try {
    if (-not (Test-Path $python)) {
        # Prefer the standalone CPython installation on Windows. Anaconda's
        # DLL search path can prevent onnxruntime_pybind11_state from loading.
        uv venv $venvDir --python-preference only-system --python 3.12
        if ($LASTEXITCODE -ne 0) { throw 'venv setup failed' }
    }
    uv pip sync --python $python prototypes/cpu-web-read/requirements.lock
    if ($LASTEXITCODE -ne 0) { throw 'dependency installation failed' }
    $env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $worktreeRoot '.cache/ms-playwright'
    & $python -m playwright install chromium --only-shell
    if ($LASTEXITCODE -ne 0) { throw 'browser installation failed' }
    & $python prototypes/cpu-web-read/prepare.py
    if ($LASTEXITCODE -ne 0) { throw 'fixture generation failed' }
    & $python prototypes/cpu-web-read/download_samples.py
    if ($LASTEXITCODE -ne 0) { throw 'public sample preparation failed' }
    $smoke = @()
    if ($Constrained) { $smoke = @('--constrained') }
    & $python prototypes/cpu-web-read/probe.py run --group $Group --name $Name @smoke
    if ($LASTEXITCODE -ne 0) { throw 'probe failed' }
} finally { Pop-Location }
