# QA Notes

## Flux Git

1. `git checkout -b feature/<nom>`
2. Commits atomiques (`feat: …`, `fix: …`, `docs: …`)
3. `git push` puis ouverture d'une Pull Request
4. Revue externe et fusion après `make check`

## Manual Verification

1. Launch the GUI with `python -m app.ui.main`.
2. Enter a prompt and press **Envoyer**.
3. The button disables while the response is generated.
4. The interface remains responsive and the button re-enables once the reply appears.

## Static Analysis

Install the development dependencies:

```
pip install -r requirements-dev.txt
```

Run Bandit to scan the codebase while ignoring Git metadata:

```
bandit -q -r . -c bandit.yml
```

Run Semgrep using the local ruleset:

```
semgrep --quiet --error --config config/semgrep.yml .
```
