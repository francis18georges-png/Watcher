# Documentation Watcher

Bienvenue dans l'espace de référence du projet **Watcher**, l'atelier local d'IA de programmation autonome.
Cette documentation complète le README et les guides techniques du dépôt en présentant la structure du
système, son modèle de sécurité et les pratiques d'exploitation.

## Parcours recommandé

1. Découvrir la [vue d'ensemble de l'architecture](architecture.md) pour comprendre comment l'orchestrateur,
   les agents spécialisés, la mémoire vectorielle et les garde-fous qualité coopèrent.
2. Lire le [modèle de menaces](threat-model.md) afin d'identifier les actifs critiques, les attaques possibles
   et les contre-mesures.
3. Consulter la [charte éthique officielle](ethics.md) (extraite de [`ETHICS.md`](https://github.com/<github-username>/Watcher/blob/main/ETHICS.md)) qui encadre la
   gouvernance des données et l'utilisation responsable de Watcher.

!!! tip "Navigation rapide"
    Les onglets en haut de page regroupent l'architecture, la sécurité et l'exploitation. Utilisez la barre de
    recherche pour accéder rapidement aux journaux de conception ou aux conventions spécifiques.

## Ressources complémentaires

- Les conventions de [journalisation](logging.md) détaillent la configuration du logger JSON et les bons
  réflexes pour instrumenter le code.
- Les feuilles de route et journaux historiques sont conservés dans
  [ROADMAP.md](ROADMAP.md), [CHANGELOG.md](CHANGELOG.md) et le [journal de conception](journal/).
- Pour les règles de fusion et la gouvernance de projet, référez-vous à la
  [politique de merge](merge-policy.md).

## Prévisualiser la documentation localement

```bash
pip install -r requirements-dev.txt
mkdocs serve
```

La commande `mkdocs serve` démarre un serveur de développement à `http://127.0.0.1:8000` avec rechargement
à chaud des pages lorsque les fichiers Markdown sont modifiés.
