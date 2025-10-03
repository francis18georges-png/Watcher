"""Autopilot orchestration pipeline linking discovery, scraping and ingestion."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Iterator, Mapping, MutableMapping, Protocol, Sequence
from urllib.parse import urlparse

from app.autopilot.scheduler import AutopilotError, AutopilotScheduler
from app.ingest.pipeline import IngestPipeline, IngestValidationError, RawDocument
from app.policy.manager import PolicyError
from app.policy.schema import DomainRule, Policy
from app.scrapers.http import HTTPScraper, ScrapeResult

LOGGER = logging.getLogger(__name__)

__all__ = [
    "AutopilotController",
    "AutopilotRunResult",
    "ConsentGate",
    "DiscoveryResult",
    "LedgerView",
    "MultiSourceVerifier",
    "ReportGenerator",
]


# ---------------------------------------------------------------------------
# Protocols & dataclasses


@dataclass(slots=True)
class DiscoveryResult:
    """Result coming from the discovery crawler."""

    url: str
    title: str
    summary: str
    licence: str | None = None
    published_at: datetime | None = None


class DiscoveryCrawler(Protocol):
    """Protocol expected from discovery implementations."""

    def discover(
        self,
        topics: Sequence[str],
        rules: Sequence[DomainRule],
    ) -> Iterable[DiscoveryResult]:
        """Yield discovery results for the provided *topics* and *rules*."""


class Scraper(Protocol):
    """Protocol for scraping engines."""

    def fetch(self, url: str, *, respect_robots: bool = True) -> ScrapeResult | None:
        """Return a :class:`ScrapeResult` for *url* or ``None`` when unavailable."""


@dataclass(slots=True)
class AutopilotRunResult:
    """Summary returned after an autopilot orchestration cycle."""

    ingested: int
    skipped: list[str] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)
    reason: str | None = None


class ConsentGate:
    """Gatekeeper enforcing allowlist and consent ledger rules."""

    def __init__(
        self,
        *,
        allowed: Mapping[str, DomainRule],
        consented: Mapping[str, str],
        require_consent: bool,
        logger: logging.Logger | None = None,
    ) -> None:
        self._allowed = allowed
        self._consented = consented
        self._require_consent = require_consent
        self._logger = logger or LOGGER
        self._blocked: set[str] = set()

    def allow(self, url: str) -> bool:
        domain = _domain_from_url(url)
        if not domain:
            return False
        if domain in self._allowed:
            return True
        if not self._require_consent:
            return False
        if domain not in self._consented:
            if domain not in self._blocked:
                self._logger.warning(
                    "Domaine %s suspendu – consentement manquant.",
                    domain,
                )
            self._blocked.add(domain)
            return False
        # Single-use consent: consume immediately
        del self._consented[domain]
        self._logger.info(
            "Consentement unique consommé pour %s.",
            domain,
        )
        return True

    @property
    def blocked(self) -> list[str]:
        return sorted(self._blocked)


class MultiSourceVerifier:
    """Ensure that documents are corroborated by multiple sources."""

    def __init__(self, *, min_sources: int) -> None:
        self._min_sources = max(2, min_sources)

    def filter(self, documents: Sequence[tuple[RawDocument, str]]) -> list[tuple[RawDocument, str]]:
        grouped: MutableMapping[str, list[tuple[RawDocument, str]]] = defaultdict(list)
        for document, digest in documents:
            grouped[digest].append((document, digest))
        validated: list[tuple[RawDocument, str]] = []
        for digest, items in grouped.items():
            domains = {_domain_from_url(item[0].url) for item in items}
            if len(domains) < self._min_sources:
                continue
            validated.extend(items)
        return validated


class VectorStoreTransaction:
    """Best-effort transactional guard for vector store mutations."""

    def __init__(self, store) -> None:
        self._store = store
        self._committed = False
        self._token = None
        self._path = Path(getattr(store, "path", "")) if getattr(store, "path", None) else None

    def __enter__(self) -> "VectorStoreTransaction":
        self._snapshot()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is not None or not self._committed:
            self.rollback()

    def commit(self) -> None:
        self._committed = True

    # ------------------------------------------------------------------

    def _snapshot(self) -> None:
        if hasattr(self._store, "snapshot"):
            self._token = self._store.snapshot()
            return
        if self._path and self._path.exists():
            self._token = self._path.read_bytes()

    def rollback(self) -> None:
        if hasattr(self._store, "restore"):
            if self._token is not None:
                self._store.restore(self._token)
            return
        if self._path is None:
            return
        if self._token is None:
            if self._path.exists():
                self._path.unlink()
            return
        self._path.write_bytes(self._token)


class LedgerView:
    """Read access helper for the consent ledger."""

    def __init__(self, path: Path | None) -> None:
        self.path = path

    def approvals(self) -> dict[str, str]:
        records = self._load_entries()
        approvals: dict[str, str] = {}
        for entry in records:
            action = entry.get("action")
            domain = entry.get("domain")
            if not isinstance(domain, str):
                continue
            if action == "approve":
                approvals[domain] = entry.get("timestamp", "")
            elif action == "revoke":
                approvals.pop(domain, None)
        return approvals

    def revocations_since(self, since: datetime) -> list[str]:
        records = self._load_entries()
        revoked: list[str] = []
        since_norm = _normalise_datetime(since)
        for entry in records:
            if entry.get("action") != "revoke":
                continue
            timestamp = self._parse_timestamp(entry.get("timestamp"))
            if timestamp is None:
                continue
            if _normalise_datetime(timestamp) < since_norm:
                continue
            domain = entry.get("domain")
            if isinstance(domain, str):
                revoked.append(domain)
        return revoked

    def _load_entries(self) -> Iterator[dict[str, str]]:
        if self.path is None or not self.path.exists():
            return iter(())
        with self.path.open("r", encoding="utf-8") as handle:
            lines = handle.readlines()
        if not lines:
            return iter(())
        entries: list[dict[str, str]] = []
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            entries.append({str(k): v for k, v in data.items()})
        return iter(entries)

    @staticmethod
    def _parse_timestamp(value: object) -> datetime | None:
        if not isinstance(value, str):
            return None
        try:
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            return datetime.fromisoformat(value)
        except ValueError:
            return None


class ReportGenerator:
    """Persist weekly HTML report about ingested and revoked sources."""

    def __init__(self, output_path: Path) -> None:
        self.output_path = output_path
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._history_path = output_path.with_suffix(".json")

    def record(
        self,
        *,
        ingested: Sequence[str],
        revoked: Sequence[str],
        timestamp: datetime,
    ) -> None:
        history = self._load_history()
        now_iso = timestamp.isoformat()
        for url in ingested:
            history.append({"type": "ingested", "value": url, "timestamp": now_iso})
        for domain in revoked:
            history.append({"type": "revoked", "value": domain, "timestamp": now_iso})
        self._save_history(history)
        self._write_report(history, timestamp)

    def _load_history(self) -> list[dict[str, str]]:
        if not self._history_path.exists():
            return []
        try:
            data = json.loads(self._history_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict)]

    def _save_history(self, history: Sequence[dict[str, str]]) -> None:
        self._history_path.write_text(
            json.dumps(list(history), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _write_report(self, history: Sequence[Mapping[str, str]], now: datetime) -> None:
        window_start = now - timedelta(days=7)
        since_norm = _normalise_datetime(window_start)
        ingested: list[str] = []
        revoked: list[str] = []
        for entry in history:
            timestamp = LedgerView._parse_timestamp(entry.get("timestamp"))
            if timestamp is None:
                continue
            if _normalise_datetime(timestamp) < since_norm:
                continue
            if entry.get("type") == "ingested":
                ingested.append(str(entry.get("value", "")))
            elif entry.get("type") == "revoked":
                revoked.append(str(entry.get("value", "")))
        html = [
            "<html>",
            "  <head>",
            "    <meta charset='utf-8'>",
            "    <title>Ce qui a été appris</title>",
            "  </head>",
            "  <body>",
            f"    <h1>Ce qui a été appris – semaine du {window_start.date()}</h1>",
        ]
        html.append("    <h2>Sources ingérées</h2>")
        if ingested:
            html.append("    <ul>")
            html.extend(f"      <li>{item}</li>" for item in sorted(set(ingested)))
            html.append("    </ul>")
        else:
            html.append("    <p>Aucune nouvelle source.</p>")
        html.append("    <h2>Sources révoquées</h2>")
        if revoked:
            html.append("    <ul>")
            html.extend(f"      <li>{item}</li>" for item in sorted(set(revoked)))
            html.append("    </ul>")
        else:
            html.append("    <p>Aucune révocation enregistrée.</p>")
        html.extend(["  </body>", "</html>"])
        self.output_path.write_text("\n".join(html), encoding="utf-8")


# ---------------------------------------------------------------------------
# Controller implementation


class AutopilotController:
    """High level coordinator chaining discovery, scraping and ingestion."""

    def __init__(
        self,
        *,
        scheduler: AutopilotScheduler,
        pipeline: IngestPipeline,
        crawler: DiscoveryCrawler | None = None,
        scraper: Scraper | None = None,
        throttle_seconds: float = 1.0,
        report_path: Path | None = None,
        logger: logging.Logger | None = None,
        sleep_func: callable | None = None,
        clock: callable | None = None,
    ) -> None:
        self.scheduler = scheduler
        self.pipeline = pipeline
        if crawler is None:
            from app.autopilot.discovery import DefaultDiscoveryCrawler

            crawler = DefaultDiscoveryCrawler()
        self.crawler = crawler
        self.scraper = scraper or HTTPScraper()
        self._throttle = max(0.0, float(throttle_seconds))
        self._sleep = sleep_func or time.sleep
        self._clock = clock or datetime.utcnow
        self._logger = logger or LOGGER
        policy_manager = scheduler._policy_manager  # type: ignore[attr-defined]
        self._policy_loader = scheduler._policy_loader  # type: ignore[attr-defined]
        self._config_dir = (
            policy_manager.config_dir
            if policy_manager is not None
            else Path.home() / ".watcher"
        )
        self._ledger_path = (
            policy_manager.ledger_path if policy_manager is not None else None
        )
        reports_dir = report_path or (self._config_dir / "reports" / "weekly.html")
        self._reporter = ReportGenerator(Path(reports_dir))
        self._ledger_view = LedgerView(self._ledger_path)
        self._last_request: dict[str, float] = {}

    # ------------------------------------------------------------------

    def run(self, topics: Sequence[str] | None = None) -> AutopilotRunResult:
        now = self._clock()
        topics = list(topics or [])
        if topics:
            state = self.scheduler.enable(topics, now=now)
        else:
            state = self.scheduler.evaluate(now=now)
        if not state.online:
            reason = state.last_reason or "offline"
            self._logger.info("Autopilot en pause (%s)", reason)
            return AutopilotRunResult(ingested=0, reason=reason)
        try:
            policy = self._policy_loader()
        except PolicyError as exc:  # pragma: no cover - defensive
            raise AutopilotError(str(exc)) from exc
        if policy.defaults.kill_switch:
            self._logger.warning("Kill-switch actif – exécution interrompue.")
            return AutopilotRunResult(ingested=0, reason="kill-switch")
        if not policy.network.allowlist:
            self._logger.warning("Aucun domaine autorisé – rien à faire.")
            return AutopilotRunResult(ingested=0, reason="allowlist vide")

        allowed = {rule.domain: rule for rule in policy.network.allowlist}
        consented = self._ledger_view.approvals()
        gate = ConsentGate(
            allowed=allowed,
            consented=consented,
            require_consent=policy.defaults.require_consent,
            logger=self._logger,
        )
        verifier = MultiSourceVerifier(min_sources=self.pipeline.min_sources)

        discovered = list(self.crawler.discover(topics or state.queue, allowed.values()))
        collected: list[tuple[RawDocument, str]] = []
        skipped: list[str] = []

        bandwidth_limit = float(policy.network.bandwidth_mb)
        total_bandwidth = 0.0
        per_domain_bandwidth: MutableMapping[str, float] = defaultdict(float)
        start_time = now

        for item in discovered:
            if not gate.allow(item.url):
                continue
            domain = _domain_from_url(item.url)
            if not domain:
                skipped.append(item.url)
                continue
            rule = allowed.get(domain)
            if rule is None:
                # consent single-use without explicit rule
                rule = DomainRule(
                    domain=domain,
                    categories=[],
                    bandwidth_mb=policy.network.bandwidth_mb,
                    time_budget_minutes=policy.network.time_budget_minutes,
                    allow_subdomains=True,
                    scope="web",
                )
            if self._exceeded_time(policy, rule, start_time):
                self._logger.warning("Budget temporel dépassé pour %s.", domain)
                break
            self._throttle_domain(domain)
            result = self.scraper.fetch(item.url, respect_robots=True)
            if result is None or not result.content:
                skipped.append(item.url)
                continue
            licence = result.license or item.licence
            if licence is None or licence not in self.pipeline.allowed_licences:
                skipped.append(item.url)
                continue
            text = result.content.strip()
            if not text:
                skipped.append(item.url)
                continue
            title = item.title or self._guess_title(text)
            raw = RawDocument(
                url=item.url,
                title=title,
                text=text,
                licence=licence,
                published_at=item.published_at,
            )
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            collected.append((raw, digest))
            payload_mb = _bytes_to_mb(len(result.raw_content))
            total_bandwidth += payload_mb
            per_domain_bandwidth[domain] += payload_mb
            if total_bandwidth > bandwidth_limit:
                self._logger.warning("Budget global dépassé (%s MB).", bandwidth_limit)
                break
            if per_domain_bandwidth[domain] > float(rule.bandwidth_mb):
                self._logger.warning(
                    "Budget de bande passante dépassé pour %s (%.2f MB).",
                    domain,
                    rule.bandwidth_mb,
                )
                break

        verified = verifier.filter(collected)
        if not verified:
            self._logger.info("Aucun contenu corroboré à ingérer.")
            return AutopilotRunResult(ingested=0, skipped=skipped, blocked=gate.blocked)

        try:
            with VectorStoreTransaction(self.pipeline.store) as transaction:
                ingested = self.pipeline.ingest([item[0] for item in verified])
                transaction.commit()
        except IngestValidationError as exc:
            self._logger.error("Ingestion interrompue: %s", exc)
            return AutopilotRunResult(
                ingested=0,
                skipped=skipped,
                blocked=gate.blocked,
                reason="ingestion invalide",
            )

        recent_revoked = self._ledger_view.revocations_since(now - timedelta(days=7))
        self._reporter.record(
            ingested=[item[0].url for item in verified],
            revoked=recent_revoked,
            timestamp=now,
        )
        return AutopilotRunResult(
            ingested=ingested,
            skipped=skipped,
            blocked=gate.blocked,
        )

    # ------------------------------------------------------------------

    def _throttle_domain(self, domain: str) -> None:
        if self._throttle <= 0:
            return
        now = time.monotonic()
        last = self._last_request.get(domain)
        if last is not None:
            delta = now - last
            if delta < self._throttle:
                self._sleep(self._throttle - delta)
        self._last_request[domain] = time.monotonic()

    def _exceeded_time(
        self,
        policy: Policy,
        rule: DomainRule,
        start: datetime,
    ) -> bool:
        elapsed = (self._clock() - start).total_seconds() / 60
        if elapsed > float(policy.network.time_budget_minutes):
            return True
        return elapsed > float(rule.time_budget_minutes)

    @staticmethod
    def _guess_title(text: str) -> str:
        first_line = text.split("\n", 1)[0]
        return first_line[:120].strip() or "Document"


# ---------------------------------------------------------------------------
# Helpers


def _domain_from_url(url: str) -> str | None:
    try:
        parsed = urlparse(url)
    except Exception:  # pragma: no cover - defensive
        return None
    hostname = parsed.hostname or ""
    return hostname.lower() or None


def _bytes_to_mb(size: int) -> float:
    if size <= 0:
        return 0.0
    return round(size / (1024 * 1024), 4)


def _normalise_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)

