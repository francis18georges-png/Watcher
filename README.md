# Watcher

Atelier local d'IA de programmation autonome (offline par défaut).
Mémoire vectorielle, curriculum adaptatif, A/B + bench et quality gate sécurité.

## Installation

1. Cloner ce dépôt.
2. Créer un environnement Python 3.12 puis installer les outils de développement :

   ```bash
   pip install black ruff pytest
   ```

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
ruff check .
black --check .
mypy .
bandit -q -r .
semgrep --quiet --error --config config/semgrep.yml .
pytest -q
```

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

## Structure du dépôt

- `app/` : moteur principal, mémoire, benchmarks et interface utilisateur.
- `datasets/` : jeux d'entraînement Python (`fib`, `fizzbuzz`, `is_prime`).
- `config/` : paramètres et règles de sécurité (`semgrep`).

## Sécurité

Sandbox d'exécution confinée, tests et linters obligatoires avant adoption de code.
Semgrep utilise un fichier de règles local (`config/semgrep.yml`), aucun accès réseau requis.

