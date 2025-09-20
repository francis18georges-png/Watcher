# Conventions de logging

Le projet utilise un logging structuré au format JSON pour toutes les sorties.

## Configuration

Le module `app.core.logging_setup` centralise la configuration du logging et
fournit un logger unique nommé ``watcher``.  Il lit un fichier YAML ou JSON et
expose deux configurations prêtes à l'emploi : `config/logging.yml` et
`config/logging.json`.  Changez de variante en définissant la variable
d'environnement `LOGGING_CONFIG_PATH` :

```bash
export LOGGING_CONFIG_PATH=./config/logging.json  # ou ./config/logging.yml
```

Chaque fichier configure un formatter JSON, un filtre de contexte
(`RequestIdFilter`) et un filtre d'échantillonnage (`SamplingFilter`).  Les clés
`request_id_field`, `trace_id_field` et `sample_rate_field` contrôlent le nom
des champs sérialisés dans la sortie JSON tandis que `sample_rate` détermine la
proportion de messages conservés.  Ajustez ces valeurs pour faire correspondre
la structure de vos pipelines d'observabilité.

Les messages sont enrichis d'un identifiant de requête (`request_id`) ou de
trace (`trace_id`) lorsqu'ils sont définis via
`logging_setup.set_request_id()` et `logging_setup.set_trace_context()`.

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
