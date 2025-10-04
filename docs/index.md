# Documentation Watcher

Bienvenue dans l'espace de référence du projet **Watcher**, l'atelier local d'IA de programmation autonome.
Cette documentation complète le README en décrivant la structure logicielle, les mesures de sécurité et le
mode d'exploitation de la plate-forme.

## Parcours recommandé

1. Démarrer l'instance à l'aide du [Quickstart sans commande](quickstart-sans-commande.md) qui couvre la mise en service plug-and-play.
2. Comprendre la [vue d'ensemble de l'architecture](architecture.md) pour visualiser le dialogue entre
   orchestrateur, agents spécialisés et mémoire vectorielle.
3. Évaluer la surface d'attaque avec le [modèle de menaces](threat-model.md) et ses diagrammes Mermaid et
   PlantUML.
4. Consolider la gouvernance en suivant le [guide de consentement](policy-consent.md) et la [charte éthique](ethics.md).
5. Préparer les opérations récurrentes avec le [cycle de vie de l'autopilote](autopilot.md), la [vérification des artefacts](verifier-artefacts.md)
   et la [procédure de dépannage](depannage.md).

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
- Chaque release `vMAJOR.MINOR.PATCH` publie des exécutables Windows, Linux et macOS, les SBOM CycloneDX associés
  (`Watcher-sbom.json`, `Watcher-linux-sbom.json`, `Watcher-macos-sbom.json`) ainsi qu'une attestation SLSA
  (`Watcher-Setup.intoto.jsonl`). Ces artefacts facilitent l'audit de la chaîne de compilation et la conformité multi-plateformes.

## Accès à la documentation publiée

La version statique la plus récente est accessible à l'adresse
[https://francis18georges-png.github.io/Watcher/](https://francis18georges-png.github.io/Watcher/).
Elle est déployée automatiquement par le workflow GitHub Actions **Deploy MkDocs site** sur l'environnement
**github-pages** après chaque push sur `main`.

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
