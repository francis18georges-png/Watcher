#!/usr/bin/env bash
set -euo pipefail

# 1) créer branche + noms automatiques
ts=$(date +"%Y%m%d-%H%M%S")
datefile=$(date +"%Y-%m-%d")
branch="feature/$ts"
git checkout -b "$branch"

# 2) MAJ changelog & journal
cat <<EOFCHANGE >> CHANGELOG.md
## [$datefile]
### Added
- feat($ts): auto entry (#PR)
EOFCHANGE

mkdir -p docs/journal
cat <<EOFJOURNAL > "docs/journal/$datefile.md"
### $datefile
- **Fait** : …
- **Décisions / blocages** : …
- **Prochaines étapes** : …
EOFJOURNAL

# 3) commit + push
git add -A
git commit -m "feat($ts): auto commit"
git push -u origin "$branch"

echo "Branche poussée : $branch"
echo "Créer la PR : https://github.com/francis18georges-png/Watcher/pull/new/$branch"
