#!/usr/bin/env bash
set -euo pipefail

feature="$1"                       # ex: db-cache
ts=$(date +"%Y%m%d-%H%M%S")
today=$(date +"%Y-%m-%d")
branch="feature/$feature-$ts"

# 1) créer la branche
git checkout -b "$branch"

# 2) placeholder changelog + journal
mkdir -p docs/journal
cat <<EOFCHANGE >> docs/CHANGELOG.md
## [$today]
### Added
- feat($feature-$ts): description (#PR)
EOFCHANGE

cat <<EOFJOURNAL > "docs/journal/$today.md"
### $today
- **Fait** : ...
- **Décisions / blocages** : ...
- **Prochaines étapes** : ...
EOFJOURNAL

# 3) commit + push
git add -A
git commit -m "feat($feature-$ts): auto commit"
git push -u origin "$branch"

echo "PR : https://github.com/francis18georges-png/Watcher/pull/new/$branch"
