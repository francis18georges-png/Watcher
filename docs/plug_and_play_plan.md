# Watcher Plug-and-Play Implementation Plan

## Scope Warning
The requested feature set exceeds the capacity of a single iteration in this environment. This plan captures the architecture, task breakdown, and sequencing required for a future implementation while keeping the repository untouched regarding runtime behaviour.

## Architectural Overview
1. Hardware introspection service producing model selection profiles.
2. Policy and consent subsystem with signed JSONL ledger.
3. Controlled scraping pipeline enforcing robots.txt and licensing.
4. Local-only RAG ingestion stack with SQLite VSS backend.
5. Autopilot orchestrator enforcing policy budgets and offline windows.
6. Sandboxed tool runner using OS-specific isolation primitives.
7. Unified CLI covering init, policy, ingest, autopilot, cache, eval.
8. Comprehensive test suite with offline defaults and high coverage targets.
9. Supply chain hardening and release automation (SBOM, signatures, containers).
10. Autonomy reporting module producing weekly HTML summaries.

## Workstreams
- **Initialization**: implement `watcher init --auto`, download manager, config writer, scripts generation.
- **Policy**: enforce schema, consent ledger, CLI actions, kill-switch integration.
- **Scraping**: modular scrapers, throttling, dedupe, licence detection, multi-source verification.
- **Ingestion**: chunking, embeddings, index (SQLite-VSS/FAISS), metadata tracking.
- **Autopilot**: scheduler, network gating, topic planning, journaling.
- **Sandbox**: subprocess isolation, cgroups/jobs, FS confinement.
- **CLI**: restructure with Typer/argparse ensuring stable exit codes, offline default.
- **Testing**: adopt pytest-socket, deterministic offline run, coverage gates.
- **CI/CD**: integrate Scorecard, CodeQL, gitleaks, pip-audit, release packaging, MkDocs sections.
- **Reporting**: aggregated metrics, HTML reports, JSON logs with trace IDs.

## Next Steps
1. Align stakeholders on the staged roadmap.
2. Establish infra for large file downloads and caching.
3. Implement high-priority safety controls (policy enforcement, sandboxing) before enabling autopilot.
