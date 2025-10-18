# Gap Report — Watcher « grand public »

Ce rapport synthétise les écarts entre l'état actuel du dépôt et la mission « Watcher grand public ». Les priorités suivent la nomenclature P0 (bloquant), P1 (majeur), P2 (amélioration). Chaque écart documente l'impact sur l'utilisateur final et les actions correctives recommandées.

## Résumé exécutif

- L'infrastructure de release couvre désormais Linux, Windows et macOS, publie PyPI via Trusted Publishing et génère les installeurs multi-OS attendus (MSI/MSIX, DMG notarizable, AppImage/DEB/RPM/Flatpak).
- Aucun client graphique ni installeur multi-OS n'est disponible : l'expérience reste réservée aux profils techniques capables d'utiliser la CLI et des archives brutes.
- Les engagements sûreté/autonomie (collecte vérifiée, sandbox, autodiagnostic, i18n) sont amorcés dans le code existant mais nécessitent des compléments fonctionnels et des tests pour atteindre un niveau « grand public ».

## P0 — Distribution immédiate et onboarding

| Exigence « grand public » | Couverture actuelle | Écart critique | Action recommandée |
| --- | --- | --- | --- |
| Release tag `v*` → build multi-OS + publication PyPI | `.github/workflows/release.yml` orchestre des jobs Linux, Windows, macOS (x86_64/arm64), publie sdist/wheel sur PyPI via OIDC et regroupe SBOM + attestations | Validation manuelle de la notarisation/signature à réaliser à chaque release et surveillance des runtimes PyInstaller | Ajouter des tests fumée post-release (Watchman, codesign --verify) et automatiser les contrôles `cosign verify-blob` des checksums |
| Installeurs desktop (MSI/MSIX, DMG notarized, AppImage/DEB/RPM/Flatpak) | Scripts `scripts/package_windows.py` et `scripts/package_linux.py` génèrent MSI/MSIX, DMG, AppImage, DEB, RPM, Flatpak à partir du bundle PyInstaller | Les manifestes GUI restent absents et les scripts supposent des métadonnées par défaut (icônes, descriptions) → expérience perfectible | Intégrer des ressources UI finales (icônes, EULA, privacy) et ajouter des tests d'installation automatisés pour chaque format |
| Interface graphique « watcher-gui » avec onboarding 3 étapes | Aucun projet Tauri/Electron, pas de répertoire `watcher-gui`, pas de commandes `watcher-gui` exposées | L'utilisateur ne dispose que de la CLI → friction majeure pour un usage grand public | Initialiser une application Tauri + React avec flux d'accueil (consentement, choix modèle, dossier données) et synchroniser avec la CLI |
| Mode offline par défaut avec téléchargement vérifié des modèles | La CLI `watcher init --auto` installe un modèle démo local mais ne vérifie pas de catalogue officiel ni de hashing externe | Les modèles tierce-partie ne sont pas vérifiés par hash/taille côté utilisateur → risque d'intégrité | Définir un registre de modèles (hash/size) consommé par la CLI et la GUI, avec reprise de téléchargement et double vérification |
| Autostart utilisateur sans commande (Task Scheduler / systemd-user / LaunchAgent) | Pas de scripts ni services fournis ; documentation limitée à la CLI | Aucun démarrage automatique → les utilisateurs non techniques ne peuvent activer l'agent en arrière-plan | Ajouter générateurs de jobs (PowerShell, systemd user service, LaunchAgent plist) créés lors de `watcher init --fully-auto` |
| Documentation publique orientée GUI (Quickstart, FAQ, Dépannage, Vérification) | Documentation actuelle centrée CLI (`docs/quickstart-sans-commande.md`, `docs/depannage.md`) ; aucun guide GUI ni lien depuis README | Les nouveaux utilisateurs ne trouvent pas de parcours graphique, ni instructions pour vérifier signatures | Écrire un guide Quickstart GUI, FAQ et procédures de vérification adaptées aux installeurs ; relier ces pages depuis README et le site MkDocs |
| Cadre légal (Privacy Policy, Terms, EULA, Model Card, Third-Party Notices) | Aucun document juridique ni NOTICE généré ; SBOM CycloneDX seulement | Incompatibilité avec une distribution grand public (absence de politique de confidentialité et mentions légales) | Rédiger les documents requis, automatiser la génération NOTICE/SBOM → NOTICE, intégrer au pipeline de release et aux installeurs |
| Docker multi-arch GHCR signé + gate de vérification | Workflow `docker.yml` pousse linux/amd64,arm64 avec SBOM et attestation SLSA ; un job `verify-attestation` applique `cosign verify-attestation --type slsaprovenance` | Aucun suivi automatique des digests dans la doc publique ; nécessite un HOWTO signatures côté utilisateur final | Documenter la commande de vérification et exposer les digests attestés dans la release + documentation |

## Validation PR #446 « grand public gap analysis »

Le contenu introduit par la PR #446 reste aligné avec l'état du code :

