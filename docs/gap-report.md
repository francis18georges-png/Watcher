# Gap Report — Watcher 0.4.0 « IA grand public »

## Résumé exécutif

- **P0 (Livraison vérifiable).** Les workflows Release/Docker/Pages couvrent les exigences de build multi-OS, de signatures cosign et d'attestations SLSA, et la CLI fournit les commandes `watcher init --fully-auto` et `watcher run --offline`. Les actions de vérification côté utilisateur restent peu documentées et il manque une validation intégrale des commandes contractuelles dans la documentation publique.
- **P1 (Autonomie & sûreté).** Les briques de scraping vérifié, de politique réseau/consentement, d'ingestion locale et de pipeline RAG sont implémentées avec tests hors-ligne. L'autopilot remonte désormais les knowledge gaps durant les cycles et les publie dans le rapport hebdomadaire/CLI, et les contrôles supply-chain attendus (CodeQL, secret-scan, pip-audit) sont désormais intégrés dans la CI.
- **P2 (Expérience & distribution).** Aucun binaire Tauri « watcher-gui » n'est livrable, les installeurs Linux ne sont pas signés et aucun manifeste winget/Homebrew/Flatpak externe n'est publié. L'écosystème d'assistance progresse avec `watcher doctor`, mais les guides CLI grand public et la distribution multi-canal restent à finaliser.

## P0 — Livraison vérifiable

| Domaine | Exigence cible | Statut | Constats et écarts |
| --- | --- | --- | --- |
| Release GitHub | Tags `v*` + `workflow_dispatch` → sdist/wheel, PyInstaller Win/mac/Linux, SBOM, checksums signés, SLSA, publication PyPI | ✅ | Le workflow `.github/workflows/release.yml` orchestre les jobs multi-OS, génère SBOM CycloneDX, signe `checksums.txt` avec cosign et produit une attestation SLSA avant de pousser les artefacts sur GitHub Release/PyPI. Aucune documentation utilisateur n'explique encore comment vérifier les signatures téléchargées. |
| Docker multi-arch | Build `linux/amd64,linux/arm64`, SBOM, cosign `verify-attestation` | ✅ | `.github/workflows/docker.yml` construit et pousse l'image GHCR, exécute `imagetools inspect`, signe chaque tag et déclenche `cosign verify-attestation --type slsaprovenance`. Aucun guide CLI n'accompagne les commandes de vérification. |
| Documentation Pages | MkDocs strict + déploiement GitHub Pages | ⚠️ | `deploy-docs.yml` publie bien le site MkDocs. Le guide « Vérification des artefacts » décrit désormais un protocole CLI réel (`sha256sum`, `cosign verify-blob`, `cosign verify-attestation`), mais la page « Quickstart sans commande » reste orientée GUI non livrée, ce qui maintient un écart partiel. |
| CLI prête | `watcher` exposé via `pyproject`, commandes `init --fully-auto` / `run --offline` opérationnelles | ✅ | `pyproject.toml` déclare `watcher = "app.cli:main"`; la CLI fournit `perform_auto_init` et `perform_offline_run`, vérifie les empreintes des modèles et utilise `llama_cpp` en mode déterministe. |
| Première exécution | Génération de `~/.watcher/{config.toml,policy.yaml,consents.jsonl}`, téléchargement par hash | ✅ | `FirstRunConfigurator` détecte le matériel, sélectionne les modèles via `ensure_models`, écrit config/policy/ledger et consigne le consentement initial; `ModelSpec` impose SHA-256 + taille avec reprise de téléchargement. |
| Validation CLI | `watcher run --offline` déterministe | ⚠️ | Le test `tests/test_e2e_offline.py` exécute `python -m app.cli run --offline`, mais la documentation publique n'illustre pas l'utilisation du binaire installé (`watcher run --offline --prompt "Bonjour"`). Ajouter un guide opérateur et une vérification CLI installée est recommandé. |

### Actions P0 recommandées
- Documenter pas-à-pas `pip install -e .`, `watcher init --fully-auto`, `watcher run --offline --prompt "…"`.
- Étendre les tests E2E pour exécuter la console-script `watcher` depuis un environnement virtualenv.

## P1 — Autonomie & sûreté

