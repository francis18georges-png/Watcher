# Plan de tests `pytest`

Les suites automatisées garantissent le mode plug-and-play et la conformité réseau.

## Marqueurs

- `first_run` : couvre l'initialisation hors-ligne, le téléchargement par hash et la génération de `policy.yaml`.
- `autopilot` : valide la planification réseau, les budgets CPU/RAM/bande passante et le kill-switch.
- `scraping` : vérifie le respect de `robots.txt`, la prise en charge ETag/If-Modified-Since et la déduplication des URLs.
- `offline` : exécute `watcher run --offline` avec un modèle GGUF réduit pour garantir une sortie déterministe sans réseau.
- `security` : regroupe les tests de sandbox (cgroups/Job Objects) et de verrouillage réseau via `pytest-socket`.

## Exemples de commandes

```bash
pytest -m first_run --disable-warnings
pytest -m autopilot --maxfail=1
pytest -m "scraping and not slow"
pytest -m offline --socket-disabled
pytest -m security --cov=app --cov-report=xml
```

## Couverture visée

- Couverture globale ≥ 85 % (`pytest --cov=app --cov-report=term-missing`).
- Diff coverage 100 % via `pytest --cov-report=xml` et l'analyse `diff-cover` exécutée en CI.
- Utilisation de `pytest-socket` pour interdire toute connexion réseau durant les tests par défaut.
