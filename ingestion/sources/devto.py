"""Dev.to articles via the public Forem API (no key needed for reads).

Long-form "why we migrated" posts are the densest switching content available
without an approval-gated API. Two official endpoints are used: the tag feed
(`/articles?tag=`) to list articles, and `/articles/{id}` for the full markdown
body, which the list endpoint does not include.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from ingestion import config
from ingestion.http import PoliteClient, log_fetch
from ingestion.models import FetchedItem

SOURCE = "devto"

# Pre-filter for broad tags, on metadata only. Deliberately loose (bare words): it only decides
# whether to spend a request on the body; the strict mention rules run later on the full text.
_RELEVANT = re.compile(
    r"\b(?:databricks|snowflake|cloudera|redshift|aws glue|synapse|microsoft fabric|bigquery|lakehouse|"
    r"delta lake|iceberg|hudi)\b",
    re.IGNORECASE,
)
# Article ids already fetched in this process: the same post often carries several of our tags.
_SEEN: set[int] = set()


def fetch(query: str, since: datetime, limit: int = config.DEFAULT_LIMIT, client: PoliteClient | None = None) -> list[FetchedItem]:
    """`query` is a tag from config.DEVTO_TAGS. Returns up to `limit` articles published after `since`."""
    own = client is None
    client = client or PoliteClient(SOURCE, config.DEVTO_MIN_INTERVAL_S)
    items: list[FetchedItem] = []
    try:
        with log_fetch(SOURCE, f"tag:{query}") as counter:
            for summary in _list_tag(client, query, since):
                if len(items) >= limit:
                    break
                if summary["id"] in _SEEN:
                    continue
                if query in config.DEVTO_BROAD_TAGS and not _is_relevant(summary):
                    continue
                _SEEN.add(summary["id"])
                article = client.get_json(f"{config.DEVTO_API}/articles/{summary['id']}")
                items.append(FetchedItem(SOURCE, "article", str(article["id"]), datetime.now(timezone.utc), query, _raw(article)))
            counter["count"] = len(items)
    finally:
        if own:
            client.close()
    return items


def _list_tag(client: PoliteClient, tag: str, since: datetime) -> list[dict[str, Any]]:
    """All article summaries for a tag published after `since`, up to DEVTO_MAX_PAGES_PER_TAG pages.

    The feed's order is not documented as strictly chronological, so we filter by date
    rather than stopping at the first old article.
    """
    out: list[dict[str, Any]] = []
    for page in range(1, config.DEVTO_MAX_PAGES_PER_TAG + 1):
        batch = client.get_json(f"{config.DEVTO_API}/articles", {"tag": tag, "per_page": 100, "page": page})
        if not batch:
            break
        for a in batch:
            published = a.get("published_at")
            if published and datetime.fromisoformat(published.replace("Z", "+00:00")) >= since:
                out.append(a)
    return out


def _is_relevant(summary: dict[str, Any]) -> bool:
    tags = summary.get("tag_list") or []
    tags = tags if isinstance(tags, list) else str(tags).split(",")
    text = " ".join([summary.get("title") or "", summary.get("description") or "", " ".join(tags)])
    return bool(_RELEVANT.search(text))


def _raw(a: dict[str, Any]) -> dict[str, Any]:
    tags = a.get("tags") or a.get("tag_list") or []
    return {
        "id": a["id"],
        "title": a.get("title"),
        "body_markdown": a.get("body_markdown") or "",
        "url": a.get("url") or a.get("canonical_url"),
        "author": (a.get("user") or {}).get("username"),
        "published_at": a.get("published_at"),
        "reactions": a.get("public_reactions_count") or a.get("positive_reactions_count"),
        "comments_count": a.get("comments_count"),
        "tags": tags if isinstance(tags, list) else str(tags).split(", "),
    }
