\"\"\"
Scraper asynchrone respectable et basique :
- vérifie robots.txt (simple)
- rate limiting par domaine
- cache sur disque (datasets/raw)
- extrait blocs de code et texte principal
\"\"\"
from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

RAW_DIR = Path("datasets/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)

USER_AGENT = "WatcherBot/1.0 (+https://github.com/francis18georges-png/Watcher)"

RATE_PER_DOMAIN = 1.0  # seconds between requests to same domain

class DomainRateLimiter:
    def __init__(self):
        self._locks: dict[str, asyncio.Lock] = {}
        self._last_seen: dict[str, float] = {}

    async def wait(self, domain: str):
        lock = self._locks.setdefault(domain, asyncio.Lock())
        async with lock:
            last = self._last_seen.get(domain, 0)
            now = asyncio.get_event_loop().time()
            wait = RATE_PER_DOMAIN - (now - last)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_seen[domain] = asyncio.get_event_loop().time()

async def fetch(url: str, client: httpx.AsyncClient) -> tuple[str, bytes] | None:
    parsed = urlparse(url)
    domain = parsed.netloc
    # robots.txt: simple check (can be improved with robotsparser)
    robots_url = f"{parsed.scheme}://{domain}/robots.txt"
    try:
        r = await client.get(robots_url, headers={"user-agent": USER_AGENT}, timeout=10.0)
        if r.status_code == 200 and "Disallow: /" in r.text:
            logger.info("robots.txt disallows scraping %s", domain)
            return None
    except Exception:
        pass

    try:
        resp = await client.get(url, headers={"user-agent": USER_AGENT}, timeout=20.0)
        resp.raise_for_status()
        return url, resp.content
    except httpx.HTTPError as exc:
        logger.warning("fetch error %s: %s", url, exc)
        return None

def content_hash(url: str, content: bytes) -> str:
    h = hashlib.sha256()
    h.update(url.encode("utf-8"))
    h.update(content)
    return h.hexdigest()

def extract_text_and_code(html: bytes) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    for sel in ("nav", "footer", "aside", "header", "script", "style"):
        for el in soup.select(sel):
            el.decompose()
    title = soup.title.string.strip() if soup.title else ""
    code_blocks = []
    for pre in soup.find_all(["pre", "code"]):
        text = pre.get_text("\n", strip=True)
        if text:
            code_blocks.append(text)
    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    text = "\n\n".join(paragraphs)[:100_000]
    return {"title": title, "text": text, "code_blocks": code_blocks}

async def scrape_one(url: str, client: httpx.AsyncClient, limiter: DomainRateLimiter):
    parsed = urlparse(url)
    domain = parsed.netloc
    await limiter.wait(domain)
    res = await fetch(url, client)
    if not res:
        return None
    url, content = res
    key = content_hash(url, content)
    out_path = RAW_DIR / f"{key}.html"
    if out_path.exists():
        logger.debug("cached %s", url)
        return str(out_path)
    out_path.write_bytes(content)
    meta = extract_text_and_code(content)
    (RAW_DIR / f"{key}.meta.txt").write_text(f"url: {url}\ntitle: {meta['title']}\ncode_blocks: {len(meta['code_blocks'])}\n")
    logger.info("scraped %s -> %s", url, out_path.name)
    return str(out_path)

async def scrape(urls: list[str], concurrency: int = 5):
    limiter = DomainRateLimiter()
    async with httpx.AsyncClient(timeout=30.0) as client:
        sem = asyncio.Semaphore(concurrency)
        async def _wrap(u):
            async with sem:
                return await scrape_one(u, client, limiter)
        tasks = [asyncio.create_task(_wrap(u)) for u in urls]
        return await asyncio.gather(*tasks)
