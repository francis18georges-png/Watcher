import asyncio
from pathlib import Path

from app.data.scraper import scrape

def test_scrape_one_local_file(tmp_path: Path):
    html = "<html><head><title>t</title></head><body><p>hello</p><pre>print(1)</pre></body></html>"
    f = tmp_path / "t.html"
    f.write_text(html, encoding="utf-8")
    url = f"file://{f}"
    # Use asyncio.run to avoid an overly long single line and to follow modern asyncio API
    results = asyncio.run(scrape([url], concurrency=1))
    assert results is not None
