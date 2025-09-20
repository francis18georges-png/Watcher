# Watcher

![Benchmark status badge](metrics/performance_badge.svg)

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

## Benchmarks

Le script `python -m app.core.benchmark run` exécute trois scénarios représentatifs
(`planner_briefing`, `learner_update`, `metrics_tracking`) en mesurant le temps
et l'utilisation mémoire via `tracemalloc`. Chaque exécution ajoute une entrée
historique dans `metrics/benchmarks.jsonl`, met à jour le résumé courant dans
`metrics/benchmarks-latest.json` et régénère le badge `metrics/performance_badge.svg`.

Les seuils de non-régression sont définis dans `metrics/bench_thresholds.json`.
Pour vérifier qu'ils sont respectés, utilisez :

```bash
python -m app.core.benchmark run --samples 5 --warmup 1
python -m app.core.benchmark check --update-badge
```

La CI (`ci.yml`) exécute automatiquement ces commandes et échoue si un scénario
dépasse l'un des seuils configurés.

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

## Mémoire et migrations

Le module `Memory` s'appuie sur SQLite et exécute automatiquement les
migrations [Alembic](https://alembic.sqlalchemy.org/) au démarrage pour garantir
la présence du schéma attendu. Chaque connexion active `journal_mode=WAL`,
`foreign_keys=ON`, `busy_timeout=5000`, `secure_delete=ON` et tente d'exposer
FTS5 lorsque la compilation de SQLite le permet.

### Activer le chiffrement SQLCipher

Watcher détecte automatiquement la prise en charge de
[SQLCipher](https://www.zetetic.net/sqlcipher/). Lorsque le binaire `sqlite3`
est compilé avec cette extension, vous pouvez chiffrer la base mémoire en
définissant les variables d'environnement suivantes avant de lancer
l'application :

```bash
export WATCHER_MEMORY_ENABLE_SQLCIPHER=1
export WATCHER_MEMORY_SQLCIPHER_PASSWORD="motdepasse-solide"
```

Si SQLCipher n'est pas détecté ou si le mot de passe est absent, Watcher
revient automatiquement à un stockage non chiffré et inscrit un avertissement
dans les journaux pour faciliter le diagnostic.

## Utilisation

### Interface graphique

Sous Windows :

1. `./installer.ps1 -SkipOllama` pour installer l'environnement local sans télécharger les modèles Ollama.
   Omettez l'option `-SkipOllama` pour déclencher l'installation complète lorsque vous avez besoin des modèles.
2. `./run.ps1`

Dans un environnement sans serveur d'affichage (CI, sessions distantes), forcez le mode headless en vidant `DISPLAY`
avant d'exécuter le lanceur :

```powershell
$env:DISPLAY = ""
./run.ps1
```

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
Bandit, Semgrep, Codespell ainsi que le correcteur `end-of-file-fixer`. Après avoir installé les dépendances de
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

## Gouvernance des contributions

- Les modèles disponibles dans `.github/ISSUE_TEMPLATE/` ajoutent automatiquement
  les labels `needs-triage` et `bug`/`enhancement` selon le type d'issue. Le
  modèle de discussion sous `.github/DISCUSSION_TEMPLATE/` applique le label
  `discussion`.
- Le fichier `.github/CODEOWNERS` assigne les revues aux équipes responsables.
  Adaptez les alias (`@WatcherOrg/...`) à votre organisation GitHub.
- Avant toute fusion, assurez-vous que `nox -s lint typecheck security tests
  build` est vert sur la CI et qu'au moins un CODEOWNER a approuvé la PR. Un
  mainteneur peut ensuite poser le label `automerge` qui déclenchera la fusion
  automatique.

Pour plus de détails (priorités, gestion du label `blocked`, etc.), consultez
`docs/merge-policy.md`.

## Reproductibilité

Un utilitaire `set_seed` permet de fixer la graine aléatoire pour Python,
NumPy et, si disponible, PyTorch. Le fichier de configuration `config/settings.toml`
contient un paramètre `seed` dans la section `[training]` qui peut être adapté
pour garantir des exécutions déterministes.

La commande CLI `watcher` applique automatiquement cette graine dès son
démarrage afin d'initialiser toutes les bibliothèques stochastiques. Une
option `--seed` est disponible pour surcharger ponctuellement la valeur par
défaut définie dans `config/settings.toml`. Pour les exécutions automatisées,
exportez `PYTHONHASHSEED` ainsi que `WATCHER_TRAINING__SEED` avant de lancer
Nox ou vos scripts afin d'aligner l'environnement avec la configuration
versionnée.

## Données

La pipeline [DVC](https://dvc.org/) décrite dans `dvc.yaml` prépare et valide le
jeu de données linéaire utilisé par `train.py` :

- `prepare-data` lit `datasets/raw/simple_linear.csv`, applique les paramètres
  définis dans `params.yaml` (graine, taille d'échantillon) et génère
  `datasets/processed/simple_linear.csv`.
- `validate-data` enchaîne trois scripts de validation (`scripts/validate_*`)
  pour vérifier le schéma, la taille et le hachage du fichier produit.

Les hyperparamètres d'entraînement ainsi que les contraintes de validation sont
centralisés dans `params.yaml` (syntaxe JSON valide YAML pour éviter d'ajouter
une dépendance d'analyse). Pour exécuter la pipeline complète et garantir
que les validations passent, lancez :

```bash
dvc repro validate-data
```

Un remote S3 nommé `storage` est configuré dans `.dvc/config` (URL
`s3://watcher-artifacts`). Renseignez vos identifiants AWS via les variables
d'environnement standard (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
éventuellement `AWS_SESSION_TOKEN`) ou un profil configuré, puis synchronisez
les artefacts DVC avec :

```bash
# envoyer les données préparées sur le bucket
dvc push
# récupérer les dernières versions depuis le stockage
dvc pull
```

Vous pouvez remplacer le bucket par un autre en adaptant la configuration du
remote :

```bash
dvc remote modify storage url s3://votre-bucket
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

Watcher peut charger une configuration de journalisation personnalisée depuis un fichier YAML **ou** JSON. Définissez la
variable d'environnement `LOGGING_CONFIG_PATH` pour indiquer le chemin du fichier :

```bash
# YAML par défaut
export LOGGING_CONFIG_PATH=./config/logging.yml

# Variante JSON équivalente
export LOGGING_CONFIG_PATH=./config/logging.json
```

Les deux fichiers décrivent un pipeline avec un formatter JSON et un filtre d'échantillonnage (`SamplingFilter`). Adaptez le
paramètre `sample_rate` pour contrôler la proportion de messages conservés :

```yaml
filters:
  sampling:
    (): app.core.logging_setup.SamplingFilter
    sample_rate: 0.1  # ne journalise qu'environ 10 % des messages
```

Le module `app.core.logging_setup` expose également `set_trace_context(trace_id, sample_rate)` pour propager dynamiquement ces
valeurs dans les journaux structurés.

Si `LOGGING_CONFIG_PATH` est absent ou que le fichier fourni est introuvable, le fichier `config/logging.yml` inclus dans le
projet est utilisé. En dernier recours, Watcher applique la configuration basique de Python (`logging.basicConfig`) avec le
niveau `INFO`.

## Éthique et traçabilité

Les actions du système sont journalisées via le module standard `logging`. Les erreurs et décisions importantes sont ainsi consignées pour audit ou débogage.

Les contenus générés peuvent être conservés dans une base SQLite par le composant de mémoire (`app/core/memory.py`). Cette base stocke textes et métadonnées afin d'offrir un historique local des opérations.

Pour un aperçu détaillé des principes éthiques et des limites d'utilisation, consultez [ETHICS.md](ETHICS.md).

