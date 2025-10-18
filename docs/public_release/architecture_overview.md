# Architecture cible Watcher

## Arborescence logique cible
```
Watcher/
├── app/
│   ├── cli/
│   │   ├── __init__.py
│   │   └── main.py
│   ├── gui/
│   │   ├── src-tauri/
│   │   │   ├── tauri.conf.json
│   │   │   └── src/
│   │   │       └── main.rs
│   │   └── ui/
│   │       ├── App.tsx
│   │       └── i18n/
│   │           ├── en.json
│   │           └── fr.json
│   ├── core/
│   │   ├── autopilot.py
│   │   ├── ingestion/
│   │   │   ├── download.py
│   │   │   ├── scrape.py
│   │   │   └── verify.py
│   │   ├── rag/
│   │   │   ├── index.py
│   │   │   ├── embeddings.py
│   │   │   └── search.py
│   │   ├── policy/
│   │   │   ├── enforcement.py
│   │   │   └── schemas.py
│   │   └── diagnostics/
│   │       ├── self_test.py
│   │       └── export.py
│   ├── services/
│   │   ├── config.py
│   │   ├── scheduler.py
│   │   ├── sandbox.py
│   │   └── updates.py
│   └── data/
│       ├── model_registry.json
│       └── templates/
│           ├── config.toml.j2
│           ├── policy.yaml.j2
│           └── consents.jsonl.j2
├── installers/
│   ├── windows/
│   │   ├── wix/
│   │   └── msix/
│   ├── macos/
│   │   ├── dmg/
│   │   └── notarize.sh
│   └── linux/
│       ├── appimage/
│       ├── deb/
│       ├── rpm/
│       └── flatpak/
├── packaging/
│   ├── pyinstaller/
│   │   ├── watcher.spec
│   │   └── watcher_gui.spec
│   ├── docker/
│   │   └── Dockerfile
│   └── tauri/
│       └── updater.json
├── docs/
│   ├── user/
│   │   ├── quickstart.md
│   │   ├── faq.md
│   │   └── troubleshooting.md
│   ├── legal/
│   │   ├── privacy-policy.md
│   │   ├── terms.md
│   │   ├── model-card.md
│   │   ├── data-card.md
│   │   └── third-party-notices.md
│   ├── dev/
│   │   ├── ci-cd.md
│   │   └── architecture.md
│   └── sbom/
│       └── watcher-cyclonedx.json
├── .github/
│   └── workflows/
│       ├── release.yml
│       ├── docker.yml
│       ├── pages.yml
│       ├── codeql.yml
│       ├── scorecard.yml
│       └── supply-chain.yml
├── mkdocs.yml
└── pyproject.toml
```

## Diagramme d'architecture (texte)
```
[User]
  |-- interacts --> [CLI watcher]
  |                      |
  |                      v
  |                  [Core Services]
  |                      |
  |    [GUI watcher-gui (Tauri)]
  |                      |
  |                      v
  +----> [Config Service] --reads/writes--> ~/.watcher/{config.toml,policy.yaml,consents.jsonl}
                         |
                         v
                [Autopilot Orchestrator]
                         |
        +----------------+----------------+
        |                                 |
        v                                 v
 [Scraper Service]                [RAG Pipeline]
        |                                 |
        v                                 v
[Network Window Manager]     [Ingestion Normaliser]
        |                                 |
        v                                 v
[Sandbox Runtime]          [Embeddings Engine]
        |                                 |
        |                                 v
        |                         [Vector Index (SQLite-VSS/FAISS)]
        |                                 |
        +------------- feeds -------------+
                         |
                         v
                 [Query Engine]
                         |
                         v
                      [Results]

Side channels:
- [Diagnostics & Self-Test] -> generates -> logs.jsonl, diagnostic.zip
- [Updater Service] -> (opt-in) -> release assets/signatures
- [CI/CD] -> builds/signs -> installers, docker images, docs
```

## Flux critiques
1. **Initialisation** : CLI/GUI détecte `~/.watcher/first_run`, déclenche onboarding, génère fichiers de politique, télécharge modèles vérifiés.
2. **Autopilot** : planification `systemd-user`/`LaunchAgent`/`Task Scheduler` appelle le service CLI, qui orchestre `discover → scrape → verify → ingest → reindex` avec contrôle offline.
3. **Recherche** : GUI/CLI appelle API locale `search`, qui utilise embeddings FAISS/SQLite-VSS et renvoie résultats avec métadonnées/score.
4. **Mises à jour** : Workflows GitHub signent et publient packages ; GUI propose l'update via Tauri Updater opt-in.
5. **Sécurité** : Cosign + SLSA garantissent provenance ; sandbox limite les sous-processus ; logs et diagnostics restent locaux.
