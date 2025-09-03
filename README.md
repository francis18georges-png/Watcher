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

## Configuration

Les principaux réglages se trouvent dans `config/settings.toml` :

- `[llm]` : backend (`backend`) et modèle (`model`) pour le client LLM.
- `[dev.test_timeout_sec]` : délai maximal des tests et linters.
- `[memory.db_path]` : chemin de la base SQLite des souvenirs de l'agent.
- `[memory.top_k]` : nombre de résultats retournés lors d'une recherche.

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

## Structure du dépôt

- `app/` : moteur principal, mémoire, benchmarks et interface utilisateur.
- `datasets/` : jeux d'entraînement Python (`fib`, `fizzbuzz`, `is_prime`).
- `config/` : paramètres et règles de sécurité (`semgrep`).

## Sécurité

Sandbox d'exécution confinée, tests et linters obligatoires avant adoption de code.
Semgrep utilise un fichier de règles local (`config/semgrep.yml`), aucun accès réseau requis.

