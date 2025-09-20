# Gouvernance des issues et des Pull Requests

Ce document complète le README en décrivant la façon dont les labels, les CODEOWNERS et
automations GitHub sont utilisés pour assurer un cycle de revue cohérent.

## Triage et labels

| Label            | Usage | Responsable |
| ---------------- | ----- | ----------- |
| `needs-triage`   | Ajouté automatiquement tant que la demande n'a pas été classée. | Mainteneurs |
| `bug`            | Rattaché aux rapports créés via le template dédié. | Demandeur |
| `enhancement`    | Attaché aux demandes de fonctionnalités. | Demandeur |
| `discussion`     | Appliqué automatiquement pour les discussions d'architecture. | Demandeur |
| `blocked`        | Indique qu'une PR est en attente d'une dépendance externe. | Mainteneurs |
| `automerge`      | Déclenche la fusion automatique une fois la CI verte et les revues obtenues. | Mainteneurs |

Lors du tri, le mainteneur assigne un propriétaire fonctionnel, met à jour les
labels (ex. priorité, composant) et retire `needs-triage`.

## CODEOWNERS et revues

Le fichier `.github/CODEOWNERS` enregistre les équipes responsables des
composants. Toute Pull Request modifiant un répertoire listé déclenche
automatiquement une demande de revue auprès de l'équipe correspondante.

- Les équipes renseignées doivent exister dans l'organisation GitHub du dépôt
  (ex. `@WatcherOrg/maintainers`).
- Si un sous-répertoire n'est pas couvert, ajoutez une entrée dédiée afin
  d'expliciter le propriétaire.

## Conditions de fusion

1. Les jobs `nox -s lint typecheck security tests build` déclenchés par la CI
   doivent réussir sur les trois plateformes supportées.
2. Au moins un membre de l'équipe CODEOWNER concernée approuve la PR.
3. Le label `automerge` peut être posé par un mainteneur une fois les points 1 et
   2 respectés. Le workflow `.github/workflows/automerge.yml` fusionne alors la PR
   avec la méthode `merge`.
4. En cas de fusion manuelle, les mainteneurs suivent la même check-list et
   retirent `automerge` si la fusion doit être différée.

Pour des modifications sensibles (sécurité, configuration), ajoutez
`blocked` jusqu'à la validation explicite du plan d'action.