- Les exigences d'initialisation autonome et offline reposent sur `FirstRunConfigurator` qui crée les sentinelles `~/.watcher/first_run`, la configuration TOML et le ledger de consentement signé. 【F:app/core/first_run.py†L1-L164】
- La matrice de release y décrite a été prolongée côté CI pour couvrir macOS (arm64/x64) et publier sur PyPI, ce qui répond aux écarts identifiés dans le rapport. 【F:.github/workflows/release.yml†L1-L260】
- Le pipeline Docker inclut désormais la vérification d'attestation exigée par la mission grand public, cohérente avec la recommandation initiale de la PR. 【F:.github/workflows/docker.yml†L1-L170】

## P1 — Autonomie, sûreté et qualité opérationnelle

| Exigence | Couverture actuelle | Lacune principale | Suivi |
| --- | --- | --- | --- |
| Scraping vérifié (robots, ETag, throttling, licences, corroboration ≥2 sources) | Module `app/scrapers/http.py` gère robots.txt et cache local ; pas de validation licence/corroboration ni scoring de confiance | Risque d'ingérer des sources incompatibles/licence propriétaire sans double vérification | Étendre les scrapers pour extraire licence, implémenter un pipeline de corroboration et rejeter les sources non conformes |
| RAG local avec métadonnées complètes + export/import | `SimpleVectorStore` stocke embeddings localement mais ne capture pas licence/hash ni mécanismes d'export/import | Manque d'audit trail et d'opérations de sauvegarde/restauration pour partage/diagnostic | Élargir le schéma pour stocker {url,titre,licence,date,hash,score}, ajouter commandes CLI/GUI `index export/import` |
| Autopilot discover→scrape→verify→ingest→reindex + rapports hebdo | Scheduler existant gère la priorité de sujets (`TopicScore`) mais pas de boucle complète ni génération de rapports HTML | Les utilisateurs ne reçoivent pas de synthèse hebdomadaire ni de traçabilité des rejets | Implémenter une pipeline orchestrée avec production de rapports (HTML + JSON) déposés dans `~/.watcher/reports/` |
| Sécurité runtime (sandbox LLM, FS confiné, réseau OFF par défaut) | `app/core/sandbox.py` fournit une base de sandbox mais pas d'intégration cgroups/Job Objects ; politique réseau via fichiers statiques | Isolation incomplète (pas de confinement OS spécifique), risque d'exposition réseau | Intégrer cgroups v2 (Linux), Job Objects (Windows), App Sandbox (macOS) et enforceur réseau dynamique aligné sur `policy.yaml` |
| Consentement explicite + ledger signé | `watcher init` crée policy/config mais n'enregistre pas les consentements avec signature horodatée | Non-conformité réglementaire (pas de trace de consentement ni révocation) | Implémenter `consents.jsonl` signé, bouton GUI pour retirer/accorder consentements, vérification lors du démarrage |
| Updater opt-in respectant offline | Aucun mécanisme de mise à jour (ni CLI ni GUI) | Les utilisateurs doivent re-télécharger manuellement chaque version | Activer updater Tauri (ou équivalent) avec canal opt-in, vérification de signatures, compatibilité offline |

## P2 — Expérience et écosystème

| Exigence | Couverture actuelle | Opportunité | Prochaines étapes |
| --- | --- | --- | --- |
| Auto-diagnostic CLI/GUI (GPU, AVX/NEON, permissions, réseau) | Pas de commande dédiée ; tests ponctuels dans `tests/` | Support difficile (pas de rapport d'état prêt à partager) | Ajouter `watcher doctor` (CLI) et panneau GUI « Diagnostics » générant un ZIP exportable |
| Journalisation et support utilisateur | Logs locaux textuels, pas de packaging ZIP ni bouton « Envoyer au support » | Assistance post-déploiement compliquée | Normaliser la journalisation JSON + export ZIP chiffré volontaire |
| Internationalisation fr/en (accessibilité AA) | CLI/documents majoritairement en français ; pas de fichiers de locales ni support clavier GUI | Public non francophone exclu | Intégrer `react-i18next` (GUI), catalogues YAML, tests d'accessibilité (axe-core) |
| Tests et gates (pytest-socket, Playwright/Cypress, diff-coverage) | CI actuelle (`ci.yml`) couvre lint/tests Python mais pas les scénarios offline ni tests E2E GUI | Qualité incertaine sur les parcours critiques grand public | Étendre la CI avec pytest-socket, suites E2E offline, tests Playwright, diff-coverage 100 % |
| Supply-chain (Scorecard, CodeQL, secret-scan, pip-audit) | `ci.yml` déclenche Scorecard et sécurité basique mais pas CodeQL/pip-audit obligatoires | Risque d'exposition supply-chain non détectée | Ajouter jobs CodeQL, pip-audit, dépendances signées |
| Distribution écosystème (winget, Homebrew, Flatpak) | Aucun manifeste pour winget/Homebrew/Flatpak | Découvreabilité limitée | Générer manifestes automatiquement lors des releases |

## Conclusion

La base CLI actuelle fournit un socle local-first et certaines primitives de sécurité (mode offline, politique réseau, signatures). Pour atteindre l'objectif « grand public », Watcher doit prioriser l'industrialisation de la distribution (release multi-OS, GUI Tauri/Electron, installeurs signés) avant d'étendre les modules d'autonomie et de conformité. Une feuille de route incrémentale peut suivre l'ordre P0 → P1 → P2 ci-dessus pour livrer rapidement une version installable en un clic, sûre et respectueuse des contraintes offline.
