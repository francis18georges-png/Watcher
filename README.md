# Watcher
Atelier local d'IA de programmation autonome (offline par défaut).
- Mémoire vectorielle, curriculum adaptatif, A/B + bench, quality gate sécurité.

## Utilisation
1. .\installer.ps1
2. .\run.ps1

## Config
Voir config/settings.toml.

## Sécurité
Sandbox d'exécution confinée, tests + linters obligatoires avant adoption de code.
Semgrep utilise un fichier de règles local (`config/semgrep.yml`), aucun accès réseau requis.


## Entraînement
- Datasets: datasets/python/*
- python -m pytest -q dans chaque dossier
- UI: bouton *Améliorer (A/B)* appelle l'autograde + bench
