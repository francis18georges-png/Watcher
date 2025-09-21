# Gouvernance des issues et des Pull Requests

Ce document décrit la façon dont les labels, les CODEOWNERS et les
workflows GitHub sont utilisés pour assurer un cycle de contribution
cohérent. Il complète les informations générales du `README.md` et les
check-lists qualité documentées dans `QA.md`.

> 📌 **Rappel citation** : lors de la préparation d'une release ou d'une
> contribution majeure, vérifiez que la version publiée et le fichier
> `CITATION.cff` sont alignés avec le `pyproject.toml` et le `CHANGELOG.md` afin
> que les équipes externes puissent citer correctement le projet.

## Typologie des labels

Trois familles de labels sont utilisées pour classifier les issues et les
Pull Requests. Elles peuvent être combinées entre elles.

### Labels `status:*`

| Label                   | Usage principal | Responsable |
| ----------------------- | --------------- | ----------- |
| `status:needs-triage`   | Ajouté par défaut par les templates d'issue. À retirer une fois l'analyse effectuée. | Mainteneurs |
| `status:in-progress`    | Indique qu'une personne travaille activement sur le sujet. | Mainteneur / assigné |
| `status:ready-for-review` | Pour les PR prêtes à être relues après la phase de développement. | Auteur de la PR |
| `status:changes-requested` | Utilisé lorsqu'une revue demande des modifications majeures. | Reviewer |
| `status:blocked`        | Suspend la fusion en attendant une action externe (décision produit, dépendance amont, incident…). | Mainteneurs |
| `status:ready-to-merge` | Toutes les revues requises sont obtenues et la CI est verte. | Mainteneurs |
| `status:auto-merge`     | Autorise le workflow d'automatisation à fusionner la PR (voir ci-dessous). | Mainteneurs |

> ⚠️ L'ajout de `status:auto-merge` implique que `status:ready-to-merge` est
> déjà présent et qu'aucun label bloquant n'est appliqué. Si l'un de ces
> prérequis n'est plus respecté, retirez `status:auto-merge`.

### Labels `type:*`

| Label             | Usage |
| ----------------- | ----- |
| `type:bug`        | Rapport de bug créé via le template dédié. |
| `type:feature`    | Demande de fonctionnalité ou d'amélioration UX. |
| `type:maintenance`| Dette technique, refactoring, mise à jour de dépendance. |
| `type:discussion` | Question, RFC ou support via les discussions GitHub. |

### Labels `scope:*`

Les labels de portée permettent d'identifier rapidement les équipes
concernées. Ils sont alignés sur la configuration de
`.github/CODEOWNERS` :

| Label        | Équipes CODEOWNERS impliquées | Dossiers principaux |
| ------------ | ----------------------------- | ------------------- |
| `scope:app`  | `@WatcherOrg/app-core`, `@WatcherOrg/design-system` | `app/`, `packaging/` |
| `scope:ml`   | `@WatcherOrg/ml-research` | `datasets/`, `metrics/`, `train.py` |
| `scope:docs` | `@WatcherOrg/documentation` | `docs/`, `README.md`, `CHANGELOG.md`, `ETHICS.md`, `QA.md`, `METRICS.md` |
| `scope:ops`  | `@WatcherOrg/release-engineering` | `.github/workflows/`, `scripts/`, `noxfile.py` |
| `scope:quality` | `@WatcherOrg/qa` | `tests/`, `pytest.ini` |
| `scope:security` | `@WatcherOrg/security-team` | `config/`, `app/plugins.toml`, `example.env` |

Lors du tri, les mainteneurs ajoutent au moins un label `scope:*` pour
chaque issue/PR, idéalement sur la base des indications fournies dans les
formulaires.

## Processus de tri et de revue

1. **Création** : les templates d'issue appliquent `status:needs-triage`
   et un label `type:*`. Les reporters sont invités à préciser la zone
   concernée via le champ « Zone impactée ».
2. **Triage** : un mainteneur assigne la demande, ajoute les labels
   `scope:*` pertinents et retire `status:needs-triage`. Si nécessaire,
   ajoutez `status:blocked` en attendant une action externe.
