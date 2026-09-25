"""Shared HTTP plumbing so every adapter is polite in the same way.

Centralising User-Agent, throttling and 429 backoff here means the collection
constraints are enforced once and cannot drift per adapter. robots.txt is not
here on purpose: it governs crawlers on web pages, not documented API access,
so it lives in vendor_docs.py, the only adapter that fetches web pages.
"""

from __future__ import annotations

import logging
import random
import time
from contextlib import contextmanager
from typing import Any, Iterator

import httpx

from ingestion import config

log = logging.getLogger("strata.fetch")

RETRY_STATUSES = {429, 500, 502, 503, 504}


class PoliteClient:
    """httpx client with a fixed User-Agent, per-client throttle and exponential backoff."""

    def __init__(
        self,
        source: str,
        min_interval_s: float = 1.0,
        max_retries: int = 6,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.source = source
        self.min_interval_s = min_interval_s
        self.max_retries = max_retries
        self.requests_made = 0
        self._last_request = 0.0
        self._client = httpx.Client(
            headers={"User-Agent": config.USER_AGENT, **(headers or {})},
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
        )

    def _throttle(self) -> None:
        wait = self.min_interval_s - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    def get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        """GET with backoff on 429/5xx. Retry-After wins over our own schedule when present,
        because the server knows its limits better than we do."""
        for attempt in range(self.max_retries + 1):
            self._throttle()
            self.requests_made += 1
            try:
                resp = self._client.get(url, params=params)
            except httpx.TransportError as exc:
                if attempt == self.max_retries:
                    raise
                delay = _backoff(attempt)
                log.warning("%s transport error %s; retrying in %.1fs", self.source, exc, delay)
                time.sleep(delay)
                continue
            if resp.status_code in RETRY_STATUSES and attempt < self.max_retries:
                delay = _retry_after(resp) or _backoff(attempt)
                log.warning("%s HTTP %s on %s; backing off %.1fs", self.source, resp.status_code, url, delay)
                time.sleep(delay)
                continue
            resp.raise_for_status()
            return resp
        raise RuntimeError("unreachable")

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        return self.get(url, params).json()

    def close(self) -> None:
        self._client.close()


def _backoff(attempt: int, base: float = 2.0, cap: float = 300.0) -> float:
    # Full jitter avoids synchronised retries if several runs hit the same limit.
    return random.uniform(0, min(cap, base * (2**attempt))) + base


def _retry_after(resp: httpx.Response) -> float | None:
    value = resp.headers.get("Retry-After")
    if value and value.isdigit():
        return float(value)
    return None


@contextmanager
def log_fetch(source: str, query: str) -> Iterator[dict[str, int]]:
    """Log source, query, count and elapsed for every fetch() call; the caller sets counter['count']."""
    counter = {"count": 0}
    start = time.monotonic()
    try:
        yield counter
    finally:
        log.info(
            "fetch source=%s query=%r count=%d elapsed=%.1fs", source, query, counter["count"], time.monotonic() - start
        )
