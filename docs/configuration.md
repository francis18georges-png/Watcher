# Configuration et variables d'environnement

Watcher s'appuie sur des variables `WATCHER_*` pour adapter son comportement sans
modifier les fichiers TOML. Toutes les variables listées ci-dessous peuvent être
renseignées dans l'environnement de la machine, dans un fichier `.env` pris en
charge par `pydantic-settings` ou via des secrets CI/CD. Les valeurs indiquées
comme défaut correspondent à la configuration de base (`config/settings.toml`).

## Profils et instrumentation

`WATCHER_ENV` / `WATCHER_PROFILE`
: Sélectionne un profil dédié (par exemple `dev` ou `prod`) qui complète le
  socle `config/settings.toml` avec `config/settings.<profil>.toml`. À défaut,
  l'application ne charge que la configuration de base.

`WATCHER_TRAINING__SEED`
: Définit la graine utilisée pour les composants d'apprentissage. La valeur
  par défaut est `42`, ce qui garantit la reproductibilité lorsque la variable
  n'est pas forcée.

`WATCHER_NOX_PYTHON`
: Liste des versions Python ciblées par les sessions Nox et les workflows CI.
  Par défaut, l'automatisation s'exécute sur Python `3.12`, ce qui aligne les
  environnements locaux et distants ; surcharger la variable permet de tester
  plusieurs versions en parallèle.

## Données et stockage

`WATCHER_DATASETS`
: Chemin vers le répertoire des jeux d'entraînement. Si elle est absente, la
  plateforme résout automatiquement `datasets/python` livré avec le projet.

`WATCHER_DATABASE__URL`
: URL SQLAlchemy de la base principale (défaut : `sqlite+aiosqlite:///./data/watcher.db`).

`WATCHER_DATABASE__POOL_SIZE`
: Taille minimale du pool de connexions pour la base de données (défaut : `5`).

## Mémoire et persistance sécurisée

`WATCHER_MEMORY_ENABLE_SQLCIPHER`
: Active le chiffrement SQLCipher de la mémoire vectorielle lorsqu'elle vaut
  `1`, `true`, `yes` ou `on`. Par défaut, le chiffrement est inactif.

`WATCHER_MEMORY_SQLCIPHER_PASSWORD`
: Secret utilisé pour initialiser la clé SQLCipher. Il doit être défini dès que
  `WATCHER_MEMORY_ENABLE_SQLCIPHER` est actif, faute de quoi la base restera en
  clair.

## Interface et intelligence artificielle

`WATCHER_UI__MODE`
: Mode d'affichage privilégié par l'interface utilisateur (défaut : `Sur`).

`WATCHER_LLM__BACKEND`
: Backend de génération LLM (défaut : `ollama`).

`WATCHER_LLM__MODEL`
: Identifiant du modèle LLM à invoquer (défaut : `llama3.2:3b`).

## Exécution sandbox et plugins

`WATCHER_SANDBOX__TIMEOUT_SECONDS`
: Délai maximal (en secondes) accordé à une exécution sandbox (défaut : `30`).

`WATCHER_BLOCK_NETWORK`
: Quand la variable vaut `1`, les plugins Python sont lancés sans accès réseau,
  ce qui durcit l'isolation des tâches automatisées.

## Documentation et métadonnées

`WATCHER_DOCS_URL`
: URL publique du site MkDocs généré ; laissée vide, elle retombe sur la valeur
  fournie par GitHub Pages.

`WATCHER_REPO_URL`
: Lien vers le dépôt GitHub exposé dans la navigation de la documentation.
