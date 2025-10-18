# Plan d'architecture Watcher (local-first)

## Objectifs

1. Fonctionnement 100 % hors-ligne par défaut avec déverrouillage explicite via `policy.yaml`.
2. Chaîne RAG vérifiable en local (ingestion → embeddings → moteur de requête) sur SQLite + VSS.
3. Observabilité deterministe : logs JSON, rapports HTML, provenance.

## Composants

- **CLI (`app/cli.py`)** : point d'entrée `watcher`. Modes `init --fully-auto`, `run --offline`, `ask`.
- **Bootstrap (`app/bootstrap.py`)** : détection du premier démarrage, création des dossiers `~/.watcher` et du kill-switch `disable`.
- **Crawler (`app/crawl/*`)** : pipeline structuré autour de `AllowlistManager`, `RobotsCache`, `FetchWorker`, `Parser`, `QualityScorer`.
- **Vector Store (`app/embeddings/store.py`)** : surcouche SQLite/FAISS (`sqlite-vss`) et conversions embeddings `sentence-transformers`.
- **Scheduler (`app/autopilot/scheduler.py`)** : tâches périodiques (crawl, reindex, rapport hebdo) suivant la politique.
- **Consent Ledger (`app/policy/consent.py`)** : append-only JSONL signé (clé Ed25519 générée lors du `init`).
- **Sandbox (`app/security/sandbox.py`)** : wrapper cgroups/Job Objects + coupe-circuit réseau (iptables/Windows Firewall) + `pytest-socket`.

## Flux fonctionnels (diagramme texte)

```
Utilisateur -> watcher CLI
  watcher init --fully-auto
    -> HardwareProbe
    -> ModelRegistry (GGUF metadata, SHA256)
    -> DownloadManager (hash+taille, offline cache)
    -> ConfigWriter (config.toml, policy.yaml, consents.jsonl)
    -> ConsentLedger.sign()

watcher run --offline
  -> ConfigLoader
  -> Sandbox.start()
  -> LocalModel (llama-cpp)
  -> RAGPipeline
       -> QueryRouter
       -> VectorStore.search()
       -> ResponseBuilder
  -> Sandbox.stop()

Scheduler (au démarrage)
  -> PolicyManager.next_tasks()
  -> CrawlTask(fetch->parse->quality->store)
  -> EmbedTask(index SQLite-VSS)
  -> ReportTask(render HTML)
```

## Données & stockage

- `~/.watcher/config.toml` : configuration modèle + options sandbox.
- `~/.watcher/policy.yaml` : règles d'accès domaine/scope, budgets, fréquence crawl.
- `~/.watcher/consents.jsonl` : ledger signé (Ed25519) avec horodatage RFC3339 et version de consentement.
- `~/.watcher/cache/` : contenu brut + métadonnées HTTP (`etag`, `last-modified`).
- `~/.watcher/index.db` : SQLite avec tables `documents`, `embeddings`, `sources`, `consents`.

## Sécurité

- Mode offline enforced : variables d'environnement + `pytest-socket`.
- Sandbox : cgroups v2 (Linux) / Job Objects (Windows), profils `seccomp` optionnels.
- Kill-switch : fichier `~/.watcher/disable` désactive toute tâche planifiée.
- Cosign + SLSA pour binaires et images.

## Observabilité

- `app/logging.py` : logger structuré (JSON) + routeur console.
- `reports/weekly/index.html` généré par `ReportTask` (agrégations ingestion/rejets/licences).

## Interop & publication

- Release GitHub (sdist, wheel, PyInstaller, SBOM, cosign, SLSA).
- Docker multi-arch (amd64/arm64) avec attestation SLSA.
- Documentation MkDocs → GitHub Pages.
