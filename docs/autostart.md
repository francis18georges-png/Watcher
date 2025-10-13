# Scripts d'autostart générés

Watcher automatise l'exécution de l'autopilote sans commandes en configurant des tâches spécifiques selon l'OS.

## Windows (Task Scheduler + RunOnce)

```powershell
# Créé lors de `watcher init --auto`
$runOnce = "watcher init --auto"
$autopilot = "watcher autopilot run --noninteractive"

New-Item -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce' -Force | Out-Null
Set-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce' `
    -Name 'WatcherInit' -Type String -Value $runOnce -Force

schtasks /Create /TN "Watcher Autopilot" /TR $autopilot /SC ONLOGON /F
```

- **RunOnce** exécute `watcher init --auto` si la sentinelle `~/.watcher/first_run` est présente.
- La tâche planifiée `Watcher Autopilot` lance `watcher autopilot run --noninteractive` à chaque ouverture de session.
- La présence de `~/.watcher/disable` ou de l'environnement `WATCHER_DISABLE=1` annule la planification, sauf si `WATCHER_AUTOSTART=1` force explicitement l'activation (l'override s'applique même si les deux kill-switch sont présents).

## Linux (systemd --user)

```ini
# ~/.config/systemd/user/watcher-autopilot.service
[Unit]
Description=Watcher Autopilot orchestrator

[Service]
Type=oneshot
WorkingDirectory=%h
Environment=WATCHER_HOME=%h/.watcher
ExecStart=%h/.local/bin/python -m app.cli autopilot run --noninteractive

[Install]
WantedBy=default.target
```

```ini
# ~/.config/systemd/user/watcher-autopilot.timer
[Unit]
Description=Watcher Autopilot orchestrator schedule

[Timer]
OnBootSec=30s
OnUnitActiveSec=1h
Persistent=true
Unit=watcher-autopilot.service

[Install]
WantedBy=timers.target
```

Ces unités sont installées et activées (`systemctl --user enable --now watcher-autopilot.timer`) automatiquement par `FirstRunConfigurator` lorsque le kill-switch est absent.
