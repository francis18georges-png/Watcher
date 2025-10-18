param(
    [string]$Prompt = "test"
)

$env:WATCHER_OFFLINE = "1"
$env:WATCHER_DISABLE_NETWORK = "1"
$logPath = Join-Path $env:USERPROFILE ".watcher\logs\autostart-$(Get-Date -Format 'yyyyMMdd').log"
New-Item -ItemType Directory -Path (Split-Path $logPath) -Force | Out-Null

$command = "watcher run --offline --prompt `"$Prompt`""
Invoke-Expression $command | Tee-Object -FilePath $logPath -Append
