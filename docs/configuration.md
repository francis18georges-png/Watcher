# Configuration

Cette page regroupe les variables d'environnement `WATCHER_*` ainsi que les
valeurs appliquées par défaut. Lorsque aucune variable n'est définie, Watcher
charge `config/settings.toml` (et éventuellement `config/settings.<profil>.toml`)
pour initialiser les sections listées ci-dessous. Les overrides peuvent être
fournis via l'environnement, un fichier `.env` ou la ligne de commande.

## Variables d'environnement `WATCHER_*`

### Profils et instrumentation

| Variable | Valeur par défaut | Description |
| --- | --- | --- |
| `WATCHER_ENV` | Non définie (profil `settings.toml`) | Sélectionne un profil explicite (`settings.<env>.toml`). |
| `WATCHER_PROFILE` | Non définie (profil `settings.toml`) | Alias historique de `WATCHER_ENV`. |
| `WATCHER_DATASETS` | Résolution automatique vers `datasets/python` | Spécifie un répertoire de jeux de données à utiliser par l'autograder. |
| `WATCHER_BLOCK_NETWORK` | Non définie | Poser `1` (ou `true`) force le sandbox à couper tout accès réseau. |
| `WATCHER_MEMORY_ENABLE_SQLCIPHER` | Désactivé | Active le chiffrement SQLCipher pour la base mémoire (`1/true/yes`). |
| `WATCHER_MEMORY_SQLCIPHER_PASSWORD` | Non définie | Mot de passe SQLCipher requis lorsque le chiffrement est activé. |

### Chemins et stockage

| Variable | Valeur par défaut | Description |
| --- | --- | --- |
| `WATCHER_PATHS__BASE_DIR` | Racine du dépôt (détectée dynamiquement) | Point d'ancrage pour la résolution des chemins relatifs. |
| `WATCHER_PATHS__DATA_DIR` | `data` | Dossier des artefacts et fichiers d'exécution. |
| `WATCHER_PATHS__DATASETS_DIR` | `datasets` | Racine des jeux de données suivis par DVC. |
| `WATCHER_PATHS__MEMORY_DIR` | `memory` | Répertoire contenant la base mémoire persistée. |
| `WATCHER_PATHS__LOGS_DIR` | `logs` | Répertoire de stockage des journaux structurés. |
| `WATCHER_DATABASE__URL` | `sqlite+aiosqlite:///./data/watcher.db` | Chaîne de connexion SQLAlchemy. |
| `WATCHER_DATABASE__POOL_SIZE` | `5` | Taille minimale du pool de connexions. |
| `WATCHER_DATABASE__POOL_TIMEOUT` | `30` | Délai d'attente (secondes) pour obtenir une connexion. |
| `WATCHER_DATABASE__POOL_RECYCLE` | `1800` | Durée (secondes) avant recyclage automatique des connexions. |
| `WATCHER_DATABASE__ECHO` | `false` | Active la journalisation SQL verbeuse lorsque positionné à `true`. |

### Interface et UX

| Variable | Valeur par défaut | Description |
| --- | --- | --- |
| `WATCHER_UI__MODE` | `Sur` | Mode d'affichage par défaut de l'interface. |
| `WATCHER_UI__THEME` | `dark` | Thème Material initial. |
| `WATCHER_UI__LANGUAGE` | `fr` | Langue principale de l'interface utilisateur. |
| `WATCHER_UI__AUTOSAVE` | `true` | Active l'enregistrement automatique de l'état. |

### LLM et embeddings

| Variable | Valeur par défaut | Description |
| --- | --- | --- |
| `WATCHER_LLM__BACKEND` | `ollama` | Backend LLM préféré. |
| `WATCHER_LLM__MODEL` | `llama3.2:3b` | Modèle chargé par défaut. |
| `WATCHER_LLM__HOST` | `127.0.0.1:11434` | Adresse de l'hôte Ollama. |
| `WATCHER_LLM__CTX` | `4096` | Taille de fenêtre de contexte à fournir au backend. |
| `WATCHER_LLM__FALLBACK_PHRASE` | `Echo` | Préfixe utilisé en mode secours. |
| `WATCHER_MEMORY__DB_PATH` | `memory/mem.db` | Localisation du fichier SQLite de mémoire vectorielle. |
| `WATCHER_MEMORY__CACHE_SIZE` | `128` | Taille du cache LRU en mémoire. |
| `WATCHER_MEMORY__EMBED_MODEL` | `nomic-embed-text` | Modèle d'embedding Ollama. |
| `WATCHER_MEMORY__EMBED_HOST` | `127.0.0.1:11434` | Adresse de service pour la génération d'embeddings. |
| `WATCHER_MEMORY__SUMMARY_MAX_TOKENS` | `512` | Limite de tokens pour les résumés automatiques. |
| `WATCHER_EMBEDDINGS__BACKEND` | `local_faiss` | Implémentation d'index vectoriel. |

### Observabilité et développement

