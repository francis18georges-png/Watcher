# Watcher Autonomy & Release Readiness Gap Analysis

This document captures the blocking items identified to make Watcher "functionnelle comme une IA" and distributable. It is structured by priority tiers (P0: indispensable, P1: qualité & observabilité) and maps to implementation directories plus CI/CD actions.

## Constat actuel
- Pas encore plug-and-play : absence de release publiée, workflows Release/Docker en échec, image GHCR non multi-arch, documentation publique 404.
- Les commandes cibles (`watcher init --auto`, `watcher autopilot enable --topics "…"`, `watcher ingest --auto`, `watcher run --offline --prompt "…"`) ne disposent pas encore d'un chemin entièrement automatisé et vérifié.

## P0 — Indispensables
1. **First-run automatique**
   - Commande `watcher init --auto` qui détecte CPU/GPU, sélectionne un modèle local, télécharge par hash, initialise `~/.watcher/config.toml` et peuple `models/`.
   - Script first-run unique avec garde-fous et vérification d'intégrité des modèles.
   - Test CI dédié qui échoue si un téléchargement ou hash ne correspond pas ; exécution `pytest -m first_run` en mode offline.
2. **Policy & consentement explicites**
   - Ajouter `config/policy.yaml` définissant allowlist de domaines, budgets (temps/bande passante), quotas CPU/RAM, fréquences et catégories de contenu autorisées.
   - Mettre en place un "consent ledger" JSON signé pour journaliser chaque nouvelle autorisation utilisateur ou source.
3. **Autopilot planifié & sandbox réseau**
   - Implémenter `watcher autopilot enable --topics "X,Y"` : planification des étapes discover → scrape → dedupe → verify → ingest → reindex.
   - Forcer le respect des `robots.txt`, des en-têtes `ETag`/`Last-Modified`, du throttling et des licences ; réseau désactivé hors fenêtres "autopilot".
4. **Vérification multi-sources**
   - Requérir corroboration ≥ 2 sources indépendantes avant ingestion.
   - Calculer un score de confiance ; rejeter si licence incompatible ou source à faible réputation.
5. **RAG local robuste**
   - Pipeline ingestion → normalisation → détection de langue → chunking → embeddings locaux.
   - Stockage dans SQLite-VSS/FAISS avec métadonnées `{url, titre, licence, date, hash, score}` ; déduplication par hash.
6. **Tests reproductibles offline**
   - Marqueur `pytest -m e2e_offline` qui lance `watcher run --offline` avec réseau bloqué.
   - Gates de couverture et de performance pour garantir la reproductibilité.

## P1 — Qualité & Observabilité
7. **Rapports automatiques**
   - Génération hebdomadaire d'un rapport HTML listant connaissances acquises, sources et coûts estimés.
8. **Logs & métriques structurés**
   - Sortie logs JSON avec `trace_id` ; compteurs `pages_scrapees`, `taux_rejet`, `latence`, `tokens`.
9. **Profils prêts à l'emploi**
   - Options `--profile dev-docs`, `--profile research` chargeant des allowlists, budgets et parseurs spécialisés.

## CI/CD — Actions immédiates
- Publier la release `v0.4.0` après correction du workflow Release (92 échecs en cours).
- Fournir binaires, SBOM et attestations SLSA pour chaque release.
- Corriger le workflow Docker : construire et publier des images multi-arch (`linux/amd64`, `linux/arm64`) signées et attester les manifest lists.
- Stabiliser l'image GHCR en éliminant les digests `unknown/unknown`.
- Activer GitHub Pages/MkDocs afin que la documentation ne retourne plus 404.

## Mapping implémentation → dossiers
- `app/cli/init.py` → logique first-run automatique.
- `config/policy.yaml` & `app/policy/` → validation de policy, budgets, ledger de consentement.
- `app/autopilot/` → scheduler (intervalle), tâches orchestrées, gestion du mode réseau.
- `app/scrapers/` → scraping HTTP/sitemaps/GitHub via `trafilatura`/Readability en respectant robots.txt.
- `app/ingest/` → normalisation, chunking, embeddings, déduplication par hash.
- `app/index/` → stockage SQLite-VSS/FAISS, migrations Alembic.
- `tests/e2e/test_offline.py` → exécution offline déterministe bloquant le réseau par défaut.

## Prochaines étapes suggérées
1. Allouer une itération dédiée au lot P0 pour débloquer un chemin autonome offline.
2. Mettre en place un board Kanban ou GitHub Projects reflétant ces éléments critiques.
3. Ajouter ces exigences dans la feuille de route officielle et le `TODO.md` pour visibilité cross-team.
4. Bloquer les merges sur la réussite des workflows Release/Docker et des tests offline.
5. Après livraison P0, planifier P1 (observabilité) puis la publication `v0.4.0` avec artefacts signés.

