# Contribuer à Watcher

Merci de votre intérêt pour l'amélioration de Watcher ! Ce guide détaille les attentes du projet, la préparation de votre
environnement et la politique de revue/merge appliquée par l'équipe de maintenance.

## Respecter le code de conduite

Toutes les contributions doivent respecter le [Code de conduite](CODE_OF_CONDUCT.md). Signalez immédiatement tout comportement
inapproprié aux mainteneurs.

## Préparer son environnement

- **Python 3.12** : créez un environnement virtuel dédié (`python -m venv .venv`).
- **Dépendances projet** : installez les requirements de base et de développement :
  ```bash
  pip install -r requirements.txt
  pip install -r requirements-dev.txt
  ```
- **Nox** : l'ensemble des linters, tests, vérifications de sécurité et build passe par [Nox](https://nox.thea.codes/). Installez-le
  globalement ou dans votre venv (`pip install nox`). Les commandes utilisées par la CI sont :
  ```bash
  nox -s lint typecheck security tests build
  ```
- **DVC** : Watcher versionne des artefacts de données via [DVC](https://dvc.org/). Installez `dvc` (par exemple `pip install "dvc[s3]"`)
  puis synchronisez les données nécessaires :
  ```bash
  dvc pull
  ```
  Le pipeline `dvc repro` orchestre la préparation (`scripts/prepare_data.py`) et la validation (`scripts/validate_schema.py`,
  `scripts/validate_size.py`, `scripts/validate_hash.py`). Assurez-vous que ces étapes restent reproductibles et committez les
  fichiers `.dvc` et `dvc.lock` mis à jour si besoin.
- **Scripts utilitaires** : les commandes `python -m app.core.benchmark run` et `python -m app.core.benchmark check --update-badge`
  sont utilisées pour surveiller les performances et rafraîchir le badge `metrics/performance_badge.svg`. Lancez-les en cas de
  modifications susceptibles d'impacter les temps d'exécution.
- **Hooks pre-commit** : activez les hooks fournis (`pre-commit install`) pour aligner vos contributions sur les formats attendus.

## Processus de développement

1. **Créer une branche** : travaillez sur une branche dérivée de `main` pour chaque contribution.
2. **Synchroniser les données** : si votre changement affecte la pipeline DVC, mettez à jour les artefacts (`dvc repro`) et commitez
   les fichiers suivis (`*.dvc`, `dvc.lock`, `metrics/…`).
3. **Exécuter la suite Nox** : vérifiez localement que `nox -s lint typecheck security tests build` passe avant d'ouvrir la PR.
4. **Mettre à jour la documentation** : adaptez `README.md`, `docs/` ou les guides associés pour décrire les nouvelles capacités ou
   les breaking changes.
5. **Rédiger un changelog** : ajoutez une entrée dans `CHANGELOG.md` si la modification est visible pour l'utilisateur final.

## Politique de merge et des pull requests

- **Template obligatoire** : utilisez le modèle de PR par défaut et fournissez un contexte clair (motivation, tests, impact).
- **Vérifications automatisées** : une PR n'est éligible à la fusion que si tous les checks GitHub (Nox, DVC, benchmarks, lint)
  sont verts. Les échecs doivent être résolus ou justifiés.
- **Revue par les CODEOWNERS** : au moins un membre `@WatcherOrg/maintainers` (ou l'équipe `scope:*` concernée définie dans
  `.github/CODEOWNERS`) doit approuver.
- **Automerge contrôlé** : après approbation et succès de la CI, un mainteneur applique le label `status:ready-to-merge`. Le workflow
  `.github/auto_merge.yml` fusionne ensuite automatiquement la PR. N'ajoutez pas ce label vous-même.
- **Conflits et escalade** : en cas de désaccord technique ou de comportement inapproprié pendant la revue, contactez les
  mainteneurs via `maintainers@watcher.local`. Les sujets liés à la sécurité doivent être escaladés à `security@watcher.local`.
- **Backports** : les correctifs critiques peuvent être cherry-pickés vers les branches de maintenance après validation expresse d'un
  mainteneur.

## Questions fréquentes

- **Comment signaler un bug ?** Ouvrez une issue via le template `Bug report`. Fournissez les étapes de reproduction, les logs
  pertinents et la version utilisée.
- **Comment proposer une nouvelle fonctionnalité ?** Utilisez le template `Feature request` et expliquez comment la fonctionnalité
  s'intègre aux objectifs de Watcher et à l'expérience utilisateur.
- **Qui contacter en cas de doute ?** Consultez `docs/merge-policy.md` pour connaître la gouvernance détaillée des labels et
  contactez `@WatcherOrg/maintainers` sur GitHub ou par e-mail en cas de question.

Merci de contribuer à un atelier d'IA de qualité, transparent et sécurisé !
