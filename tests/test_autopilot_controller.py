"""End-to-end and guardrail tests for the autopilot controller."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Sequence

import yaml

from app.autopilot import (
    AutopilotController,
    ConsentGate,
    DiscoveryResult,
    MultiSourceVerifier,
)
from app.autopilot.scheduler import AutopilotScheduler, ResourceUsage
from app.ingest import IngestPipeline
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


class DummyCrawler:
    def __init__(self) -> None:
        self._batches: list[list[DiscoveryResult]] = []

    def queue(self, results: Iterable[DiscoveryResult]) -> None:
        self._batches.append(list(results))

    def discover(
        self,
        topics: Sequence[str],
        rules: Sequence,
    ) -> Iterable[DiscoveryResult]:
        if self._batches:
            return self._batches.pop(0)
        return []


class DummyScraper:
    def __init__(self, mapping: dict[str, ScrapeResult]) -> None:
        self.mapping = mapping

    def fetch(self, url: str, *, respect_robots: bool = True) -> ScrapeResult | None:  # noqa: D401
        return self.mapping.get(url)


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
    window = {"days": [now.strftime("%a").lower()[:3]], "window": "09:00-10:00"}
    allowlist = [
        {
            "domain": "allowed-one.test",
            "categories": ["news"],
            "bandwidth_mb": 15,
            "time_budget_minutes": 30,
            "allow_subdomains": True,
            "scope": "web",
            "last_approved": now.isoformat(),
        },
        {
            "domain": "allowed-two.test",
            "categories": ["news"],
            "bandwidth_mb": 15,
            "time_budget_minutes": 30,
            "allow_subdomains": True,
            "scope": "web",
            "last_approved": now.isoformat(),
        },
    ]
    policy = {
        "version": 1,
        "subject": {"hostname": "test", "generated_at": now.isoformat()},
        "defaults": {"offline": False, "require_consent": True, "kill_switch": False},
        "network": {
            "allowed_windows": [window],
            "allowlist": allowlist,
            "bandwidth_mb": 50,
            "time_budget_minutes": 60,
        },
        "budgets": {"cpu_percent": 80, "ram_mb": 1024},
        "categories": {"allowed": ["news"]},
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
    text = "Le contenu valide partagé."
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
    result = verifier.filter([(doc_a, digest_same), (doc_b, digest_same), (doc_c, digest_unique)])
    assert (doc_c, digest_unique) not in result
    assert len(result) == 2
