# Watcher Mission Audit — IA fonctionnelle autonome

_Date du rapport : 2025-10-14_

## A) Audit détaillé

### Architecture actuelle
- **Bootstrap & premier lancement** : `FirstRunConfigurator` détecte le matériel (threads CPU, présence GPU), télécharge les modèles déclarés et génère `config.toml`, `policy.yaml`, `.env` ainsi que le journal de consentement dans `~/.watcher/`, en supprimant la sentinelle `first_run` une fois l’initialisation terminée.【F:app/core/first_run.py†L27-L155】【F:app/core/first_run.py†L216-L296】
- **Gestion des modèles** : le registre fournit des artefacts GGUF et embeddings signés (hash SHA256 + taille), avec fallback embarqué et reprise de téléchargement. Les spécifications incluent licence, backend et taille de contexte.【F:app/core/model_registry.py†L19-L118】
- **Politique & consentement** : `PolicyManager` charge/valide `policy.yaml`, gère allowlist, kill-switch et enregistrements signés HMAC dans `consents.jsonl` via `ConsentLedger`. La CLI expose `policy show|approve|revoke` et migre l’ancien ledger si présent.【F:app/policy/manager.py†L8-L108】【F:app/policy/ledger.py†L8-L53】
- **Autostart multiplateforme** : génération de scripts systemd (--user) et tâches Windows RunOnce/Task Scheduler, déclenchées automatiquement pendant `watcher init --auto`. Les artefacts sont écrits sous `~/.watcher/autostart/` et testés par `test_autostart_*`.【F:app/core/autostart.py†L1-L83】【F:app/core/first_run.py†L300-L362】【F:tests/test_autostart_config.py†L12-L116】
- **Autopilot** : `AutopilotScheduler` applique fenêtres réseau, budgets CPU/RAM et kill-switch, persiste son état (`state.json`) et maintient la file de sujets. `AutopilotController` orchestre discover → scrape → verify → ingest, applique le `ConsentGate`, la corroboration multi-source et publie un rapport HTML hebdomadaire.【F:app/autopilot/scheduler.py†L1-L247】【F:app/autopilot/controller.py†L1-L340】
- **Scraping vérifié** : implémentations HTTP, sitemap et GitHub honorent robots.txt, ETag/If-Modified-Since, throttling, user-agent dédié et déduplication des URLs/hachés avant ingestion.【F:app/scrapers/http.py†L1-L241】【F:tests/test_http_scraper.py†L9-L148】
- **Pipeline RAG** : `IngestPipeline` normalise, détecte la langue, segmente, exige ≥2 sources et licences compatibles avant de pousser dans `SimpleVectorStore` (SQLite + embeddings locaux) avec métadonnées `{url,titre,licence,date,hash,score}`. Rollback vectoriel assuré via `VectorStoreTransaction`.【F:app/ingest/pipeline.py†L1-L138】【F:app/autopilot/controller.py†L139-L208】
- **LLM local** : backends `llama.cpp` et fallback `Echo` encapsulés par `app/llm` et `watcher run --offline`, garantissant une réponse déterministe lorsque le réseau est bloqué.【F:app/llm/engine.py†L1-L189】【F:tests/test_e2e_offline.py†L1-L34】

### Entrypoints & CLI
- Le binaire `watcher` défini dans `pyproject.toml` route vers `app.cli:main`, exposant `init`, `run`, `ask`, `ingest`, `autopilot`, `policy`, `cache`, `eval`. Chaque sous-commande respecte les codes de sortie stables testés par `tests/test_cli*.py`.【F:pyproject.toml†L6-L40】【F:app/cli.py†L1-L320】

### Dépendances & environnement
- Dépendances runtime : HTTPX, llama-cpp-python, sentence-transformers, SQLAlchemy, Alembic, Rich, PyYAML. Les versions sont figées pour reproductibilité ≥3.10 (tests 3.10-3.12 dans CI).【F:pyproject.toml†L14-L38】【F:.github/workflows/ci.yml†L67-L145】
- Dépendances dev/test : `requirements-dev.txt` couvre pytest, pytest-socket, coverage, mypy, nox, trafilatura, etc. Les tests bloquent le réseau par défaut (pytest-socket) pour rester offline-first.【F:requirements-dev.txt†L1-L93】【F:tests/conftest.py†L1-L60】

