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
from app.ingest import KnowledgeStatus, SourceRegistry
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
    "KnowledgeGapDetector",
    "LedgerView",
    "MultiSourceVerifier",
    "PromotionEvaluator",
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
    content: str | None = None
    fetched_at: datetime | None = None
    etag: str | None = None
    last_modified: str | None = None
    source_type: str = "web"


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
    knowledge_gaps: list[str] = field(default_factory=list)
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    """Outcome of the lightweight promotion gate."""

    promote: bool
    evaluation_status: str
    evaluation_score: float
    evaluation_reason: str


class PromotionEvaluator:
    """Minimal deterministic gate applied before promotion."""

    def __init__(self, *, max_age_days: int | None = 365) -> None:
        self.max_age_days = max_age_days

    def evaluate(
        self,
        *,
        document: RawDocument,
        corroborating_domains: int,
        now: datetime,
        min_corroborating_domains: int,
    ) -> PromotionDecision:
        domains = max(0, int(corroborating_domains))
        minimum = max(2, int(min_corroborating_domains))
        if domains < minimum:
            score = round(min(0.49, 0.25 + (domains * 0.1)), 2)
            return PromotionDecision(
                promote=False,
                evaluation_status="rejected",
                evaluation_score=score,
                evaluation_reason=(
                    f"rejected by evaluator: only {domains} corroborating domains"
                ),
            )

        age_days = _document_age_days(document.published_at, now)
        if age_days is not None and self.max_age_days is not None and age_days > self.max_age_days:
            score = round(min(0.69, 0.45 + max(0, domains - minimum) * 0.05), 2)
            return PromotionDecision(
                promote=False,
                evaluation_status="rejected",
                evaluation_score=score,
                evaluation_reason=(
                    f"rejected by evaluator: content is {age_days} days old "
                    f"(max {self.max_age_days})"
                ),
            )

        freshness_bonus = 0.05
        freshness_label = "freshness unknown"
        if age_days is not None:
            freshness_bonus = 0.2 if age_days <= 30 else 0.1
            freshness_label = f"age {age_days} days"
        score = round(
            min(1.0, 0.6 + max(0, domains - minimum) * 0.1 + freshness_bonus),
            2,
        )
        return PromotionDecision(
            promote=True,
            evaluation_status="promoted",
            evaluation_score=score,
            evaluation_reason=(
                "promoted after evaluation: "
                f"{domains} corroborating domains and {freshness_label}"
            ),
        )