| Variable | Valeur par défaut | Description |
| --- | --- | --- |
| `WATCHER_DEV__LOGGING` | `debug` | Niveau de log privilégié en mode développeur. |
| `WATCHER_DEV__TRACE_REQUESTS` | `false` | Active la trace HTTP détaillée en développement. |
| `WATCHER_LOGGING__CONFIG_PATH` | `None` | Fichier YAML/JSON de configuration logging (auto si non défini). |
| `WATCHER_LOGGING__FALLBACK_LEVEL` | `INFO` | Niveau appliqué lorsque aucun fichier de configuration n'est trouvé. |

### Planification et intelligence

| Variable | Valeur par défaut | Description |
| --- | --- | --- |
| `WATCHER_PLANNER__DEFAULT_PLATFORM` | `windows` | Plateforme cible par défaut pour les plans. |
| `WATCHER_PLANNER__DEFAULT_LICENSE` | `MIT` | Licence suggérée pour les nouveaux projets. |
| `WATCHER_INTELLIGENCE__MODE` | `offline` | Mode global du moteur d'intelligence. |
| `WATCHER_INTELLIGENCE__CURRICULUM` | `default` | Parcours de curriculum appliqué par défaut. |

### Apprentissage et entraînement

| Variable | Valeur par défaut | Description |
| --- | --- | --- |
| `WATCHER_LEARN__OPTIMIZER` | `adam` | Optimiseur utilisé dans la boucle d'apprentissage. |
| `WATCHER_LEARN__LEARNING_RATE` | `0.1` | Taux d'apprentissage du module `learn`. |
| `WATCHER_LEARN__REWARD_CLIP` | `1.0` | Valeur absolue maximale pour le clipping de récompense. |
| `WATCHER_TRAINING__SEED` | `42` | Graine déterministe utilisée en CI. |
| `WATCHER_TRAINING__BATCH_SIZE` | `16` | Taille de batch des tâches d'entraînement. |
| `WATCHER_TRAINING__LR` | `1e-4` | Taux d'apprentissage principal du module `training`. |

### Données, modèles et scraping

| Variable | Valeur par défaut | Description |
| --- | --- | --- |
| `WATCHER_DATA__RAW_DIR` | `datasets/raw` | Répertoire des données brutes versionnées. |
| `WATCHER_DATA__PROCESSED_DIR` | `datasets/processed` | Répertoire des données préparées. |
| `WATCHER_DATA__STEPS` | `{}` | Mapping des étapes de pipeline DVC additionnelles. |
| `WATCHER_DATASET__RAW_DIR` | `datasets/raw` | Chemin racine des jeux de données sources. |
| `WATCHER_DATASET__PROCESSED_DIR` | `datasets/processed` | Chemin racine des jeux de données traités. |
| `WATCHER_MODEL__NAME` | `watcher` | Nom logique du modèle embarqué. |
| `WATCHER_MODEL__REVISION` | `0.1` | Numéro de révision du modèle. |
| `WATCHER_MODEL__PRECISION` | `fp16` | Format numérique privilégié. |
| `WATCHER_SCRAPER__RATE_PER_DOMAIN` | `1.0` | Débit cible des requêtes par domaine. |
| `WATCHER_SCRAPER__CONCURRENCY` | `6` | Nombre maximum de requêtes parallèles. |
| `WATCHER_SCRAPER__USER_AGENT` | `WatcherBot/1.0 (+https://github.com/francis18georges-png/Watcher)` | En-tête `User-Agent` fourni par défaut. |

### Critiques et sandbox

| Variable | Valeur par défaut | Description |
| --- | --- | --- |
| `WATCHER_CRITIC__POLITE_KEYWORDS` | `("please", "thank you", "merci", "s'il vous plaît", "s'il vous plait", "bonjour", "salut")` | Liste de mots-clés détectés par le module `Critic`. |
| `WATCHER_SANDBOX__CPU_SECONDS` | `60` | Quota CPU maximum par processus sandboxé. |
| `WATCHER_SANDBOX__MEMORY_BYTES` | `268435456` (256 MiB) | Limite mémoire par processus. |
| `WATCHER_SANDBOX__TIMEOUT_SECONDS` | `30.0` | Délai maximum d'exécution mur. |

## Compatibilité CPU / GPU

| Plateforme | Support CPU | Support GPU | Notes |
| --- | --- | --- | --- |
| Linux x86_64 | ✅ | ✅ (CUDA/ROCm via PyTorch optionnel) | Pipeline CI complet et binaire PyInstaller Linux. |
| macOS (x86_64 / arm64) | ✅ | ⚠️ (accélération Metal non testée) | Fonctionne sur Python natif; GPU dépend de PyTorch. |
| Windows x86_64 | ✅ | ⚠️ (CUDA optionnel) | Installeur PyInstaller officiel; GPU utilisable si PyTorch CUDA est présent. |

Les traitements Watcher restent fonctionnels sur CPU uniquement. L'exploitation du
GPU dépend du support proposé par les bibliothèques optionnelles (principalement
PyTorch installée avec `sentence-transformers`).
