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
