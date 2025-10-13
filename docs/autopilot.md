# Cycle de vie de l'autopilote

Ce document détaille la gouvernance du mode Autopilote de Watcher. Il structure l'exploitation en trois temps : préparation, exécution surveillée et clôture, sans passer par des scripts ou commandes externes.

## Préparation

1. Ouvrir la vue « Autopilote » et sélectionner « Configurer un nouveau scénario ».
2. Choisir le périmètre fonctionnel (par exemple refonte d'un service, rédaction d'une analyse) et préciser la fenêtre temporelle souhaitée.
3. Associer le scénario aux consentements pertinents en sélectionnant les fiches actives listées dans le volet latéral.
4. Définir un budget de tâches et une limite de ressources (temps CPU, accès aux outils) via les curseurs proposés.
5. Enregistrer le scénario. Il devient visible dans le tableau de bord avec l'état « Prêt ».

## Exécution surveillée

1. Pour démarrer, cliquer sur « Lancer ». L'autopilote entre dans la phase « Analyse » où il collecte les informations nécessaires.
2. Examiner les hypothèses affichées. Approuver ou ajuster les hypothèses invalides avant de poursuivre vers la phase « Planification ».
3. Durant la phase « Planification », l'assistant propose une liste d'actions. Désactiver les actions qui dépassent le périmètre ou exigent un consentement absent.
4. Valider pour passer à la phase « Exécution ». Surveiller les notifications de sécurité ; un indicateur rouge implique une intervention humaine immédiate.
5. À tout moment, utiliser « Mettre en pause » pour suspendre les actions restantes, ou « Arrêter » pour revenir au statut « Prêt » après justification dans le journal.

## Contrôles intégrés

- Les actions critiques déclenchent un double contrôle. L'autopilote sollicite un binôme pour confirmation avant de poursuivre.
- Les ressources consommées sont agrégées en temps réel dans le widget « Budget ». Lorsque 80 % du budget est atteint, le système impose une revue intermédiaire.
- Le moteur applique la politique de consentement pour filtrer les fichiers et sources non autorisés. Une tâche refusée passe automatiquement en revue manuelle.
- La politique `policy.yaml` (v2) impose : fenêtre réseau 02:00–04:00 (`network_windows`), `allowlist_domains` explicite, kill-switch `~/.watcher/disable`, budgets CPU 60 %, RAM 4 Go et bande passante 200 Mo/j. L'autopilote coupe le réseau hors créneau et respecte ces limites.

## Clôture et archivage

1. À la fin de la phase « Synthèse », l'autopilote propose un rapport structuré.
2. Examiner les sections « Actions réalisées », « Décisions humaines » et « Recommandations ». Ajouter des commentaires si nécessaire.
3. Sélectionner « Approuver et archiver » pour générer le paquet d'audit contenant le journal, les artefacts signés et les hachages de référence.
4. Exporter le paquet vers le coffre hors ligne ou sur la clé de contrôle conformément aux règles internes.

## Entretien récurrent

- Planifier des revues trimestrielles des scénarios pour s'assurer que les budgets et contraintes restent pertinents.
- Utiliser la [procédure de vérification des artefacts](verifier-artefacts.md) afin de valider les livrables avant diffusion.
- En cas d'incident, suivre la [procédure de dépannage](depannage.md) pour suspendre l'autopilote et diagnostiquer la cause racine.
- Pour une mise en route rapide sans script, se référer au [Quickstart sans commande](quickstart-sans-commande.md).
