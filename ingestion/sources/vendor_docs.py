"""Vendor pricing and docs pages.

These feed the capability matrix and pricing context, not switching data. We
check robots.txt before every fetch, try plain HTTP first, and only reach for
a headless browser when the page is demonstrably JS-rendered, because a
browser is heavier on the vendor's servers and harder to audit.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from ingestion import config
from ingestion.http import PoliteClient, log_fetch
from ingestion.models import FetchedItem

log = logging.getLogger("strata.vendor_docs")
SOURCE = "vendor_docs"
MIN_TEXT_CHARS = 800  # below this after stripping boilerplate, the page is probably client-rendered


class RobotsCache:
    """robots.txt per host. Used only for web pages, never for API adapters.

    Fetched with our own client so the proxy and User-Agent apply.

    Semantics follow RFC 9309: 4xx (other than 401/403) means no restrictions;
    401/403 or an unreachable/5xx robots.txt means we treat the whole host as
    disallowed, because the conservative reading is the defensible one.
    """

    def __init__(self, client: PoliteClient) -> None:
        self._client = client
        self._parsers: dict[str, RobotFileParser | None] = {}

    def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        host = f"{parts.scheme}://{parts.netloc}"
        if host not in self._parsers:
            self._parsers[host] = self._load(host)
        parser = self._parsers[host]
        if parser is None:
            return False
        return parser.can_fetch(config.USER_AGENT, url)

    def crawl_delay(self, url: str) -> float | None:
        parts = urlsplit(url)
        parser = self._parsers.get(f"{parts.scheme}://{parts.netloc}")
        delay = parser.crawl_delay(config.USER_AGENT) if parser else None
        return float(delay) if delay else None

    def _load(self, host: str) -> RobotFileParser | None:
        parser = RobotFileParser()
        try:
            resp = self._client._client.get(f"{host}/robots.txt")
        except httpx.HTTPError as exc:
            log.warning("robots.txt unreachable for %s (%s); treating host as disallowed", host, exc)
            return None
        if resp.status_code in (401, 403) or resp.status_code >= 500:
            log.warning("robots.txt for %s returned %s; treating host as disallowed", host, resp.status_code)
            return None
        if resp.status_code >= 400:
            parser.parse([])
        else:
            parser.parse(resp.text.splitlines())
        return parser


def fetch(query: str, since: datetime | None = None, limit: int = 100) -> list[FetchedItem]:
    """`query` is a vendor key from config.VENDOR_DOC_URLS. `since` is unused: pages are snapshots."""
    client = PoliteClient(SOURCE, config.DOCS_MIN_INTERVAL_S)
    robots = RobotsCache(client)
    items: list[FetchedItem] = []
    with log_fetch(SOURCE, query) as counter:
        try:
            for url in config.VENDOR_DOC_URLS[query][:limit]:
                item = _fetch_page(client, robots, query, url)
                if item:
                    items.append(item)
        finally:
            client.close()
        counter["count"] = len(items)
    return items


def _fetch_page(client: PoliteClient, robots: RobotsCache, vendor: str, url: str) -> FetchedItem | None:
    if not robots.allowed(url):
        log.warning("robots.txt disallows %s; skipped", url)
        return None
    delay = robots.crawl_delay(url)
    if delay:
        time.sleep(delay)
    try:
        resp = client.get(url)
    except Exception as exc:  # one bad page must not sink the other vendors
        log.warning("failed to fetch %s: %s", url, exc)
        return None
    html = resp.text
    title, text = extract_text(html)
    method = "http"
    if len(text) < MIN_TEXT_CHARS or "enable javascript" in text.lower():
        rendered = _render_with_playwright(url) if config.DOCS_USE_PLAYWRIGHT else None
        if rendered:
            html, method = rendered, "playwright"
            title, text = extract_text(html)
        else:
            log.warning("%s looks JS-rendered (%d chars); Playwright fallback %s", url, len(text),
                        "failed" if config.DOCS_USE_PLAYWRIGHT else "disabled")
    raw: dict[str, Any] = {
        "vendor": vendor,
        "url": str(resp.url),
        "requested_url": url,
        "title": title,
        "text": text,
        "last_modified": resp.headers.get("Last-Modified"),
        "method": method,
    }
    return FetchedItem(SOURCE, "doc_page", url, datetime.now(timezone.utc), vendor, raw)


def extract_text(html: str) -> tuple[str | None, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else None
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "svg", "form", "iframe"]):
        tag.decompose()
    root = soup.find("main") or soup.body or soup
    lines = [ln.strip() for ln in root.get_text("\n").splitlines()]
    return title, "\n".join(ln for ln in lines if ln)


def _render_with_playwright(url: str) -> str | None:
    """Optional dependency: only imported when DOCS_USE_PLAYWRIGHT=1."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.warning("playwright not installed; cannot render %s", url)
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(user_agent=config.USER_AGENT)
            page.goto(url, wait_until="networkidle", timeout=60_000)
            html = page.content()
            browser.close()
            return html
    except Exception as exc:
        log.warning("playwright render failed for %s: %s", url, exc)
        return None
