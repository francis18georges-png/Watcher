# Principes éthiques

Watcher vise à offrir un atelier local d'IA respectant la confidentialité des données et la transparence des opérations.

## Principes
- **Transparence** : les actions sont journalisées et les décisions importantes conservées pour audit.
- **Souveraineté des données** : aucun envoi réseau n'est effectué; les informations restent sur l'environnement local.
- **Responsabilité** : l'utilisateur conserve le contrôle et doit valider les résultats produits.

## Limites
- Les modèles sous-jacents peuvent générer des réponses erronées ou biaisées.
- Les journaux et la mémoire peuvent contenir des données sensibles; leur gestion incombe à l'utilisateur.
- Le système ne réalise pas de modération de contenu avancée.

## Traçabilité
- Journalisation via le module `logging` standard de Python.
- Stockage persistant des décisions dans une base SQLite gérée par `app/core/memory.py`.

## Conservation et effacement des retours
- Les retours et commentaires de l'utilisateur sont conservés sur l'environnement local.
- L'utilisateur peut à tout moment exporter ou supprimer ces informations pour préserver la confidentialité.
- Aucune transmission externe n'est réalisée lors de ces opérations.

