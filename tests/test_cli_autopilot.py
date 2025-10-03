from types import SimpleNamespace

import pytest

from app import cli
from app.autopilot import (
    AutopilotRunResult,
    AutopilotState,
    DefaultDiscoveryCrawler,
    DiscoveryResult,
)
from app.ingest.pipeline import RawDocument
from app.policy.schema import DomainRule
from app.scrapers.http import ScrapeResult


class DummyEngine:
    def __init__(self) -> None:
        self.offline: list[bool] = []

    def set_offline(self, value: bool) -> None:  # pragma: no cover - executed in tests
        self.offline.append(bool(value))


class DummyScheduler:
    def __init__(
        self,
        *,
        enable_state: AutopilotState | None = None,
        disable_state: AutopilotState | None = None,
        evaluate_state: AutopilotState | None = None,
    ) -> None:
        self.enable_calls: list[list[str]] = []
        self.disable_calls: list[list[str] | None] = []
        self.evaluate_calls = 0
        self._enable_state = enable_state or AutopilotState(enabled=True, online=True, queue=["foo"], last_reason="ok")
        self._disable_state = disable_state or AutopilotState(enabled=False, online=False, queue=[])
        self._evaluate_state = evaluate_state or self._enable_state

    def enable(self, topics, *, engine=None, now=None):  # pragma: no cover - executed in tests
        values = list(topics)
        self.enable_calls.append(values)
        if engine is not None:
            engine.set_offline(not self._enable_state.online)
        state = AutopilotState(**self._enable_state.to_dict())
        state.queue = list(values)
        state.current_topic = values[0] if values else None
        return state

    def disable(self, topics=None, *, engine=None, now=None):  # pragma: no cover - executed in tests
        values = list(topics) if topics else None
        self.disable_calls.append(values)
        if engine is not None:
            engine.set_offline(True)
        return AutopilotState(**self._disable_state.to_dict())

    def evaluate(self, *, engine=None, now=None):  # pragma: no cover - executed in tests
        self.evaluate_calls += 1
        if engine is not None:
            engine.set_offline(not self._evaluate_state.online)
        return AutopilotState(**self._evaluate_state.to_dict())


@pytest.fixture(autouse=True)
def _stub_cli_settings(monkeypatch):
    settings = SimpleNamespace(
        llm=SimpleNamespace(backend="stub", model="stub-model"),
        training=SimpleNamespace(seed=42),
        intelligence=SimpleNamespace(mode="offline"),
    )
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    return settings


def test_cli_autopilot_enable(monkeypatch, capsys):
    engine = DummyEngine()
    enable_state = AutopilotState(enabled=True, online=True, queue=["foo", "bar"], last_reason="ok")
    scheduler = DummyScheduler(enable_state=enable_state)
    monkeypatch.setattr(cli, "AutopilotScheduler", lambda: scheduler)
    monkeypatch.setattr(cli, "Engine", lambda: engine)

    exit_code = cli.main(["autopilot", "enable", "--topics", "foo,bar"])

    assert exit_code == 0
    assert scheduler.enable_calls == [["foo", "bar"]]
    assert engine.offline[-1] is False
    captured = capsys.readouterr()
    assert "Autopilot activé (en ligne)" in captured.out
    assert "foo, bar" in captured.out


def test_cli_autopilot_status_offline(monkeypatch, capsys):
    engine = DummyEngine()
    status_state = AutopilotState(enabled=True, online=False, queue=["foo"], last_reason="hors fenêtre réseau")
    scheduler = DummyScheduler(evaluate_state=status_state)
    monkeypatch.setattr(cli, "AutopilotScheduler", lambda: scheduler)
    monkeypatch.setattr(cli, "Engine", lambda: engine)

    exit_code = cli.main(["autopilot", "status", "--topics", "bar"])

    assert exit_code == 0
    assert scheduler.evaluate_calls == 1
    assert engine.offline[-1] is True
    captured = capsys.readouterr()
    assert "Autopilot hors ligne (hors fenêtre réseau)" in captured.out
    assert "Sujets absents de la file: bar" in captured.out


def test_cli_autopilot_disable(monkeypatch, capsys):
    engine = DummyEngine()
    disable_state = AutopilotState(enabled=False, online=False, queue=[])
    scheduler = DummyScheduler(disable_state=disable_state)
    monkeypatch.setattr(cli, "AutopilotScheduler", lambda: scheduler)
    monkeypatch.setattr(cli, "Engine", lambda: engine)

    exit_code = cli.main(["autopilot", "disable"])

    assert exit_code == 0
    assert scheduler.disable_calls == [None]
    assert engine.offline[-1] is True
    captured = capsys.readouterr()
    assert "Autopilot désactivé" in captured.out


