"""Reddit via the official Data API (praw, OAuth app credentials).

Comments carry most of the "why we left X" reasoning, so every matching
submission is expanded into its full comment tree and flattened; each comment
becomes its own item with a pointer to its submission.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from ingestion import config
from ingestion.http import _backoff, log_fetch
from ingestion.models import FetchedItem

log = logging.getLogger("strata.reddit")
SOURCE = "reddit"


class MissingCredentials(RuntimeError):
    pass


def _client() -> Any:
    if not (config.REDDIT_CLIENT_ID and config.REDDIT_CLIENT_SECRET):
        raise MissingCredentials("REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET must be set")
    import praw  # imported lazily so the other adapters run without praw configured

    # App-only read-only OAuth: public subreddit data needs no username or password,
    # so none is asked for or stored.
    reddit = praw.Reddit(
        client_id=config.REDDIT_CLIENT_ID,
        client_secret=config.REDDIT_CLIENT_SECRET,
        user_agent=config.USER_AGENT,
        ratelimit_seconds=300,  # let praw sleep through documented rate-limit windows
    )
    reddit.read_only = True
    return reddit


def _with_backoff(fn: Any, *args: Any, **kwargs: Any) -> Any:
    """praw handles X-Ratelimit headers itself; this covers explicit 429s it surfaces."""
    from prawcore.exceptions import ServerError, TooManyRequests

    for attempt in range(7):
        try:
            return fn(*args, **kwargs)
        except (TooManyRequests, ServerError) as exc:
            delay = _backoff(attempt)
            log.warning("reddit %s; backing off %.1fs", type(exc).__name__, delay)
            time.sleep(delay)
    return fn(*args, **kwargs)


def fetch(query: str, since: datetime, limit: int = config.DEFAULT_LIMIT) -> list[FetchedItem]:
    """Search each configured subreddit for `query`, newest first, stopping at `since`.

    `limit` caps submissions per subreddit; comments are unbounded per submission
    because truncating a thread would bias toward top-voted opinions.
    """
    reddit = _client()
    items: list[FetchedItem] = []
    since_ts = since.timestamp()
    with log_fetch(SOURCE, query) as counter:
        for sub_name in config.REDDIT_SUBREDDITS:
            subreddit = reddit.subreddit(sub_name)
            results = _with_backoff(lambda: list(subreddit.search(query, sort="new", time_filter="all", limit=limit)))
            for submission in results:
                if submission.created_utc < since_ts:
                    continue
                now = datetime.now(timezone.utc)
                items.append(
                    FetchedItem(SOURCE, "submission", f"t3_{submission.id}", now, query, _submission_raw(submission, sub_name))
                )
                _with_backoff(submission.comments.replace_more, limit=config.REDDIT_REPLACE_MORE_LIMIT)
                for comment in submission.comments.list():
                    items.append(
                        FetchedItem(SOURCE, "comment", f"t1_{comment.id}", now, query, _comment_raw(comment, submission, sub_name))
                    )
        counter["count"] = len(items)
    return items


def _author(obj: Any) -> str | None:
    return obj.author.name if getattr(obj, "author", None) else None


def _submission_raw(s: Any, sub_name: str) -> dict[str, Any]:
    return {
        "id": s.id,
        "subreddit": sub_name,
        "title": s.title,
        "selftext": s.selftext,
        "url": s.url,
        "permalink": f"https://www.reddit.com{s.permalink}",
        "author": _author(s),
        "created_utc": s.created_utc,
        "score": s.score,
        "num_comments": s.num_comments,
        "is_self": s.is_self,
    }


def _comment_raw(c: Any, s: Any, sub_name: str) -> dict[str, Any]:
    return {
        "id": c.id,
        "subreddit": sub_name,
        "submission_id": s.id,
        "submission_title": s.title,
        "parent_id": c.parent_id,
        "body": c.body,
        "permalink": f"https://www.reddit.com{c.permalink}",
        "author": _author(c),
        "created_utc": c.created_utc,
        "score": c.score,
        "num_replies": len(c.replies) if hasattr(c, "replies") else None,
    }
