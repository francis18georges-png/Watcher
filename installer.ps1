param([switch]$SkipOllama)
Write-Host "== Watcher installer =="

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

python -m venv .venv
.\.venv\Scripts\pip install --upgrade pip wheel
.\.venv\Scripts\pip install rich pydantic tomli-w psutil pillow pyperclip "urllib3<3"
    ruff black mypy bandit semgrep pytest pytest-cov hypothesis coverage
    requests httpx numpy scikit-learn sqlite-utils

if (-not $SkipOllama) {
  try { winget install -e --id Ollama.Ollama -h } catch {}
  Start-Process -FilePath "C:\Program Files\Ollama\ollama.exe" -ArgumentList "serve"
  Start-Sleep -Seconds 2
  & "C:\Program Files\Ollama\ollama.exe" pull llama3.2:3b
  & "C:\Program Files\Ollama\ollama.exe" pull nomic-embed-text
}
