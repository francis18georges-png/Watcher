param([switch])
Write-Host "== Watcher installer =="

python -m venv .venv
.\.venv\Scripts\pip install --upgrade pip wheel
.\.venv\Scripts\pip install rich pydantic tomli-w psutil pillow pyperclip "urllib3<3" 
    ruff black mypy bandit semgrep pytest pytest-cov hypothesis coverage 
    requests httpx numpy scikit-learn sqlite-utils

if (-not ) {
  try { winget install -e --id Ollama.Ollama -h } catch {}
  Start-Process -FilePath "C:\Program Files\Ollama\ollama.exe" -ArgumentList "serve"
  Start-Sleep -Seconds 2
  & "C:\Program Files\Ollama\ollama.exe" pull llama3.2:3b
  & "C:\Program Files\Ollama\ollama.exe" pull nomic-embed-text
}
