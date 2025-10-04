# Vérification des artefacts Watcher

La chaîne plug-and-play de Watcher produit des rapports signés et des paquets d'exécution. Cette procédure décrit comment vérifier leur intégrité sans recourir à des commandes en ligne. Toutes les opérations se déroulent dans les modules « Provenance » et « Audits » de l'interface.

## Préparer l'espace de contrôle

1. Insérer la clé de contrôle ou monter le coffre hors ligne contenant les fichiers d'attestation remis avec le bundle.
2. Depuis le tableau de bord, ouvrir l'onglet « Provenance » puis sélectionner « Nouvelle vérification ».
3. Choisir la source à valider : paquet d'autopilote, index de connaissances ou build applicative.

## Vérification automatique

1. Charger le paquet à contrôler via le sélecteur de fichiers intégré.
2. L'interface calcule automatiquement l'empreinte SHA-256 et l'affiche à l'écran.
3. L'application recherche la signature correspondante dans le registre `Watcher-Setup.intoto.jsonl`. Vérifier que l'indicateur « Signature valide » s'affiche en vert.
4. Examiner le résumé CycloneDX associé pour confirmer la liste des dépendances, versions et licences.

## Contrôles supplémentaires

1. Ouvrir l'onglet « Comparaison » pour juxtaposer le paquet courant avec la référence précédente.
2. Vérifier que les différences signalées correspondent aux modifications attendues (nouvelles fonctionnalités, correctifs de sécurité).
3. Si une divergence inattendue apparaît, basculer sur « Escalade » afin de notifier l'équipe sécurité et figer la diffusion des artefacts.

## Journalisation et conservation

1. Valider la vérification pour consigner le résultat dans le journal append-only. Une entrée horodatée est ajoutée avec le détail des hachages contrôlés.
2. Archiver le rapport PDF généré automatiquement sur le support sécurisé dédié.
3. Associer la vérification à la session Autopilote concernée pour maintenir la traçabilité bout en bout.

## Intégration dans les autres procédures

- Le [Quickstart sans commande](quickstart-sans-commande.md) renvoie vers cette page à l'étape de revue finale.
- Les contrôles de consentement décrits dans le [guide de politique de consentement](policy-consent.md) doivent être cohérents avec les artefacts validés.
- En cas d'anomalie détectée, suivre la [procédure de dépannage](depannage.md) pour enclencher l'enquête et, si nécessaire, révoquer les livrables.
