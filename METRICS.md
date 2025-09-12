# Métriques clés

## Performance
- **Temps de réponse moyen** : viser < 500 ms par requête.
  - *Mesure* : journaliser l'heure d'entrée et de sortie pour chaque requête puis calculer la moyenne.

## Qualité
- **Couverture des tests** : maintenir ≥ 85 % de code exécuté pendant les tests unitaires.
  - *Mesure* : `pytest --cov=app --cov-report=term-missing`.

## Stabilité
- **Erreurs de typage** : viser zéro diagnostic fourni par `mypy`.
  - *Mesure* : `mypy .`.

## Maintenabilité
- **Respect du style** : viser zéro avertissement de `ruff` et `black`.
  - *Mesure* : `ruff .` puis `black --check .`.

