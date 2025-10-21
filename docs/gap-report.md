# Gap Report — Watcher 0.4.0 « IA grand public »

## Résumé exécutif

- **P0 (Livraison vérifiable).** Les workflows Release/Docker/Pages couvrent les exigences de build multi-OS, de signatures cosign et d'attestations SLSA, et la CLI fournit les commandes `watcher init --fully-auto` et `watcher run --offline`. Les actions de vérification côté utilisateur restent peu documentées et il manque une validation intégrale des commandes contractuelles dans la documentation publique.
- **P1 (Autonomie & sûreté).** Les briques de scraping vérifié, de politique réseau/consentement, d'ingestion locale et de pipeline RAG sont implémentées avec tests hors-ligne. En revanche, l'autopilot n'expose pas encore de détection active des knowledge gaps et les contrôles supply-chain attendus (CodeQL, secret-scan, pip-audit) ne sont pas en place.
- **P2 (Expérience & distribution).** Aucun binaire Tauri « watcher-gui » n'est livrable, les installeurs Linux ne sont pas signés et aucun manifeste winget/Homebrew/Flatpak externe n'est publié. L'écosystème d'assistance (`watcher doctor`, guide CLI grand public) reste à construire.

## P0 — Livraison vérifiable

| Domaine | Exigence cible | Statut | Constats et écarts |
| --- | --- | --- | --- |
| Release GitHub | Tags `v*` + `workflow_dispatch` → sdist/wheel, PyInstaller Win/mac/Linux, SBOM, checksums signés, SLSA, publication PyPI | ✅ | Le workflow `.github/workflows/release.yml` orchestre les jobs multi-OS, génère SBOM CycloneDX, signe `checksums.txt` avec cosign et produit une attestation SLSA avant de pousser les artefacts sur GitHub Release/PyPI. Aucune documentation utilisateur n'explique encore comment vérifier les signatures téléchargées. |
| Docker multi-arch | Build `linux/amd64,linux/arm64`, SBOM, cosign `verify-attestation` | ✅ | `.github/workflows/docker.yml` construit et pousse l'image GHCR, exécute `imagetools inspect`, signe chaque tag et déclenche `cosign verify-attestation --type slsaprovenance`. Aucun guide CLI n'accompagne les commandes de vérification. |
| Documentation Pages | MkDocs strict + déploiement GitHub Pages | ⚠️ | `deploy-docs.yml` publie bien le site MkDocs, mais les pages « Quickstart sans commande » et « Vérification des artefacts » décrivent une interface graphique fictive et ne mentionnent pas les commandes contractuelles, créant un écart avec l'expérience réelle. |
| CLI prête | `watcher` exposé via `pyproject`, commandes `init --fully-auto` / `run --offline` opérationnelles | ✅ | `pyproject.toml` déclare `watcher = "app.cli:main"`; la CLI fournit `perform_auto_init` et `perform_offline_run`, vérifie les empreintes des modèles et utilise `llama_cpp` en mode déterministe. |
| Première exécution | Génération de `~/.watcher/{config.toml,policy.yaml,consents.jsonl}`, téléchargement par hash | ✅ | `FirstRunConfigurator` détecte le matériel, sélectionne les modèles via `ensure_models`, écrit config/policy/ledger et consigne le consentement initial; `ModelSpec` impose SHA-256 + taille avec reprise de téléchargement. |
| Validation CLI | `watcher run --offline` déterministe | ⚠️ | Le test `tests/test_e2e_offline.py` exécute `python -m app.cli run --offline`, mais la documentation publique n'illustre pas l'utilisation du binaire installé (`watcher run --offline --prompt "Bonjour"`). Ajouter un guide opérateur et une vérification CLI installée est recommandé. |

### Actions P0 recommandées
- Ajouter dans la documentation Pages un tutoriel « Vérifier une release » avec `docker buildx imagetools inspect` et `cosign verify-attestation`.
- Documenter pas-à-pas `pip install -e .`, `watcher init --fully-auto`, `watcher run --offline --prompt "…"`.
- Étendre les tests E2E pour exécuter la console-script `watcher` depuis un environnement virtualenv.

## P1 — Autonomie & sûreté

