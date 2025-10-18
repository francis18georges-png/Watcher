# Plan de tests `pytest`

Les suites automatisées garantissent le mode plug-and-play et la conformité réseau.

## Marqueurs

- `first_run` : couvre l'initialisation hors-ligne, le téléchargement par hash et la génération de `policy.yaml`.
- `autopilot` : valide la planification réseau, les budgets CPU/RAM/bande passante et le kill-switch.
- `scraping` : vérifie le respect de `robots.txt`, la prise en charge ETag/If-Modified-Since et la déduplication des URLs.
- `offline` : exécute `watcher run --offline` avec un modèle GGUF réduit pour garantir une sortie déterministe sans réseau.
- `security` : regroupe les tests de sandbox (cgroups/Job Objects) et de verrouillage réseau via `pytest-socket`.
- `reporting` : garantit la génération du rapport hebdo HTML et la consolidation des métriques d'ingestion.
- `consent` : couvre le ledger signé, l'unicité des consentements par domaine/scope/version et la rotation de clé.

## Exemples de commandes

```bash
pytest -m first_run --disable-warnings
pytest -m autopilot --maxfail=1
pytest -m "scraping and not slow"
pytest -m offline --socket-disabled
pytest -m security --cov=app --cov-report=xml
pytest -m reporting --html=reports/pytest/report.html --self-contained-html
pytest -m consent --ff
```

## Couverture visée

- Couverture globale ≥ 85 % (`pytest --cov=app --cov-report=term-missing`).
- Diff coverage 100 % via `pytest --cov-report=xml` et l'analyse `diff-cover` exécutée en CI.
- Utilisation de `pytest-socket` pour interdire toute connexion réseau durant les tests par défaut.
- Activation de `pytest-rerunfailures` uniquement pour les tests marqués `flaky` (aucun test critique ne doit en dépendre).
- Intégration d'un job `release-dry-run` sur chaque PR pour dérouler la chaîne `release.yml` avec `publish=false`.
