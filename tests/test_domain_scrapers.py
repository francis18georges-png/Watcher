import app.data.scrapers.french as fr
import app.data.scrapers.programming as prog


def test_french_defaults(monkeypatch, tmp_path):
    called = {}

    async def fake(urls, cache_dir, *, concurrency=5):
        called["urls"] = set(urls)
        return {u: "ok" for u in urls}

    monkeypatch.setattr(fr, "scrape_all", fake)
    result = fr.fetch_french_corpus(None, tmp_path)
    assert called["urls"] == fr.DEFAULT_URLS
    assert result == {u: "ok" for u in fr.DEFAULT_URLS}


def test_programming_custom_urls(monkeypatch, tmp_path):
    urls = ["https://example.com"]
    captured = {}

    async def fake(urls, cache_dir, *, concurrency=5):
        captured["urls"] = list(urls)
        return {u: "ok" for u in urls}

    monkeypatch.setattr(prog, "scrape_all", fake)
    result = prog.fetch_programming_docs(urls, tmp_path)
    assert captured["urls"] == urls
    assert result == {u: "ok" for u in urls}