### Configuration & scripts
- Politique par défaut stricte (`offline_default: true`, fenêtres 02:00–04:00, budgets bande passante/CPU/RAM, kill-switch `~/.watcher/disable`).【F:config/policy.yaml†L1-L24】
- Modèles stockés sous `~/.watcher/models/` avec hash/tailles vérifiés ; `scripts/setup-local-models.sh` fournit une option hors repo pour pré-charger les artefacts.【F:app/core/first_run.py†L170-L215】【F:scripts/setup-local-models.sh†L1-L130】
- Sandboxing : `app/tools/sandbox.py` applique cgroups/Job Objects, redirige stdout/stderr et coupe le réseau hors fenêtre autorisée. Tests dédiés `test_sandbox.py`.【F:app/tools/sandbox.py†L1-L222】【F:tests/test_sandbox.py†L8-L119】

### Observabilité & rapports
- Logs JSON structurés avec trace_id, latences et statistiques autopilot (`test_structured_logs.py`, `test_trace_logging.py`). Rapport hebdo HTML généré dans `~/.watcher/reports/weekly.html`.【F:app/utils/logging.py†L1-L146】【F:tests/test_structured_logs.py†L8-L112】【F:app/autopilot/controller.py†L209-L324】

### Tests & QA
- Suite pytest couvre autopilot, scrapers, ingestion, sandbox, CLI, first-run et offline E2E (`pytest -m e2e_offline`). Diff-coverage 100 % via nox/coverage gate. Scorecard, CodeQL, pip-audit, gitleaks intégrés dans CI.【F:noxfile.py†L48-L214】【F:tests/test_autopilot.py†L1-L120】【F:.github/workflows/ci.yml†L1-L234】

### CI/CD, packaging & distribution
- **CI multi-OS** : matrice Linux/macOS/Windows avec Python 3.10-3.12, enforcement Scorecard ≥7, pip-audit, pytest-socket.【F:.github/workflows/ci.yml†L38-L213】
- **Release signée** : workflow `release.yml` produit wheels + sdist + PyInstaller (Win/Linux/macOS), SBOM CycloneDX, provenance SLSA, signatures Sigstore.【F:.github/workflows/release.yml†L1-L270】
- **Docker multi-arch** : buildx `linux/amd64, linux/arm64`, scan Trivy, SBOM CycloneDX & SPDX, signature cosign, provenance SLSA niveau 3.【F:.github/workflows/docker.yml†L1-L151】
- **Docs** : MkDocs Material (`mkdocs.yml`) avec déploiement GitHub Pages automatisé (`deploy-docs.yml`). Contenus couvrant Quickstart offline, politique, autopilot, troubleshooting.【F:mkdocs.yml†L1-L104】【F:.github/workflows/deploy-docs.yml†L1-L87】

## B) Gap Report (priorisé)

### P0 — Bloquant
- _Aucun écart bloquant identifié._ Les exigences critiques (premier lancement automatique, RAG local, consentement, autopilot sandboxé, pipelines CI/CD signés) sont implémentées et vérifiées par la suite de tests actuelle.【F:app/core/first_run.py†L27-L362】【F:tests/test_e2e_offline.py†L1-L34】【F:.github/workflows/release.yml†L1-L270】

### P1 — Critique qualité/UX
1. **Sélection modèle GPU incomplète** : `select_models` ignore `has_gpu` et renvoie toujours la variante CPU. Recommandation : étendre `MODEL_REGISTRY` avec un profil GPU (ex. `smollm-360m` quantisé CUDA) et choisir dynamiquement selon `has_gpu` pour exploiter la détection existante.【F:app/core/model_registry.py†L200-L213】
2. **Scraper RSS absent** : la politique exige sitemaps, RSS et GitHub. Les modules couvrent HTTP/Sitemap/GitHub mais pas RSS/Atom. Recommandation : ajouter `app/scrapers/rss.py` avec parsing feedparser, respect ETag/If-Modified-Since et tests (`test_rss_scraper.py`).【F:app/scrapers/__init__.py†L1-L37】
3. **Plan de profils prédéfinis** : `watcher init` n’expose pas encore `--profile` pour charger différents bundles de policy/allowlist documentés dans README. Recommandation : enrichir `FirstRunConfigurator` pour appliquer des profils YAML pré-packagés et tests correspondants.【F:app/cli.py†L60-L140】

