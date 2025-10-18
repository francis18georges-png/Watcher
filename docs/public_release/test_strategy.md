# Plan de tests Watcher (CLI & GUI)

## Objectifs
Garantir une expérience hors ligne fiable, sécurisée et cohérente sur Windows, macOS et Linux pour la version grand public. Les tests couvrent fonctionnalités cœur, distribution, sécurité supply-chain et conformité.

## Stratégie générale
- **Pyramide de tests** : unitaires (core, policy, ingestion) → intégration (RAG, sandbox, autopilot) → E2E (CLI/GUI) → smoke post-install.
- **Automatisation** : GitHub Actions (matrix OS/arch), exécution locale via `nox`/`tox`, scénarios GUI pilotés par Playwright.
- **Isolation offline** : utilisation de `pytest-socket` pour interdire le réseau sauf fenêtres explicitement mockées.

## Suites de tests

### 1. Tests unitaires (pytest)
- `tests/core/test_policy.py` : génération policy, validation allowlists, kill-switch.
- `tests/core/test_ingestion.py` : normalisation, chunking, déduplication hash, validation licence.
- `tests/core/test_rag.py` : index SQLite-VSS/FAISS, recherche par similarité, métadonnées.
- `tests/services/test_config.py` : création `~/.watcher` (config, consents) et reprise.
- `tests/services/test_sandbox.py` : confinement FS, interdiction réseau hors fenêtres.

### 2. Tests d'intégration
- `tests/integration/test_first_run.py` : exécution `watcher init --fully-auto` crée ressources, télécharge modèles mockés par hash.
- `tests/integration/test_autopilot_cycle.py` : simulateur orchestrant `discover→scrape→verify→ingest→reindex` avec fixtures.
- `tests/integration/test_diagnostics.py` : génération logs JSON, export ZIP.

### 3. Tests E2E CLI
- `tests/e2e/test_offline_cli.py` : `watcher run --offline --prompt "Bonjour"` renvoie réponse basée sur index local.
- `tests/e2e/test_update_opt_in.py` : vérifie absence de requêtes réseau sans consentement, simulateur d'update Tauri.

### 4. Tests E2E GUI (Playwright)
- `tests/gui/test_onboarding.spec.ts` : parcours onboarding 3 étapes (policy, modèle, dossier données).
- `tests/gui/test_autopilot_toggle.spec.ts` : activation/désactivation autopilot + kill-switch.
- `tests/gui/test_search.spec.ts` : requête, affichage résultats, filtres source/licence.

### 5. Tests de distribution & supply-chain
- `tests/release/test_pyinstaller.py` : validation contenus bundles PyInstaller, présence SBOM, cosign signature.
- `tests/release/test_installers.py` : smoke install MSI/DMG/AppImage/DEB/RPM/Flatpak dans environnements CI (WIX, notarytool, docker buildx).
- `tests/release/test_docker_image.py` : `docker run` offline, vérification provenance SLSA, cosign verify.
- `tests/release/test_docs.py` : build `mkdocs`, validation liens et ressources.

### 6. Diagnostics & auto-tests
- Script `scripts/self_check.py` exécuté par GUI/CLI :
  - Détecte GPU/CPU (AVX/NEON), droits écriture `~/.watcher`, capacité réseau.
  - Vérifie intégrité modèles (hash + taille).
  - Produit `diagnostic.json` + archive `diagnostic.zip` compressant logs/config anonymisés.
- Tests `tests/diagnostics/test_self_check.py` assurent couverture.

## Matrice de plateformes
| Suite | Windows (x64) | Windows (arm64) | macOS (x64) | macOS (arm64) | Linux (x64) | Linux (arm64) |
|-------|---------------|-----------------|-------------|---------------|-------------|----------------|
| Unitaires | ✅ | ✅ (emulé) | ✅ | ✅ | ✅ | ✅ |
| Intégration | ✅ | ⚠️ (cross-build) | ✅ | ✅ | ✅ | ✅ |
| CLI E2E | ✅ | ⚠️ (emulé) | ✅ | ✅ | ✅ | ✅ |
| GUI E2E | ✅ | ⚠️ (emulé) | ✅ | ✅ | ✅ | ✅ |
| Distribution | ✅ | ⚠️ (build croisé) | ✅ | ✅ | ✅ | ✅ |
| Diagnostics | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

## Intégration CI/CD
- `release.yml` : déclenche sur tag `v*`, build sdist/wheel, PyInstaller, générer SBOM, signer via cosign, publier release + PyPI.
- `docker.yml` : buildx multi-arch, cosign, SLSA provenance, gate `imagetools inspect`.
- `pages.yml` : build `mkdocs`, publier sur GitHub Pages.
- `quality.yml` : pytest + coverage (≥85 %), diff-cover 100 %, CodeQL, Scorecard, secret scan, pip-audit.
- `gui.yml` : Playwright matrix OS.

## Exigences de validation finale
1. **Commandes obligatoires** :
   - `pip install -e .`
   - `watcher init --fully-auto`
   - `watcher run --offline --prompt "Bonjour"`
   - `watcher-gui`
   - `git tag -a v0.5.0 -m "Public release" && git push origin v0.5.0`
   - `cosign verify-attestation --type slsaprovenance ghcr.io/<owner>/watcher:latest`
2. **Critères d'acceptation** :
   - Installeurs signés disponibles et testés.
   - GUI opérationnelle offline, sans pop-ups répétitives.
   - Release signée (SBOM + SLSA), image GHCR multi-arch signée.
   - Docs grand public publiées et vérifiables.

## Suivi et reporting
- Rapports Allure/Playwright HTML uploadés en artefacts GitHub Actions.
- Badge couverture et Scorecard dans README.
- Rapport hebdomadaire autopilot accessible depuis GUI (HTML statique).
