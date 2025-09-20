# Documentation Watcher

Bienvenue dans l'espace de référence du projet **Watcher**, l'atelier local d'IA de programmation autonome.
Cette documentation complète le README en décrivant la structure logicielle, les mesures de sécurité et le
mode d'exploitation de la plate-forme.

## Installer Watcher

- **pipx** : `pipx install watcher` déploie la CLI dans un environnement isolé et facilite les mises à jour
  (`pipx upgrade watcher`).
- **pip** : `python -m pip install watcher` installe le package dans l'environnement virtuel actif.
- **Windows** : un installeur signé reste proposé via les releases GitHub pour ceux qui préfèrent un
  exécutable autonome (voir la procédure détaillée dans le README).

## Parcours recommandé

1. Comprendre la [vue d'ensemble de l'architecture](architecture.md) pour visualiser le dialogue entre
   orchestrateur, agents spécialisés et mémoire vectorielle.
2. Évaluer la surface d'attaque avec le [modèle de menaces](threat-model.md) et ses diagrammes Mermaid et
   PlantUML.
3. Approfondir la gouvernance via la [charte éthique](ethics.md) et les politiques opérationnelles listées ci-dessous.

!!! tip "Navigation rapide"
    Les onglets Material en haut de page regroupent l'architecture, la sécurité et l'exploitation. Utilisez la barre de
    recherche pour accéder directement aux journaux de conception ou aux procédures de déploiement.

## Architecture et sécurité

- La page [architecture](architecture.md) cartographie les composants principaux (orchestrateur, agents, mémoire, QA)
  et illustre leurs interactions par diagrammes Mermaid et PlantUML.
- Le [modèle de menaces](threat-model.md) présente les actifs critiques, la cartographie des risques et la séquence de
  réponse à incident.
- Les conventions de [journalisation](logging.md) détaillent la configuration du logger JSON et les réflexes
  d'observabilité à conserver hors ligne.

## Exploitation et références

- Les feuilles de route et journaux historiques sont conservés dans [ROADMAP.md](ROADMAP.md),
  [CHANGELOG.md](CHANGELOG.md) et le [journal de conception](journal/).
- Pour les règles de fusion et la gouvernance du dépôt, référez-vous à la [politique de merge](merge-policy.md).
- Chaque release `vMAJOR.MINOR.PATCH` publie un installeur Windows signé, un SBOM CycloneDX (`Watcher-sbom.json`) et une
  attestation SLSA (`Watcher-Setup.intoto.jsonl`). Ces artefacts facilitent l'audit de la chaîne de compilation.

## Accès à la documentation publiée

Lorsque le workflow GitHub Actions **Deploy MkDocs site** est exécuté sur la branche `main`, la version statique la plus
récente est disponible à l'adresse : `https://<github-username>.github.io/Watcher/` (remplacez `<github-username>` par
votre compte ou organisation GitHub).

!!! info "URL personnalisée"
    Si un domaine personnalisé est configuré, mettez à jour le champ `site_url` dans `mkdocs.yml` et ajoutez un fichier
    `CNAME` dans `docs/` pour refléter la nouvelle adresse.

## Prévisualiser la documentation localement

```bash
pip install -r requirements-dev.txt
mkdocs serve
```

La commande `mkdocs serve` démarre un serveur de développement à `http://127.0.0.1:8000` avec rechargement à chaud des
pages lorsque les fichiers Markdown sont modifiés.