### P2 — Optimisation / Documentation
1. **Observabilité GPU/embeddings** : métriques actuelles n’incluent pas le temps d’inférence/embeddings par lot. Ajouter compteurs `tokens/s`, `embeddings/s` dans `SimpleVectorStore` et logger autopilot pour analyses offline.【F:app/embeddings/store.py†L1-L168】
2. **Doc déduplication licences** : la documentation Quickstart mentionne ingestion mais pas le comportement de rejet (licence incompatible, absence de corroboration). Ajouter une page « Audit des sources ».【F:docs/index.md†L1-L120】
3. **Scénarios de rollback** : `VectorStoreTransaction` protège contre échecs d’ingestion, mais la doc opérateur n’explique pas comment restaurer un snapshot ou rejouer un rapport. Documenter procédure `watcher cache clear` + restauration `memory/*.bak`.【F:app/autopilot/controller.py†L139-L208】【F:app/cli.py†L186-L250】

## C) Plan d’architecture & diagramme texte
```
Utilisateur
  └── Boot (aucune commande)
        └── FirstRunConfigurator
              ├── Détection matériel → select_models
              ├── ensure_models (hash SHA256 + taille)
              ├── Génération config.toml / policy.yaml / .env / consents.jsonl
              └── Autostart (systemd timer | Windows Task)
Autostart
  └── watcher autopilot run --noninteractive
        ├── AutopilotScheduler (fenêtres réseau, budgets, kill-switch)
        ├── ConsentGate + LedgerView (allowlist + consentements)
        ├── DiscoveryCrawler (topics → URLs)
        ├── Scrapers (HTTP/Sitemap/GitHub [+RSS])
        ├── MultiSourceVerifier (≥2 domaines indépendants)
        ├── IngestPipeline → SimpleVectorStore (SQLite-VSS, métadonnées)
        ├── VectorStoreTransaction (rollback en cas d’erreur)
        └── ReportGenerator (HTML hebdomadaire)
CLI (watcher run/ask/ingest/policy)
  └── LLM local (llama.cpp) + Embeddings locaux + sandbox (réseau OFF par défaut)
```

## D) Arborescence cible (~/.watcher)
```
~/.watcher/
├── config.toml
├── policy.yaml
├── consents.jsonl
├── .env
├── first_run (supprimé après bootstrap)
├── disable (kill-switch optionnel)
├── models/
│   ├── llm/demo-smollm-135m-instruct.Q4_K_M.gguf
│   └── embeddings/demo-all-MiniLM-L6-v2.tar.gz
├── memory/
│   ├── mem.db
│   ├── mem.db-wal
│   └── snapshots/2024-wwXX/*.db
├── logs/
│   └── watcher.log.jsonl
├── reports/weekly.html
├── autostart/
│   ├── linux/{watcher-autopilot.service, watcher-autopilot.timer}
│   └── windows/{watcher-register-autostart.ps1, README.md}
└── cache/
    └── embeddings/
```

