# Quickstart sans commande

Ce guide propose un démarrage immédiat de Watcher en respectant la philosophie « plug-and-play ». Toutes les étapes se déroulent via l'interface graphique et les assistants embarqués, sans recours à une invite de commande. Le premier lancement configure automatiquement `~/.watcher/` (policy v2, modèles locaux, autostart) puis planifie l'autopilote quotidien dans la fenêtre réseau 02:00–04:00.

## Prérequis matériels et sécurité

1. Vérifier que la station est déconnectée d'Internet ou placée derrière un pare-feu qui bloque les connexions sortantes inattendues en dehors du créneau policy (02:00–04:00).
2. Brancher le module matériel Watcher (NPU ou GPU local selon la configuration) et attendre que le voyant d'état passe au vert fixe.
3. Insérer la clé USB de provisionnement contenant le bundle signé remis lors de la livraison.
4. Ouvrir l'application Watcher depuis le menu « Applications locales » et confirmer l'identité de l'opérateur à l'aide du code PIN fourni.

## Initialisation guidée

1. À l'écran d'accueil, choisir « Activer l'espace isolé » pour monter le conteneur hors ligne et charger le profil matériel.
2. Lire les avertissements de la charte éthique puis sélectionner « Poursuivre » pour accéder au tableau de bord.
3. Dans le widget « Consentements », cliquer sur « Nouvelle capture » afin d'enregistrer les personnes concernées par l'assistant. Se référer au [guide de consentement](policy-consent.md) pour détailler cette étape.
4. Dans la section « Politique d'exécution », vérifier que le kill-switch est inactif et que la fenêtre réseau 02:00–04:00 est affichée. Les budgets CPU 60 %, RAM 4 Go et bande passante 200 Mo/j sont appliqués automatiquement.

## Chargement des connaissances locales

1. Insérer les supports (dossiers projet, documents de référence) dans le dossier partagé « Sources approuvées ».
2. Depuis le tableau de bord, choisir « Indexer maintenant ». L'assistant d'ingestion affiche une progression et signale les fichiers rejetés avec leur motif. Deux sources indépendantes minimum sont requises avant indexation.
3. Valider la suggestion de taxonomie proposée. En cas de doute, sélectionner « Révision humaine » pour reporter une décision.

## Lancement d'un cycle pilote

1. Ouvrir l'onglet « Autopilote » puis choisir « Créer un plan expérimental ».
2. Confirmer les objectifs de la session (par exemple « Refactoriser le module d'observabilité ») et ajouter les contraintes de sécurité souhaitées.
3. Laisser l'assistant générer les tâches. Revoir les actions proposées, décocher celles qui ne doivent pas être exécutées, puis valider.
4. Surveiller la phase « Analyse », « Synthèse » et « Validation » dans l'ordre. Chaque transition nécessite une approbation explicite pour maintenir une supervision forte.

## Revue finale

1. À la fin du cycle, ouvrir la carte « Journal des décisions » et vérifier que toutes les interventions sont consignées.
2. Consulter le rapport d'artefacts signés (voir [vérification des artefacts](verifier-artefacts.md)) afin de confirmer l'intégrité des sorties.
3. Exporter le paquet de session sur la clé USB de contrôle pour archivage.
4. Passer en mode veille en sélectionnant « Suspendre le conteneur » avant de débrancher le matériel.

## Prochaines étapes

- Approfondir la gouvernance avec le [guide de consentement détaillé](policy-consent.md).
- Configurer l'autopilote durablement en suivant le [cycle de vie de l'autopilote](autopilot.md).
- Apprendre à diagnostiquer les anomalies via la [procédure de dépannage](depannage.md).
- Vérifier l'intégrité des éléments livrés grâce au [protocole de contrôle d'artefacts](verifier-artefacts.md).
