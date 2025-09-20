# Lance l'UI Watcher
Set-Location $PSScriptRoot

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

.\.venv\Scripts\python.exe app/ui/main.py