| Domaine | Exigence cible | Statut | Constats et écarts |
| --- | --- | --- | --- |
| Scraping vérifié | robots.txt, ETag/If-Modified-Since, throttling, UA dédié, dédup/hash, licence | ✅ | `HTTPScraper` gère robots.txt, fenêtres réseau, reprise conditionnelle, extraction Readability/trafilatura, déduplication par hash et détection de licence, tout en conservant un cache local. |
| Politique & kill-switch | Allowlist, fenêtres réseau, budgets, `~/.watcher/disable` | ✅ | Le schéma `Policy` impose `network_windows`, budgets et chemin de kill-switch; la baseline `policy.yaml` fournit allowlist, budgets et kill switch activables. |
| RAG local | Ingest → normalisation → langue → chunking → embeddings → index SQLite-VSS | ✅ | `IngestPipeline` exige ≥2 sources, filtre par licence, stocke `{url,titre,licence,date,hash,score}`; `SimpleVectorStore` encode localement (SentenceTransformers) et persiste dans SQLite, utilisé par `rag.answer_question`. |
| Autopilot | Cycle discover→scrape→verify→ingest→rapport hebdo | ⚠️ | `AutopilotController` orchestre discovery/scraping/ingestion, applique kill-switch et génère `reports/weekly.html`, mais aucun module n'implémente la détection des « knowledge gaps » demandée, ni une diffusion du rapport (CLI/Docs). |
| Tests hors-ligne | pytest-socket, E2E offline | ✅ | La suite inclut un shim `pytest_socket` qui bloque le réseau par défaut et un test e2e offline déterministe sur le modèle GGUF embarqué, garantissant l'exécution sans dépendance réseau. |
| Supply-chain CI | Scorecard, CodeQL, secret-scan, pip-audit | ❌ | Le dépôt dispose d'un job Scorecard, mais aucun workflow CodeQL, secret-scan ou pip-audit n'est défini; les scans vulnérabilité Trivy ne couvrent que l'image Docker. |

### Actions P1 recommandées
- Ajouter un module de détection des knowledge gaps (ex : comparaison topics/policy vs index) avec rapport CLI/HTML.
- Publier le rapport hebdomadaire via CLI (`watcher autopilot report`) et documenter sa consultation.
- Créer des workflows CodeQL (langages Python/Rust/Tauri), secret-scan et pip-audit pour satisfaire la gouvernance supply-chain.

## P2 — Expérience & distribution

| Domaine | Exigence cible | Statut | Constats et écarts |
| --- | --- | --- | --- |
| GUI Tauri | `watcher-gui` minimale, onboarding 3 étapes, i18n fr/en | ❌ | Aucun projet Tauri n'est présent dans le dépôt; la documentation mentionne un répertoire `src-tauri/` mais aucun code n'est livré. |
| Installeurs signés & canaux | MSI/MSIX signés, DMG notarized, AppImage/DEB/RPM/Flatpak signés + publication winget/Homebrew | ⚠️ | Les scripts génèrent MSI/MSIX (avec signature si secrets fournis) et DMG notarized; les paquets Linux (AppImage/DEB/RPM/Flatpak) sont construits sans signature GPG ni publication winget/Homebrew/Flatpak remote. |
| Support utilisateur | Plan de tests + scripts auto-diagnostic (`watcher doctor`) | ❌ | Le plan de tests existe, mais aucun utilitaire `watcher doctor` ou bundle d'autodiagnostic n'est distribué; la documentation publique reste centrée sur une UI inexistante. |
| Documentation grand public | Guides CLI, vérification artefacts | ❌ | Les guides actuels décrivent des assistants graphiques fictifs, sans instructions CLI concrètes pour l'installation, l'initialisation ou la vérification des signatures. |

### Actions P2 recommandées
- Monter un projet Tauri (`watcher-gui`) avec onboarding minimal et intégrer le pipeline de build/signature.
- Ajouter la signature GPG des artefacts Linux, générer les manifestes winget/Homebrew et automatiser leur publication.
- Concevoir `watcher doctor` (collecte anonymisée des diagnostics, vérification des hash modèles) et intégrer le script dans les installeurs.
- Réécrire les guides utilisateur autour du flux CLI réel (installation, vérification des artefacts, mode offline).
