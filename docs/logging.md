# Conventions de logging

Le projet utilise un logging structuré au format JSON pour toutes les sorties.

## Configuration

Le module `app.core.logging_setup` centralise la configuration du logging et
fournit un logger unique nommé ``watcher``.  Il lit un fichier YAML
`config/logging.yml` ou la variable d'environnement `LOGGING_CONFIG_PATH`. Les
messages sont enrichis d'un identifiant de requête (`request_id`) lorsqu'il est
défini via `logging_setup.set_request_id()`.

Pour activer le logging, appelez `logging_setup.configure()` au démarrage de
votre script puis obtenez un logger via `logging_setup.get_logger(__name__)`.
Tous les loggers enfants ainsi créés propagent leurs messages vers le logger
central ``watcher``.

## Niveaux

- `logger.info` pour les évènements ordinaires.
- `logger.warning` pour les situations anormales ou les dégradations de
  service.
- `logger.error` ou `logger.exception` pour les erreurs.

Les messages sont sérialisés en JSON et sont visibles sur la sortie standard
ainsi que dans le fichier `watcher.log`.
