# Arborescence cible

L'installation plug-and-play génère automatiquement l'arborescence suivante dans `~/.watcher` lors du premier lancement :

```
~/.watcher/
├── config.toml             # configuration LLM, chemins locaux et sandbox
├── policy.yaml             # politique réseau/offline unique (version 2)
├── .env                    # variables d'environnement dérivées et hachages de référence
├── consents.jsonl          # registre signé des consentements et décisions de policy
├── disable                 # kill-switch manuel (facultatif)
├── models/
│   ├── llm/
│   │   └── *.gguf          # modèles llama.cpp téléchargés par hash
│   └── embeddings/
│       └── *.bin           # modèles d'embeddings locaux
├── memory/
│   └── mem.db              # index vectoriel SQLite-VSS/FAISS
├── logs/
│   └── autopilot.log       # traces consolidées des cycles
├── reports/
│   └── weekly.html         # rapport hebdo des sources ingérées/révoquées
├── workspace/              # bac à sable isolé pour les outils
└── systemd/
    └── watcher-autopilot.{service,timer} # service utilisateur (Linux)
```

Sous Windows, `watcher init --auto` crée également :

```
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Watcher Autopilot.lnk
HKCU\Software\Microsoft\Windows\CurrentVersion\RunOnce\WatcherInit
SCHTASKS /Create /TN "Watcher Autopilot" /SC ONLOGON /TR "watcher autopilot run --noninteractive"
```

Cette arborescence garantit un environnement isolé, reproductible et sans dépendance à une infrastructure distante.
