# Gap Report — Watcher « IA grand public »

## Résumé exécutif

- **P0 (Livraison vérifiable).** Les workflows GitHub Actions construisent et signent les artefacts principaux (sdist/wheel, exécutables PyInstaller, images Docker multi-arch) et déclenchent Trusted Publishing, mais il reste à aligner le build Python sur la pipeline `nox -s build` exigée par la mission et à documenter la vérification utilisateur dans la documentation publique.
- **P1 (Autonomie sûre).** Les briques de collecte vérifiée, d'ingestion locale et de pilotage autonome sont présentes dans le code et couvertes par des tests unitaires, mais la surveillance supply-chain manque encore d'une exécution CodeQL dédiée et la documentation utilisateur n'explique pas comment exploiter les rapports hebdomadaires.
- **P2 (Expérience & écosystème).** L'ensemble de la documentation oriente toujours vers une interface graphique inexistante et ne couvre ni la prise en main CLI ni les canaux de distribution communautaires (winget/Homebrew). Une refonte éditoriale reste nécessaire pour refléter l'expérience réelle.

## P0 — Livraison vérifiable

### Release GitHub

**État actuel.** Le workflow `.github/workflows/release.yml` déclenche une matrice `ubuntu-24.04` / `windows-2022` / `macos-14` avec Python 3.12, construit la sdist et la wheel via `python -m build`, génère les bundles PyInstaller/DMG/AppImage/DEB/RPM/Flatpak, publie un fichier de checksums signé (`cosign sign-blob`) et produit une attestation SLSA pour `checksums.txt` avant de créer la release GitHub et de pousser sur PyPI via OIDC.【F:.github/workflows/release.yml†L1-L310】【F:.github/workflows/release.yml†L312-L400】

**Écarts.** Le cahier des charges impose un enchaînement `pip install -r requirements-dev.txt && nox -s build`, alors que le workflow contourne Nox et appelle directement `python -m build` et les scripts PyInstaller personnalisés (`scripts/package_linux.py`, `scripts/package_windows.py`).【F:.github/workflows/release.yml†L70-L210】 Harmoniser le pipeline avec `nox -s build` assurerait que les mêmes contrôles s'appliquent localement et en CI.

### Docker multi-arch + provenance

**État actuel.** Le workflow `.github/workflows/docker.yml` configure QEMU/Buildx, pousse une image `linux/amd64,linux/arm64` sur GHCR, extrait le digest, appelle `docker buildx imagetools inspect` et déclenche `cosign verify-attestation --type slsaprovenance` après génération de l'attestation SLSA v1 `generator_container_slsa3`.【F:.github/workflows/docker.yml†L1-L170】

**Écarts.** Les digests et commandes de vérification ne sont pas relayés dans la documentation publique : les guides `quickstart-sans-commande.md` et `verifier-artefacts.md` présupposent une interface graphique et ne fournissent aucun exemple CLI pour `cosign`/`imagetools`。【F:docs/quickstart-sans-commande.md†L1-L60】【F:docs/verifier-artefacts.md†L1-L32】 Il faut ajouter un guide opérationnel aligné sur les commandes attendues (`docker buildx imagetools inspect …`, `cosign verify-attestation …`).

### Documentation publique

**État actuel.** Le déploiement MkDocs via `.github/workflows/deploy-docs.yml` publie automatiquement le site GitHub Pages en exécutant `mkdocs build --strict` et en déployant l'artefact `site/` sur l'environnement `github-pages`.【F:.github/workflows/deploy-docs.yml†L1-L48】

**Écarts.** Les contenus clefs (« Quickstart sans commande », « Vérification des artefacts ») décrivent des écrans inexistants (widgets GUI, boutons « Nouvelle vérification ») et ne mentionnent pas les commandes `watcher init --fully-auto`, `watcher run --offline`, ni les contrôles de signatures attendus par la mission.【F:docs/quickstart-sans-commande.md†L1-L40】【F:docs/verifier-artefacts.md†L1-L32】 Une réécriture orientée CLI est indispensable pour rendre la documentation publiable.

### CLI offline prête à l'emploi

**État actuel.** La commande `watcher init --fully-auto` déclenche désormais `FirstRunConfigurator`, crée `~/.watcher/{config.toml,policy.yaml,consents.jsonl}` et télécharge les modèles déclarés avec vérification SHA-256 avant d'annoncer l'emplacement des fichiers au terminal.【F:app/cli.py†L114-L154】 Le mode `watcher run --offline` lit la configuration `llm`/`model`, vérifie l'empreinte du modèle (avec reprise via le bundle embarqué) puis exécute `llama_cpp.Llama` en seed déterministe.【F:app/cli.py†L196-L274】

**Écarts.** Aucun test d'intégration n'exécute la séquence demandée (`watcher init --fully-auto` suivi de `watcher run --offline --prompt …`). Les tests d'autostart couvrent encore explicitement le flag `--auto` historique et la configuration minimale.【F:tests/test_first_run_autostart.py†L91-L113】 Il faut ajouter un scénario e2e spécifique pour garantir la compatibilité Python ≥ 3.12 et l'exécution offline sans manual tweaking.

## P1 — Autonomie sûre

- **Scraping vérifié.** `HTTPScraper` gère robots.txt, throttling, ETag/If-Modified-Since et calcule un hachage de contenu pour de-duplication.【F:app/scrapers/http.py†L24-L188】
- **Ingestion locale.** `IngestPipeline` exige au moins deux sources distinctes, filtre par licence et stocke les métadonnées `{url,title,licence,hash,score,date}` dans la base vectorielle locale.【F:app/ingest/pipeline.py†L1-L110】
- **Autopilot.** `AutopilotController` applique le kill-switch, la consent ledger, la corroboration et produit un rapport hebdomadaire HTML via `ReportGenerator`.【F:app/autopilot/controller.py†L300-L420】

**Écarts.** La mission exige CodeQL et un rapport hebdomadaire communiqué aux opérateurs. Aucun workflow CodeQL n'est présent dans `.github/workflows/`, et les tests/documentations n'exploitent pas le rapport `reports/weekly.html` généré par l'autopilote.【F:.github/workflows†L1-L8】【F:app/autopilot/controller.py†L318-L386】 Il faut ajouter un workflow CodeQL dédié et documenter la consultation hebdomadaire (ou exposer un lien CLI/Docs).

## P2 — Expérience & écosystème

- **Documentation réaliste.** Les pages Quickstart et Vérification décrivent toujours des interactions GUI fictives, générant une dissonance pour les utilisateurs CLI.【F:docs/quickstart-sans-commande.md†L1-L60】【F:docs/verifier-artefacts.md†L1-L32】
- **Distribution écosystème.** Aucun manifeste winget/Homebrew/Flatpak supplémentaire n'est produit en sortie de release malgré la fabrication des paquets correspondants.【F:.github/workflows/release.yml†L128-L210】
- **Support utilisateur.** Pas de commande `watcher doctor` ni de packaging automatique des journaux mentionnés dans la documentation.

Ces écarts P2 peuvent être traités après la mise en conformité P0/P1 pour livrer une expérience réellement « grand public ».
