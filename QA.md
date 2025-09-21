# QA Notes

## Flux Git

1. `git checkout -b feature/<nom>`
2. Commits atomiques (`feat: …`, `fix: …`, `docs: …`)
3. `git push` puis ouverture d'une Pull Request
4. Revue externe et fusion après `make check`
5. Laisser le label par défaut `status:needs-triage` sur la PR ; un mainteneur le
   retirera après revue. Une fois la CI verte, seul un mainteneur pose
   `status:ready-to-merge` pour déclencher la fusion automatique.

## PR Dependabot

* Dependabot ouvre des PR hebdomadaires pour `requirements.txt`, `requirements-dev.txt`
  et les workflows GitHub Actions. Il ne garde que 5 PR Python et 3 PR Actions
  ouvertes simultanément afin de limiter le bruit.
* Chaque PR est automatiquement affectée à l'équipe `@WatcherOrg/release-engineering`
  (CODEOWNERS). Elle vérifie la matrice CI complète (`make check` localement si
  nécessaire) avant d'approuver.
* Si une mise à jour casse la compatibilité, répondre avec `@dependabot close`
  en ouvrant un ticket de suivi. Pour les correctifs critiques, demander une
  mise à jour dédiée via `@dependabot recreate` après avoir fusionné les
  correctifs bloquants.
* Déclencher `@dependabot rebase` lorsque la branche est en retard ou que la CI
  échoue pour cause de conflits. Fusionner en **Squash & merge** une fois la
  revue validée et la CI verte.

## Manual Verification

1. Launch the GUI with `python -m app.ui.main`.
2. Enter a prompt and press **Envoyer**.
3. The button disables while the response is generated.
4. The interface remains responsive and the button re-enables once the reply appears.

## Continuous Integration

* Le job `Scorecard gate` rejoue l'analyse OpenSSF Scorecard pour chaque Pull Request via
  `ossf/scorecard-action@v2`. La CI échoue dès que le score global descend sous `7` afin de
  bloquer la fusion tant que les recommandations critiques ne sont pas appliquées.
* The Windows job invokes `./installer.ps1 -SkipOllama` to validate that the PowerShell installer succeeds
  without the Ollama models.
* Immediately afterwards the workflow launches `./run.ps1` with an empty `DISPLAY` variable to emulate
  headless mode. Any startup failure or premature exit fails the build.
* Forked pull requests skip the DVC artifact pull and verification steps because the AWS credentials are not
  exposed to external runners. Maintainer branches still fail when artifacts are missing or corrupt.

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