def test_cli_autopilot_run_success(monkeypatch, capsys):
    scheduler = SimpleNamespace(name="scheduler")
    pipeline = SimpleNamespace(name="pipeline")
    crawler = SimpleNamespace(name="crawler")
    run_calls: list[list[str]] = []

    http_instance = SimpleNamespace(name="http")
    sitemap_instance = SimpleNamespace(name="sitemap")
    github_instance = SimpleNamespace(name="github")

    class DummyController:
        def __init__(self, *, scheduler, pipeline, crawler, scraper):  # pragma: no cover - tested via CLI
            assert scheduler is scheduler_instance
            assert pipeline is pipeline_instance
            assert crawler is crawler_instance
            assert scraper is http_instance

        def run(self, topics=None):  # pragma: no cover - executed in tests
            run_calls.append(list(topics or []))
            return AutopilotRunResult(
                ingested=2,
                skipped=["https://skipped.test/doc"],
                blocked=["blocked.test"],
            )

    scheduler_instance = scheduler
    pipeline_instance = pipeline
    crawler_instance = crawler

    monkeypatch.setattr(cli, "AutopilotScheduler", lambda: scheduler_instance)
    monkeypatch.setattr(cli, "_build_autopilot_pipeline", lambda: pipeline_instance)

    def fake_http():  # pragma: no cover - helper used in test
        return http_instance

    def fake_sitemap(http):  # pragma: no cover - helper used in test
        assert http is http_instance
        return sitemap_instance

    def fake_github(http):  # pragma: no cover - helper used in test
        assert http is http_instance
        return github_instance

    def fake_crawler_builder(*, noninteractive, http=None, sitemap=None, github=None):  # pragma: no cover - helper used in test
        assert noninteractive is False
        assert http is http_instance
        assert sitemap is sitemap_instance
        assert github is github_instance
        return crawler_instance

    monkeypatch.setattr(cli, "HTTPScraper", fake_http)
    monkeypatch.setattr(cli, "SitemapScraper", fake_sitemap)
    monkeypatch.setattr(cli, "GitHubScraper", fake_github)
    monkeypatch.setattr(cli, "_build_autopilot_crawler", fake_crawler_builder)
    monkeypatch.setattr(cli, "AutopilotController", DummyController)
    monkeypatch.setattr("builtins.input", lambda _: "o")

    exit_code = cli.main(["autopilot", "run", "--topics", "foo,bar"])

    assert exit_code == 0
    assert run_calls == [["foo", "bar"]]
    captured = capsys.readouterr()
    assert "Cycle autopilot terminé: 2 source(s) ingérée(s)" in captured.out
    assert "Ignorées: https://skipped.test/doc" in captured.out
    assert "Bloquées: blocked.test" in captured.out
    assert "Cycle interrompu" not in captured.out


def test_cli_autopilot_run_blocked(monkeypatch, capsys):
    scheduler = SimpleNamespace(name="scheduler")
    pipeline = SimpleNamespace(name="pipeline")
    crawler = SimpleNamespace(name="crawler")

    http_instance = SimpleNamespace(name="http")
    sitemap_instance = SimpleNamespace(name="sitemap")
    github_instance = SimpleNamespace(name="github")

    class DummyController:
        def __init__(self, *, scheduler, pipeline, crawler, scraper):  # pragma: no cover - tested via CLI
            assert scheduler is scheduler_instance
            assert pipeline is pipeline_instance
            assert crawler is crawler_instance
            assert scraper is http_instance

        def run(self, topics=None):  # pragma: no cover - executed in tests
            assert topics is None
            return AutopilotRunResult(ingested=0, skipped=[], blocked=[], reason="kill-switch")

    scheduler_instance = scheduler
    pipeline_instance = pipeline
    crawler_instance = crawler

    def fake_http():  # pragma: no cover - helper used in test
        return http_instance

    def fake_sitemap(http):  # pragma: no cover - helper used in test
        assert http is http_instance
        return sitemap_instance

    def fake_github(http):  # pragma: no cover - helper used in test
        assert http is http_instance
        return github_instance

    def fake_crawler_builder(*, noninteractive, http=None, sitemap=None, github=None):  # pragma: no cover - helper used in test
        assert noninteractive is True
        assert http is http_instance
        assert sitemap is sitemap_instance
        assert github is github_instance
        return crawler_instance

    monkeypatch.setattr(cli, "AutopilotScheduler", lambda: scheduler_instance)
    monkeypatch.setattr(cli, "_build_autopilot_pipeline", lambda: pipeline_instance)
    monkeypatch.setattr(cli, "HTTPScraper", fake_http)
    monkeypatch.setattr(cli, "SitemapScraper", fake_sitemap)
    monkeypatch.setattr(cli, "GitHubScraper", fake_github)
    monkeypatch.setattr(cli, "_build_autopilot_crawler", fake_crawler_builder)
    monkeypatch.setattr(cli, "AutopilotController", DummyController)
    monkeypatch.setattr(
        "builtins.input",
        lambda _: (_ for _ in ()).throw(AssertionError("should not prompt")),
    )

    exit_code = cli.main(["autopilot", "run", "--noninteractive"])

    assert exit_code == 3
    captured = capsys.readouterr()
    assert "Cycle autopilot terminé: 0 source(s) ingérée(s)" in captured.out
    assert "Cycle interrompu: kill-switch" in captured.out


