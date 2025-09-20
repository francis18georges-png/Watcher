# Gouvernance des issues et des Pull Requests

Ce document décrit la façon dont les labels, les CODEOWNERS et les
workflows GitHub sont utilisés pour assurer un cycle de contribution
cohérent. Il complète les informations générales du `README.md` et les
check-lists qualité documentées dans `QA.md`.

## Typologie des labels

Trois familles de labels sont utilisées pour classifier les issues et les
Pull Requests. Elles peuvent être combinées entre elles.

### Labels `status:*`

| Label                     | Usage principal | Responsable |
| ------------------------- | --------------- | ----------- |
| `status:needs-triage`     | Ajouté par défaut par les templates d'issue. À retirer une fois l'analyse effectuée. | Mainteneurs |
| `status:in-progress`      | Indique qu'une personne travaille activement sur le sujet. | Mainteneur / assigné |
| `status:awaiting-review`  | Pour les PR prêtes à être relues après la phase de développement. | Auteur de la PR |
| `status:changes-requested`| Utilisé lorsqu'une revue demande des modifications majeures. | Reviewer |
| `status:qa-approved`      | Atteste que les vérifications fonctionnelles/UX sont passées (CI verte, QA manuelle si besoin). | Équipe QA |
| `status:maintainer-approved` | Toutes les revues CODEOWNER sont obtenues et la PR est prête à être fusionnée. | Mainteneurs |
| `status:queued-for-merge` | Autorise le workflow d'automatisation à fusionner la PR (voir ci-dessous). | Mainteneurs |
| `status:blocked`          | Suspend la fusion en attendant une action externe (décision produit, dépendance amont, incident…). | Mainteneurs |

> ⚠️ L'ajout de `status:queued-for-merge` n'est possible qu'après
> `status:maintainer-approved` et `status:qa-approved`. Si l'un de ces
> prérequis n'est plus respecté (CI rouge, changement de scope, nouvelle
> revue demandée), retirez `status:queued-for-merge`.

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

| Label               | Équipes CODEOWNERS impliquées | Dossiers principaux |
| ------------------- | ----------------------------- | ------------------- |
| `scope:app-experience`  | `@WatcherOrg/app-core`, `@WatcherOrg/design-system` | `app/`, `packaging/` |
| `scope:data-insights`   | `@WatcherOrg/ml-research` | `datasets/`, `metrics/`, `train.py`, `dvc.yaml`, `params.yaml` |
| `scope:documentation`   | `@WatcherOrg/documentation` | `docs/`, `README.md`, `CHANGELOG.md`, `ETHICS.md`, `QA.md`, `METRICS.md` |
| `scope:platform`        | `@WatcherOrg/platform-engineering` | `.github/workflows/`, `.github/auto_merge.yml`, `automation-playbook.sh`, `auto_flow.sh`, `noxfile.py`, `scripts/`, `Makefile`, `requirements*.txt`, `installer.ps1`, `run.ps1` |
| `scope:quality`         | `@WatcherOrg/qa` | `tests/`, `pytest.ini` |
| `scope:security`        | `@WatcherOrg/security-team` | `config/`, `plugins.toml`, `example.env` |

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
   `status:in-progress`, puis positionne `status:awaiting-review` lorsque
   le code est prêt.
4. **Revue CODEOWNER** : GitHub demande automatiquement la revue des
   équipes définies dans `.github/CODEOWNERS`. Chaque équipe concernée
   doit approuver la PR. Lorsque les vérifications fonctionnelles sont
   terminées, l'équipe QA ajoute `status:qa-approved` (ou une personne
   mandatée si le scope ne requiert pas de QA dédiée).
5. **Validation finale** : une fois la CI verte et les revues obtenues,
   un mainteneur ajoute `status:maintainer-approved`. Ajoutez ensuite
   `status:queued-for-merge` pour déléguer la fusion au workflow ou
   fusionnez manuellement.

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
3. Les labels `status:maintainer-approved`, `status:qa-approved` **et** `status:queued-for-merge` permettent
   au workflow `.github/workflows/automerge.yml` de fusionner la PR via la
   méthode `merge`. La présence de `status:blocked` empêche
   l'automatisation.
4. Retirez `status:queued-for-merge` si de nouveaux commits sont poussés ou si
   une investigation supplémentaire est nécessaire. Ajustez
   `status:qa-approved` et `status:maintainer-approved` si les conditions changent.

Les modifications sensibles (sécurité, configuration, opérations) doivent
rester en `status:blocked` tant que le plan d'action n'est pas validé par
l'équipe responsable.
