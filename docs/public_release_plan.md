# Watcher Public Release Readiness Pack

This document captures the current delta between Watcher's existing capabilities and the "Transformer Watcher" grand-public product vision. It also provides the target reference architecture, packaging roadmap, and validation strategy required to ship a trustworthy offline-first release across desktop platforms.

## Gap Report

Status legend: **P0** = launch-blocking, **P1** = launch-critical, **P2** = post-launch but planned.

### P0 – Distribution & Trustworthiness

| Area | Expected for Public Release | Current Status | Gap Severity |
| --- | --- | --- | --- |
| Release Automation | Tag-triggered workflow producing reproducible wheels, sdists, and PyInstaller bundles per-OS; release notes with SBOM, checksums, and SLSA provenance. | No release workflow; packaging scripts are manual. | **P0** |
| Python Package | Trusted Publishing to PyPI with OIDC, signed artifacts. | No PyPI automation, project metadata lacks `project.scripts` for CLI/GUI. | **P0** |
| Desktop GUI | Installable Tauri app (`watcher-gui`) with onboarding, autopilot controls, i18n, offline defaults. | GUI absent; only CLI prototype scripts. | **P0** |
| Installers | Signed MSI/MSIX, notarized DMG, AppImage/DEB/RPM/Flatpak with auto-updater hooks. | No installer infrastructure. | **P0** |
| Local-first Onboarding | First-run sentinel, config generation, consent tracking, hash-verified model downloads. | Config scripts incomplete; no consent or hash verification. | **P0** |
| Automation Sentinels | Cross-platform autostart services with kill-switch controls. | Not implemented. | **P0** |
| Security Artifacts | CycloneDX SBOM, cosign signatures, provenance attestations, policy docs. | No SBOM/signatures; legal docs incomplete. | **P0** |

### P1 – Autonomy, Safety & Quality

| Area | Expected | Current | Gap |
| --- | --- | --- | --- |
| Scraping Compliance | robots.txt enforcement, throttling, licence filters, corroboration logic. | Basic data ingestion; lacks compliance & trust scoring. | **P1** |
| RAG Pipeline | Local chunking, embeddings, FAISS/SQLite-VSS index with metadata API. | Partial ingestion; no persistent index or metadata governance. | **P1** |
| Autopilot Loop | Scheduled discover → verify → ingest cycle with metrics + weekly HTML reports. | Manual scripts only. | **P1** |
| Runtime Sandboxing | Constrained subprocesses, network windows, zero telemetry default. | Not present. | **P1** |
| Self-Test Suite | CLI/GUI diagnostics, GPU capability checks, offline E2E tests. | Unit tests only. | **P1** |
| Logging & Support | Structured JSON logs, export bundle, crash handling. | Limited logging; no export path. | **P1** |
| Internationalisation | Full fr/en localisation. | Single-language strings. | **P1** |

### P2 – Ecosystem & Compliance

| Area | Expected | Current | Gap |
| --- | --- | --- | --- |
| OS Package Ecosystem | winget, Homebrew tap, AppImage/DEB/RPM automation, Flatpak manifest. | No distribution listings. | **P2** |
| Testing & Gates | ≥85 % coverage, diff-coverage 100 %, Playwright GUI tests, scraping gates. | Coverage ~? (pending measurement); GUI tests absent. | **P2** |
| Supply Chain Hardening | OSSF Scorecard, CodeQL, secret scanning, pip-audit, SLSA generator pipeline. | Partial: CodeQL optional, no Scorecard or pip-audit gating. | **P2** |
| Legal Docs | Privacy Policy, Terms/EULA, Model/Data Card, SBOM-derived Third-Party Notices. | Only ETHICS.md; rest missing. | **P2** |

## Target Architecture

```
watcher/
├── app/
│   ├── cli.py            # CLI entrypoint (watcher)
│   ├── gui/
│   │   ├── src-tauri/    # Tauri project (Rust backend + updater)
│   │   └── ui/           # Frontend (Svelte/React) with i18n bundles
│   ├── autopilot/
│   │   ├── scheduler.py  # discover→scrape→verify→ingest loop
│   │   └── reports.py    # Weekly HTML report generator
│   ├── ingestion/
│   │   ├── fetch.py      # robots-aware fetcher with throttling
│   │   ├── extract.py    # Readability/trafilatura wrapper
│   │   └── licence.py    # Licence detection & policy engine
│   ├── rag/
│   │   ├── embeddings.py # Local model management + hash verification
│   │   ├── index.py      # SQLite-VSS/FAISS index API
│   │   └── export.py     # Import/export tooling
│   ├── sandbox/
│   │   └── isolation.py  # cgroups/Job Object wrappers
│   └── config/
│       ├── first_run.py  # Sentinel + config generation
│       └── policy.py     # Allowlist enforcement
├── packaging/
│   ├── installers/       # MSI, DMG, AppImage/DEB/RPM/Flatpak scripts
│   ├── workflows/        # Shared CI helper scripts (sbom, signing)
│   └── docs/             # Customer-facing release notes templates
├── docs/
│   ├── quickstart/       # GUI/CLI quickstart guides
│   ├── faq.md
│   ├── troubleshooting.md
│   ├── security.md       # Signature verification instructions
│   └── legal/            # Policy, Terms, Model Card, Notices
└── tests/
    ├── cli/              # Offline-first pytest suites
    ├── gui/              # Playwright onboarding/autopilot tests
    ├── ingestion/        # Scraper compliance tests
    └── autopilot/        # Scenario simulations & coverage
```

### Textual Architecture Diagram

