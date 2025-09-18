import asyncio
from pathlib import Path
from types import SimpleNamespace

from app.data import scraper


class DummyResponse:
    def __init__(self, text: str):
        self._text = text

    def read(self) -> bytes:  # pragma: no cover - simple accessor
        return self._text.encode("utf-8")

    def __enter__(self) -> "DummyResponse":  # pragma: no cover - context mgr
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - context mgr
        pass


def test_scraper_caches(monkeypatch, tmp_path):
    """Fetching the same URL twice hits the network only once."""

    calls = 0

    def fake_urlopen(url: str):
        nonlocal calls
        calls += 1
        return DummyResponse("hello world")

    monkeypatch.setattr(
        scraper, "urllib_request", SimpleNamespace(urlopen=fake_urlopen)
    )

    async def _run() -> None:
        url = "https://example.com"
        await scraper.scrape_all([url], tmp_path)
        # Second run should read from cache and not increment calls
        await scraper.scrape_all([url], tmp_path)

    asyncio.run(_run())

    assert calls == 1
    # Cached file exists
    assert list(tmp_path.iterdir())


def test_scrape_uses_default_cache(monkeypatch, tmp_path):
    """scrape() should populate the default cache directory when unspecified."""

    url = "https://example.com"
    fake_repo = tmp_path / "repo"
    fake_file = fake_repo / "app" / "data" / "scraper.py"
    fake_file.parent.mkdir(parents=True)
    monkeypatch.setattr(scraper, "__file__", str(fake_file))

    calls = 0

    def fake_urlopen(request_url: str):
        nonlocal calls
        calls += 1
        assert request_url == url
        return DummyResponse("payload")

    monkeypatch.setattr(
        scraper, "urllib_request", SimpleNamespace(urlopen=fake_urlopen)
    )

    async def _run():
        return await scraper.scrape([url])

    results = asyncio.run(_run())

    default_cache = fake_repo / "datasets" / "cache"
    assert calls == 1
    assert default_cache.exists()

    stored_path = Path(results[url])
    assert stored_path.parent == default_cache
    assert stored_path.read_text() == "payload"
