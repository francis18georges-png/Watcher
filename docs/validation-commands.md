# Commandes de validation Watcher

Ces commandes doivent être exécutées pour valider une livraison Watcher locale avant publication.

## Préparation

```bash
python -m venv .venv
source .venv/bin/activate  # ou .venv\\Scripts\\activate sur Windows
pip install -e .[dev]
```

## Chaîne hors-ligne

```bash
watcher init --fully-auto
watcher run --offline --prompt "test"
```

## Publication

```bash
git tag -a v0.5.0 -m "Public release"
git push origin v0.5.0
cosign verify-attestation --type slsaprovenance ghcr.io/<owner>/watcher:latest
```

## Contrôles supplémentaires

```bash
pytest --maxfail=1 --disable-warnings
pytest -m offline --socket-disabled
pytest --cov=app --cov-report=xml
nox -s lint
```

> ℹ️ `pytest-socket` est activé par défaut (voir `pytest.ini`). Utiliser `--socket-allow-hosts` uniquement pour les tests explicitement online.
