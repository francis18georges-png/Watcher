# Métriques clés

## Performance
- **Temps de réponse** : mesurer le délai moyen pour générer une réponse complète.
  - *Mesure* : journaliser l'heure d'entrée et de sortie pour chaque requête.

## Qualité
- **Couverture des tests** : suivre le pourcentage de code exécuté pendant les tests unitaires.
  - *Mesure* : `pytest --cov=app --cov-report=term-missing`.

## Stabilité
- **Erreurs de typage** : surveiller les diagnostics fournis par `mypy`.
  - *Mesure* : `mypy .`.

## Maintenabilité
- **Respect du style** : suivre les avertissements de `ruff`.
  - *Mesure* : `ruff .`.

