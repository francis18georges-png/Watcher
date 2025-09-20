# QA Notes

## Flux Git

1. `git checkout -b feature/<nom>`
2. Commits atomiques (`feat: …`, `fix: …`, `docs: …`)
3. `git push` puis ouverture d'une Pull Request
4. Revue externe et fusion après `make check`
5. Laisser le label par défaut `status:needs-triage` sur la PR ; un mainteneur le
   retirera après revue. Une fois la CI verte, faites valider le scope par la QA
   (`status:qa-approved`), puis un mainteneur pose `status:maintainer-approved`
   et `status:queued-for-merge` pour déclencher la fusion automatique.

## Manual Verification

1. Launch the GUI with `python -m app.ui.main`.
2. Enter a prompt and press **Envoyer**.
3. The button disables while the response is generated.
4. The interface remains responsive and the button re-enables once the reply appears.

## Continuous Integration

* The Windows job invokes `pwsh ./installer.ps1 -SkipOllama` to validate that the PowerShell installer
  succeeds without the Ollama models.
* The same job launches `pwsh ./run.ps1` with an empty `DISPLAY` variable to emulate headless mode. Any
  startup failure or premature exit fails the build.

## Static Analysis

Install the development dependencies:

```
pip install -r requirements-dev.txt
```

Install the Git hooks once the dependencies are available:

```
pre-commit install
pre-commit run --all-files
```

Run Bandit to scan the codebase while ignoring Git metadata:

```
bandit -q -r . -c bandit.yml
```

Run Semgrep using the local ruleset:

```
semgrep --quiet --error --config config/semgrep.yml .
```
