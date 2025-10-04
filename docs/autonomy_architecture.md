# Watcher Autonomy Overhaul Blueprint

## 1. Résumé d'architecture

Watcher devient une plateforme locale orchestrant quatre plans fonctionnels :

1. **Initialisation automatique** – `watcher init --auto` détecte le matériel CPU/GPU, choisit la pile llama.cpp adaptée et provisionne les modèles par hachage dans `~/.watcher/models`. Un cache checksum permet la reprise en cas de coupure.
2. **Conformité & consentement** – Un moteur de politique lit `config/policy.yaml`, applique les budgets de ressources, et signe chaque accord utilisateur dans un grand livre JSONL immuable.
3. **Pipeline de connaissance autonome** – Modules de scraping respectueux (`app/scrapers/`) collectent des sources approuvées, vérifiées puis ingérées dans un index vectoriel local (`app/ingest/`).
4. **Autopilot supervisé** – `watcher autopilot` orchestre découverte → scraping → vérification → ingestion → réindexation tout en restant offline hors fenêtres autorisées.

Les journaux JSON (avec `trace_id`) et un rapport HTML hebdomadaire documentent chaque activité, garantissant auditabilité et sécurité.

## Diagramme de flux (texte)

```
+-------------+       watcher init --auto        +-----------------+
|  Hardware   | --detect--> PlatformProfiler --> | llama.cpp Setup |
+-------------+                                  +-----------------+
        |                                               |
        v                                               v
+-------------------+    policy constraints   +------------------+
| Policy Engine     | <---------------------> | Consent Ledger   |
+-------------------+                        +------------------+
        |                                               |
        v                                               v
+-------------------+    allowed windows     +------------------+
| Autopilot Runner  | ---------------------> | Scraper Workers  |
+-------------------+                        +------------------+
        |                                               |
        v                                               v
+-------------------+    vetted corpus       +------------------+
| Verification Hub  | ---------------------> | Ingestion Engine |
+-------------------+                        +------------------+
                                                |
                                                v
                                      +-------------------+
                                      | Vector Index (VSS)|
                                      +-------------------+
                                                |
                                                v
                                      +-------------------+
                                      | watcher run       |
                                      +-------------------+
```

## 2. Arborescence fichiers cible

```
Watcher/
├─ app/
│  ├─ cli/
│  │  ├─ __init__.py
│  │  ├─ init.py
│  │  ├─ autopilot.py
│  │  ├─ policy.py
│  │  ├─ cache.py
│  │  └─ run.py
│  ├─ core/
│  │  ├─ config.py
│  │  ├─ hardware.py
│  │  ├─ logging.py
│  │  ├─ policy.py
│  │  └─ consent.py
│  ├─ scrapers/
│  │  ├─ __init__.py
│  │  ├─ base.py
│  │  ├─ http.py
│  │  ├─ sitemap.py
│  │  └─ github.py
│  ├─ ingest/
│  │  ├─ __init__.py
│  │  ├─ normalization.py
│  │  ├─ embeddings.py
│  │  ├─ index.py
│  │  └─ pipeline.py
│  └─ autopilot/
│     ├─ __init__.py
│     ├─ scheduler.py
│     ├─ budgets.py
│     └─ state.py
├─ config/
│  ├─ policy.yaml
│  └─ profiles/
│     ├─ dev-docs.yaml
│     └─ research.yaml
├─ scripts/
│  ├─ setup-local-models.sh
│  └─ setup-local-models.ps1
├─ docs/
│  ├─ quickstart-offline.md
│  ├─ policy-consent.md
│  ├─ autopilot-guide.md
│  ├─ verifying-artifacts.md
│  └─ troubleshooting.md
├─ packaging/
│  ├─ pyinstaller/
│  │  ├─ watcher.spec
│  │  └─ hooks/
│  └─ release/
│     ├─ cosign-sign.sh
│     ├─ sbom-cyclonedx.sh
│     └─ slsa-provenance.yaml
├─ tests/
│  ├─ conftest.py
│  ├─ test_cli_init.py
│  ├─ test_policy.py
│  ├─ test_scrapers.py
│  ├─ test_ingest.py
│  ├─ test_index.py
│  ├─ test_autopilot.py
│  ├─ test_offline_run.py
│  └─ e2e/
│     └─ test_offline_session.py
└─ watcher/
   ├─ __init__.py
   ├─ cli.py
   ├─ autopilot.py
   ├─ policy.py
   ├─ cache.py
   └─ runtime.py
```

## 3. Blocs de code clés (extraits)

### CLI – initialisation automatique (`app/cli/init.py`)

```python
import argparse
from pathlib import Path

from app.core.hardware import detect_capabilities
from app.core.config import ConfigWriter
from app.core.policy import PolicyValidator
from app.core.consent import ConsentLedger
from app.cache.models import ModelCache


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("init", help="Initialise Watcher")
    parser.add_argument("--auto", action="store_true", help="Mode totalement automatique")
    parser.set_defaults(func=handle)


def handle(args: argparse.Namespace) -> int:
    capabilities = detect_capabilities()
    cache = ModelCache(Path("~/.watcher/models").expanduser())
    writer = ConfigWriter(Path("~/.watcher/config.toml").expanduser())

    config = writer.bootstrap(capabilities, cache.ensure_models())
    PolicyValidator().ensure_defaults(config)
    ConsentLedger.default().record_bootstrap(config)
    return 0
```

