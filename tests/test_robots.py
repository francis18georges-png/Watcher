from collections import defaultdict
from typing import Dict, List
from urllib.error import URLError

import pytest

from app.scrapers.http import HTTPScraper


class FakeResponse:
    def __init__(self, body: str, headers=None):
        self._body = body.encode("utf-8")
        self.headers = defaultdict(str)
        if headers:
            for key, value in headers.items():
                self.headers[key] = value

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "FakeResponse":  # pragma: no cover
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover
        return None


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.slept: List[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, delay: float) -> None:
        self.slept.append(delay)
        self.now += delay

    def advance(self, delta: float) -> None:
        self.now += delta


def build_urlopen(responses: Dict[str, List[object]], recorded: List[Dict[str, object]]):
    def _urlopen(request, timeout=None):  # pragma: no cover - helper
        url = getattr(request, "full_url", request)
        headers = {k.lower(): v for k, v in getattr(request, "headers", {}).items()}
        recorded.append({"url": url, "headers": headers, "timeout": timeout})
        queue = responses.get(url)
        if not queue:
            raise AssertionError(f"No response queued for {url}")
        response = queue.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    return _urlopen


def test_robots_disallow_blocks_fetch():
    responses: Dict[str, List[object]] = defaultdict(list)
    records: List[Dict[str, object]] = []
    robots_url = "https://example.com/robots.txt"
    responses[robots_url].append(
        FakeResponse("User-agent: *\nDisallow: /private")
    )

    scraper = HTTPScraper(opener=build_urlopen(responses, records))

    result = scraper.fetch("https://example.com/private/page.html")
    assert result is None
    assert records[0]["url"] == robots_url


def test_missing_robots_allows_fetch():
    responses: Dict[str, List[object]] = defaultdict(list)
    records: List[Dict[str, object]] = []
    robots_url = "https://example.com/robots.txt"
    responses[robots_url].append(URLError("no robots"))
    page_url = "https://example.com/index.html"
    responses[page_url].append(
        FakeResponse("<html><body>Hello</body></html>", headers={"Content-Type": "text/html"})
    )

    scraper = HTTPScraper(opener=build_urlopen(responses, records))

    result = scraper.fetch(page_url)
    assert result is not None
    assert "Hello" in result.content


def test_throttling_waits_between_requests():
    responses: Dict[str, List[object]] = defaultdict(list)
    records: List[Dict[str, object]] = []
    robots_url = "https://example.com/robots.txt"
    responses[robots_url].append(FakeResponse("User-agent: *\nAllow: /"))
    page_url = "https://example.com/data"
    responses[page_url].append(
        FakeResponse("<html><body>Payload</body></html>", headers={"Content-Type": "text/html"})
    )
    responses[page_url].append(
        FakeResponse("<html><body>Payload</body></html>", headers={"Content-Type": "text/html"})
    )

    clock = FakeClock()
    scraper = HTTPScraper(
        opener=build_urlopen(responses, records),
        throttle_delay=1.0,
        time_func=clock.time,
        sleep_func=clock.sleep,
    )

    first = scraper.fetch_raw(page_url)
    assert first is not None
    clock.advance(0.3)
    second = scraper.fetch_raw(page_url)
    assert second is not None

    assert clock.slept
    assert pytest.approx(clock.slept[0], rel=1e-3) == 0.7
    assert records[0]["url"] == robots_url
    assert records[1]["url"] == page_url
    assert records[2]["url"] == page_url
