# Scripts d'autostart générés

Watcher automatise l'exécution de l'autopilote sans commandes en configurant des tâches spécifiques selon l'OS.

## Windows (Task Scheduler + RunOnce)

Les artefacts générés sont archivés dans `~/.watcher/autostart/windows/` pour audit :

- `watcher-register-autostart.ps1` peut être relancé pour recréer le RunOnce et la tâche planifiée.
- `README.md` résume les étapes appliquées durant `watcher init --auto`.
- **RunOnce** exécute `watcher init --auto` si la sentinelle `~/.watcher/first_run` est présente.
- La tâche planifiée `Watcher Autopilot` lance `watcher autopilot run --noninteractive` à chaque ouverture de session.
- `WATCHER_DISABLE=1` ou `~/.watcher/disable` désactivent le démarrage automatique, sauf si `WATCHER_AUTOSTART=1` force explicitement l'activation.

```powershell
# Contenu de ~/.watcher/autostart/windows/watcher-register-autostart.ps1
$runOnce = "watcher init --auto"
$autopilot = "watcher autopilot run --noninteractive"

New-Item -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce' -Force | Out-Null
Set-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce' `
    -Name 'WatcherInit' -Type String -Value $runOnce -Force

schtasks /Create /TN "Watcher Autopilot" /TR $autopilot /SC ONLOGON /F
```

## Linux (systemd --user)

Les fichiers systemd sont stockés dans `~/.watcher/autostart/linux/` et recopiés dans `~/.config/systemd/user/` pour activation.
Toute dérive peut être corrigée en recopiant les artefacts signés depuis le dossier d'autostart.

```ini
# ~/.watcher/autostart/linux/watcher-autopilot.service
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
# ~/.watcher/autostart/linux/watcher-autopilot.timer
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