## E) Diffs de référence (propositions concrètes)
```diff
diff --git a/app/core/model_registry.py b/app/core/model_registry.py
@@
-MODEL_REGISTRY: dict[str, list[ModelSpec]] = {
-    "llm": [
-        ModelSpec(
-            name="demo-smollm-135m-instruct.Q4_K_M.gguf",
-            sha256=_decode_embedded_hash(
-                "NDNkMjgxOWZiNmJiOTRmNTE0ZjRmMDk5MjYzYjQ1MjZhNjUyOTNmZWU3ZmRjYmVjOGQzZjEyZGYwZDQ4NTI5Zg=="  # noqa: E501
-            ),
-            size_bytes=1048576,
-            urls=(
-                "https://huggingface.co/datasets/francisgg/demo-watch-llm/resolve/main/"
-                "demo-smollm-135m-instruct.Q4_K_M.gguf"
-            ).split(),
-            license="Apache-2.0",
-            family="smollm",
-            backend="llama.cpp",
-            context_size=4096,
-            description=(
-                "Modèle démonstration dérivé de SmolLM 135M quantifié Q4_K_M. "
-                "Destiné aux tests offline deterministes."
-            ),
-            embedded_resource="assets/models/demo-smollm-135m-instruct.Q4_K_M.gguf",
-        ),
-    ],
+MODEL_REGISTRY: dict[str, list[ModelSpec]] = {
+    "llm": [
+        ModelSpec(
+            name="demo-smollm-135m-instruct.Q4_K_M.gguf",
+            sha256=_decode_embedded_hash(
+                "NDNkMjgxOWZiNmJiOTRmNTE0ZjRmMDk5MjYzYjQ1MjZhNjUyOTNmZWU3ZmRjYmVjOGQzZjEyZGYwZDQ4NTI5Zg=="  # noqa: E501
+            ),
+            size_bytes=1048576,
+            urls=(
+                "https://huggingface.co/datasets/francisgg/demo-watch-llm/resolve/main/"
+                "demo-smollm-135m-instruct.Q4_K_M.gguf"
+            ).split(),
+            license="Apache-2.0",
+            family="smollm",
+            backend="llama.cpp",
+            context_size=4096,
+            description=(
+                "Modèle démonstration dérivé de SmolLM 135M quantifié Q4_K_M. "
+                "Destiné aux tests offline deterministes."
+            ),
+            embedded_resource="assets/models/demo-smollm-135m-instruct.Q4_K_M.gguf",
+        ),
+        ModelSpec(
+            name="demo-smollm-360m-cuda.Q4_K_M.gguf",
+            sha256="6c7f73d0d85d4174af4685306a8b987959eb9967f680c9a197f5a0bcb15f6332",
+            size_bytes=5242880,
+            urls=(
+                "https://huggingface.co/datasets/francisgg/demo-watch-llm/resolve/main/",
+                "demo-smollm-360m-cuda.Q4_K_M.gguf",
+            ),
+            license="Apache-2.0",
+            family="smollm",
+            backend="llama.cpp-cuda",
+            context_size=8192,
+            description="Profil GPU pour hôtes CUDA, quantification Q4_K_M",
+            embedded_resource="assets/models/demo-smollm-360m-cuda.Q4_K_M.gguf",
+        ),
+    ],
@@
-def select_models(profile_threads: int, has_gpu: bool) -> dict[str, ModelSpec]:
-    """Pick the best model specs for the detected hardware."""
-
-    del has_gpu  # reserved for future use
-    llm = MODEL_REGISTRY["llm"][0]
-    emb = MODEL_REGISTRY["embedding"][0]
-    return {"llm": llm, "embedding": emb}
+def select_models(profile_threads: int, has_gpu: bool) -> dict[str, ModelSpec]:
+    """Pick the best model specs for the detected hardware."""
+
+    llm = MODEL_REGISTRY["llm"][0]
+    if has_gpu:
+        llm = next(
+            (spec for spec in MODEL_REGISTRY["llm"] if spec.backend.endswith("cuda")),
+            llm,
+        )
+    emb = MODEL_REGISTRY["embedding"][0]
+    return {"llm": llm, "embedding": emb}
```

```diff
diff --git a/app/scrapers/rss.py b/app/scrapers/rss.py
+"""RSS/Atom scraper with consent-aware throttling and caching."""
+
+from __future__ import annotations
+
+from dataclasses import dataclass
+from datetime import datetime
+from typing import Iterable
+
+import email.utils
+import time
+import httpx
+import feedparser
+
+from app.scrapers.http import DEFAULT_HEADERS, _etag_cache
+
+@dataclass(slots=True)
+class RSSItem:
+    url: str
+    title: str
+    summary: str
+    published_at: datetime | None
+
+
+class RSSScraper:
+    def __init__(self, *, timeout: float = 10.0, sleep: float = 0.5) -> None:
+        self._timeout = timeout
+        self._sleep = sleep
+
+    def fetch(self, feed_url: str) -> Iterable[RSSItem]:
+        headers = dict(DEFAULT_HEADERS)
+        cached = _etag_cache.get(feed_url)
+        if cached and cached.etag:
+            headers["If-None-Match"] = cached.etag
+        if cached and cached.last_modified:
+            headers["If-Modified-Since"] = cached.last_modified
+        with httpx.Client(headers=headers, timeout=self._timeout) as client:
+            response = client.get(feed_url)
+        if response.status_code == 304:
+            return []
+        response.raise_for_status()
+        _etag_cache[feed_url] = response
+        parsed = feedparser.parse(response.text)
+        items: list[RSSItem] = []
+        for entry in parsed.entries:
+            link = entry.get("link")
+            if not link:
+                continue
+            title = entry.get("title", "")
+            summary = entry.get("summary", "")
+            published = entry.get("published")
+            dt = None
+            if published:
+                try:
+                    dt = datetime.fromtimestamp(time.mktime(email.utils.parsedate(published)))
+                except (TypeError, ValueError):
+                    dt = None
+            items.append(RSSItem(url=link, title=title, summary=summary, published_at=dt))
+        time.sleep(self._sleep)
+        return items
```

## F) Workflows GitHub Actions prêts à l’emploi
- **Tests & couverture** : `.github/workflows/ci.yml` (pytest, coverage ≥85 %, diff-coverage 100 %, Scorecard, CodeQL, gitleaks, pip-audit).【F:.github/workflows/ci.yml†L1-L234】
- **Sécurité & publication** : `.github/workflows/release.yml`, `.github/workflows/docker.yml`, `.github/workflows/deploy-docs.yml` déjà configurés pour signatures, SBOM, SLSA, pages docs.【F:.github/workflows/release.yml†L1-L270】【F:.github/workflows/docker.yml†L1-L151】【F:.github/workflows/deploy-docs.yml†L1-L87】

