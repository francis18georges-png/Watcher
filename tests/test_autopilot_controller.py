"""End-to-end and guardrail tests for the autopilot controller."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import yaml

from app.autopilot import (
    AutopilotController,
    ConsentGate,
    DefaultDiscoveryCrawler,
    DiscoveryResult,
    KnowledgeGapDetector,
    MultiSourceVerifier,
    PromotionEvaluator,
)
from app.autopilot.scheduler import AutopilotScheduler, ResourceUsage
from app.ingest import IngestPipeline, KnowledgeStatus, SourceRegistry
from app.ingest.pipeline import IngestValidationError, RawDocument
from app.policy.manager import PolicyManager
from app.scrapers.http import ScrapeResult


class ControlledClock:
    def __init__(self, start: datetime) -> None:
        self._now = start

    def advance(self, *, minutes: int = 0, seconds: int = 0) -> None:
        self._now += timedelta(minutes=minutes, seconds=seconds)

    def set(self, new_value: datetime) -> None:
        self._now = new_value

    def __call__(self) -> datetime:
        return self._now


class SequenceProbe:
    def __init__(self, values: Sequence[ResourceUsage]) -> None:
        self._values = list(values)
        self._index = 0

    def snapshot(self) -> ResourceUsage:
        value = self._values[min(self._index, len(self._values) - 1)]
        self._index += 1
        return value


class MemoryVectorStore:
    def __init__(self) -> None:
        self.data: list[tuple[str, dict[str, object]]] = []

    def add(self, texts: Sequence[str], metas: Sequence[dict[str, object]]) -> None:
        for text, meta in zip(texts, metas, strict=True):
            self.data.append((text, dict(meta)))

    def snapshot(self) -> list[tuple[str, dict[str, object]]]:
        return [
            (text, dict(meta))
            for text, meta in self.data
        ]

    def restore(self, snapshot: Sequence[tuple[str, dict[str, object]]]) -> None:
        self.data = [
            (text, dict(meta))
            for text, meta in snapshot
        ]

    def delete_by_domains(self, domains: Sequence[str]) -> int:
        revoked = {
            str(domain).strip().lower()
            for domain in domains
            if str(domain).strip()
        }
        original = len(self.data)
        self.data = [
            (text, dict(meta))
            for text, meta in self.data
            if str(meta.get("domain", "")).strip().lower() not in revoked
        ]
        return original - len(self.data)


class DummyCrawler:
    def __init__(self) -> None:
        self._batches: list[list[DiscoveryResult]] = []
        self.calls = 0

    def queue(self, results: Iterable[DiscoveryResult]) -> None:
        self._batches.append(list(results))

    def discover(
        self,
        topics: Sequence[str],
        rules: Sequence,
    ) -> Iterable[DiscoveryResult]:
        self.calls += 1
        if self._batches:
            return self._batches.pop(0)
        return []


class DummyScraper:
    def __init__(self, mapping: dict[str, ScrapeResult]) -> None:
        self.mapping = mapping
        self.calls: list[tuple[str, bool]] = []

    def fetch(self, url: str, *, respect_robots: bool = True) -> ScrapeResult | None:  # noqa: D401
        self.calls.append((url, respect_robots))
        return self.mapping.get(url)


class StubHTTP:
    def __init__(self, payloads: Mapping[str, bytes]) -> None:
        self.payloads = dict(payloads)
        self.calls: list[tuple[str, bool]] = []

    def fetch_raw(self, url: str, *, respect_robots: bool = True):  # noqa: D401
        self.calls.append((url, respect_robots))
        payload = self.payloads.get(url)
        if payload is None:
            return None
        return payload, {}


class FaultyPipeline(IngestPipeline):
    def ingest(self, documents: Sequence[RawDocument], *, seen_digests: set[str] | None = None) -> int:  # noqa: D401
        super().ingest(documents, seen_digests=seen_digests)
        raise IngestValidationError("rollback test")


@dataclass
class PolicyFiles:
    policy_path: Path
    ledger_path: Path


def _prepare_policy(home: Path, now: datetime) -> PolicyFiles:
    config_dir = home / ".watcher"
    config_dir.mkdir(parents=True, exist_ok=True)
    policy_path = config_dir / "policy.yaml"
    ledger_path = config_dir / "consents.jsonl"
    window = {
        "days": [now.strftime("%a").lower()[:3]],
        "start": "09:00",
        "end": "10:00",
    }
    policy = {
        "version": 2,
        "autostart": True,
        "offline_default": True,
        "require_corroboration": 2,
        "kill_switch_file": str(config_dir / "disable"),
        "network_windows": [window],
        "budgets": {
            "bandwidth_mb_per_day": 50,
            "cpu_percent_cap": 80,
            "ram_mb_cap": 1024,
        },
        "allowlist_domains": ["allowed-one.test", "allowed-two.test"],
        "subject": {"hostname": "test", "generated_at": now.isoformat()},
        "models": {
            "llm": {"name": "dummy", "sha256": "0", "license": "Apache-2.0"},
            "embedding": {"name": "dummy", "sha256": "1", "license": "Apache-2.0"},
        },
    }
    policy_path.write_text(yaml.safe_dump(policy, sort_keys=False), encoding="utf-8")
    timestamp = now.isoformat(timespec="seconds") + "Z"
    ledger_content = "\n".join(
        [
            json.dumps({"type": "metadata", "secret_hex": "00" * 32}),
            json.dumps(
                {
                    "type": "entry",
                    "timestamp": timestamp,
                    "action": "approve",
                    "domain": "oneshot.test",
                    "scope": "web",
                    "policy_hash": "abc",
                    "signature": "sig",
                }
            ),
            json.dumps(
                {
                    "type": "entry",
                    "timestamp": timestamp,
                    "action": "revoke",
                    "domain": "revoked.test",
                    "scope": "web",
                    "policy_hash": "abc",
                    "signature": "sig",
                }
            ),
        ]
    )
    ledger_path.write_text(ledger_content + "\n", encoding="utf-8")
    return PolicyFiles(policy_path=policy_path, ledger_path=ledger_path)


def _scrape(url: str, text: str) -> ScrapeResult:
    payload = text.encode("utf-8")
    return ScrapeResult(
        url=url,
        content=text,
        raw_content=payload,
        content_hash=hashlib.sha256(payload).hexdigest(),
        license="CC-BY-4.0",
        headers={},
        etag=None,
        last_modified=None,
        is_duplicate=False,
    )


def test_autopilot_controller_end_to_end(tmp_path: Path) -> None:
    start = datetime(2024, 1, 2, 9, 5, 0)
    files = _prepare_policy(tmp_path, start)
    clock = ControlledClock(start)
    probe = SequenceProbe(
        [
            ResourceUsage(cpu_percent=20, ram_mb=256),
            ResourceUsage(cpu_percent=95, ram_mb=256),
            ResourceUsage(cpu_percent=20, ram_mb=256),
            ResourceUsage(cpu_percent=20, ram_mb=256),
        ]
    )
    store = MemoryVectorStore()
    pipeline = IngestPipeline(store, chunk_size=256, min_sources=2, allowed_licences={"CC-BY-4.0"})

    crawler = DummyCrawler()
    text = "Le contenu valide partagé." * 8
    crawler.queue(
        [
            DiscoveryResult(
                url="https://allowed-one.test/article",
                title="Article A",
                summary="",
                licence="CC-BY-4.0",
            ),
            DiscoveryResult(
                url="https://allowed-two.test/article",
                title="Article B",
                summary="",
                licence="CC-BY-4.0",
            ),
            DiscoveryResult(
                url="https://blocked.test/info",
                title="Bloqué",
                summary="",
                licence="CC-BY-4.0",
            ),
            DiscoveryResult(
                url="https://oneshot.test/update",
                title="Consentement",
                summary="",
                licence="CC-BY-4.0",
            ),
        ]
    )
    crawler.queue(
        [
            DiscoveryResult(
                url="https://allowed-one.test/article",
                title="Article A",
                summary="",
                licence="CC-BY-4.0",
            ),
            DiscoveryResult(
                url="https://allowed-two.test/article",
                title="Article B",
                summary="",
                licence="CC-BY-4.0",
            ),
        ]
    )

    scraper = DummyScraper(
        {
            "https://allowed-one.test/article": _scrape("https://allowed-one.test/article", text),
            "https://allowed-two.test/article": _scrape("https://allowed-two.test/article", text),
            "https://oneshot.test/update": _scrape("https://oneshot.test/update", text),
        }
    )

    manager = PolicyManager(home=tmp_path)
    scheduler = AutopilotScheduler(
        policy_manager=manager,
        state_path=files.policy_path.parent / "autopilot-state.json",
        resource_probe=probe,
        clock=clock,
    )
    controller = AutopilotController(
        scheduler=scheduler,
        pipeline=pipeline,
        crawler=crawler,
        scraper=scraper,
        throttle_seconds=0.0,
        clock=clock,
        sleep_func=lambda _: None,
        report_path=files.policy_path.parent / "reports" / "weekly.html",
    )

    result = controller.run(["veille"])
    assert result.ingested == 1
    assert "blocked.test" in result.blocked
    assert store.data, "store must contain ingested entries"
    registry = {
        item["source"]: item
        for item in json.loads(
            (files.policy_path.parent / "source-registry.json").read_text(encoding="utf-8")
        )
    }
    assert registry["https://allowed-one.test/article"]["status"] == "promoted"
    assert registry["https://allowed-two.test/article"]["status"] == "promoted"
    assert registry["https://oneshot.test/update"]["status"] == "promoted"
    assert registry["https://allowed-one.test/article"]["corroborating_sources"] == 3
    assert (
        registry["https://allowed-one.test/article"]["status_reason"]
        == "promoted after evaluation: 3 corroborating domains and freshness unknown"
    )
    assert registry["https://allowed-one.test/article"]["evaluation_status"] == "promoted"
    assert registry["https://allowed-one.test/article"]["evaluation_score"] == 0.75
    assert (
        registry["https://allowed-one.test/article"]["evaluation_reason"]
        == "promoted after evaluation: 3 corroborating domains and freshness unknown"
    )
    assert registry["https://blocked.test/info"]["status"] == "raw"
    assert (
        registry["https://blocked.test/info"]["status_reason"]
        == "rejected: blocked by policy or consent"
    )
    assert store.data[0][1]["evaluation_status"] == "promoted"
    assert store.data[0][1]["evaluation_score"] == 0.75

    # Budgets exceeded – autopilot pauses before scraping
    clock.advance(minutes=1)
    result_budget = controller.run()
    assert result_budget.reason == "budgets dépassés"
    assert len(store.data) == 1

    # Outside allowed window
    clock.set(datetime(2024, 1, 2, 11, 0, 0))
    result_window = controller.run()
    assert result_window.reason == "hors fenêtre réseau"
    assert len(store.data) == 1

    # Rollback when ingestion fails
    clock.set(datetime(2024, 1, 2, 9, 5, 0))
    crawler.queue(
        [
            DiscoveryResult(
                url="https://allowed-one.test/article",
                title="Article A",
                summary="",
                licence="CC-BY-4.0",
            ),
            DiscoveryResult(
                url="https://allowed-two.test/article",
                title="Article B",
                summary="",
                licence="CC-BY-4.0",
            ),
        ]
    )
    controller.pipeline = FaultyPipeline(store, chunk_size=256, min_sources=2, allowed_licences={"CC-BY-4.0"})
    result_fail = controller.run()
    assert result_fail.reason == "ingestion invalide"
    assert len(store.data) == 1, "store should be restored after failure"

    report_path = files.policy_path.parent / "reports" / "weekly.html"
    assert report_path.exists()
    report_html = report_path.read_text(encoding="utf-8")
    assert "Ce qui a été appris" in report_html
    assert "revoked.test" in report_html
    assert "Knowledge gaps détectés" in report_html


def test_consent_gate_and_verifier() -> None:
    gate = ConsentGate(
        allowed={"allowed.test": object()},
        consented={"oneshot.test": "now"},
        require_consent=True,
    )
    assert gate.allow("https://allowed.test/foo")
    assert gate.allow("https://oneshot.test/bar")
    assert not gate.allow("https://oneshot.test/bar")
    assert "oneshot.test" in gate.blocked

    doc_a = RawDocument(url="https://a.test/1", title="A", text="same", licence="CC-BY-4.0")
    doc_b = RawDocument(url="https://b.test/2", title="B", text="same", licence="CC-BY-4.0")
    doc_c = RawDocument(url="https://c.test/3", title="C", text="unique", licence="CC-BY-4.0")
    digest_same = hashlib.sha256("same".encode("utf-8")).hexdigest()
    digest_unique = hashlib.sha256("unique".encode("utf-8")).hexdigest()
    verifier = MultiSourceVerifier(min_sources=2)
    counts = verifier.corroboration_counts(
        [(doc_a, digest_same), (doc_b, digest_same), (doc_c, digest_unique)]
    )
    result = verifier.filter([(doc_a, digest_same), (doc_b, digest_same), (doc_c, digest_unique)])
    assert counts[digest_same] == 2
    assert counts[digest_unique] == 1
    assert (doc_c, digest_unique) not in result
    assert len(result) == 2


def test_knowledge_gap_detector_flags_missing_topics() -> None:
    detector = KnowledgeGapDetector()
    discovered = [
        DiscoveryResult(
            url="https://allowed.test/python-news",
            title="Python updates",
            summary="release",
            licence="CC-BY-4.0",
        )
    ]
    ingested = [
        RawDocument(
            url="https://allowed.test/python-news",
            title="Python updates",
            text="Python release notes",
            licence="CC-BY-4.0",
        )
    ]

    gaps = detector.detect(
        topics=["python", "security", "ml"],
        discovered=discovered,
        ingested=ingested,
    )

    assert "security: aucune source découverte" in gaps
    assert "ml: aucune source découverte" in gaps
    assert not any(item.startswith("python:") for item in gaps)


def test_controller_tracks_bandwidth_and_robots_mode(tmp_path: Path) -> None:
    start = datetime(2024, 1, 2, 9, 5, 0)
    files = _prepare_policy(tmp_path, start)
    clock = ControlledClock(start)
    probe = SequenceProbe([ResourceUsage(cpu_percent=20, ram_mb=256)])
    store = MemoryVectorStore()
    pipeline = IngestPipeline(store, chunk_size=256, min_sources=2, allowed_licences={"CC-BY-4.0"})

    crawler = DummyCrawler()
    crawler.queue(
        [
            DiscoveryResult(
                url="https://allowed-one.test/article",
                title="Article A",
                summary="",
                licence="CC-BY-4.0",
            ),
            DiscoveryResult(
                url="https://allowed-two.test/article",
                title="Article B",
                summary="",
                licence="CC-BY-4.0",
            ),
        ]
    )
    text = "Le contenu valide partagé." * 8
    scraper = DummyScraper(
        {
            "https://allowed-one.test/article": _scrape("https://allowed-one.test/article", text),
            "https://allowed-two.test/article": _scrape("https://allowed-two.test/article", text),
        }
    )

    manager = PolicyManager(home=tmp_path)
    scheduler = AutopilotScheduler(
        policy_manager=manager,
        state_path=files.policy_path.parent / "autopilot-state.json",
        resource_probe=probe,
        clock=clock,
    )
    controller = AutopilotController(
        scheduler=scheduler,
        pipeline=pipeline,
        crawler=crawler,
        scraper=scraper,
        throttle_seconds=0.0,
        clock=clock,
        sleep_func=lambda _: None,
        report_path=files.policy_path.parent / "reports" / "weekly.html",
    )

    result = controller.run(["veille"])

    assert result.ingested == 1
    assert scraper.calls
    assert all(call[1] is True for call in scraper.calls)
    assert scheduler.state.bandwidth_mb_today > 0
    registry_path = files.policy_path.parent / "source-registry.json"
    assert registry_path.exists()
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    assert {item["status"] for item in registry} == {"promoted"}
    assert all(item["source_type"] == "web" for item in registry)


def test_controller_rejects_promotion_when_content_is_too_old(tmp_path: Path) -> None:
    start = datetime(2024, 1, 2, 9, 5, 0)
    files = _prepare_policy(tmp_path, start)
    clock = ControlledClock(start)
    probe = SequenceProbe([ResourceUsage(cpu_percent=20, ram_mb=256)])
    store = MemoryVectorStore()
    pipeline = IngestPipeline(store, chunk_size=256, min_sources=2, allowed_licences={"CC-BY-4.0"})

    stale = datetime(2022, 1, 1, 8, 0, 0)
    crawler = DummyCrawler()
    crawler.queue(
        [
            DiscoveryResult(
                url="https://allowed-one.test/article",
                title="Veille Article A",
                summary="",
                licence="CC-BY-4.0",
                published_at=stale,
            ),
            DiscoveryResult(
                url="https://allowed-two.test/article",
                title="Veille Article B",
                summary="",
                licence="CC-BY-4.0",
                published_at=stale,
            ),
        ]
    )
    text = "Ancien contenu corroboré mais devenu trop vieux."
    scraper = DummyScraper(
        {
            "https://allowed-one.test/article": _scrape("https://allowed-one.test/article", text),
            "https://allowed-two.test/article": _scrape("https://allowed-two.test/article", text),
        }
    )

    manager = PolicyManager(home=tmp_path)
    scheduler = AutopilotScheduler(
        policy_manager=manager,
        state_path=files.policy_path.parent / "autopilot-state.json",
        resource_probe=probe,
        clock=clock,
    )
    controller = AutopilotController(
        scheduler=scheduler,
        pipeline=pipeline,
        crawler=crawler,
        scraper=scraper,
        throttle_seconds=0.0,
        clock=clock,
        sleep_func=lambda _: None,
        report_path=files.policy_path.parent / "reports" / "weekly.html",
        promotion_evaluator=PromotionEvaluator(max_age_days=30),
    )

    result = controller.run(["veille"])

    assert result.ingested == 0
    assert result.reason == "évaluation défavorable"
    assert store.data == []
    assert sorted(result.skipped) == [
        "https://allowed-one.test/article",
        "https://allowed-two.test/article",
    ]
    assert result.knowledge_gaps == ["veille: sources découvertes mais non ingérées"]
    registry = {
        item["source"]: item
        for item in json.loads(
            (files.policy_path.parent / "source-registry.json").read_text(encoding="utf-8")
        )
    }
    assert registry["https://allowed-one.test/article"]["status"] == "validated"
    assert registry["https://allowed-one.test/article"]["evaluation_status"] == "rejected"
    assert registry["https://allowed-one.test/article"]["evaluation_score"] == 0.45
    assert (
        registry["https://allowed-one.test/article"]["evaluation_reason"]
        == "rejected by evaluator: content is 731 days old (max 30)"
    )
    report_html = (files.policy_path.parent / "reports" / "weekly.html").read_text(
        encoding="utf-8"
    )
    assert "Promotions rejetées" in report_html
    assert "https://allowed-one.test/article | rejected by evaluator: content is 731 days old (max 30)" in report_html


def test_controller_revokes_promoted_sources_after_ledger_revoke(tmp_path: Path) -> None:
    start = datetime(2024, 1, 2, 9, 5, 0)
    files = _prepare_policy(tmp_path, start)
    clock = ControlledClock(start)
    probe = SequenceProbe([ResourceUsage(cpu_percent=20, ram_mb=256)])
    store = MemoryVectorStore()
    store.data = [
        ("revoked content", {"domain": "revoked.test", "source": "https://revoked.test/old"}),
        ("allowed content", {"domain": "allowed-one.test", "source": "https://allowed-one.test/keep"}),
    ]
    pipeline = IngestPipeline(store, chunk_size=256, min_sources=2, allowed_licences={"CC-BY-4.0"})
    registry = SourceRegistry(files.policy_path.parent / "source-registry.json")
    registry.record(
        source="https://revoked.test/old",
        source_type="web",
        status=KnowledgeStatus.PROMOTED,
        confidence=0.8,
        freshness_at=start,
        licence="CC-BY-4.0",
        status_reason="promoted after evaluation: 2 corroborating domains and freshness unknown",
        evaluation_status="promoted",
        evaluation_score=0.8,
        evaluation_reason="promoted after evaluation: 2 corroborating domains and freshness unknown",
        observed_at=start,
    )
    registry.record(
        source="https://allowed-one.test/keep",
        source_type="web",
        status=KnowledgeStatus.PROMOTED,
        confidence=0.8,
        freshness_at=start,
        licence="CC-BY-4.0",
        status_reason="promoted after evaluation: 2 corroborating domains and freshness unknown",
        evaluation_status="promoted",
        evaluation_score=0.8,
        evaluation_reason="promoted after evaluation: 2 corroborating domains and freshness unknown",
        observed_at=start,
    )

    crawler = DummyCrawler()
    manager = PolicyManager(home=tmp_path)
    scheduler = AutopilotScheduler(
        policy_manager=manager,
        state_path=files.policy_path.parent / "autopilot-state.json",
        resource_probe=probe,
        clock=clock,
    )
    controller = AutopilotController(
        scheduler=scheduler,
        pipeline=pipeline,
        crawler=crawler,
        scraper=DummyScraper({}),
        throttle_seconds=0.0,
        clock=clock,
        sleep_func=lambda _: None,
        report_path=files.policy_path.parent / "reports" / "weekly.html",
    )

    result = controller.run(["veille"])

    assert result.ingested == 0
    assert result.reason is None
    assert result.knowledge_gaps == ["veille: aucune source découverte"]
    assert len(store.data) == 1
    assert store.data[0][1]["domain"] == "allowed-one.test"
    registry_data = {
        item["source"]: item
        for item in json.loads(
            (files.policy_path.parent / "source-registry.json").read_text(encoding="utf-8")
        )
    }
    assert registry_data["https://revoked.test/old"]["evaluation_status"] == "revoked"
    assert (
        registry_data["https://revoked.test/old"]["evaluation_reason"]
        == "revoked by consent ledger"
    )
    assert registry_data["https://allowed-one.test/keep"]["evaluation_status"] == "promoted"
    report_html = (files.policy_path.parent / "reports" / "weekly.html").read_text(
        encoding="utf-8"
    )
    assert "Sources révoquées" in report_html
    assert "https://revoked.test/old" in report_html
    assert "Domaines révoqués" in report_html
    assert "revoked.test" in report_html


def test_controller_counts_discovery_bandwidth_before_scraping(tmp_path: Path) -> None:
    start = datetime(2024, 1, 2, 9, 5, 0)
    files = _prepare_policy(tmp_path, start)
    policy = yaml.safe_load(files.policy_path.read_text(encoding="utf-8"))
    policy["budgets"]["bandwidth_mb_per_day"] = 0
    files.policy_path.write_text(yaml.safe_dump(policy, sort_keys=False), encoding="utf-8")

    clock = ControlledClock(start)
    probe = SequenceProbe([ResourceUsage(cpu_percent=20, ram_mb=256)])
    store = MemoryVectorStore()
    pipeline = IngestPipeline(store, chunk_size=256, min_sources=2, allowed_licences={"CC-BY-4.0"})
    manager = PolicyManager(home=tmp_path)
    scheduler = AutopilotScheduler(
        policy_manager=manager,
        state_path=files.policy_path.parent / "autopilot-state.json",
        resource_probe=probe,
        clock=clock,
    )
    controller = AutopilotController(
        scheduler=scheduler,
        pipeline=pipeline,
        scraper=DummyScraper({}),
        throttle_seconds=0.0,
        clock=clock,
        sleep_func=lambda _: None,
        report_path=files.policy_path.parent / "reports" / "weekly.html",
    )

    feed = b"""<?xml version='1.0'?>
    <rss version='2.0'>
      <channel>
        <item>
          <title>AI Weekly</title>
          <link>https://allowed-one.test/article</link>
          <description>Focus on trustworthy AI systems.</description>
        </item>
      </channel>
    </rss>
    """

    class DiscoveryHTTP:
        def __init__(self, payload: bytes) -> None:
            self.payload = payload
            self.calls: list[tuple[str, bool]] = []

        def fetch_raw(self, url: str, *, respect_robots: bool = True):
            self.calls.append((url, respect_robots))
            if url.endswith("/feed"):
                return self.payload, {}
            return None

    discovery_http = DiscoveryHTTP(feed)
    controller.crawler = DefaultDiscoveryCrawler(
        http=discovery_http,
        can_fetch=controller._can_fetch_more_bandwidth,
        register_payload_bytes=controller._register_bandwidth_bytes,
    )

    result = controller.run(["AI"])

    assert result.ingested == 0
    assert result.reason is None
    assert discovery_http.calls == []
    assert scheduler.state.bandwidth_mb_today == 0
    assert controller.scraper.calls == []


def test_controller_records_raw_validated_promoted_states(tmp_path: Path) -> None:
    start = datetime(2024, 1, 2, 9, 5, 0)
    files = _prepare_policy(tmp_path, start)
    clock = ControlledClock(start)
    probe = SequenceProbe([ResourceUsage(cpu_percent=20, ram_mb=256)])
    store = MemoryVectorStore()
    pipeline = IngestPipeline(store, chunk_size=256, min_sources=2, allowed_licences={"CC-BY-4.0"})

    crawler = DummyCrawler()
    crawler.queue(
        [
            DiscoveryResult(
                url="https://allowed-one.test/article",
                title="Article A",
                summary="",
                licence="CC-BY-4.0",
            ),
            DiscoveryResult(
                url="https://allowed-two.test/article",
                title="Article B",
                summary="",
                licence="CC-BY-4.0",
            ),
        ]
    )
    text = "Le contenu valide partagé." * 8
    scraper = DummyScraper(
        {
            "https://allowed-one.test/article": _scrape("https://allowed-one.test/article", text),
            "https://allowed-two.test/article": _scrape("https://allowed-two.test/article", text),
        }
    )

    manager = PolicyManager(home=tmp_path)
    scheduler = AutopilotScheduler(
        policy_manager=manager,
        state_path=files.policy_path.parent / "autopilot-state.json",
        resource_probe=probe,
        clock=clock,
    )
    controller = AutopilotController(
        scheduler=scheduler,
        pipeline=pipeline,
        crawler=crawler,
        scraper=scraper,
        throttle_seconds=0.0,
        clock=clock,
        sleep_func=lambda _: None,
        report_path=files.policy_path.parent / "reports" / "weekly.html",
    )

    controller.run(["veille"])

    registry_path = files.policy_path.parent / "source-registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))

    assert len(registry) == 2
    assert {item["status"] for item in registry} == {"promoted"}
    assert all(item["confidence"] >= 1.0 for item in registry)
    assert all(item["source"] in {"https://allowed-one.test/article", "https://allowed-two.test/article"} for item in registry)


def test_controller_uses_prefetched_github_content_without_extra_scrape(tmp_path: Path) -> None:
    start = datetime(2024, 1, 2, 9, 5, 0)
    files = _prepare_policy(tmp_path, start)
    policy = yaml.safe_load(files.policy_path.read_text(encoding="utf-8"))
    policy["allowlist_domains"] = ["allowed-two.test", "github.com"]
    files.policy_path.write_text(yaml.safe_dump(policy, sort_keys=False), encoding="utf-8")

    clock = ControlledClock(start)
    probe = SequenceProbe([ResourceUsage(cpu_percent=20, ram_mb=256)])
    store = MemoryVectorStore()
    pipeline = IngestPipeline(store, chunk_size=256, min_sources=2, allowed_licences={"CC-BY-4.0"})
    crawler = DummyCrawler()
    text = "Le contenu valide partagé." * 8
    crawler.queue(
        [
            DiscoveryResult(
                url="https://github.com/octocat/Hello-World/releases/tag/v1.2.3",
                title="Release 1.2.3",
                summary="Bug fixes",
                licence="CC-BY-4.0",
                content=text,
                source_type="git-release",
                fetched_at=start,
                etag='"release"',
                last_modified="Wed, 03 Jan 2024 10:00:00 GMT",
            ),
            DiscoveryResult(
                url="https://allowed-two.test/article",
                title="Article B",
                summary="",
                licence="CC-BY-4.0",
            ),
        ]
    )
    scraper = DummyScraper(
        {
            "https://allowed-two.test/article": _scrape("https://allowed-two.test/article", text),
        }
    )

    manager = PolicyManager(home=tmp_path)
    scheduler = AutopilotScheduler(
        policy_manager=manager,
        state_path=files.policy_path.parent / "autopilot-state.json",
        resource_probe=probe,
        clock=clock,
    )
    controller = AutopilotController(
        scheduler=scheduler,
        pipeline=pipeline,
        crawler=crawler,
        scraper=scraper,
        throttle_seconds=0.0,
        clock=clock,
        sleep_func=lambda _: None,
        report_path=files.policy_path.parent / "reports" / "weekly.html",
    )

    result = controller.run(["release"])

    assert result.ingested == 1
    assert scraper.calls == [("https://allowed-two.test/article", True)]
    registry = json.loads((files.policy_path.parent / "source-registry.json").read_text(encoding="utf-8"))
    assert {item["status"] for item in registry} == {"promoted"}
    assert {item["source_type"] for item in registry} == {"git-release", "web"}


def test_controller_accepts_domain_rules_without_allowlist_key(tmp_path: Path) -> None:
    start = datetime(2024, 1, 2, 9, 5, 0)
    files = _prepare_policy(tmp_path, start)
    policy = yaml.safe_load(files.policy_path.read_text(encoding="utf-8"))
    policy.pop("allowlist_domains", None)
    policy["domain_rules"] = [
        {"domain": "allowed-one.test", "scope": "web"},
        {"domain": "allowed-two.test", "scope": "web"},
    ]
    files.policy_path.write_text(yaml.safe_dump(policy, sort_keys=False), encoding="utf-8")

    clock = ControlledClock(start)
    probe = SequenceProbe([ResourceUsage(cpu_percent=20, ram_mb=256)])
    store = MemoryVectorStore()
    pipeline = IngestPipeline(store, chunk_size=256, min_sources=2, allowed_licences={"CC-BY-4.0"})
    crawler = DummyCrawler()
    text = "Le contenu valide partagé." * 8
    crawler.queue(
        [
            DiscoveryResult(
                url="https://allowed-one.test/article",
                title="Article A",
                summary="",
                licence="CC-BY-4.0",
            ),
            DiscoveryResult(
                url="https://allowed-two.test/article",
                title="Article B",
                summary="",
                licence="CC-BY-4.0",
            ),
        ]
    )
    scraper = DummyScraper(
        {
            "https://allowed-one.test/article": _scrape("https://allowed-one.test/article", text),
            "https://allowed-two.test/article": _scrape("https://allowed-two.test/article", text),
        }
    )

    manager = PolicyManager(home=tmp_path)
    scheduler = AutopilotScheduler(
        policy_manager=manager,
        state_path=files.policy_path.parent / "autopilot-state.json",
        resource_probe=probe,
        clock=clock,
    )
    controller = AutopilotController(
        scheduler=scheduler,
        pipeline=pipeline,
        crawler=crawler,
        scraper=scraper,
        throttle_seconds=0.0,
        clock=clock,
        sleep_func=lambda _: None,
        report_path=files.policy_path.parent / "reports" / "weekly.html",
    )

    result = controller.run(["veille"])
    runtime_policy = manager._read_policy()

    assert result.ingested == 1
    assert result.reason is None
    assert runtime_policy.allowlist_domains == ["allowed-one.test", "allowed-two.test"]
    assert [(rule.domain, rule.scope) for rule in runtime_policy.domain_rules()] == [
        ("allowed-one.test", "web"),
        ("allowed-two.test", "web"),
    ]


def test_controller_runtime_scope_git_uses_domain_rules_policy(tmp_path: Path) -> None:
    start = datetime(2024, 1, 2, 9, 5, 0)
    files = _prepare_policy(tmp_path, start)
    policy = yaml.safe_load(files.policy_path.read_text(encoding="utf-8"))
    policy.pop("allowlist_domains", None)
    policy["domain_rules"] = [
        {"domain": "allowed-two.test", "scope": "web"},
        {"domain": "github.com", "scope": "git"},
    ]
    files.policy_path.write_text(yaml.safe_dump(policy, sort_keys=False), encoding="utf-8")

    clock = ControlledClock(start)
    probe = SequenceProbe([ResourceUsage(cpu_percent=20, ram_mb=256)])
    store = MemoryVectorStore()
    pipeline = IngestPipeline(
        store,
        chunk_size=256,
        min_sources=2,
        allowed_licences={"CC-BY-4.0", "MIT"},
    )
    shared_text = "Shared release notes across trusted sources."
    feed = f"""<?xml version='1.0'?>
    <rss version='2.0'>
      <channel>
        <item>
          <title>Release digest</title>
          <link>https://allowed-two.test/article</link>
          <description>{shared_text}</description>
        </item>
      </channel>
    </rss>
    """.encode("utf-8")
    repo_data = json.dumps(
        {
            "full_name": "octocat/Hello-World",
            "default_branch": "main",
            "license": {"spdx_id": "MIT"},
        }
    ).encode("utf-8")
    release = json.dumps(
        {
            "tag_name": "v1.2.3",
            "name": "Release 1.2.3",
            "html_url": "https://github.com/octocat/Hello-World/releases/tag/v1.2.3",
            "published_at": "2024-01-01T10:00:00Z",
            "body": shared_text,
        }
    ).encode("utf-8")
    http = StubHTTP(
        {
            "https://allowed-two.test/feed": feed,
            "https://api.github.com/repos/octocat/Hello-World": repo_data,
            "https://api.github.com/repos/octocat/Hello-World/releases/latest": release,
        }
    )
    scraper = DummyScraper(
        {
            "https://allowed-two.test/article": _scrape(
                "https://allowed-two.test/article",
                shared_text,
            ),
        }
    )

    manager = PolicyManager(home=tmp_path)
    scheduler = AutopilotScheduler(
        policy_manager=manager,
        state_path=files.policy_path.parent / "autopilot-state.json",
        resource_probe=probe,
        clock=clock,
    )
    controller = AutopilotController(
        scheduler=scheduler,
        pipeline=pipeline,
        scraper=scraper,
        throttle_seconds=0.0,
        clock=clock,
        sleep_func=lambda _: None,
        report_path=files.policy_path.parent / "reports" / "weekly.html",
    )
    controller.crawler = DefaultDiscoveryCrawler(
        http=http,
        can_fetch=controller._can_fetch_more_bandwidth,
        register_payload_bytes=controller._register_bandwidth_bytes,
    )

    result = controller.run(["octocat/Hello-World", "release"])

    assert result.ingested == 1
    assert ("https://allowed-two.test/feed", True) in http.calls
    assert ("https://api.github.com/repos/octocat/Hello-World", False) in http.calls
    assert (
        "https://api.github.com/repos/octocat/Hello-World/releases/latest",
        False,
    ) in http.calls
    assert scraper.calls == [("https://allowed-two.test/article", True)]
    registry = json.loads((files.policy_path.parent / "source-registry.json").read_text(encoding="utf-8"))
    assert {item["status"] for item in registry} == {"promoted"}
    assert {item["source_type"] for item in registry} == {"git-release", "web"}


def test_controller_honours_kill_switch_before_discovery(tmp_path: Path) -> None:
    start = datetime(2024, 1, 2, 9, 5, 0)
    files = _prepare_policy(tmp_path, start)
    policy = yaml.safe_load(files.policy_path.read_text(encoding="utf-8"))
    kill_switch = Path(policy["kill_switch_file"])
    kill_switch.write_text("1", encoding="utf-8")

    clock = ControlledClock(start)
    probe = SequenceProbe([ResourceUsage(cpu_percent=20, ram_mb=256)])
    store = MemoryVectorStore()
    pipeline = IngestPipeline(store, chunk_size=256, min_sources=2, allowed_licences={"CC-BY-4.0"})
    crawler = DummyCrawler()
    crawler.queue(
        [
            DiscoveryResult(
                url="https://allowed-one.test/article",
                title="Article A",
                summary="",
                licence="CC-BY-4.0",
            )
        ]
    )
    scraper = DummyScraper(
        {
            "https://allowed-one.test/article": _scrape(
                "https://allowed-one.test/article",
                "Le contenu valide partagé." * 8,
            ),
        }
    )

    manager = PolicyManager(home=tmp_path)
    scheduler = AutopilotScheduler(
        policy_manager=manager,
        state_path=files.policy_path.parent / "autopilot-state.json",
        resource_probe=probe,
        clock=clock,
    )
    controller = AutopilotController(
        scheduler=scheduler,
        pipeline=pipeline,
        crawler=crawler,
        scraper=scraper,
        throttle_seconds=0.0,
        clock=clock,
        sleep_func=lambda _: None,
        report_path=files.policy_path.parent / "reports" / "weekly.html",
    )

    result = controller.run(["veille"])

    assert result.ingested == 0
    assert result.reason == "kill-switch"
    assert crawler.calls == 0
    assert scraper.calls == []
