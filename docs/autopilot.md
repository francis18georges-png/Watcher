# Autopilote sans intervention

Ce document décrit l'exécution autonome de Watcher après la phase `watcher init --fully-auto`. L'objectif est de garantir une collecte
et une ingestion 100 % locales, gouvernées par la politique `policy.yaml`, sans action manuelle.

## Vue d'ensemble

1. **Démarrage automatique**
   - Windows : `watcher init --fully-auto` prépare `~/.watcher/` puis crée la tâche planifiée « Watcher Autopilot » (ONLOGON)
     qui lance `watcher autopilot run --noninteractive`.
   - Linux : la séquence d'initialisation installe `~/.config/systemd/user/watcher-autopilot.service` et
     `watcher-autopilot.timer` (OnBootSec=30s, OnUnitActiveSec=1h, Persistent=true).
   - Le kill-switch `~/.watcher/disable` ou la variable `WATCHER_DISABLE=1` désactive l'autostart. `WATCHER_AUTOSTART=1` force
     la réactivation quelles que soient les préférences précédentes.

2. **Boucle continue**
   - La commande `watcher autopilot run --noninteractive` déclenche le contrôleur (`app/autopilot/controller.py`) qui orchestre
     la boucle `discover → scrape → verify → ingest → report` jusqu'à la prochaine fenêtre programmée.
   - La planification (`app/autopilot/scheduler.py`) applique les créneaux réseau (`network_windows`) et les
     budgets (`bandwidth_mb_per_day`, `cpu_percent_cap`, `ram_mb_cap`). Le quota bande passante est compté sur une fenêtre glissante de 24h. Hors plage, le réseau reste coupé.
   - Les autorisations de domaine sont lues depuis `policy.yaml` via `domain_rules` (`domain` + `scope`). `allowlist_domains`
     reste synchronisé pour compatibilité avec les garde-fous runtime existants.

3. **Surveillance et rapports**
   - Chaque itération journalise un `trace_id` JSON structuré pour audit (`~/.watcher/logs/`).
   - Les métriques hebdomadaires sont résumées dans `~/.watcher/reports/weekly.html` : sources contactées, éléments
     ingérés, rejets (licence ou corroboration insuffisante) et consommation budgétaire.

## Phases de la boucle Autopilot

| Phase      | Description                                                                                             | Modules clés                                                     |
|------------|---------------------------------------------------------------------------------------------------------|------------------------------------------------------------------|
| Discover   | Exploration via sitemaps, flux RSS/Atom et résolution GitHub ciblée à partir des `domain_rules`.      | `app/autopilot/discovery.py`, `app/scrapers/sitemap.py`, `app/scrapers/github.py` |
| Scrape     | Téléchargement HTTP contrôlé pour les pages web découvertes (`respect_robots=True`, throttling, etc.). | `app/scrapers/http.py`, `app/autopilot/controller.py`            |
| Verify     | Filtrage par policy/consentement, corroboration multi-source (≥ 2 domaines) et contrôle de licence.    | `app/autopilot/controller.py`                                    |
| Evaluate   | Gate déterministe avant promotion (corroboration minimale, fraîcheur max optionnelle, score et motif). | `app/autopilot/controller.py`, `app/ingest/source_registry.py`   |
| Ingest     | Normalisation, détection de langue, chunking, embeddings locaux et indexation vectorielle.              | `app/ingest/pipeline.py`                                         |
| Report     | Mise à jour du source registry, révocation locale et génération du rapport hebdomadaire HTML.           | `app/autopilot/controller.py`                                    |

Le runtime reste borné par la policy (`network_windows`, budgets, kill-switch), le `ConsentGate` et la corroboration
multi-source avant toute promotion dans l'index local. Une source validée peut désormais être rejetée par le gate
d'évaluation avant ingestion, avec persistance de `evaluation_status`, `evaluation_score` et `evaluation_reason`.

## Gestion des budgets et du réseau

- **Offline par défaut** : la politique impose `offline_default: true`. Le réseau n'est activé que durant les fenêtres
  autorisées. `pytest-socket` garantit ce comportement en tests.
- **Budgets** : la scheduler coupe le passage online dès qu'un quota CPU/RAM/bande passante est dépassé. Le contrôleur et la discovery débitent tous deux le budget journalier de bande passante, sur une fenêtre glissante de 24 h, puis arrêtent toute nouvelle requête dès qu'il est épuisé.
- **Kill-switch** : la présence de `~/.watcher/disable` arrête la boucle en cours. Le fichier est surveillé à chaque itération.

## Journalisation et audit

- Toutes les actions autopilot passent par la journalisation configurée (`LOGGING_CONFIG_PATH` ou `config/logging.yml`) et sont écrites par défaut sous `~/.watcher/logs/`, avec `trace_id` lorsque le formatter structuré est activé.
- Le ledger `~/.watcher/consents.jsonl` n'enregistre qu'un nouvel item lorsqu'une source (domaine/scope/version) change.
- Le rapport hebdomadaire inclut désormais les sources ingérées, les promotions rejetées, les sources révoquées localement et les domaines révoqués observés dans le ledger récent.
- Les scripts d'autostart générés (`~/.watcher/autostart/windows/*`, `~/.watcher/autostart/linux/*`) peuvent être ré-exécutés
  pour audit ou réparation.

## Tests recommandés

- `pytest tests/test_autopilot.py tests/test_autopilot_controller.py tests/test_autopilot_discovery.py -q` : valide la planification réseau, les budgets, le kill-switch, `domain_rules` et le chemin `scope=git`.
- `pytest tests/test_cli_autopilot.py -q` : couvre la surface CLI `watcher autopilot ...`.
- Simulation d'un logon Windows ou `systemd --user` : vérifier que `watcher autopilot run --noninteractive` démarre sans
  interaction.

Ces tests sont intégrés aux pipelines CI, assurant le mode plug-and-play et la conformité aux critères de confiance.


## Exceptions réseau minimales

- **HTTP non chiffré (`http://`)** : interdit par défaut en discovery.
- **Exception locale uniquement** : `localhost`, `127.0.0.1`, `::1` peuvent conserver un fallback HTTP pour les environnements de test/offline locaux.
- **Robots.txt** : discovery et scraping utilisent `respect_robots=True` partout, y compris pour les sitemaps et les flux RSS.
- **GitHub scope (`scope=git`)** : unique exception runtime. Watcher interroge seulement `api.github.com/repos/<owner>/<repo>` avec `respect_robots=False`, car il s'agit d'un endpoint API machine explicite utilisé uniquement pour résoudre un dépôt déjà ciblé par la policy (`domain_rules`, avec `allowlist_domains` maintenu en compatibilité). Aucune autre voie `no-robots` n'est autorisée.