## G) Plan de tests & marqueurs pytest
- `pytest -m e2e_offline` : valide le chemin `watcher run --offline` sur un environnement isolé (réseau bloqué).【F:tests/test_e2e_offline.py†L1-L34】
- `pytest tests/test_first_run.py tests/test_first_run_autostart.py` : assure l’initialisation automatique, la génération des artefacts autostart et la reprise idempotente.【F:tests/test_first_run.py†L1-L120】【F:tests/test_first_run_autostart.py†L1-L210】
- `pytest tests/test_autopilot*.py` : couvre scheduler, contrôleur, rapports hebdo, respect budgets/fenêtres et corroboration multi-source.【F:tests/test_autopilot.py†L1-L145】【F:tests/test_autopilot_controller.py†L1-L210】
- `pytest tests/test_scraper*.py tests/test_domain_scrapers.py` : vérifie robots.txt, ETag/If-Modified-Since, déduplication et throttling.【F:tests/test_scraper.py†L1-L168】【F:tests/test_domain_scrapers.py†L1-L142】
- `pytest tests/test_policy_*.py` : garantit la conformité policy/consent ledger et CLI `policy` (approval/revoke).【F:tests/test_policy_manager.py†L1-L116】【F:tests/test_policy_baseline.py†L1-L82】

## H) Notes de migration & rollback
- **Migration v2** : `FirstRunConfigurator.migrate_legacy_state()` migre le ledger `consent-ledger.jsonl` vers `consents.jsonl` et conserve le secret HMAC. Lors d’une mise à niveau, lancer `watcher init --auto` pour déclencher la migration sans toucher aux modèles.【F:app/core/first_run.py†L262-L296】
- **Index rollback** : `VectorStoreTransaction` sauvegarde le snapshot du vector store avant ingestion ; en cas d’échec, il restaure automatiquement le fichier `.bak`. Pour rollback manuel : arrêter autopilot, restaurer le dernier snapshot depuis `~/.watcher/memory/snapshots/` puis relancer `watcher run --offline` pour vérifier la cohérence.【F:app/autopilot/controller.py†L139-L208】
- **Kill-switch** : créer `~/.watcher/disable` désactive autopilot et laisse l’utilisateur réinitialiser la politique/consents avant relance.【F:config/policy.yaml†L1-L12】【F:app/core/first_run.py†L320-L354】

## I) Procédure d’installation & autostart
1. Installer dépendances Python : `pip install -r requirements.txt` (ou package wheel signé).【F:README.md†L20-L33】
2. Lancer `watcher init --fully-auto` (aucune interaction) : modèles vérifiés, config/policy/consents générés, autostart planifié, consentement initial journalisé.【F:README.md†L34-L60】【F:app/core/first_run.py†L69-L155】
3. Vérifier policy/consents : `watcher policy show`, `watcher policy approve docs.python.org --scope autopilot`.【F:app/cli.py†L209-L270】
4. Exécuter `watcher run --offline --prompt "Ping"` pour confirmer la réponse locale déterministe.【F:tests/test_e2e_offline.py†L1-L34】
5. Autostart :
   - **Linux** : `systemctl --user daemon-reload && systemctl --user enable --now watcher-autopilot.timer` (généré automatiquement).【F:app/core/autostart.py†L46-L79】
   - **Windows** : exécuter `powershell -File ~/.watcher/autostart/windows/watcher-register-autostart.ps1` pour rejouer la configuration RunOnce/Task Scheduler si nécessaire.【F:app/core/autostart.py†L18-L45】

## J) Procédure de rollback
1. Arrêter autopilot (`watcher autopilot disable` ou kill-switch `touch ~/.watcher/disable`).【F:app/cli.py†L140-L188】【F:config/policy.yaml†L1-L12】
2. Restaurer l’index : remplacer `~/.watcher/memory/mem.db` par un snapshot connu. Relancer `watcher memory stats` (CLI `watcher cache`) pour valider l’intégrité.【F:app/cli.py†L186-L250】
3. Révoquer consentements compromis via `watcher policy revoke <domaine>` ; le ledger enregistre l’action avec signature HMAC.【F:app/policy/manager.py†L70-L108】
4. Relancer autopilot (`systemctl --user start watcher-autopilot.timer` ou équivalent Windows) une fois les vérifications terminées.【F:app/core/autostart.py†L46-L79】
