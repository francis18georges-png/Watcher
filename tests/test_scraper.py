import asyncio
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


def test_scrape_all_default_cache_dir(monkeypatch, tmp_path):
    """When cache_dir is omitted the configuration default is used."""

    def fake_urlopen(url: str):
        return DummyResponse("hello world")

    monkeypatch.setattr(
        scraper, "urllib_request", SimpleNamespace(urlopen=fake_urlopen)
    )
    monkeypatch.setattr(scraper, "_DEFAULT_CACHE_DIR", tmp_path)

    async def _run() -> None:
        await scraper.scrape_all(["https://example.com"])

    asyncio.run(_run())

    assert list(tmp_path.iterdir())