### Consentement (`app/core/consent.py`)

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping

from app.crypto.signing import DetachedSigner


@dataclass(frozen=True, slots=True)
class ConsentRecord:
    domain: str
    scope: str
    policy_version: str
    hash_value: str
    granted_at: datetime

    def to_json(self) -> str:
        payload = {
            "domain": self.domain,
            "scope": self.scope,
            "policy_version": self.policy_version,
            "hash": self.hash_value,
            "granted_at": self.granted_at.isoformat(),
        }
        return json.dumps(payload, ensure_ascii=False)


class ConsentLedger:
    def __init__(self, path: Path, signer: DetachedSigner) -> None:
        self._path = path
        self._signer = signer
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def default(cls) -> "ConsentLedger":
        ledger = Path("~/.watcher/consents.jsonl").expanduser()
        signer = DetachedSigner.from_env()
        return cls(ledger, signer)

    def append(self, record: ConsentRecord) -> None:
        payload = record.to_json()
        signature = self._signer.sign(payload.encode("utf-8"))
        line = json.dumps({"payload": payload, "signature": signature}, ensure_ascii=False)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def record_bootstrap(self, config: Mapping[str, object]) -> None:
        record = ConsentRecord(
            domain="local://bootstrap",
            scope="initial_configuration",
            policy_version=str(config.get("policy", {}).get("version", "0")),
            hash_value=DetachedSigner.compute_hash(config),
            granted_at=datetime.now(timezone.utc),
        )
        self.append(record)
```

### Scraper HTTP (`app/scrapers/http.py`)

```python
import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Iterator

import httpx

from app.scrapers.base import CrawlRequest, CrawlResult, Scraper


@dataclass(slots=True)
class HttpScraper(Scraper):
    max_retries: int = 2
    throttle_seconds: float = 0.5

    def crawl(self, request: CrawlRequest) -> Iterator[CrawlResult]:
        with httpx.Client(timeout=10.0, headers={"User-Agent": request.user_agent}, transport=request.transport) as client:
            for url in request.urls:
                self._respect_throttle()
                if not self._allowed_by_robots(url):
                    continue
                response = client.get(
                    url,
                    headers={
                        "If-None-Match": request.etag_cache.get(url, ""),
                        "If-Modified-Since": request.timestamp_cache.get(url, ""),
                    },
                )
                if response.status_code == 304:
                    continue
                yield CrawlResult.from_response(response)

    def _respect_throttle(self) -> None:
        time.sleep(self.throttle_seconds)
```

### Index vectoriel (`app/ingest/index.py`)

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

import sqlite3


@dataclass(slots=True)
class DocumentChunk:
    chunk_id: str
    text: str
    embedding: list[float]
    metadata: Mapping[str, str]


class VectorIndex:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._conn = sqlite3.connect(path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                chunk_id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                embedding BLOB NOT NULL,
                url TEXT NOT NULL,
                title TEXT,
                licence TEXT,
                crawled_at TEXT,
                hash TEXT NOT NULL,
                score REAL NOT NULL
            )
            """
        )

    def add(self, chunks: Iterable[DocumentChunk]) -> None:
        with self._conn:
            self._conn.executemany(
                """
                INSERT OR REPLACE INTO documents
                (chunk_id, text, embedding, url, title, licence, crawled_at, hash, score)
                VALUES (:chunk_id, :text, :embedding, :url, :title, :licence, :crawled_at, :hash, :score)
                """,
                [
                    {
                        "chunk_id": chunk.chunk_id,
                        "text": chunk.text,
                        "embedding": memoryview(bytes(chunk.embedding)),
                        **chunk.metadata,
                    }
                    for chunk in chunks
                ],
            )
```

## 4. Commandes clés

```bash
# Installation
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]

# Initialisation sans interaction
watcher init --auto

# Exécution hors ligne
watcher run --offline --model-path ~/.watcher/models/llama3-8b-q4.gguf

# Ingestion automatique
watcher ingest --auto ./datasets/local_corpus

# Autopilot avec politique stricte
watcher autopilot enable --topics "dev-docs,security" --profile dev-docs
```

## 5. Plan de tests

- `pytest -m "not network"` – tests unitaires offline (activation via `pytest-socket`).
- `pytest tests/test_cli_init.py -k auto` – vérifie l’écriture de `config.toml` et du cache modèles.
- `pytest tests/test_scrapers.py::test_robots_respected` – simulateur HTTP local.
- `pytest tests/test_ingest.py::test_vector_index_roundtrip` – vérifie l’index SQLite-VSS.
- `pytest tests/e2e/test_offline_session.py` – lance `watcher run --offline` avec un modèle GGUF minimal.
- `pytest --cov=app --cov-report=term-missing` – couverture globale ≥85 %.

## 6. Notes de migration

- **Index** : migration vers SQLite-VSS nécessite exécution de `alembic upgrade head` pour créer la table `documents` avec colonnes `licence`, `hash`, `score`.
- **Configuration** : ancien `config.yaml` doit être remplacé par `~/.watcher/config.toml`. Un script `watcher migrate-config` convertira les clés.
- **Consent Ledger** : créer `~/.watcher/consents.jsonl` et importer les consentements existants via `watcher policy approve --import legacy.json`.
- **Scripts modèles** : utiliser `scripts/setup-local-models.sh`/`.ps1` pour télécharger et vérifier les GGUF par SHA256 ; les anciens chemins `models/` dans le repo sont obsolètes.
```