```
                             ┌──────────────────────────┐
                             │    Tauri GUI Frontend    │
                             │  (watcher-gui desktop)   │
                             └────────────┬─────────────┘
                                            │
                         IPC (commands/events) via JSON-RPC
                                            │
┌────────────────────────────────────────────┴─────────────────────────────────────┐
│                                Watcher Core (Python)                             │
│  ┌──────────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐  │
│  │ Autopilot Scheduler  │→→│ Ingestion Pipeline    │→→│   RAG Index Manager   │  │
│  │ (async tasks, timers)│   │ (fetch, extract, LIC │   │ (embeddings, FAISS   │  │
│  └──────────┬───────────┘   │ scoring, dedupe)     │   │ indexes, metadata)   │  │
│             │               └──────────┬──────────┘   └──────────┬───────────┘  │
│             │                           │                         │              │
│   ┌─────────▼─────────┐      ┌──────────▼──────────┐    ┌─────────▼──────────┐  │
│   │ Policy & Consent  │      │ Sandbox Controller   │    │ Config & Sentinel  │  │
│   │ (allowlists, logs)│      │ (cgroups/JobObjects) │    │ (~/.watcher/*.toml)│  │
│   └─────────┬─────────┘      └──────────┬──────────┘    └─────────┬──────────┘  │
│             │                           │                         │              │
│        JSON Log Bus            Resource isolation            First-run tasks    │
└───────────┬─────────────────────────────────────────────────────────────────────┘
            │
   Structured telemetry (local only, opt-in export)
            │
┌───────────▼───────────┐
│ Docs & Support Bundle │ (HTML reports, log exports, diagnostics)
└────────────────────────┘
```

## CI/CD Blueprint

1. **Release Workflow (`.github/workflows/release.yml`)**
   - Trigger: `push` tags matching `v*`.
   - Jobs: lint & test → build wheels/sdists → PyInstaller bundles → SBOM (CycloneDX) → checksums → cosign sign → provenance attestation → GitHub Release publishing (notes + artefacts) → PyPI publish via Trusted Publishing.

2. **Docker Workflow (`.github/workflows/docker.yml`)**
   - Buildx matrix for `linux/amd64` + `linux/arm64`.
   - Push to `ghcr.io/<owner>/watcher` with `latest` & version tags.
   - Cosign sign + generate SLSA v3 provenance (generator-container).
   - Gate: `docker buildx imagetools inspect` + `cosign verify-attestation`.

3. **Docs Workflow (`.github/workflows/docs.yml`)**
   - Build MkDocs site, upload as artifact, deploy to GitHub Pages.
   - Post status + link in README.

4. **Quality Gates (`ci.yml`)**
   - pytest with `pytest-socket`, CLI E2E offline run, Playwright GUI tests.
   - Coverage upload (≥85 % enforced).
   - Security scanners: `pip-audit`, `bandit`, `ossf/scorecard-action`, `github/codeql-action`, `trufflesecurity/trufflehog`, `sigstore/cosign-installer@v3` for verification.

## Installer & Packaging Strategy

- **Windows**: Tauri bundler → MSIX; convert to MSI with `wix` or `advanced installer`. Sign via GitHub Actions using secure certificate storage (e.g., Azure Key Vault). Publish via winget manifest automation.
- **macOS**: Universal binary build, sign with Developer ID Application, notarize via API, wrap in DMG with background, publish via Homebrew tap.
- **Linux**: Generate AppImage (appimagetool), DEB/RPM via `fpm`, Flatpak manifest & repo (Flathub submission template).
- **Python Package**: `pyproject.toml` updated with scripts (`watcher`, `watcher-gui`), optional extras for GPU.
- **Docker**: Base on `python:3.12-slim`, embed offline models via hashed downloads, run as non-root, provide volume mounts.

## Documentation Deliverables

| Document | Summary |
| --- | --- |
| `docs/quickstart/gui.md` | Step-by-step GUI onboarding, offline defaults, verification of signatures. |
| `docs/quickstart/cli.md` | Commands (`watcher init --fully-auto`, `watcher run --offline`). |
| `docs/faq.md` | Consumer-friendly Q&A. |
| `docs/troubleshooting.md` | Common issues, diagnostic scripts. |
| `docs/security/signatures.md` | Verifying checksums, cosign, provenance. |
| `docs/legal/*` | Privacy Policy, Terms/EULA, Model Card, Data Card, Third-Party Notices. |

## Test Plan Overview

### CLI

- `pytest` suites for ingestion, autopilot scheduling, sandbox wrappers.
- Deterministic offline E2E: `watcher run --offline --prompt "Bonjour"` with fixture models.
- Socket restrictions via `pytest-socket`.

### GUI

- Playwright flows covering onboarding (consent → model selection → data folder), autopilot toggle, search, export.
- Snapshot tests for accessibility (contrast, keyboard focus).

### Scraping & RAG

- Contract tests for robots.txt respect, ETag caching, deduplication, licence rejection, corroboration requirements.
- Integration tests verifying ingestion metadata saved to SQLite/FAISS.

### Platform

- Installer smoke tests in CI (Windows runner MSI/MSIX, macOS DMG notarization, Linux package installation in containers).
- Cosign verification gate in CI using ephemeral keys.

### Diagnostics

- `scripts/selftest_cli.py` and `scripts/selftest_gui.py` invoked by support instructions.
- Automatic log bundle generator zipped for support.

## Next Actions

1. Establish release workflows and packaging scripts to satisfy P0 distribution requirements.
2. Build the Tauri-based GUI with onboarding, autopilot controls, and offline-first behaviour.
3. Implement compliance-focused ingestion pipeline and RAG storage with sandboxing.
4. Expand automated testing, documentation, and legal artefacts to meet P1/P2 goals.

