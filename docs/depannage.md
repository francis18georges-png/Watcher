# Dépannage plug-and-play

Cette procédure fournit une méthode sans ligne de commande pour diagnostiquer les incidents Watcher en environnement isolé.

## Symptômes courants

- **Autopilote bloqué en phase Analyse** : le module attend une validation de consentement ou une ressource manquante.
- **Échec de vérification des artefacts** : les hachages ne correspondent pas au registre de référence.
- **Alertes de quota** : le budget de tâches défini a été dépassé ou une ressource critique est saturée.

## Étapes de résolution

1. Ouvrir le panneau « Surveillance » depuis le tableau de bord principal.
2. Consulter la carte « Alertes actives ». Chaque alerte renvoie vers un diagnostic guidé.
3. Si l'alerte concerne le consentement, accéder directement à la fiche via le lien fourni et appliquer le [guide de consentement](policy-consent.md).
4. Pour un incident Autopilote, cliquer sur « Suspendre en sécurité ». Cette action met l'exécution en pause et enregistre l'état actuel.
5. Examiner la chronologie des actions dans « Journal des événements ». Repérer l'étape fautive et vérifier les contraintes associées.
6. Si un artefact est suspect, passer sur « Contrôles d'intégrité » et appliquer la [procédure de vérification des artefacts](verifier-artefacts.md).
7. Documenter la résolution dans la zone « Compte rendu ». Ce rapport sera joint aux audits ultérieurs.

## Escalade

1. Lorsque la résolution locale échoue, sélectionner « Escalader vers l'équipe sécurité ».
2. Choisir le type d'incident (panne fonctionnelle, suspicion de compromission, incident de consentement).
3. Joindre les journaux pertinents et confirmer l'envoi. Le système crypte les données et les stocke sur le support sécurisé convenu.

## Reprise contrôlée

1. Une fois la cause identifiée, retourner sur la carte « Autopilote » et sélectionner « Reprendre après validation ».
2. Indiquer quelles actions doivent être rejouées ou annulées.
3. Lancer la reprise. Surveiller les premiers événements pour garantir la stabilité.

## Prévention

- Planifier des vérifications régulières via le [cycle de vie de l'autopilote](autopilot.md) afin d'anticiper les blocages.
- Renforcer l'intégrité des livrables par la [vérification des artefacts](verifier-artefacts.md) à chaque itération.
- Actualiser les consentements suivant le [processus dédié](policy-consent.md) pour éviter les suspensions préventives.
- Intégrer le [Quickstart sans commande](quickstart-sans-commande.md) dans les formations afin de réduire les erreurs de manipulation.
