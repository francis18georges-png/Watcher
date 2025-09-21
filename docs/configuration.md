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

## Qualité et automatisation

Les sessions Nox et la matrice Python du pipeline CI respectent la variable d'environnement `WATCHER_NOX_PYTHON`. Elle accepte une liste de versions séparées par des virgules et/ou des espaces (par exemple `"3.10, 3.11 3.12"`). Lorsque la variable est absente ou ne contient aucune version, la valeur par défaut reste `3.12`.
