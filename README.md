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

## Auto-amélioration

Lors de la routine `auto_improve`, Watcher calcule une récompense
composite utilisée pour ajuster sa stratégie d'apprentissage :

- 70 % provient du taux de réussite du QualityGate (linters, tests, etc.).
- 30 % provient de la note moyenne des retours utilisateurs (échelle 0‑5
  normalisée sur 0‑1).

Cette récompense est transmise à `Learner.update_policy` pour influencer
les décisions futures.

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

## Éthique et traçabilité

Les actions du système sont journalisées via le module standard `logging`. Les erreurs et décisions importantes sont ainsi consignées pour audit ou débogage.

Les contenus générés peuvent être conservés dans une base SQLite par le composant de mémoire (`app/core/memory.py`). Cette base stocke textes et métadonnées afin d'offrir un historique local des opérations.

Pour un aperçu détaillé des principes éthiques et des limites d'utilisation, consultez [ETHICS.md](ETHICS.md).

