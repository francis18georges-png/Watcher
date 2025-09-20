# Watcher

Atelier local d'IA de programmation autonome (offline par défaut).
Mémoire vectorielle, curriculum adaptatif, A/B + bench et quality gate sécurité.

## Documentation

La documentation technique est générée avec [MkDocs Material](https://squidfunk.github.io/mkdocs-material/)
et déployée automatiquement sur GitHub Pages : https://<github-username>.github.io/Watcher/.

Pour la prévisualiser localement :

```bash
pip install -r requirements-dev.txt
mkdocs serve
```

Le workflow GitHub Actions `deploy-docs.yml` publie le site statique à chaque push sur `main`.

## Installation

1. Cloner ce dépôt.
2. Créer et activer un environnement Python 3.12 :

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/macOS
   .venv\Scripts\activate   # Windows
   ```

3. Installer les dépendances :

   ```bash
   pip install -r requirements.txt
   ```

   Pour activer les quotas d'exécution sur Windows, installez
   également la dépendance optionnelle `pywin32` :

   ```bash
   pip install pywin32  # facultatif
   ```

4. Installer les outils de développement :

    ```bash
    pip install -r requirements-dev.txt
    ```

    Ce fichier fixe des versions précises afin d'assurer une installation reproductible.

    Sur Windows, le script `installer.ps1` installe automatiquement toutes ces dépendances.

Les fichiers d'environnement (`*.env`), les journaux (`*.log`) et les environnements virtuels (`.venv/`) sont ignorés par Git afin d'éviter la mise en version de données sensibles ou temporaires.

## Environnement de développement

Un dossier `.devcontainer/` est fourni pour disposer d'un environnement prêt à l'emploi
dans VS Code ou GitHub Codespaces. Il utilise l'image Python 3.12 officielle,
préconfigure les caches `pip` et `DVC` sur des volumes persistants et installe
automatiquement les dépendances du projet ainsi que les hooks `pre-commit`.

Pour ouvrir le projet dans un devcontainer :

1. Installer l'extension [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers).
2. Dans VS Code, exécuter la commande **Dev Containers: Reopen in Container**.
3. Attendre la fin du script `.devcontainer/post-create.sh` qui prépare l'environnement.

Les caches partagés accélèrent notamment les installations pip et la synchronisation DVC
entre plusieurs sessions Codespaces.

## Compatibilité NumPy

Watcher tente d'utiliser la bibliothèque `numpy` lorsqu'elle est disponible.
Si son import échoue, un module de repli léger `numpy_stub` est utilisé à la
place. Les modules Python importent donc `np` via `from app.utils import np`
pour bénéficier automatiquement de ce mécanisme.

## Utilisation

### Interface graphique

Sous Windows :

1. `./installer.ps1`
2. `./run.ps1`

### Ligne de commande

```bash
python -m app.ui.main
```

### Générer une CLI Python

Un utilitaire `create_python_cli` (dans `app.tools.scaffold`) permet de
générer un squelette de projet sous `app/projects/<nom>`. Passer
`force=True` écrase les fichiers existants sans demande de confirmation.

## Plugins

Watcher peut être étendu par des plugins implémentant l'interface
`Plugin` définie dans `app/tools/plugins`. Chaque plugin expose un
attribut `name` ainsi qu'une méthode `run()` retournant un message à
l'utilisateur.

Deux mécanismes de découverte sont supportés :

- déclaration explicite dans le fichier `plugins.toml` ;
- [entry points](https://packaging.python.org/en/latest/specifications/entry-points/)
  Python via le groupe `watcher.plugins` recherchés par
  `discover_entry_point_plugins()`.

Pour enregistrer un plugin via les entry points dans un projet
emballé, ajoutez par exemple dans votre `pyproject.toml` :

```toml
[project.entry-points."watcher.plugins"]
hello = "monpaquet.monmodule:MonPlugin"
```

Un exemple minimal est fourni dans `app/tools/plugins/hello.py`.

## Tests & Qualité

Watcher s'appuie désormais sur [Nox](https://nox.thea.codes/) pour unifier les
linters, l'analyse statique, les tests et la construction du package :

```bash
nox -s lint typecheck security tests
```

Les sessions peuvent également être exécutées individuellement (`nox -s lint`,
`nox -s tests`, etc.) et une étape `nox -s build` génère les artefacts wheel et
sdist.

Pour automatiser les corrections, la cible `make format` applique Ruff (lint
et formattage) puis Black, et `make check` délègue dorénavant à Nox.

### Hooks pre-commit

Le dépôt inclut une configuration `pre-commit` regroupant Ruff, Black, mypy,
Bandit, Semgrep et Codespell. Après avoir installé les dépendances de
développement, activez les hooks localement :

```bash
pre-commit install
```

Vous pouvez ensuite valider l'ensemble des fichiers :

```bash
pre-commit run --all-files
```

La configuration `bandit.yml` exclut notamment les répertoires `.git`, `datasets`,
`.venv`, `build`, `dist` et `*.egg-info` afin d'éviter l'analyse de contenus
non pertinents.

## Reproductibilité

Un utilitaire `set_seed` permet de fixer la graine aléatoire pour Python,
NumPy et, si disponible, PyTorch. Le fichier de configuration `config/settings.toml`
contient un paramètre `seed` dans la section `[training]` qui peut être adapté
pour garantir des exécutions déterministes.

## Données

Les jeux de données localisés dans `datasets/raw` et `datasets/processed` sont
gérés avec [DVC](https://dvc.org/). Exemple de cycle de travail :

```bash
# enregistrer les modifications locales
dvc add datasets/raw datasets/processed
# sauvegarder dans le cache DVC
dvc commit
# récupérer les données depuis le stockage distant
dvc pull
```

### Collecte

Un module de scraping asynchrone (`app/data/scraper.py`) permet de
collecter des pages web en parallèle tout en les mettant en cache sur
disque. Les téléchargements déjà effectués ne sont pas relancés, ce qui
accélère les itérations et facilite la reprise après interruption.

## Structure du dépôt

- `app/` : moteur principal, mémoire, benchmarks et interface utilisateur.
- `datasets/` : jeux d'entraînement Python (`fib`, `fizzbuzz`, `is_prime`).
- `config/` : paramètres et règles de sécurité (`semgrep`).

## Sécurité

Sandbox d'exécution confinée, tests et linters obligatoires avant adoption de code.
Semgrep utilise un fichier de règles local (`config/semgrep.yml`), aucun accès réseau requis.

## Confidentialité

Watcher fonctionne hors ligne par défaut et n'envoie aucune donnée vers l'extérieur.
Les journaux comme les contenus mémorisés restent sur l'environnement local et peuvent être effacés par l'utilisateur.

## Configuration des logs

Watcher peut charger une configuration de journalisation personnalisée depuis un fichier YAML. Définissez la variable d'environnement `LOGGING_CONFIG_PATH` pour indiquer le chemin du fichier :

```bash
export LOGGING_CONFIG_PATH=/chemin/vers/logging.yml
```

Si cette variable est absente ou que le fichier fourni est introuvable, le fichier `config/logging.yml` inclus dans le projet est utilisé. En dernier recours, Watcher applique la configuration basique de Python (`logging.basicConfig`) avec le niveau `INFO`.

## Éthique et traçabilité

Les actions du système sont journalisées via le module standard `logging`. Les erreurs et décisions importantes sont ainsi consignées pour audit ou débogage.

Les contenus générés peuvent être conservés dans une base SQLite par le composant de mémoire (`app/core/memory.py`). Cette base stocke textes et métadonnées afin d'offrir un historique local des opérations.

Pour un aperçu détaillé des principes éthiques et des limites d'utilisation, consultez [ETHICS.md](ETHICS.md).