class KnowledgeGapDetector:
    """Detect topics that are not sufficiently covered by a run."""

    def detect(
        self,
        *,
        topics: Sequence[str],
        discovered: Sequence[DiscoveryResult],
        ingested: Sequence[RawDocument],
    ) -> list[str]:
        gaps: list[str] = []
        for topic in topics:
            label = topic.strip()
            if not label:
                continue
            lowered = label.lower()
            discovered_match = any(
                _topic_matches(lowered, item.url, item.title, item.summary)
                for item in discovered
            )
            ingested_match = any(
                _topic_matches(lowered, doc.url, doc.title, doc.text)
                for doc in ingested
            )
            if not discovered_match:
                gaps.append(f"{label}: aucune source découverte")
                continue
            if not ingested_match:
                gaps.append(f"{label}: sources découvertes mais non ingérées")
        return gaps


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

    def corroboration_counts(
        self,
        documents: Sequence[tuple[RawDocument, str]],
    ) -> dict[str, int]:
        grouped: MutableMapping[str, list[tuple[RawDocument, str]]] = defaultdict(list)
        for document, digest in documents:
            grouped[digest].append((document, digest))
        counts: dict[str, int] = {}
        for digest, items in grouped.items():
            domains = {
                domain
                for document, _ in items
                if (domain := _domain_from_url(document.url)) is not None
            }
            counts[digest] = len(domains)
        return counts

    def filter(self, documents: Sequence[tuple[RawDocument, str]]) -> list[tuple[RawDocument, str]]:
        grouped: MutableMapping[str, list[tuple[RawDocument, str]]] = defaultdict(list)
        for document, digest in documents:
            grouped[digest].append((document, digest))
        counts = self.corroboration_counts(documents)
        validated: list[tuple[RawDocument, str]] = []
        for digest, items in grouped.items():
            if counts.get(digest, 0) < self._min_sources:
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
    """Persist weekly HTML report about promotion and rollback outcomes."""

    def __init__(self, output_path: Path) -> None:
        self.output_path = output_path
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._history_path = output_path.with_suffix(".json")

    def record(
        self,
        *,
        ingested: Sequence[str],
        rejected: Sequence[str],
        revoked_domains: Sequence[str],
        revoked_sources: Sequence[str],
        knowledge_gaps: Sequence[str],
        timestamp: datetime,
    ) -> None:
        history = self._load_history()
        now_iso = timestamp.isoformat()
        for url in ingested:
            history.append({"type": "ingested", "value": url, "timestamp": now_iso})
        for item in rejected:
            history.append(
                {"type": "rejected_promotion", "value": item, "timestamp": now_iso}
            )
        for domain in revoked_domains:
            history.append(
                {"type": "revoked_domain", "value": domain, "timestamp": now_iso}
            )
        for url in revoked_sources:
            history.append(
                {"type": "revoked_source", "value": url, "timestamp": now_iso}
            )
        for gap in knowledge_gaps:
            history.append({"type": "knowledge_gap", "value": gap, "timestamp": now_iso})
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
        rejected: list[str] = []
        revoked_domains: list[str] = []
        revoked_sources: list[str] = []
        knowledge_gaps: list[str] = []
        for entry in history:
            timestamp = LedgerView._parse_timestamp(entry.get("timestamp"))
            if timestamp is None:
                continue
            if _normalise_datetime(timestamp) < since_norm:
                continue
            if entry.get("type") == "ingested":
                ingested.append(str(entry.get("value", "")))
            elif entry.get("type") == "rejected_promotion":
                rejected.append(str(entry.get("value", "")))
            elif entry.get("type") in {"revoked", "revoked_domain"}:
                revoked_domains.append(str(entry.get("value", "")))
            elif entry.get("type") == "revoked_source":
                revoked_sources.append(str(entry.get("value", "")))
            elif entry.get("type") == "knowledge_gap":
                knowledge_gaps.append(str(entry.get("value", "")))
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
        html.append("    <h2>Promotions rejetées</h2>")
        if rejected:
            html.append("    <ul>")
            html.extend(f"      <li>{item}</li>" for item in sorted(set(rejected)))
            html.append("    </ul>")
        else:
            html.append("    <p>Aucune promotion rejetée.</p>")
        html.append("    <h2>Sources révoquées</h2>")
        if revoked_sources:
            html.append("    <ul>")
            html.extend(f"      <li>{item}</li>" for item in sorted(set(revoked_sources)))
            html.append("    </ul>")
        else:
            html.append("    <p>Aucune source révoquée.</p>")
        html.append("    <h2>Domaines révoqués</h2>")
        if revoked_domains:
            html.append("    <ul>")
            html.extend(f"      <li>{item}</li>" for item in sorted(set(revoked_domains)))
            html.append("    </ul>")
        else:
            html.append("    <p>Aucun domaine révoqué.</p>")
        html.append("    <h2>Knowledge gaps détectés</h2>")
        if knowledge_gaps:
            html.append("    <ul>")
            html.extend(f"      <li>{item}</li>" for item in sorted(set(knowledge_gaps)))
            html.append("    </ul>")
        else:
            html.append("    <p>Aucun gap détecté.</p>")
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
        promotion_evaluator: PromotionEvaluator | None = None,
    ) -> None:
        self.scheduler = scheduler
        self.pipeline = pipeline
        policy_manager = scheduler._policy_manager  # type: ignore[attr-defined]
        self._policy_loader = scheduler._policy_loader  # type: ignore[attr-defined]
        if crawler is None:
            from app.autopilot.discovery import DefaultDiscoveryCrawler

            crawler = DefaultDiscoveryCrawler(
                can_fetch=self._can_fetch_more_bandwidth,
                register_payload_bytes=self._register_bandwidth_bytes,
            )
        self.crawler = crawler
        self.scraper = scraper or HTTPScraper()
        self._throttle = max(0.0, float(throttle_seconds))
        self._sleep = sleep_func or time.sleep
        self._clock = clock or datetime.utcnow
        self._logger = logger or LOGGER
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
        self._gap_detector = KnowledgeGapDetector()
        self._source_registry = SourceRegistry(self._config_dir / "source-registry.json")
        self._last_request: dict[str, float] = {}
        self._promotion_evaluator = promotion_evaluator or PromotionEvaluator()

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
        if policy.kill_switch_engaged():
            self._logger.warning("Kill-switch actif – exécution interrompue.")
            return AutopilotRunResult(ingested=0, reason="kill-switch")
        if not policy.allowlist_domains:
            self._logger.warning("Aucun domaine autorisé – rien à faire.")
            return AutopilotRunResult(ingested=0, reason="allowlist vide")

        allowed_rules = policy.domain_rules()
        allowed = {rule.domain: rule for rule in allowed_rules}
        consented = self._ledger_view.approvals()
        gate = ConsentGate(
            allowed=allowed,
            consented=consented,
            require_consent=True,
            logger=self._logger,
        )
        if policy.require_corroboration > self.pipeline.min_sources:
            self.pipeline.min_sources = policy.require_corroboration
        verifier = MultiSourceVerifier(min_sources=self.pipeline.min_sources)
        recent_revoked = self._ledger_view.revocations_since(now - timedelta(days=7))
        revoked_sources = self._apply_recent_revocations(recent_revoked, observed_at=now)

        active_topics = topics or state.topics
        discovered = list(self.crawler.discover(active_topics, allowed.values()))
        for item in discovered:
            self._source_registry.record(
                source=item.url,
                source_type=item.source_type or _source_type_from_url(item.url),
                status=KnowledgeStatus.RAW,
                confidence=0.0,
                freshness_at=item.published_at,
                licence=item.licence,
                status_reason="discovered",
                observed_at=now,
            )
        collected: list[tuple[RawDocument, str]] = []
        skipped: list[str] = []

        per_domain_bandwidth: MutableMapping[str, float] = defaultdict(float)
        start_time = now

        for item in discovered:
            if not self.scheduler.has_bandwidth_budget(policy, now=self._clock()):
                self._logger.warning(
                    "Budget global dépassé (%.2f MB).",
                    float(policy.budgets.bandwidth_mb_per_day),
                )
                break
            if not gate.allow(item.url):
                self._source_registry.reject(
                    source=item.url,
                    source_type=item.source_type or _source_type_from_url(item.url),
                    reason="blocked by policy or consent",
                    freshness_at=item.published_at,
                    licence=item.licence,
                    observed_at=self._clock(),
                )
                continue
            domain = _domain_from_url(item.url)
            if not domain:
                skipped.append(item.url)
                self._source_registry.reject(
                    source=item.url,
                    source_type=item.source_type or _source_type_from_url(item.url),
                    reason="invalid domain",
                    freshness_at=item.published_at,
                    licence=item.licence,
                    observed_at=self._clock(),
                )
                continue
            rule = allowed.get(domain)
            if rule is None:
                rule = DomainRule(
                    domain=domain,
                    bandwidth_mb=policy.budgets.bandwidth_mb_per_day,
                    time_budget_minutes=policy.window_duration_minutes(),
                )
            if self._exceeded_time(policy, rule, start_time):
                self._logger.warning("Budget temporel dépassé pour %s.", domain)
                break
            source_type = item.source_type or _source_type_from_url(item.url)
            if item.content is not None:
                text = item.content.strip()
                licence = item.licence
                fetched_at = item.fetched_at or self._clock()
                etag = item.etag
                last_modified = item.last_modified
            else:
                self._throttle_domain(domain)
                result = self.scraper.fetch(item.url, respect_robots=True)
                if result is None:
                    skipped.append(item.url)
                    self._source_registry.reject(
                        source=item.url,
                        source_type=source_type,
                        reason="fetch failed",
                        freshness_at=item.published_at,
                        licence=item.licence,
                        observed_at=self._clock(),
                    )
                    continue
                payload_mb = _bytes_to_mb(len(result.raw_content))
                per_domain_bandwidth[domain] += payload_mb
                self.scheduler.register_bandwidth_usage(payload_mb, now=self._clock())
                if per_domain_bandwidth[domain] > float(rule.bandwidth_mb):
                    self._logger.warning(
                        "Budget de bande passante dépassé pour %s (%.2f MB).",
                        domain,
                        rule.bandwidth_mb,
                    )
                    break
                if not result.content:
                    skipped.append(item.url)
                    self._source_registry.reject(
                        source=item.url,
                        source_type=source_type,
                        reason="empty content",
                        freshness_at=item.published_at,
                        licence=result.license or item.licence,
                        observed_at=self._clock(),
                    )
                    continue
                text = result.content.strip()
                licence = result.license or item.licence
                fetched_at = self._clock()
                etag = result.etag
                last_modified = result.last_modified
            if licence is None or licence not in self.pipeline.allowed_licences:
                skipped.append(item.url)
                self._source_registry.reject(
                    source=item.url,
                    source_type=source_type,
                    reason="incompatible licence",
                    freshness_at=item.published_at,
                    licence=licence,
                    observed_at=self._clock(),
                )
                continue
            if not text:
                skipped.append(item.url)
                self._source_registry.reject(
                    source=item.url,
                    source_type=source_type,
                    reason="blank content",
                    freshness_at=item.published_at,
                    licence=licence,
                    observed_at=self._clock(),
                )
                continue
            title = item.title or self._guess_title(text)
            fetched_at = self._clock()
            raw = RawDocument(
                url=item.url,
                title=title,
                text=text,
                licence=licence,
                published_at=item.published_at,
                source_type=source_type,
                fetched_at=fetched_at,
                etag=etag,
                last_modified=last_modified,
            )
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            collected.append((raw, digest))

        corroboration_counts = verifier.corroboration_counts(collected)
        verified = verifier.filter(collected)
        verified_documents = [item[0] for item in verified]
        verified_sources = {item.url for item in verified_documents}
        rejected_promotions: list[str] = []
        for document, digest in verified:
            corroborating_domains = corroboration_counts.get(digest, 0)
            self._source_registry.record(
                source=document.url,
                source_type=document.source_type,
                status=KnowledgeStatus.VALIDATED,
                confidence=1.0,
                freshness_at=document.published_at,
                licence=document.licence,
                corroborating_sources=corroborating_domains,
                status_reason=_validated_reason(corroborating_domains),
                observed_at=self._clock(),
            )
        promotable: list[tuple[RawDocument, str, PromotionDecision]] = []
        promotable_documents: list[RawDocument] = []
        for document, digest in verified:
            corroborating_domains = corroboration_counts.get(digest, 0)
            decision = self._promotion_evaluator.evaluate(
                document=document,
                corroborating_domains=corroborating_domains,
                now=self._clock(),
                min_corroborating_domains=self.pipeline.min_sources,
            )
            if decision.promote:
                document.evaluation_status = decision.evaluation_status
                document.evaluation_score = decision.evaluation_score
                document.evaluation_reason = decision.evaluation_reason
                promotable.append((document, digest, decision))
                promotable_documents.append(document)
                continue
            skipped.append(document.url)
            self._source_registry.record(
                source=document.url,
                source_type=document.source_type,
                status=KnowledgeStatus.VALIDATED,
                confidence=decision.evaluation_score,
                freshness_at=document.published_at,
                licence=document.licence,
                corroborating_sources=corroborating_domains,
                status_reason=decision.evaluation_reason,
                evaluation_status=decision.evaluation_status,
                evaluation_score=decision.evaluation_score,
                evaluation_reason=decision.evaluation_reason,
                observed_at=self._clock(),
            )
            rejected_promotions.append(
                f"{document.url} | {decision.evaluation_reason}"
            )
        for document, digest in collected:
            if document.url in verified_sources:
                continue
            self._source_registry.reject(
                source=document.url,
                source_type=document.source_type,
                reason="insufficient corroboration",
                freshness_at=document.published_at,
                licence=document.licence,
                corroborating_sources=corroboration_counts.get(digest),
                observed_at=self._clock(),
            )
        knowledge_gaps = self._gap_detector.detect(
            topics=active_topics,
            discovered=discovered,
            ingested=promotable_documents,
        )
        if not verified:
            self._logger.info("Aucun contenu corroboré à ingérer.")
            return self._finalize_run(
                ingested=0,
                ingested_urls=[],
                rejected=rejected_promotions,
                revoked_domains=recent_revoked,
                revoked_sources=revoked_sources,
                skipped=skipped,
                blocked=gate.blocked,
                knowledge_gaps=knowledge_gaps,
            )
        if not promotable:
            self._logger.info("Aucun contenu n'a franchi la porte de promotion.")
            return self._finalize_run(
                ingested=0,
                ingested_urls=[],
                rejected=rejected_promotions,
                revoked_domains=recent_revoked,
                revoked_sources=revoked_sources,
                skipped=skipped,
                blocked=gate.blocked,
                knowledge_gaps=knowledge_gaps,
                reason="évaluation défavorable",
            )

        try:
            with VectorStoreTransaction(self.pipeline.store) as transaction:
                ingested = self.pipeline.ingest(promotable_documents)
                transaction.commit()
        except IngestValidationError as exc:
            self._logger.error("Ingestion interrompue: %s", exc)
            return self._finalize_run(
                ingested=0,
                ingested_urls=[],
                rejected=rejected_promotions,
                revoked_domains=recent_revoked,
                revoked_sources=revoked_sources,
                skipped=skipped,
                blocked=gate.blocked,
                knowledge_gaps=knowledge_gaps,
                reason="ingestion invalide",
            )
        for document, digest, decision in promotable:
            corroborating_domains = corroboration_counts.get(digest, 0)
            self._source_registry.record(
                source=document.url,
                source_type=document.source_type,
                status=KnowledgeStatus.PROMOTED,
                confidence=decision.evaluation_score,
                freshness_at=document.published_at,
                licence=document.licence,
                corroborating_sources=corroborating_domains,
                status_reason=decision.evaluation_reason,
                evaluation_status=decision.evaluation_status,
                evaluation_score=decision.evaluation_score,
                evaluation_reason=decision.evaluation_reason,
                observed_at=self._clock(),
            )
        return self._finalize_run(
            ingested=ingested,
            ingested_urls=[item.url for item in promotable_documents],
            rejected=rejected_promotions,
            revoked_domains=recent_revoked,
            revoked_sources=revoked_sources,
            skipped=skipped,
            blocked=gate.blocked,
            knowledge_gaps=knowledge_gaps,
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
        if elapsed > float(policy.window_duration_minutes()):
            return True
        return elapsed > float(rule.time_budget_minutes)

    @staticmethod
    def _guess_title(text: str) -> str:
        first_line = text.split("\n", 1)[0]
        return first_line[:120].strip() or "Document"

    def _can_fetch_more_bandwidth(self) -> bool:
        try:
            policy = self._policy_loader()
        except PolicyError:
            return False
        return self.scheduler.has_bandwidth_budget(policy, now=self._clock())

    def _register_bandwidth_bytes(self, payload_bytes: int) -> None:
        if payload_bytes <= 0:
            return
        self.scheduler.register_bandwidth_usage(
            _bytes_to_mb(payload_bytes),
            now=self._clock(),
        )

    def _apply_recent_revocations(
        self,
        revoked_domains: Sequence[str],
        *,
        observed_at: datetime,
    ) -> list[str]:
        domains = sorted(
            {
                domain.strip().lower()
                for domain in revoked_domains
                if isinstance(domain, str) and domain.strip()
            }
        )
        if not domains:
            return []
        reason = "revoked by consent ledger"
        revoked_entries = self._source_registry.revoke_domains(
            domains=domains,
            reason=reason,
            observed_at=observed_at,
        )
        delete_by_domains = getattr(self.pipeline.store, "delete_by_domains", None)
        if callable(delete_by_domains):
            removed = int(delete_by_domains(domains))
            if removed:
                self._logger.info(
                    "%s documents supprimés du vector store après révocation.",
                    removed,
                )
        return [entry.source for entry in revoked_entries]

    def _finalize_run(
        self,
        *,
        ingested: int,
        ingested_urls: Sequence[str],
        rejected: Sequence[str],
        revoked_domains: Sequence[str],
        revoked_sources: Sequence[str],
        skipped: Sequence[str],
        blocked: Sequence[str],
        knowledge_gaps: Sequence[str],
        reason: str | None = None,
    ) -> AutopilotRunResult:
        self._reporter.record(
            ingested=ingested_urls,
            rejected=rejected,
            revoked_domains=revoked_domains,
            revoked_sources=revoked_sources,
            knowledge_gaps=knowledge_gaps,
            timestamp=self._clock(),
        )
        return AutopilotRunResult(
            ingested=ingested,
            skipped=list(skipped),
            blocked=list(blocked),
            knowledge_gaps=list(knowledge_gaps),
            reason=reason,
        )


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


def _validated_reason(corroborating_domains: int) -> str:
    return (
        f"corroborated by {max(0, int(corroborating_domains))} distinct domains"
    )


def _document_age_days(
    published_at: datetime | None,
    now: datetime,
) -> int | None:
    if published_at is None:
        return None
    delta = _normalise_datetime(now) - _normalise_datetime(published_at)
    return max(0, int(delta.total_seconds() // 86400))


def _topic_matches(topic: str, *values: str) -> bool:
    haystack = " ".join(value.lower() for value in values if value)
    return topic in haystack


def _normalise_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _source_type_from_url(url: str) -> str:
    domain = _domain_from_url(url) or ""
    if domain == "github.com":
        return "git"
    return "web"
