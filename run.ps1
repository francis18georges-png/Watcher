# Lance l'UI Watcher
Stop="Stop"
Set-Location (Split-Path -Parent \System.Management.Automation.InvocationInfo.MyCommand.Path)
.\.venv\Scripts\python.exe app/ui/main.py
