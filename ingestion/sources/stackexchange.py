"""Stack Overflow via the Stack Exchange API v2.3.

Two outputs: monthly question counts per vendor tag (a demand/adoption proxy
that is cheap and comparable across vendors) and question bodies (text for the
corpus). The unkeyed quota is 300 requests/day per IP, so a persistent daily
budget stops us before the API has to.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from typing import Any

from ingestion import config
from ingestion.http import PoliteClient, log_fetch
from ingestion.models import FetchedItem

log = logging.getLogger("strata.stackexchange")
SOURCE = "stackexchange"
BUDGET_FILE = config.STATE_DIR / "stackexchange_budget.json"


class BudgetExhausted(RuntimeError):
    pass


class SEClient:
    """Wraps PoliteClient with the SE-specific rules: daily budget and the mandatory `backoff` field."""

    def __init__(self) -> None:
        self._http = PoliteClient(SOURCE, min_interval_s=1.0)
        self._pending_backoff = 0.0

    def _spend(self) -> None:
        today = date.today().isoformat()
        state = json.loads(BUDGET_FILE.read_text()) if BUDGET_FILE.exists() else {}
        used = state.get(today, 0)
        budget = 9_500 if config.SE_KEY else config.SE_DAILY_BUDGET
        if used >= budget:
            raise BudgetExhausted(f"Stack Exchange daily budget of {budget} requests used")
        BUDGET_FILE.parent.mkdir(parents=True, exist_ok=True)
        BUDGET_FILE.write_text(json.dumps({today: used + 1}))

    def get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        import time

        if self._pending_backoff:
            # The API docs require waiting `backoff` seconds before hitting the same method again.
            time.sleep(self._pending_backoff)
            self._pending_backoff = 0.0
        self._spend()
        params = {"site": config.SE_SITE, **params}
        if config.SE_KEY:
            params["key"] = config.SE_KEY
        data = self._http.get_json(f"{config.SE_BASE_URL}{path}", params)
        self._pending_backoff = float(data.get("backoff", 0))
        if data.get("quota_remaining") is not None and data["quota_remaining"] < 5:
            raise BudgetExhausted(f"API reports quota_remaining={data['quota_remaining']}")
        return data

    def close(self) -> None:
        self._http.close()


def fetch(query: str, since: datetime, limit: int = config.DEFAULT_LIMIT) -> list[FetchedItem]:
    """`query` is a vendor key from config.SE_TAGS; returns tag counts plus up to `limit` questions per tag."""
    client = SEClient()
    items: list[FetchedItem] = []
    try:
        for tag in config.SE_TAGS[query]:
            items.extend(_tag_counts(client, query, tag))
            items.extend(_questions(client, query, tag, since, limit))
    except BudgetExhausted as exc:
        log.warning("stopping Stack Exchange early: %s", exc)
    finally:
        client.close()
    return items


def _month_starts(n: int) -> list[datetime]:
    today = datetime.now(timezone.utc)
    y, m = today.year, today.month
    out = []
    for _ in range(n + 1):
        out.append(datetime(y, m, 1, tzinfo=timezone.utc))
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return sorted(out)


def _tag_counts(client: SEClient, vendor: str, tag: str) -> list[FetchedItem]:
    """One `filter=total` call per complete month: cheap, and returns only a count."""
    items = []
    months = _month_starts(config.SE_TAG_COUNT_MONTHS)
    with log_fetch(SOURCE, f"tag_counts:{tag}") as counter:
        for start, end in zip(months, months[1:]):
            data = client.get(
                "/questions",
                {"tagged": tag, "fromdate": int(start.timestamp()), "todate": int(end.timestamp()) - 1, "filter": "total"},
            )
            raw = {"vendor": vendor, "tag": tag, "month": start.date().isoformat(), "total": data["total"]}
            items.append(FetchedItem(SOURCE, "tag_count", f"{tag}:{raw['month']}", datetime.now(timezone.utc), tag, raw))
        counter["count"] = len(items)
    return items


def _questions(client: SEClient, vendor: str, tag: str, since: datetime, limit: int) -> list[FetchedItem]:
    items: list[FetchedItem] = []
    page = 1
    with log_fetch(SOURCE, f"questions:{tag}") as counter:
        while len(items) < limit:
            data = client.get(
                "/questions",
                {
                    "tagged": tag,
                    "fromdate": int(since.timestamp()),
                    "sort": "creation",
                    "order": "desc",
                    "filter": "withbody",
                    "pagesize": 100,
                    "page": page,
                },
            )
            now = datetime.now(timezone.utc)
            for q in data.get("items", []):
                items.append(FetchedItem(SOURCE, "question", str(q["question_id"]), now, tag, {**q, "vendor": vendor}))
            if not data.get("has_more"):
                break
            page += 1
        counter["count"] = len(items)
    return items[:limit]
