"""Open table-format ecosystem health from the GitHub REST API.

Iceberg, Delta, Hudi and Polaris are the battleground under the vendor
products (Databricks backs Delta, Snowflake backs Polaris/Iceberg), so their
momentum is a leading indicator for lakehouse positioning. These are metrics,
not text: they never enter `documents`.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Iterator

from ingestion import config
from ingestion.http import PoliteClient, log_fetch
from ingestion.models import FetchedItem

log = logging.getLogger("strata.github")
SOURCE = "github"


class MissingCredentials(RuntimeError):
    pass


def _client(accept: str = "application/vnd.github+json") -> PoliteClient:
    if not config.GITHUB_TOKEN:
        raise MissingCredentials("STRATA_GITHUB_TOKEN must be set (a classic token with no scopes is enough)")
    return PoliteClient(
        SOURCE,
        min_interval_s=0.8,  # ~4,500/hour, under the 5,000/hour authenticated limit
        headers={"Authorization": f"Bearer {config.GITHUB_TOKEN}", "Accept": accept, "X-GitHub-Api-Version": "2022-11-28"},
    )


def fetch(query: str, since: datetime, limit: int = 1_000_000) -> list[FetchedItem]:
    """`query` is "owner/repo". Returns every star event (with starred_at), one contributor
    count, and every issue opened or updated since `since` (PRs excluded)."""
    items: list[FetchedItem] = []
    items.extend(_stars(query, limit))
    items.extend(_contributors(query))
    items.extend(_issues(query, since, limit))
    return items


def _paginate(client: PoliteClient, url: str, params: dict[str, Any]) -> Iterator[list[dict[str, Any]]]:
    next_url: str | None = url
    first = True
    while next_url:
        resp = client.get(next_url, params if first else None)
        first = False
        _respect_rate_limit(resp)
        yield resp.json()
        next_url = resp.links.get("next", {}).get("url")


def _respect_rate_limit(resp: Any) -> None:
    """GitHub documents that clients should wait for reset when remaining hits 0 (it answers 403, not 429)."""
    import time

    remaining = resp.headers.get("x-ratelimit-remaining")
    if remaining is not None and int(remaining) == 0:
        reset = int(resp.headers.get("x-ratelimit-reset", "0"))
        wait = max(0, reset - int(time.time())) + 5
        log.warning("GitHub rate limit reached; sleeping %ds", wait)
        time.sleep(wait)


def _stars(repo: str, limit: int) -> list[FetchedItem]:
    # The star+json media type adds starred_at, which is what makes "stars over time" possible.
    client = _client("application/vnd.github.star+json")
    items: list[FetchedItem] = []
    with log_fetch(SOURCE, f"stars:{repo}") as counter:
        try:
            for page in _paginate(client, f"{config.GITHUB_API}/repos/{repo}/stargazers", {"per_page": 100}):
                now = datetime.now(timezone.utc)
                for s in page:
                    user = (s.get("user") or {}).get("login", "")
                    items.append(FetchedItem(SOURCE, "repo_stars", f"{repo}:{user}", now, repo, {"repo": repo, "starred_at": s["starred_at"]}))
                if len(items) >= limit:
                    break
        finally:
            client.close()
        counter["count"] = len(items)
    return items


def _contributors(repo: str) -> list[FetchedItem]:
    """Count via the Link header's last page with per_page=1: one request instead of dozens."""
    client = _client()
    with log_fetch(SOURCE, f"contributors:{repo}") as counter:
        try:
            resp = client.get(f"{config.GITHUB_API}/repos/{repo}/contributors", {"per_page": 1, "anon": "true"})
            last = resp.links.get("last", {}).get("url")
            match = re.search(r"[?&]page=(\d+)", last or "")
            count = int(match.group(1)) if match else len(resp.json())
        finally:
            client.close()
        counter["count"] = 1
    now = datetime.now(timezone.utc)
    return [FetchedItem(SOURCE, "repo_contributors", f"{repo}:{now.date()}", now, repo, {"repo": repo, "contributors_incl_anon": count, "as_of": now.date().isoformat()})]


def _issues(repo: str, since: datetime, limit: int) -> list[FetchedItem]:
    client = _client()
    items: list[FetchedItem] = []
    with log_fetch(SOURCE, f"issues:{repo}") as counter:
        try:
            params = {"state": "all", "since": since.isoformat(), "per_page": 100, "sort": "created", "direction": "desc"}
            for page in _paginate(client, f"{config.GITHUB_API}/repos/{repo}/issues", params):
                now = datetime.now(timezone.utc)
                for i in page:
                    if "pull_request" in i:  # the issues endpoint also returns PRs
                        continue
                    raw = {"repo": repo, "since": since.isoformat(), "number": i["number"], "created_at": i["created_at"], "closed_at": i["closed_at"], "state": i["state"]}
                    items.append(FetchedItem(SOURCE, "repo_issue", f"{repo}#{i['number']}", now, repo, raw))
                if len(items) >= limit:
                    break
        finally:
            client.close()
        counter["count"] = len(items)
    return items