def test_cli_autopilot_run_noninteractive_ingests_discovered(monkeypatch, tmp_path):
    pipeline_calls: list[list[RawDocument]] = []

    class DummyPipeline:
        def __init__(self) -> None:
            self.min_sources = 2
            self.allowed_licences = {"CC-BY-4.0"}
            self.store = SimpleNamespace(path=None)

        def ingest(self, documents, seen_digests=None):  # pragma: no cover - executed in test
            batch = list(documents)
            pipeline_calls.append(batch)
            return len(batch)

    pipeline = DummyPipeline()

    def build_pipeline():  # pragma: no cover - helper used in test
        return pipeline

    monkeypatch.setattr(cli, "_build_autopilot_pipeline", build_pipeline)

    defaults = SimpleNamespace(require_consent=False, kill_switch=False)
    allowlist = [
        DomainRule(
            domain="example.com",
            categories=[],
            bandwidth_mb=50,
            time_budget_minutes=60,
            allow_subdomains=True,
            scope="web",
        ),
        DomainRule(
            domain="example.org",
            categories=[],
            bandwidth_mb=50,
            time_budget_minutes=60,
            allow_subdomains=True,
            scope="web",
        ),
    ]
    network = SimpleNamespace(
        allowlist=allowlist,
        allowed_windows=[],
        bandwidth_mb=100,
        time_budget_minutes=120,
    )
    policy = SimpleNamespace(defaults=defaults, network=network)
    state = AutopilotState(enabled=True, online=True, queue=["example"], last_reason="ok")

    class StubScheduler:
        def __init__(self) -> None:
            self._policy_loader = lambda: policy
            self._policy_manager = SimpleNamespace(config_dir=tmp_path, ledger_path=None)
            self.state = state

        def evaluate(self, *, engine=None, now=None):  # pragma: no cover - executed in test
            return self.state

        def enable(self, topics, *, engine=None, now=None):  # pragma: no cover - defensive
            self.state.queue = list(topics)
            return self.state

    monkeypatch.setattr(cli, "AutopilotScheduler", StubScheduler)

    discovered = [
        DiscoveryResult(
            url="https://example.com/article", title="Example", summary="Sample", licence="CC-BY-4.0"
        ),
        DiscoveryResult(
            url="https://example.org/article", title="Example mirror", summary="Sample", licence="CC-BY-4.0"
        ),
    ]

    def fake_discover(self, topics, rules):  # pragma: no cover - helper used in test
        return list(discovered)

    monkeypatch.setattr(DefaultDiscoveryCrawler, "discover", fake_discover)

    fetch_calls: list[str] = []

    class DummyScraper:
        def fetch(self, url, *, respect_robots=True):  # pragma: no cover - executed in test
            fetch_calls.append(url)
            return ScrapeResult(
                url=url,
                content="Shared body",
                raw_content=b"content",
                content_hash=None,
                license="CC-BY-4.0",
                headers={},
                etag=None,
                last_modified=None,
                is_duplicate=False,
            )

    dummy_scraper = DummyScraper()

    from app.autopilot.controller import AutopilotController as RealController

    def build_controller(*, scheduler, pipeline, crawler, scraper):  # pragma: no cover - helper used in test
        return RealController(
            scheduler=scheduler,
            pipeline=pipeline,
            crawler=crawler,
            scraper=dummy_scraper,
            throttle_seconds=0.0,
        )

    monkeypatch.setattr(cli, "AutopilotController", build_controller)
    monkeypatch.setattr(
        "builtins.input",
        lambda _: (_ for _ in ()).throw(AssertionError("should not prompt")),
    )

    exit_code = cli.main(["autopilot", "run", "--noninteractive"])

    assert exit_code == 0
    assert fetch_calls == ["https://example.com/article", "https://example.org/article"]
    assert len(pipeline_calls) == 1
    ingested = pipeline_calls[0]
    assert [doc.url for doc in ingested] == [
        "https://example.com/article",
        "https://example.org/article",
    ]
