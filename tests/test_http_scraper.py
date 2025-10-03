import json
from collections import defaultdict
from typing import Dict, List, Mapping
from urllib.error import HTTPError

from app.scrapers.http import HTTPScraper


class FakeResponse:
    def __init__(self, body: str, headers: Mapping[str, str] | None = None, status: int = 200):
        self._body = body.encode("utf-8")
        self.status = status
        self.headers = defaultdict(str)
        if headers:
            for key, value in headers.items():
                self.headers[key] = value

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "FakeResponse":  # pragma: no cover - context manager boilerplate
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - context manager boilerplate
        return None


def build_urlopen(responses: Dict[str, List[object]], recorded: List[Dict[str, object]]):
    def _urlopen(request, timeout=None):  # pragma: no cover - helper in tests
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


def test_headers_and_conditional_requests(monkeypatch):
    responses: Dict[str, List[object]] = defaultdict(list)
    records: List[Dict[str, object]] = []
    url = "https://example.com/article"
    responses[url].append(
        FakeResponse(
            "<html><body>Example Article</body></html>",
            headers={
                "Content-Type": "text/html; charset=utf-8",
                "ETag": "abc123",
                "Last-Modified": "Mon, 01 Jan 2024 00:00:00 GMT",
                "X-License": "MIT",
            },
        )
    )
    responses[url].append(HTTPError(url, 304, "Not Modified", hdrs=None, fp=None))

    scraper = HTTPScraper(opener=build_urlopen(responses, records), timeout=5)

    first = scraper.fetch(url)
    assert first is not None
    assert "Example Article" in first.content
    assert first.license == "MIT"

    second = scraper.fetch(url)
    assert second is not None
    assert second.content == first.content
    assert len(records) == 3
    assert records[0]["headers"]["user-agent"] == scraper.user_agent
    assert records[0]["timeout"] == 5
    assert records[1]["headers"]["user-agent"] == scraper.user_agent
    assert records[1]["headers"].get("if-none-match") is None
    assert records[2]["headers"]["if-none-match"] == "abc123"
    assert (
        records[2]["headers"]["if-modified-since"] == "Mon, 01 Jan 2024 00:00:00 GMT"
    )


def test_deduplication_detects_duplicate_content(monkeypatch):
    responses: Dict[str, List[object]] = defaultdict(list)
    records: List[Dict[str, object]] = []
    url_one = "https://example.com/one"
    url_two = "https://example.com/two"
    html = "<html><body>Same Content</body></html>"
    headers = {"Content-Type": "text/html; charset=utf-8"}
    responses[url_one].append(FakeResponse(html, headers=headers))
    responses[url_two].append(FakeResponse(html, headers=headers))

    scraper = HTTPScraper(opener=build_urlopen(responses, records))

    first = scraper.fetch(url_one)
    second = scraper.fetch(url_two)

    assert first is not None
    assert second is not None
    assert first.content_hash == second.content_hash
    assert second.is_duplicate is True


def test_fetch_raw_returns_payload(monkeypatch):
    responses: Dict[str, List[object]] = defaultdict(list)
    records: List[Dict[str, object]] = []
    url = "https://example.com/data.json"
    payload = json.dumps({"hello": "world"})
    responses[url].append(FakeResponse(payload, headers={"Content-Type": "application/json"}))

    scraper = HTTPScraper(opener=build_urlopen(responses, records))

    raw = scraper.fetch_raw(url)
    assert raw is not None
    body, headers = raw
    assert json.loads(body.decode("utf-8")) == {"hello": "world"}
    assert headers["content-type"] == "application/json"
