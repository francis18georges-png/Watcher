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
- Chaque release `vMAJOR.MINOR.PATCH` publie un installeur Windows signé, un SBOM CycloneDX (`Watcher-sbom.json`) et une
  provenance SLSA (`Watcher-Setup.intoto.jsonl`). Ces artefacts permettent de vérifier l'intégrité du binaire et d'auditer
  la liste des dépendances Python utilisées lors du build. Le workflow de release dépose également un artefact
  `release-verification` dans l'onglet **Artifacts** de GitHub Actions pour télécharger rapidement le SBOM et la
  provenance depuis un run donné.

### Vérifier une release

1. Récupérez `Watcher-Setup.zip`, `Watcher-sbom.json` et `Watcher-Setup.intoto.jsonl` depuis la page de release GitHub
   ou l'artefact `release-verification` associé au run.
2. Installez `cyclonedx-bom` pour valider ou convertir le SBOM au format désiré, puis inspectez son contenu :

   ```powershell
   python -m pip install cyclonedx-bom
   jq '.components[] | {name, version}' Watcher-sbom.json
   ```

   Les sous-commandes exposées par `cyclonedx-bom --help` permettent de valider la structure du fichier ou de le convertir
   vers d'autres formats CycloneDX.

3. Vérifiez la provenance SLSA et la signature du binaire :

   ```bash
   slsa-verifier verify-artifact Watcher-Setup.zip \
     --provenance Watcher-Setup.intoto.jsonl \
     --source-uri github.com/<organisation>/Watcher \
     --source-tag vMAJOR.MINOR.PATCH
   cosign verify-blob --bundle Watcher-Setup.zip.sigstore Watcher-Setup.zip
   ```

   Les commandes ci-dessus garantissent que l'installeur provient du dépôt officiel et qu'il a été généré par le
   pipeline automatisé attendu.

## Prévisualiser la documentation localement

```bash
pip install -r requirements-dev.txt
mkdocs serve
```

La commande `mkdocs serve` démarre un serveur de développement à `http://127.0.0.1:8000` avec rechargement
à chaud des pages lorsque les fichiers Markdown sont modifiés.
