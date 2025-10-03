# Configuration

La configuration de Watcher repose sur un tronc commun défini dans `config/settings.toml` et des "profils" facultatifs chargés dynamiquement en fonction de l'environnement. Les valeurs peuvent être redéfinies via des variables d'environnement préfixées par `WATCHER_`.

## Profils et instrumentation

Le tableau ci-dessous récapitule les principaux interrupteurs liés aux profils et à l'instrumentation.

| Élément | Variable(s) | Valeurs attendues | Effet | Valeur par défaut |
| --- | --- | --- | --- | --- |
| Sélection de profil | `WATCHER_ENV`, `WATCHER_PROFILE` | Nom de profil (`dev`, `prod`, `staging`…) | Charge `config/settings.<profil>.toml` s'il existe ; sinon le profil est ignoré. | *(aucune)* |
| Traçage HTTP détaillé | `WATCHER_DEV__TRACE_REQUESTS` | Booléen (`true`/`false`) | Lorsque `true`, les requêtes HTTP émises par l'application sont journalisées en détail pour faciliter le debugging. | `false` |
| Blocage réseau sandbox | `WATCHER_BLOCK_NETWORK` | `"0"` (désactivé), `"1"` (activé) | Injecté par `app.core.sandbox.run` et le lanceur de plugins. Seule la valeur `"1"` active le blocage réseau ; toute autre valeur laisse l'accès réseau autorisé. | `"0"` |

Les profils permettent d'adapter rapidement les limites ou le niveau de verbosité selon l'environnement d'exécution. Les commutateurs d'instrumentation garantissent quant à eux un cadre d'observabilité cohérent (traçabilité, réseau) quelle que soit la manière de lancer Watcher (processus principal, sandbox ou plugin).

## Backend LLM et mémoire locale

| Section | Clé | Description | Valeur par défaut |
| --- | --- | --- | --- |
| `[llm]` | `backend` | Sélection du moteur (`llama.cpp` pour offline, `ollama` pour un service réseau). | `llama.cpp` |
| `[llm]` | `model_path` | Chemin du fichier GGUF chargé par `llama.cpp`. | `models/llm/smollm-135m-instruct.Q4_0.gguf` |
| `[llm]` | `temperature` / `max_tokens` | Paramètres de génération locale. | `0.2` / `256` |
| `[memory]` | `embed_model_path` | Répertoire contenant le modèle SentenceTransformer exporté par `setup-local-models.sh`. | `models/embeddings/all-MiniLM-L6-v2` |
| `[memory]` | `retention_limit` | Nombre maximal d'entrées conservées par type dans la base SQLite `memory/mem.db`. | `4096` |

Les variables d'environnement correspondantes (`WATCHER_LLM__*`, `WATCHER_MEMORY__*`) peuvent rediriger le CLI vers d'autres modèles (chemin absolu, montage réseau, etc.).

## Qualité et automatisation

Les sessions Nox et la matrice Python du pipeline CI respectent la variable d'environnement `WATCHER_NOX_PYTHON`. Elle accepte une liste de versions séparées par des virgules et/ou des espaces (par exemple `"3.10, 3.11 3.12"`). Lorsque la variable est absente ou ne contient aucune version, la valeur par défaut couvre explicitement les interpréteurs pris en charge (`3.10`, `3.11` et `3.12`).

Les pull requests provenant d'un fork n'ont pas accès aux identifiants AWS nécessaires au `dvc pull`. La CI journalise un
avertissement et saute les étapes de récupération et de vérification des artefacts dans ce cas. Les branches internes
continuent d'échouer si un artefact manque ou est corrompu.

### Accès aux artefacts DVC

Les branches protégées doivent disposer des secrets GitHub suivants afin que la CI accède au remote `s3://watcher-artifacts` :

| Secret | Description |
| --- | --- |
| `AWS_ACCESS_KEY_ID` | Identifiant de la clé d'accès disposant des droits `GetObject`/`PutObject` sur le bucket `watcher-artifacts`. |
| `AWS_SECRET_ACCESS_KEY` | Secret associé à la clé précédente. |
| `AWS_DEFAULT_REGION` | Région AWS du bucket (par exemple `eu-west-1`). |
| `AWS_SESSION_TOKEN` *(optionnel)* | Jeton temporaire pour des identifiants STS. Le laisser vide pour des clés longues durées. |

Le workflow GitHub Actions configure automatiquement ces identifiants via `aws-actions/configure-aws-credentials@v4` avant de
lancer `dvc pull`. Un `dvc status --cloud` systématique vérifie ensuite la parité entre le dépôt local et le remote. Tout échec
sur ces étapes bloque la CI sur les branches des mainteneurs tant que les artefacts n'ont pas été corrigés ou régénérés.
