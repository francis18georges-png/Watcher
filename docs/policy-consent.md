# Collecte et gestion du consentement

Ce guide décrit la procédure opérée par Watcher pour consigner les consentements des personnes affectées par l'automatisation. Aucun outil en ligne de commande n'est requis : toutes les opérations s'effectuent dans l'interface « Gouvernance ».

## Principes généraux

1. Toute personne dont les données ou la production peuvent être traitées doit être identifiée par son nom, sa fonction et le périmètre d'usage autorisé.
2. Le consentement est valide pour une durée déterminée. L'échéance est définie dans la fiche et déclenche automatiquement une alerte à l'approche de la date butoir.
3. Un retrait peut intervenir à tout moment. Il doit être consigné immédiatement et prend effet sur l'ensemble des pipelines.

## Capture initiale

1. Depuis le tableau de bord, ouvrir l'espace « Consentements » puis sélectionner « Nouvelle capture ».
2. Choisir le modèle de fiche adapté (collaborateur interne, client externe, partenaire).
3. Renseigner les champs obligatoires : identité, finalités acceptées, limitations imposées, date de fin.
4. Ajouter les pièces justificatives en les déposant dans la zone prévue (scan signé, mention légale) pour qu'elles soient liées à la fiche.
5. Valider. L'application génère automatiquement une entrée signée dans le registre JSONL stocké dans le coffre hors ligne.

## Vérification et audit

1. Accéder à l'onglet « Historique » pour consulter la chronologie des consentements et retraits.
2. Utiliser le filtre « Statut » afin d'isoler les consentements expirés ou en attente d'approbation.
3. Cliquer sur une fiche pour afficher la trace de signature et les hachages correspondants. Comparer ces informations avec le registre de référence lors des audits.

## Gestion des mises à jour

1. Lorsque les finalités évoluent, sélectionner la fiche concernée puis cliquer sur « Modifier ».
2. Documenter la nouvelle portée dans la zone « Modifications ». L'application conserve la version précédente et incrémente le numéro de révision.
3. Soumettre la fiche à validation managériale en choisissant « Demander une revue ». Un binôme différent doit approuver la modification.
4. Une fois validée, la mise à jour se propage aux politiques d'accès et aux scénarios d'autopilote concernés.

## Retrait et purge

1. En cas de retrait, ouvrir la fiche et appuyer sur « Révoquer immédiatement ».
2. Sélectionner les artefacts à purger : index vectoriel, copies locales, journaux de session.
3. Confirmer l'opération. Le système planifie automatiquement une tâche d'assainissement et bloque tout nouveau traitement jusqu'à confirmation de purge complète.

## Liaison avec les politiques d'exécution

- Les consentements actifs sont exposés à l'autopilote comme contraintes. Une tâche ne peut s'exécuter que si son périmètre est couvert par un consentement valide.
- Les retraits sont synchronisés avec la [procédure de dépannage](depannage.md) pour déclencher, si nécessaire, une suspension préventive.
- La page [Quickstart sans commande](quickstart-sans-commande.md) résume la première capture à effectuer lors de l'onboarding.
- Chaque nouveau domaine ou périmètre approuvé est inscrit dans `consents.jsonl` (JSONL signé) et ajoute le domaine à `policy.yaml` (`allowlist_domains`). Aucune fenêtre popup récurrente : seule l'évolution de périmètre déclenche une nouvelle entrée.
