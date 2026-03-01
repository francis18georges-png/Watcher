# Quickstart CLI (grand public)

Ce guide décrit le parcours **réel** pour utiliser Watcher sans interface graphique.

## 1) Installation locale

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Vérifier que le binaire est disponible:

```bash
watcher --help
```

## 2) Initialisation automatique

```bash
watcher init --fully-auto
```

Cette commande crée `~/.watcher/` avec:
- `config.toml`
- `policy.yaml`
- `consents.jsonl`

## 3) Vérification santé locale

```bash
watcher doctor
```

Sortie JSON (intégration support/automatisation):

```bash
watcher doctor --format json
```

Bundle de diagnostic redacted:

```bash
watcher doctor --format json --export ./diagnostic.zip
```

## 4) Exécution offline déterministe

```bash
watcher run --offline --prompt "Bonjour"
```

## 5) Autopilot supervisé

Activer:

```bash
watcher autopilot enable --topics "python,security"
```

Lancer un cycle:

```bash
watcher autopilot run --noninteractive
```

Lire le rapport hebdomadaire:

```bash
watcher autopilot report
```

## 6) Vérifier les artefacts de release

Consulter le guide dédié: [Vérification des artefacts](verifier-artefacts.md).
