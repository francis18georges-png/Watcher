param([switch]$SkipOllama)
Write-Host "== Watcher installer =="

python -m venv .venv
.\.venv\Scripts\pip install --upgrade pip wheel
.\.venv\Scripts\pip install -r requirements.txt

if (-not $SkipOllama) {
  try { winget install -e --id Ollama.Ollama -h } catch {}
  Start-Process -FilePath "C:\Program Files\Ollama\ollama.exe" -ArgumentList "serve"
  Start-Sleep -Seconds 2
  & "C:\Program Files\Ollama\ollama.exe" pull llama3.2:3b
  & "C:\Program Files\Ollama\ollama.exe" pull nomic-embed-text
}