| Domaine | Exigence cible | Statut | Constats et écarts |
| --- | --- | --- | --- |
| Scraping vérifié | robots.txt, ETag/If-Modified-Since, throttling, UA dédié, dédup/hash, licence | ✅ | `HTTPScraper` gère robots.txt, fenêtres réseau, reprise conditionnelle, extraction Readability/trafilatura, déduplication par hash et détection de licence, tout en conservant un cache local. |
| Politique & kill-switch | Allowlist, fenêtres réseau, budgets, `~/.watcher/disable` | ✅ | Le schéma `Policy` impose `network_windows`, budgets et chemin de kill-switch; la baseline `policy.yaml` fournit allowlist, budgets et kill switch activables. |
| RAG local | Ingest → normalisation → langue → chunking → embeddings → index SQLite-VSS | ✅ | `IngestPipeline` exige ≥2 sources, filtre par licence, stocke `{url,titre,licence,date,hash,score}`; `SimpleVectorStore` encode localement (SentenceTransformers) et persiste dans SQLite, utilisé par `rag.answer_question`. |
| Autopilot | Cycle discover→scrape→verify→ingest→rapport hebdo | ✅ | `AutopilotController` orchestre discovery/scraping/ingestion, applique kill-switch, détecte les knowledge gaps par sujet et les exporte dans `reports/weekly.html`; la CLI expose `watcher autopilot report` pour consulter le chemin du rapport local. |
| Tests hors-ligne | pytest-socket, E2E offline | ✅ | La suite inclut un shim `pytest_socket` qui bloque le réseau par défaut et un test e2e offline déterministe sur le modèle GGUF embarqué, garantissant l'exécution sans dépendance réseau. |
| Supply-chain CI | Scorecard, CodeQL, secret-scan, pip-audit | ✅ | Les workflows dédiés `codeql.yml`, `secret-scan.yml` (Gitleaks + TruffleHog) et `pip-audit.yml` complètent désormais Scorecard/Trivy et couvrent la base de gouvernance supply-chain attendue. |

### Actions P1 recommandées
- Étendre la couverture CodeQL aux composants Rust/Tauri dès l'introduction du workspace GUI.

## P2 — Expérience & distribution

| Domaine | Exigence cible | Statut | Constats et écarts |
| --- | --- | --- | --- |
| GUI Tauri | `watcher-gui` minimale, onboarding 3 étapes, i18n fr/en | ❌ | Aucun projet Tauri n'est présent dans le dépôt; la documentation mentionne un répertoire `src-tauri/` mais aucun code n'est livré. |
| Installeurs signés & canaux | MSI/MSIX signés, DMG notarized, AppImage/DEB/RPM/Flatpak signés + publication winget/Homebrew | ⚠️ | Les scripts génèrent MSI/MSIX (avec signature si secrets fournis) et DMG notarized; les paquets Linux (AppImage/DEB/RPM/Flatpak) sont construits sans signature GPG ni publication winget/Homebrew/Flatpak remote. |
| Support utilisateur | Plan de tests + scripts auto-diagnostic (`watcher doctor`) | ⚠️ | La CLI fournit désormais `watcher doctor` (sortie texte/JSON + export ZIP) pour vérifier config/policy/ledger/modèle/état autopilot et générer un bundle local redacted ; la documentation support et l'intégration dans les installeurs restent à finaliser. |
| Documentation grand public | Guides CLI, vérification artefacts | ⚠️ | Le guide `quickstart-cli.md` documente désormais le flux installé (`watcher init/run/doctor/autopilot report`) et renvoie vers la vérification des artefacts; la documentation GUI reste toutefois incomplète vis-à-vis de l'expérience réellement livrée. |

### Actions P2 recommandées
- Monter un projet Tauri (`watcher-gui`) avec onboarding minimal et intégrer le pipeline de build/signature.
- Ajouter la signature GPG des artefacts Linux, générer les manifestes winget/Homebrew et automatiser leur publication.
- Intégrer `watcher doctor --export` dans les installeurs et documenter la procédure de partage support (quels fichiers transmettre, politique d'anonymisation).
- Compléter la documentation GUI pour qu'elle reflète l'état réel du produit (ou livrer effectivement le parcours graphique décrit).