3. **Développement** : l'auteur de la PR passe le ticket en
   `status:in-progress`, puis positionne `status:ready-for-review` lorsque
   le code est prêt.
4. **Revue CODEOWNER** : GitHub demande automatiquement la revue des
   équipes définies dans `.github/CODEOWNERS`. Chaque équipe concernée
   doit approuver la PR.
5. **Validation finale** : une fois la CI verte et les revues obtenues,
   un mainteneur ajoute `status:ready-to-merge`. Ajoutez `status:auto-merge`
   pour déléguer la fusion au workflow ou fusionnez manuellement.

## CODEOWNERS

Le fichier `.github/CODEOWNERS` décrit les zones de responsabilité et
assure que les équipes adéquates sont sollicitées. Quelques principes :

- Toute modification non couverte hérite des mainteneurs (`*`).
- Les entrées sont organisées par label `scope:*` pour faciliter le tri.
- Ajoutez une nouvelle ligne si un sous-répertoire n'est pas déjà couvert
  par le propriétaire attendu.

## Conditions de fusion

1. Les jobs de CI (lint, typecheck, sécurité, tests, build) doivent être
   verts sur les branches supportées.
2. Chaque équipe CODEOWNER impactée doit avoir approuvé la PR.
3. Les labels `status:ready-to-merge` **et** `status:auto-merge` permettent
   au workflow `.github/workflows/automerge.yml` de fusionner la PR via la
   méthode `merge`. La présence de `status:blocked` empêche
   l'automatisation.
4. Retirez `status:auto-merge` si de nouveaux commits sont poussés ou si
   une investigation supplémentaire est nécessaire.

Les modifications sensibles (sécurité, configuration, opérations) doivent
rester en `status:blocked` tant que le plan d'action n'est pas validé par
l'équipe responsable.

## Conventions de commit et de changelog

- **Commitlint** : le workflow `.github/workflows/commitlint.yml` applique les
  [Conventional Commits](https://www.conventionalcommits.org/fr/v1.0.0/). Les
  commits et titres de PR doivent respecter le format `type(scope): message`.
  Les types autorisés sont `feat`, `fix`, `docs`, `style`, `refactor`, `perf`,
  `test`, `build`, `ci`, `chore` et `revert`. Les scopes suivent les labels
  `scope:*` décrits ci-dessus.
- **Changelog automatisé** : Release Drafter regroupe les PR par catégories
  (`type:*`, `scope:*`) et ignore celles marquées `status:blocked`,
  `status:needs-triage` ou `status:wip`. Assurez-vous que la PR possède les
  bons labels avant merge pour alimenter les sections « Fonctionnalités »,
  « Corrections », « Maintenance », etc.
- **Résolution de version** : ajoutez un label `release:major`,
  `release:minor` ou `release:patch` lorsque la PR implique un changement
  SemVer spécifique. Sans label explicite, l'incrément par défaut est de type
  patch.

## Publication automatisée

Le workflow `.github/workflows/release-drafter.yml` met à jour le brouillon de
release à chaque push sur `main`. Une fois la release validée par les
mainteneurs :

1. Ouvrez le draft généré par Release Drafter, vérifiez les sections et
   finalisez le numéro de version (`vX.Y.Z`).
2. Publiez la release GitHub : cela crée le tag et déclenche le workflow
   `.github/workflows/release.yml` qui construit les artefacts et uploads
   associés.
3. Contrôlez que les artefacts publiés sont conformes, mettez à jour le
   `CHANGELOG.md`, `pyproject.toml` et `CITATION.cff` si besoin, puis
   communiquez la version aux équipes concernées.

> ℹ️ Les workflows commitlint et release-drafter n'accordent que les
> permissions minimales (`contents:read/pull-requests:read` pour commitlint,
> `contents:write/pull-requests:read` pour Release Drafter) et n'interfèrent
> pas avec l'automerge : ils opèrent sur des événements différents (`push` ou
> `pull_request`) et ne modifient pas les labels `status:*`.
