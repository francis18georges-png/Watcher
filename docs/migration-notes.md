# Notes de migration & rollback

## Objet

Documenter les opérations nécessaires pour faire évoluer l'index local (`~/.watcher/index.db`) et la configuration lors de la livraison de Watcher v0.4.x.

## Migration vers v0.4.x

1. **Sauvegarde préalable**
   - Copier `~/.watcher/index.db`, `config.toml`, `policy.yaml`, `consents.jsonl` dans un dossier daté (`backup-YYYYMMDD`).
   - Exporter la liste des modèles présents (`ls ~/.watcher/models > backup-YYYYMMDD/models.txt`).
2. **Mise à jour de l'application**
   - `pip install --upgrade watcher` ou installation du binaire PyInstaller.
   - Vérifier `watcher --version`.
3. **Migration de schéma**
   - Exécuter `watcher migrate --dry-run` (ajoutera les colonnes `license`, `score`, `hash` dans `documents`).
   - Si ok : `watcher migrate --apply` (script Alembic `alembic/versions/2024_gguf_upgrade.py`).
4. **Reconstruction de l'index vectoriel**
   - `watcher ingest --reindex --sources cached` pour recalculer les embeddings avec `sentence-transformers` 2.2.2.
   - Contrôler les tailles des fichiers `~/.watcher/embeddings/*.vss`.
5. **Consent Ledger**
   - Initialiser la clé privée `consents.key` (Ed25519) via `watcher consent rotate --force`.
   - Signer les entrées existantes : `watcher consent sign --all`.

## Vérifications post-migration

- `watcher status` affiche `mode=offline`, `kill-switch=absent`, `sandbox=active`.
- `watcher run --offline --prompt "test"` répond de manière déterministe.
- `watcher crawl --allowlist-check` confirme la conformité robots/licence.

## Rollback

1. Stopper toute instance (`watcher stop --all`).
2. Restaurer les fichiers depuis la sauvegarde (`cp backup-YYYYMMDD/* ~/.watcher/`).
3. Nettoyer les modèles partiellement téléchargés (`rm ~/.watcher/models/*.partial`).
4. Réinstaller la version précédente (`pip install watcher==<version>` ou ré-exécuter l'ancien binaire).
5. Vérifier `watcher status` et relancer `watcher run --offline`.

## Considérations supplémentaires

- Les attestions cosign/SLSA restent valides pour les binaires précédents ; conserver les fichiers `checksums.txt` et signatures.
- Pour Docker, supprimer les images locales (`docker image rm ghcr.io/<owner>/watcher:<tag>`) avant de tirer la version antérieure.
- Maintenir `policy.yaml` sous contrôle de version (git crypt/local) pour suivre l'historique des consentements.
