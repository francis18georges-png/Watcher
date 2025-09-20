# Documentation Watcher

Bienvenue dans l'espace de référence du projet **Watcher**, l'atelier local d'IA de programmation autonome.
Cette documentation complète le README et les guides techniques du dépôt en présentant la structure du
système, son modèle de sécurité et les pratiques d'exploitation.

## Organisation

- Une vue d'ensemble de l'[architecture](architecture.md) décrit comment les composants principaux
  coopèrent (agents, curriculum adaptatif, mémoire vectorielle, bancs d'essais et journalisation).
- Le [modèle de menaces](threat-model.md) recense les actifs critiques, les risques majeurs et les
  mesures de mitigation mises en place.
- Les conventions de [journalisation](logging.md) détaillent la configuration du logger JSON et les bons
  réflexes pour instrumenter le code.
- Les feuilles de route et journaux historiques sont conservés dans
  [ROADMAP.md](ROADMAP.md), [CHANGELOG.md](CHANGELOG.md) et le [journal de conception](journal/).

!!! tip "Charte éthique"
    La charte éthique du projet est publiée avec la documentation : consultez la page
    [Engagements éthiques](ethics.md) pour la parcourir ou la télécharger.

## Prévisualiser la documentation localement

```bash
pip install -r requirements-dev.txt
mkdocs serve
```

La commande `mkdocs serve` démarre un serveur de développement à `http://127.0.0.1:8000` avec rechargement
à chaud des pages lorsque les fichiers Markdown sont modifiés.
