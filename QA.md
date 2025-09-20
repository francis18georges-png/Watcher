# QA Notes

## Flux Git

1. `git checkout -b feature/<nom>`
2. Commits atomiques (`feat: …`, `fix: …`, `docs: …`)
3. `git push` puis ouverture d'une Pull Request
4. Revue externe et fusion après `make check`
5. Laisser le label par défaut `status:needs-triage` sur la PR ; un mainteneur le
   retirera après revue. Une fois la CI verte, seul un mainteneur pose
   `status:ready-to-merge` pour déclencher la fusion automatique.

## Manual Verification

1. Launch the GUI with `python -m app.ui.main`.
2. Enter a prompt and press **Envoyer**.
3. The button disables while the response is generated.
4. The interface remains responsive and the button re-enables once the reply appears.

## Continuous Integration

* The Windows job invokes `./installer.ps1 -SkipOllama` to validate that the PowerShell installer succeeds
  without the Ollama models.
* Immediately afterwards the workflow launches `./run.ps1` with an empty `DISPLAY` variable to emulate
  headless mode. Any startup failure or premature exit fails the build.

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

Scan the Git history for hard-coded secrets. The command fails if any match is
found.

```
gitleaks detect --source . --no-banner
```

Audit Python dependencies. The `--strict` flag elevates known
vulnerabilities to hard failures.

```
pip-audit --strict
```

Generate a CycloneDX SBOM and scan the working tree for high and critical
vulnerabilities (including secrets). The scan ignores unfixed issues to avoid
noise while still failing the build on actionable items.

```
python -c "from pathlib import Path; Path('dist').mkdir(parents=True, exist_ok=True)"
trivy sbom --format cyclonedx --output dist/Watcher-sbom.json .
trivy fs --scanners vuln,secret --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 --no-progress .
```

The CI pipeline uploads `dist/Watcher-sbom.json` as a build artifact for each
runner so downstream tooling can reuse the inventory without recomputing it.
