# Gouvernance des issues et des Pull Requests

Ce document complète le README en décrivant la façon dont les labels, les
CODEOWNERS et les automatisations GitHub sont utilisés pour assurer un cycle de
revue cohérent.

## Triage et labels

Les formulaires présents dans `.github/ISSUE_TEMPLATE/` appliquent deux familles
de labels :

| Label                        | Usage | Responsable |
| ---------------------------- | ----- | ----------- |
| `status:needs-triage`        | Ajouté automatiquement tant que la demande n'a pas été classée. | Mainteneurs |
| `status:blocked`             | Indique qu'une PR est en attente d'une dépendance externe ou d'une décision. | Mainteneurs |
| `status:ready-to-merge`      | Déclenche la fusion automatique une fois la CI verte et les revues obtenues. | Mainteneurs |
| `type:bug`                   | Rapport de bug créé via le template dédié. | Demandeur |
| `type:feature`               | Demande de fonctionnalité. | Demandeur |
| `type:discussion`            | Discussion d'architecture ou de support. | Demandeur |
| `type:maintenance` (option)  | Changement purement technique (refactoring, dépendances). | Mainteneur |

Lors du tri, un mainteneur :

1. Assigne un propriétaire fonctionnel et ajoute les labels de composant
   nécessaires (`scope:docs`, `scope:security`, etc.).
2. Retire `status:needs-triage` une fois la demande classée.
3. Ajoute `status:blocked` si une action externe est requise.

## CODEOWNERS et revues

Le fichier `.github/CODEOWNERS` enregistre les équipes responsables des
composants. Toute Pull Request modifiant un chemin listé déclenche
automatiquement une demande de revue auprès de l'équipe correspondante.

- Les équipes renseignées doivent exister dans l'organisation GitHub du dépôt
  (ex. `@WatcherOrg/release-engineering`).
- Ajoutez une entrée dédiée pour tout sous-répertoire non couvert afin
  d'expliciter le propriétaire.
- Les mainteneurs peuvent surclasser une demande en ajoutant des réviseurs
  supplémentaires au besoin (sécurité, performance, UX…).

## Conditions de fusion

1. Les jobs `nox -s lint typecheck security tests build` déclenchés par la CI
   doivent réussir sur les plateformes supportées.
2. Au moins un membre de chaque équipe CODEOWNER concernée approuve la PR.
3. Une fois les points 1 et 2 remplis, un mainteneur peut ajouter le label
   `status:ready-to-merge`. Le workflow `.github/workflows/automerge.yml` fusionne
   alors la PR avec la méthode `merge`.
4. En cas de fusion manuelle, retirez `status:ready-to-merge` si la fusion doit
   être différée ou si de nouveaux commits sont poussés avant validation.

Pour des modifications sensibles (sécurité, configuration), laissez `status:blocked`
jusqu'à la validation explicite du plan d'action ou la mise à jour des tests de
régression.
