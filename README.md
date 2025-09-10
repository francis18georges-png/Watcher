# Watcher

Atelier local d'IA de programmation autonome (offline par défaut).
Mémoire vectorielle, curriculum adaptatif, A/B + bench et quality gate sécurité.

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
   pip install black ruff pytest mypy bandit semgrep
   ```

    Sur Windows, le script `installer.ps1` installe automatiquement toutes ces dépendances.

Les fichiers d'environnement (`*.env`), les journaux (`*.log`) et les environnements virtuels (`.venv/`) sont ignorés par Git afin d'éviter la mise en version de données sensibles ou temporaires.

## Utilisation

### Interface graphique

Sous Windows :

1. `./installer.ps1`
2. `./run.ps1`

### Ligne de commande

```bash
python -m app.ui.main
```

## Tests & Qualité

Exécuter les vérifications locales avant de proposer du code :

```bash
make check
```

Les commandes exécutées par `make check` sont :

```bash
ruff check .
black --check .
mypy .
bandit -q -r . -c bandit.yml
semgrep --quiet --error --config config/semgrep.yml .
pytest -q
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

## Éthique et traçabilité

Les actions du système sont journalisées via le module standard `logging`. Les erreurs et décisions importantes sont ainsi consignées pour audit ou débogage.

Les contenus générés peuvent être conservés dans une base SQLite par le composant de mémoire (`app/core/memory.py`). Cette base stocke textes et métadonnées afin d'offrir un historique local des opérations.

Pour un aperçu détaillé des principes éthiques et des limites d'utilisation, consultez [ETHICS.md](ETHICS.md).

