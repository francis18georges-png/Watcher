# Métriques clés

## Performance
- **Temps de réponse moyen** : viser < 500 ms par requête.
  - *Mesure* : journaliser l'heure d'entrée et de sortie pour chaque requête puis calculer la moyenne.
- **Temps du moteur, de la base de données et des plugins** : suivre la durée d'exécution de ces composants critiques et compter le nombre d'appels.
  - *Mesure* : utiliser les context managers `track_engine`, `track_db` et `track_plugin` dans `app/utils/metrics.py` pour enregistrer la durée, incrémenter les compteurs et cumuler les temps via `engine_time_total`, `db_time_total` et `plugin_time_total`.

## Qualité
- **Couverture des tests** : maintenir ≥ 85 % de code exécuté pendant les tests unitaires.
  - *Mesure* : `pytest --cov=app --cov-report=term-missing`.

## Stabilité
- **Erreurs de typage** : viser zéro diagnostic fourni par `mypy`.
  - *Mesure* : `mypy .`.

## Maintenabilité
- **Respect du style** : viser zéro avertissement de `ruff` et `black`.
  - *Mesure* : `ruff .` puis `black --check .`.
