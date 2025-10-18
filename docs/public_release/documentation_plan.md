# Plan de documentation publique Watcher

## Objectifs
Fournir un portail documentaire grand public (GUI + CLI) accessible via GitHub Pages/MkDocs, avec contenus légaux, guides utilisateur et références techniques.

## Structure MkDocs proposée
- `docs/index.md` : page d'accueil avec promesse produit, téléchargement installeurs (Win/macOS/Linux) et vérification de signature.
- `docs/user/quickstart.md` : installation CLI & GUI, première exécution offline, onboarding screenshot, kill-switch.
- `docs/user/gui.md` : navigation interface, autopilot, recherche, export.
- `docs/user/cli.md` : commandes principales (`init`, `run`, `diagnostic`, `autopilot`), exemples offline.
- `docs/user/troubleshooting.md` : erreurs courantes, scripts `self_check`, collecte logs.
- `docs/user/faq.md` : privacy, offline, mises à jour, licences.
- `docs/security/verifying-signatures.md` : checksums, cosign, provenance SLSA, comparaison hash modèles.
- `docs/security/offline-mode.md` : politiques réseau, allowlists, sandboxing.
- `docs/legal/privacy-policy.md` & `docs/legal/terms.md` : conformité GDPR, opt-in updates.
- `docs/legal/model-card.md` & `docs/legal/data-card.md` : description modèle + données.
- `docs/legal/third-party-notices.md` : dépendances extraites SBOM.
- `docs/dev/ci-cd.md` : workflows release, docker, pages, quality.
- `docs/dev/build-from-source.md` : instructions PyPI/Docker/Tauri.

## Processus de production
1. **Collecte contenu** : interviews produit, audit juridique, inventaire dépendances (SBOM).
2. **Rédaction** : prioriser Quickstart, FAQ, Troubleshooting, vérification signatures.
3. **Traduction** : FR/EN via dossiers `docs/i18n/{fr,en}/LC_MESSAGES` (sphinx-intl ou mkdocs-static-i18n).
4. **Validation** : revue légale, tests reproduction Quickstart (non techniques), QA accessibilité (contraste, clavier).
5. **Publication** : workflow `pages.yml` build MkDocs + `mkdocs gh-deploy` via `actions/deploy-pages`.

## Contenu légal à produire
- **Privacy Policy** : collecte locale, absence de télémétrie par défaut, gestion consentements.
- **Terms/EULA** : licence logiciel, limites responsabilité, interdiction revente modèles.
- **Model Card** : capacités/limitations, risques biais, exigences hardware.
- **Data Card** : sources, licences, actualisation, pipeline curatif.
- **Third-Party Notices** : généré depuis SBOM CycloneDX (`cyclonedx-py` + `pip-licenses`).

## Guides signature & provenance
- Tutoriel `cosign verify` (images Docker, installeurs via `cosign verify-blob`).
- Validation checksums `sha256sum` + `openssl dgst`.
- Vérification SLSA provenance (`cosign verify-attestation --type slsaprovenance`).
- Intégration liens directs Release notes.

## Accessibilité & UX
- Captures d'écran GUI (mode clair/sombre) avec descriptions textuelles.
- Sections "Avant de commencer" résumant prérequis hardware/software.
- Tableaux comparatifs des modèles supportés, consommation mémoire.

## Maintenance
- Ajout d'un script `scripts/update_docs_index.py` pour valider que tous les installeurs listés existent dans la dernière release.
- Revue trimestrielle des politiques (privacy/terms) et mise à jour SBOM.
