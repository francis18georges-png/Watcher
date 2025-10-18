# Gap Report Watcher

Ce rapport recense les écarts entre l'état actuel du dépôt et la mission « Watcher local-first ». Les priorités suivent la nomenclature P0 (bloquant), P1 (majeur), P2 (amélioration).

## P0 — Publication, installation, exécution

- **Release GitHub incomplète** : la chaîne de construction ne valide pas systématiquement les métadonnées reproductibles ni la signature des artefacts globaux ; l'usage de PyInstaller n'est pas vérifié côté Windows et Linux avec horodatage déterministe.
- **Images Docker multi-arch** : l'ancien workflow ne gérait pas le digest partagé ni la provenance SLSA pour chaque build multi-architecture.
- **Documentation** : l'installation des dépendances MkDocs n'était pas stabilisée via un fichier `docs/requirements.txt`, empêchant un déploiement reproductible sur GitHub Pages.

## P1 — Fonctionnalités IA locales

- **Initialisation hors-ligne** : la CLI ne gère qu'un scénario auto (`--auto`) alors que la mission réclame `--fully-auto` avec sélection matérielle et ledger de consentement.
- **Pipeline d'autonomie** : les modules de crawl, d'indexation vectorielle et de planification ne couvrent pas les politiques domain-scope (robots.txt, throttling, licences) décrites dans `docs/autonomy_architecture.md`.
- **Scheduler** : l'orchestrateur interne ne pilote pas encore les cycles `fetch→parse→quality→store→embed→index` sous contrainte `policy.yaml`.

## P2 — Observabilité et sécurité

- **Journalisation structurée** : absence d'un format JSON centralisé et d'un rapport hebdomadaire HTML automatisé.
- **Sandbox** : le processus d'exécution n'applique pas encore cgroups/Job Objects pour isoler le moteur LLM.
- **Consentement** : le ledger signé n'est pas implémenté ; la CLI n'empêche pas les consentements répétés.

Chaque écart est couvert par le plan d'architecture et le plan de tests ci-dessous pour guider les itérations futures.
