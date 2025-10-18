# Watcher Public Release Gap Report

## Résumé exécutif

Cette analyse identifie les écarts prioritaires (P0 à P2) pour transformer Watcher en solution grand public installable en un clic, utilisable hors ligne et sécurisée par défaut. Les priorités reflètent le risque produit/utilisateur et les dépendances techniques.

## Priorités P0 — Bloquant release publique

### Distribution et supply-chain
- **Absence de workflows CI/CD complets** pour compiler, signer et publier sdist/wheel, bundles PyInstaller, et artefacts d'installation multiplateforme.
- **Pas de génération SBOM CycloneDX** ni signatures cosign/SLSA provenance pour les artefacts.
- **Manque d'installeurs GUI** (MSI/MSIX, DMG notarized, AppImage/DEB/RPM/Flatpak) et absence d'automatisation correspondante.
- **Pas de packaging PyPI ni Docker multi-architecture** avec signatures et validations.

### Prêt à l'emploi local
- **Aucun flux de première exécution** générant configuration, consentements signés ou téléchargement vérifié des modèles.
- **Scripts d'entrée `watcher` / `watcher-gui` manquants** dans `pyproject.toml`.
- **Pas d'application GUI desktop** (Tauri) répondant aux exigences d'onboarding, accessibilité et kill-switch.
- **Absence d'autostart multi-OS** et du kill-switch `~/.watcher/disable`.

### Documentation et support utilisateur
- **Pas de documentation grand public** (Quickstart GUI/CLI, FAQ, dépannage, vérification des signatures, politique de confidentialité, CGU/EULA, Model/Data Card, Third-Party Notices).
- **Plan de test et scripts d'auto-diagnostic inexistants**.

### Sécurité et conformité
- **Politique offline par défaut incomplète** (pas de sandbox, fenêtres réseau, allowlists, ni RAG local isolé).
- **Pas de release GitHub orchestrée** (tagging, notes automatisées).

## Priorités P1 — Qualité et sûreté avancées

### Autonomie des collectes
- **Scraping non implémenté** avec respect robots.txt, ETag/If-Modified-Since, throttling, licence, corroboration multi-sources.
- **Pas de pipeline RAG local** (normalisation, chunking, embeddings, index VSS, API export/import).
- **Autopilot absent** (planification, gap analysis, rapport hebdo HTML).

### Sécurité/runtime
- **Pas de sandboxing sous-processus** (cgroups/job objects) ni coupure réseau contrôlée.
- **Zéro instrumentation opt-in pour télémétrie ou mises à jour**.

### Qualité utilisateur
- **Self-tests GUI/CLI manquants** (détection GPU/CPU, mode offline, droits FS).
- **Logs JSON et export ZIP “diagnostic” indisponibles**.
- **Internationalisation FR/EN absente** (pas de ressources i18n).

## Priorités P2 — Écosystème & conformité avancés

- **Chaîne d'installation étendue** (MSIX signé, winget, DMG notarized universel, AppImage/DEB/RPM/Flatpak, Homebrew tap) non définie.
- **Tests automatisés** (Playwright/Cypress, pytest-socket, E2E offline, scrapers) à construire.
- **Couverture ≥85 % et diff-coverage 100 %** non mesurée.
- **Supply-chain checks** (OSSF Scorecard, CodeQL, secret scanning, pip-audit) non activés.
- **Performance budgets** (latence/mémoire) non suivis.
- **Conformité légale** (GDPR export/suppression locales, opt-in) non documentée.

## Recommandations clés
1. **Mettre en place la colonne vertébrale CI/CD** avant tout développement fonctionnel dépendant (release, docker, pages, signatures).
2. **Développer le cœur produit offline-first** : onboarding, policy, RAG local, autopilot basique avec hooks offline.
3. **Construire progressivement l'écosystème d'installation** en automatisant d'abord AppImage/DMG/MSI, puis extensions (winget, Homebrew, Flatpak).
4. **Instaurer une gouvernance sécurité/compliance** : templates SBOM, documents légaux, scripts de vérification.
5. **Documenter largement** pour adoption grand public et support.
