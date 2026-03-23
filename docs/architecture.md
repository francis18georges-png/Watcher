# Architecture Watcher

Cette page distingue explicitement :

- **l'état actuel** : ce qui est observable dans le dépôt aujourd'hui ;
- **la cible future** : ce que le projet vise, sans le présenter comme déjà livré.

## État actuel

Watcher est aujourd'hui un dépôt Python local-first centré sur une CLI, une politique runtime explicite et une chaîne d'ingestion locale.

### Arborescence réelle

```text
app/
├── core/        # noyau applicatif, bootstrap, configuration, sandbox, mémoire SQLite, logging
├── autopilot/   # scheduler, controller, discovery, reporting
├── data/        # jeux de données, scraping/data helpers, préparation
├── policy/      # schéma policy.yaml, manager, ledger de consentement
├── scrapers/    # HTTP, sitemap, GitHub, règles robots.txt
├── ingest/      # pipeline de validation et ingestion documentaire
├── embeddings/  # stockage/vectorisation locale
├── llm/         # clients et intégrations de modèles locaux
├── tools/       # plugins, scaffolding, utilitaires
└── ui/          # interface locale et point d'entrée graphique
```

### Rôle des modules

- **`app/core`** : cœur transverse du projet. On y trouve notamment le bootstrap, la configuration, le sandboxing, des composants runtime, du logging et une mémoire SQLite historique.
- **`app/autopilot`** : applique la policy runtime pendant les cycles autonomes. Ce sous-système décide le passage online/offline, gère les budgets, la discovery et l'orchestration de collecte.
- **`app/data`** : contient surtout des données, scripts et helpers de préparation/collecte. Ce n'est pas la couche métier principale.
- **`app/policy`** : source de vérité pour `policy.yaml`, la validation du schéma, l'allowlist, le kill-switch et le ledger de consentement.
- **`app/scrapers`** : couche réseau contrôlée, avec respect de `robots.txt`, throttling, cache et extraction.
- **`app/ingest`** : transforme les documents collectés en entrées validées et ingérables. Cette couche porte désormais un registre de sources minimal, les états `raw`, `validated`, `promoted`, ainsi que les motifs de validation/promotion et le comptage de corroboration.
- **`app/embeddings`** : gère la partie vector store et l'indexation locale associée.
- **`app/llm`** : encapsule les interactions avec les backends de modèles.
- **`app/tools`** : expose des utilitaires de productivité et d'extension, notamment autour des plugins.
- **`app/ui`** : interface locale actuelle.

### Flux actuel

1. La CLI charge la configuration et la policy locale.
2. `app/policy` valide les contraintes runtime.
3. `app/autopilot/scheduler.py` décide si le réseau peut être activé.
4. `app/autopilot/controller.py` orchestre `discover -> scrape -> verify -> evaluate -> promote/reject -> ingest`.
5. `app/scrapers` collecte sous contraintes.
6. `app/ingest/source_registry.py` journalise la progression des sources et de la connaissance.
7. `app/ingest` et `app/embeddings` valident puis indexent localement.

### Slice Phase 1 déjà en place

Le dépôt contient maintenant un premier slice réel de la boucle documentaire contrôlée :

- **Source Registry** : registre JSON minimal explicite (`source-registry.json`) piloté par `app/ingest/source_registry.py`.
- **États de connaissance** : `raw`, `validated`, `promoted`.
- **Traçabilité minimale explicite** : `source`, `source_type`, `confidence`, `freshness_at`, `licence`, `status`, `status_reason`, `corroborating_sources`, `evaluation_status`, `evaluation_score`, `evaluation_reason`.
- **Branchement incrémental** : la discovery et le contrôleur mettent à jour le registre sans remplacer `app/data`, `app/scrapers` ni `app/ingest`.

### GitHub ciblé actuel

Le dépôt supporte désormais une collecte GitHub prudente et bornée pour la spécialisation programmation :

- **oui** : métadonnées de dépôt, dernière release, changelogs standards, documentation ciblée, fichiers de référence explicitement autorisés ;
- **non** : scraping GitHub large, exploration récursive du dépôt, collecte d'issues/PR/commits ;
- **promotion** : toute donnée GitHub reste soumise à la corroboration et au pipeline normal `raw -> validated -> promoted`.

### Ce qui n'est plus affirmé comme état actuel

- Il n'existe pas de couche centrale `app.agents` dans l'arborescence réelle.
- La mémoire vectorielle ne doit pas être décrite uniquement via `app.core.memory`.
  L'état réel est mixte :
  `app/core/memory.py` couvre une mémoire SQLite/historique, tandis que la chaîne d'ingestion et d'embeddings repose aujourd'hui surtout sur `app/ingest` et `app/embeddings`.

## Cible future

La cible raisonnable du projet est de clarifier et stabiliser les frontières entre sous-systèmes, sans gonfler la promesse publique.

- **`app/core`** devrait rester la couche transverse commune, pas une zone fourre-tout.
- **`app/data`** devrait rester orienté datasets/préparation, avec moins de logique applicative.
- **`app/autopilot`** devrait devenir le point unique des cycles autonomes observables et auditables.
- **`app/ingest` + `app/embeddings`** devraient porter de façon plus lisible toute la chaîne documentaire locale.
- **`app/ui`** peut évoluer, mais la CLI reste aujourd'hui la surface la plus stable.
- **Documentation publique et artefacts** : la cible est d'aligner automatiquement toute promesse publique avec des éléments réellement publiés et vérifiables.

## Règle de vérité documentaire

Une affirmation peut être décrite comme **état actuel** seulement si elle est :

1. visible dans le code du dépôt ;
2. cohérente avec l'arborescence réelle ;
3. vérifiable localement ou par la CI.

Sinon, elle doit être formulée comme **cible future** ou **travail en cours**.

## Mini-checklist publique

Avant de présenter une fonctionnalité comme publique ou disponible :

- vérifier qu'elle existe bien dans `app/` ;
- vérifier que le README ne la présente pas comme déjà publiée si ce n'est pas le cas ;
- vérifier qu'un artefact, une page ou une commande locale permet réellement de la constater.
