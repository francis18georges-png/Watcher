# Autopilote sans intervention

Ce document décrit l'exécution autonome de Watcher après la phase `watcher init --auto`. L'objectif est de garantir une collecte
et une ingestion 100 % locales, gouvernées par la politique `policy.yaml`, sans action manuelle.

## Vue d'ensemble

1. **Démarrage automatique**
   - Windows : `watcher init --auto` enregistre une entrée `RunOnce` puis crée la tâche planifiée « Watcher Autopilot » (ONLOGON)
     qui lance `watcher autopilot run --noninteractive`.
   - Linux : la séquence d'initialisation installe `~/.config/systemd/user/watcher-autopilot.service` et
     `watcher-autopilot.timer` (OnBootSec=30s, OnUnitActiveSec=1h, Persistent=true).
   - Le kill-switch `~/.watcher/disable` ou la variable `WATCHER_DISABLE=1` désactive l'autostart. `WATCHER_AUTOSTART=1` force
     la réactivation quelles que soient les préférences précédentes.

2. **Boucle continue**
   - La commande `watcher autopilot run --noninteractive` déclenche le contrôleur (`app/autopilot/controller.py`) qui orchestre
     la boucle `discover → scrape → verify → ingest → reindex` jusqu'à la prochaine fenêtre programmée.
   - La planification (`app/autopilot/scheduler.py`) applique les créneaux réseau (`02:00–04:00`, `network_windows`) et les
     budgets (`bandwidth_mb_per_day`, `cpu_percent_cap`, `ram_mb_cap`). Hors plage, le réseau reste coupé.

3. **Surveillance et rapports**
   - Chaque itération journalise un `trace_id` JSON structuré pour audit (`~/.watcher/logs/`).
   - Les métriques hebdomadaires sont résumées dans `~/.watcher/reports/autopilot-YYYY-WW.html` : sources contactées, éléments
     ingérés, rejets (licence ou corroboration insuffisante) et consommation budgétaire.

## Phases de la boucle Autopilot

| Phase      | Description                                                                                          | Modules clés                                      |
|------------|------------------------------------------------------------------------------------------------------|---------------------------------------------------|
| Discover   | Exploration via sitemaps, RSS, GitHub Topics et résolution des *knowledge gaps*.                      | `app/autopilot/discovery.py`                      |
| Scrape     | Téléchargement contrôlé : robots.txt, ETag/If-Modified-Since, throttling, timeouts, UA dédié.        | `app/scrapers/http.py`, `app/scrapers/rss.py`, … |
| Verify     | Consolidation multi-sources (≥ 2 indépendantes), scoring de confiance, rejet des licences interdites. | `app/scrapers/verify.py`, `app/policy/rules.py`   |
| Ingest     | Normalisation, détection de langue, chunking, embeddings locaux, indexation SQLite-VSS/FAISS.        | `app/ingest/pipeline.py`                          |
| Reindex    | Rafraîchissement des statistiques (`index.stats`) et génération du rapport hebdomadaire.             | `app/ingest/index.py`                             |

Chaque phase tourne dans un sous-processus enfermé (Job Objects sous Windows, cgroups sous Linux) avec quotas CPU/RAM et
système de fichiers limité au workspace (`~/.watcher/workspace`).

## Gestion des budgets et du réseau

- **Offline par défaut** : la politique impose `offline_default: true`. Le réseau n'est activé que durant les fenêtres
  autorisées. `pytest-socket` garantit ce comportement en tests.
- **Budgets** : la scheduler réduit dynamiquement le nombre de tâches si les quotas CPU/RAM/bande passante approchent 100 %.
- **Kill-switch** : la présence de `~/.watcher/disable` arrête la boucle en cours. Le fichier est surveillé à chaque itération.

## Journalisation et audit

- Toutes les actions autopilot sont tracées dans `~/.watcher/logs/autopilot.jsonl` avec `trace_id`, phase, source et résultat.
- Le ledger `~/.watcher/consents.jsonl` n'enregistre qu'un nouvel item lorsqu'une source (domaine/scope/version) change.
- Les scripts d'autostart générés (`~/.watcher/autostart/windows/*`, `~/.watcher/autostart/linux/*`) peuvent être ré-exécutés
  pour audit ou réparation.

## Tests recommandés

- `pytest -m autopilot --maxfail=1` : valide la planification réseau, les budgets et le kill-switch.
- `pytest -m scraping` : couvre la conformité robots/ETag et la déduplication.
- Simulation d'un logon Windows ou `systemd --user` : vérifier que `watcher autopilot run --noninteractive` démarre sans
  interaction.

Ces tests sont intégrés aux pipelines CI, assurant le mode plug-and-play et la conformité aux critères de confiance.
