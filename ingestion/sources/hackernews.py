"""Hacker News via the Algolia HN Search API (no auth).

Stories and comments are searched separately because they answer different
questions: stories show what gets attention, comments hold the reasoning.
Algolia returns at most 1,000 hits per query, so we page backwards through
time using created_at_i windows instead of relying on page numbers alone.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ingestion import config
from ingestion.http import PoliteClient, log_fetch
from ingestion.models import FetchedItem

SOURCE = "hackernews"
HITS_PER_PAGE = 100
ALGOLIA_MAX_PAGES = 10  # 10 x 100 = Algolia's 1,000-hit ceiling per query


def fetch(query: str, since: datetime, limit: int = config.DEFAULT_LIMIT, client: PoliteClient | None = None) -> list[FetchedItem]:
    """Return up to `limit` stories and up to `limit` comments matching `query` posted after `since`."""
    own = client is None
    client = client or PoliteClient(SOURCE, config.HN_MIN_INTERVAL_S)
    items: list[FetchedItem] = []
    try:
        for tag, kind in (("story", "story"), ("comment", "comment")):
            with log_fetch(SOURCE, f"{query} [{tag}]") as counter:
                hits = _search(client, query, tag, since, limit)
                now = datetime.now(timezone.utc)
                items.extend(FetchedItem(SOURCE, kind, str(h["objectID"]), now, query, h) for h in hits)
                counter["count"] = len(hits)
    finally:
        if own:
            client.close()
    return items


def _search(client: PoliteClient, query: str, tag: str, since: datetime, limit: int) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    seen: set[str] = set()
    upper: int | None = None  # created_at_i upper bound for the current time window
    since_i = int(since.timestamp())
    while len(hits) < limit:
        filters = f"created_at_i>{since_i}" + (f",created_at_i<={upper}" if upper else "")
        window_new = 0
        oldest: int | None = None
        for page in range(ALGOLIA_MAX_PAGES):
            data = client.get_json(
                f"{config.HN_BASE_URL}/search_by_date",
                {"query": query, "tags": tag, "numericFilters": filters, "hitsPerPage": HITS_PER_PAGE, "page": page},
            )
            for h in data.get("hits", []):
                oid = str(h["objectID"])
                oldest = h["created_at_i"] if oldest is None else min(oldest, h["created_at_i"])
                if oid in seen:
                    continue
                seen.add(oid)
                hits.append(h)
                window_new += 1
            if page + 1 >= data.get("nbPages", 0) or len(hits) >= limit:
                break
        if window_new == 0 or oldest is None or len(hits) >= limit:
            break
        # Next window ends at the oldest timestamp seen; `seen` absorbs the boundary overlap.
        if upper == oldest:
            break
        upper = oldest
    return hits[:limit]
