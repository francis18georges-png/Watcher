param(
    [switch]$SkipOllama,
    [switch]$SkipDevDependencies,
    [switch]$Initialize
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "== Watcher installer (llama.cpp / offline-first) =="

$seed = $env:WATCHER_TRAINING__SEED
if (-not $seed -and $env:SEED) {
    $seed = $env:SEED
}
if (-not $seed) {
    $seed = "42"
}
$env:WATCHER_TRAINING__SEED = $seed
$env:PYTHONHASHSEED = $seed
if (-not $env:CUBLAS_WORKSPACE_CONFIG) {
    $env:CUBLAS_WORKSPACE_CONFIG = ":4096:8"
}
if (-not $env:TORCH_DETERMINISTIC) {
    $env:TORCH_DETERMINISTIC = "1"
}

if ($SkipOllama) {
    Write-Warning "-SkipOllama est conserve pour compatibilite mais n'a plus d'effet. Watcher utilise maintenant le bootstrap local via watcher init --fully-auto."
}

python -m venv .venv

$python = ".\.venv\Scripts\python.exe"
$watcher = ".\.venv\Scripts\watcher.exe"

& $python -m pip install --upgrade pip wheel
if ($LASTEXITCODE -ne 0) {
    throw "Echec de la mise a niveau de pip."
}

& $python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    throw "Echec de l'installation de requirements.txt."
}

if (-not $SkipDevDependencies) {
    & $python -m pip install -r requirements-dev.txt
    if ($LASTEXITCODE -ne 0) {
        throw "Echec de l'installation de requirements-dev.txt."
    }
}

& $python -m pip install -e .
if ($LASTEXITCODE -ne 0) {
    throw "Echec de l'installation editable du package watcher."
}

if ($Initialize) {
    & $watcher init --fully-auto
    if ($LASTEXITCODE -ne 0) {
        throw "Echec de watcher init --fully-auto."
    }
}

Write-Host ""
Write-Host "Installation terminee."
Write-Host "Prochaines etapes:"
if (-not $Initialize) {
    Write-Host "  1. $watcher init --fully-auto"
    Write-Host "  2. .\\run.ps1"
} else {
    Write-Host "  1. .\\run.ps1"
}
