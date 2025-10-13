# Résumé d'architecture

Watcher fonctionne comme un pipeline local-first orchestrant l'initialisation automatique, la collecte vérifiée et la diffusion
des connaissances en RAG. Les modules principaux sont :

- **Bootstrap** (`app/core/first_run.py`) : détecte le matériel, choisit les modèles `llama.cpp`, télécharge les artefacts par
  hachage et écrit `~/.watcher/{config.toml,policy.yaml,.env,consents.jsonl}` avant de configurer l'autostart.
- **Politique** (`app/policy`) : valide un schéma unique `policy.yaml`, expose les domaines autorisés et applique le kill-switch.
- **Autopilot** (`app/autopilot`) : planifie les créneaux réseau (02:00–04:00), applique les budgets CPU/RAM/bande passante et
  boucle sur *discover → scrape → verify → ingest* sans intervention.
- **Scrapers & ingestion** (`app/scrapers`, `app/ingest`) : récupèrent en respectant robots.txt, normalisent les textes et
  n'indexent que les contenus corroborés (≥ 2 sources) dans une base vectorielle locale.
- **Sécurité & sandbox** (`app/tools`, `app.utils`) : isole les sous-processus via Job Objects/cgroups et coupe le réseau hors
  fenêtre autorisée.

## Diagramme texte des flux

```
[Boot] -> [FirstRunConfigurator] -> [~/.watcher]
    -> [PolicyManager] -> [policy.yaml | consents.jsonl]
    -> [Autostart Tasks] -> {Windows Task Scheduler, systemd --user}
[Autostart] -> [AutopilotScheduler] -> [AutopilotController]
[AutopilotController] -> (Discovery) -> [Scrapers]
[Scrapers] -> (Trafilatura/Readability) -> [Verifier]
[Verifier] -> (>=2 sources & licence OK) -> [IngestPipeline]
[IngestPipeline] -> [SQLite-VSS/FAISS] -> [RAG API]
[RAG API] -> [watcher run --offline] -> [Deterministic answers]
```

Ce diagramme textuel souligne la séparation des responsabilités : les composants de gouvernance préparent l'exécution, les
limites de ressources sont gérées par l'autopilote, et la mémoire vectorielle reste locale et scellée.
