"""GitHub issues and discussions that talk about migrating or comparing platforms.

Maintainers' trackers for Delta, Iceberg, Hudi and dbt are where engineers write
"we are moving from X, how do we..." in detail. We search them for migration and
comparison phrases only; we never bulk-collect every issue.

Issues use the REST search API; discussions are not in REST search, so they use
the GraphQL search API. Both share GitHub's search limit of 30 requests/minute.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from ingestion import config
from ingestion.http import PoliteClient, log_fetch
from ingestion.models import FetchedItem
from ingestion.sources.github_ecosystem import MissingCredentials

log = logging.getLogger("strata.github_threads")
SOURCE = "github_threads"
SEARCH_INTERVAL_S = 2.2  # 30 searches/minute, with margin
MAX_PAGES = 3  # 300 results per phrase per repo is far above what any phrase returns in practice

DISCUSSION_QUERY = """
query($q: String!, $cursor: String) {
  search(query: $q, type: DISCUSSION, first: 50, after: $cursor) {
    pageInfo { hasNextPage endCursor }
    nodes {
      ... on Discussion {
        id number title body url createdAt upvoteCount
        author { login }
        comments { totalCount }
        repository { nameWithOwner }
      }
    }
  }
}
"""


def _client() -> PoliteClient:
    if not config.GITHUB_TOKEN:
        raise MissingCredentials("STRATA_GITHUB_TOKEN must be set (the Actions GITHUB_TOKEN is enough)")
    return PoliteClient(
        SOURCE,
        min_interval_s=SEARCH_INTERVAL_S,
        headers={"Authorization": f"Bearer {config.GITHUB_TOKEN}", "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28"},
    )


def fetch(query: str, since: datetime, limit: int = config.DEFAULT_LIMIT) -> list[FetchedItem]:
    """`query` is "owner/repo". Searches issues and discussions for each phrase in GITHUB_THREAD_PHRASES."""
    client = _client()
    items: list[FetchedItem] = []
    seen: set[str] = set()
    day = since.date().isoformat()
    try:
        for phrase in config.GITHUB_THREAD_PHRASES:
            q = f'repo:{query} "{phrase}" created:>={day}'
            with log_fetch(SOURCE, f"{query} {phrase!r}") as counter:
                found = _issues(client, q) + _discussions(client, q)
                for kind, raw in found:
                    key = raw["url"]
                    if key in seen:
                        continue
                    seen.add(key)
                    ext = f"{query}#{raw['number']}" if kind == "issue" else f"{query}/discussions/{raw['number']}"
                    items.append(FetchedItem(SOURCE, kind, ext, datetime.now(timezone.utc), phrase, {**raw, "repo": query}))
                counter["count"] = len(found)
            if len(items) >= limit:
                break
    finally:
        client.close()
    return items[:limit]


def _wait_if_limited(resp: Any) -> None:
    remaining = resp.headers.get("x-ratelimit-remaining")
    if remaining is not None and int(remaining) == 0:
        wait = max(0, int(resp.headers.get("x-ratelimit-reset", "0")) - int(time.time())) + 5
        log.warning("GitHub search limit reached; sleeping %ds", wait)
        time.sleep(wait)


def _issues(client: PoliteClient, q: str) -> list[tuple[str, dict[str, Any]]]:
    out = []
    for page in range(1, MAX_PAGES + 1):
        resp = client.get(f"{config.GITHUB_API}/search/issues", {"q": f"{q} is:issue", "per_page": 100, "page": page})
        _wait_if_limited(resp)
        data = resp.json()
        for i in data.get("items", []):
            out.append(("issue", {
                "number": i["number"], "title": i["title"], "body": i.get("body") or "", "url": i["html_url"],
                "author": (i.get("user") or {}).get("login"), "created_at": i["created_at"],
                "comments": i.get("comments"), "reactions": (i.get("reactions") or {}).get("total_count"),
            }))
        if len(data.get("items", [])) < 100:
            break
    return out


def _discussions(client: PoliteClient, q: str) -> list[tuple[str, dict[str, Any]]]:
    out = []
    cursor = None
    for _ in range(MAX_PAGES):
        resp = client._client.post(f"{config.GITHUB_API}/graphql", json={"query": DISCUSSION_QUERY, "variables": {"q": q, "cursor": cursor}})
        client.requests_made += 1
        time.sleep(SEARCH_INTERVAL_S)
        if resp.status_code != 200:
            log.warning("discussion search HTTP %s for %r", resp.status_code, q)
            break
        payload = resp.json()
        if payload.get("errors"):
            log.warning("discussion search errors for %r: %s", q, payload["errors"])
            break
        search = payload["data"]["search"]
        for d in search["nodes"]:
            if not d:
                continue
            out.append(("discussion", {
                "number": d["number"], "title": d["title"], "body": d.get("body") or "", "url": d["url"],
                "author": (d.get("author") or {}).get("login"), "created_at": d["createdAt"],
                "comments": d["comments"]["totalCount"], "reactions": d.get("upvoteCount"),
            }))
        if not search["pageInfo"]["hasNextPage"]:
            break
        cursor = search["pageInfo"]["endCursor"]
    return out
