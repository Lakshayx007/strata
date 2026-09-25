"""Map the five native payload shapes onto the `documents` schema, and find vendor mentions.

Decisions baked in here, all chosen to keep counts defensible:
- Bodies are plain text. HTML (HN, Stack Exchange) is stripped once, here.
- A link-only post (no self text) uses its title as its body, so the text
  that was actually said is never dropped.
- Deleted/removed placeholders are not documents; they carry no opinion.
- Authors are stored only as a salted hash: enough to spot one prolific
  poster dominating a theme, without storing identities.
- content_hash covers the normalised body only, so the same text posted in
  two places is one document.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from html import unescape
from typing import Callable, Iterable

import pandas as pd
from bs4 import BeautifulSoup

from ingestion import config
from ingestion.models import METRIC_KINDS, FetchedItem

PLACEHOLDER_BODIES = {"[deleted]", "[removed]", ""}


@dataclass(frozen=True)
class DocumentRow:
    source: str  # resolved to sources.id at load time
    external_id: str
    url: str
    title: str | None
    body: str
    author_hash: str | None
    posted_at: datetime | None
    score: int | None
    n_comments: int | None
    fetched_at: datetime
    content_hash: str


@dataclass(frozen=True)
class MentionRow:
    vendor: str
    mention_count: int
    first_char_offset: int | None  # offset into body; None when the vendor appears only in the title


# --- helpers ------------------------------------------------------------------

def html_to_text(html: str | None) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for br in soup.find_all(["br", "p", "li", "pre"]):
        br.insert_before("\n")
    return unescape(soup.get_text()).strip()


def normalise_for_hash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def content_hash(body: str) -> str:
    return hashlib.sha256(normalise_for_hash(body).encode("utf-8")).hexdigest()


def author_hash(source: str, author: str | None) -> str | None:
    if not author or author in {"[deleted]", "deleted"}:
        return None
    if not config.AUTHOR_HASH_SALT:
        raise RuntimeError("AUTHOR_HASH_SALT must be set so author hashes cannot be reversed by dictionary lookup")
    return hmac.new(config.AUTHOR_HASH_SALT.encode(), f"{source}:{author}".encode(), hashlib.sha256).hexdigest()[:24]


def _ts(epoch: float | int | None) -> datetime | None:
    return datetime.fromtimestamp(epoch, tz=timezone.utc) if epoch is not None else None


def _row(item: FetchedItem, url: str, title: str | None, body: str, author: str | None,
         posted_at: datetime | None, score: int | None, n_comments: int | None) -> DocumentRow | None:
    body = body.strip()
    if body in PLACEHOLDER_BODIES:
        return None
    return DocumentRow(
        source=item.source,
        external_id=item.external_id,
        url=url,
        title=title,
        body=body,
        author_hash=author_hash(item.source, author),
        posted_at=posted_at,
        score=score,
        n_comments=n_comments,
        fetched_at=item.fetched_at,
        content_hash=content_hash(body),
    )


# --- per-source mappers ---------------------------------------------------------

def _reddit(item: FetchedItem) -> DocumentRow | None:
    r = item.raw
    if item.kind == "submission":
        body = r.get("selftext") or ""
        if body.strip() in PLACEHOLDER_BODIES:
            body = r["title"]  # link post or removed self text: the title is what was said
        return _row(item, r["permalink"], r["title"], body, r.get("author"), _ts(r["created_utc"]), r.get("score"), r.get("num_comments"))
    return _row(item, r["permalink"], None, r.get("body") or "", r.get("author"), _ts(r["created_utc"]), r.get("score"), r.get("num_replies"))


def _hackernews(item: FetchedItem) -> DocumentRow | None:
    r = item.raw
    url = f"https://news.ycombinator.com/item?id={r['objectID']}"
    if item.kind == "story":
        body = html_to_text(r.get("story_text")) or (r.get("title") or "")
        return _row(item, url, r.get("title"), body, r.get("author"), _ts(r.get("created_at_i")), r.get("points"), r.get("num_comments"))
    return _row(item, url, None, html_to_text(r.get("comment_text")), r.get("author"), _ts(r.get("created_at_i")), r.get("points"), None)


def _stackexchange(item: FetchedItem) -> DocumentRow | None:
    r = item.raw
    return _row(
        item, r["link"], unescape(r.get("title") or "") or None, html_to_text(r.get("body")),
        (r.get("owner") or {}).get("display_name"), _ts(r.get("creation_date")), r.get("score"), r.get("answer_count"),
    )


def _vendor_docs(item: FetchedItem) -> DocumentRow | None:
    r = item.raw
    # posted_at stays NULL unless the server says when the page changed: a fetch date is not a publish date.
    posted = pd.to_datetime(r["last_modified"], utc=True, errors="coerce").to_pydatetime() if r.get("last_modified") else None
    if posted is not None and pd.isna(posted):
        posted = None
    return _row(item, r["url"], r.get("title"), r.get("text") or "", None, posted, None, None)


def _iso(ts: str | None) -> datetime | None:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else None


def _devto(item: FetchedItem) -> DocumentRow | None:
    r = item.raw
    # Markdown is kept as written: it is already readable text, and stripping it would lose code blocks.
    return _row(item, r["url"], r.get("title"), r.get("body_markdown") or "", r.get("author"), _iso(r.get("published_at")),
                r.get("reactions"), r.get("comments_count"))


def _github_threads(item: FetchedItem) -> DocumentRow | None:
    r = item.raw
    body = r.get("body") or ""
    if not body.strip():
        body = r.get("title") or ""  # a title-only issue: the title is what was said
    return _row(item, r["url"], r.get("title"), body, r.get("author"), _iso(r.get("created_at")), r.get("reactions"), r.get("comments"))


MAPPERS: dict[str, Callable[[FetchedItem], DocumentRow | None]] = {
    "devto": _devto,
    "github_threads": _github_threads,
    "reddit": _reddit,
    "hackernews": _hackernews,
    "stackexchange": _stackexchange,
    "vendor_docs": _vendor_docs,
}


def to_documents(items: Iterable[FetchedItem]) -> list[DocumentRow]:
    """Text items become documents; metric items (tag counts, GitHub) are skipped here."""
    rows = []
    for item in items:
        if item.kind in METRIC_KINDS:
            continue
        row = MAPPERS[item.source](item)
        if row is not None:
            rows.append(row)
    return rows


# --- signals (not documents) ---------------------------------------------------

@dataclass(frozen=True)
class SignalRow:
    source: str
    signal_type: str  # so_tag_count | gh_stars | gh_contributors | gh_issue_velocity
    entity: str  # vendor slug, or repo as owner/name
    period_start: date
    granularity: str  # month | quarter
    metric: str
    value: float
    unit: str
    fetched_at: datetime


def _month(ts: str | datetime) -> date:
    d = pd.Timestamp(ts)
    return date(d.year, d.month, 1)


def to_signals(items: Iterable[FetchedItem]) -> list[SignalRow]:
    """Aggregate metric items into monthly signal rows.

    GitHub stars and issues arrive as one item per event; they are rolled up to
    months here so the database stores the series, not every stargazer.
    """
    items = [i for i in items if i.kind in METRIC_KINDS]
    if not items:
        return []
    fetched = max(i.fetched_at for i in items)
    rows: list[SignalRow] = []

    for i in items:
        r = i.raw
        if i.kind == "tag_count":
            # One metric per tag: AWS and Microsoft have two tags each, and a question can carry
            # both, so summing tags into one vendor number would double count.
            rows.append(SignalRow(i.source, "so_tag_count", r["vendor"], date.fromisoformat(r["month"]), "month",
                                  f"questions:{r['tag']}", float(r["total"]), "questions", i.fetched_at))
        elif i.kind == "repo_contributors":
            rows.append(SignalRow(i.source, "gh_contributors", r["repo"], _month(r["as_of"]), "month",
                                  "contributors_incl_anon_snapshot", float(r["contributors_incl_anon"]), "contributors", i.fetched_at))

    stars = pd.DataFrame([i.raw for i in items if i.kind == "repo_stars"])
    if not stars.empty:
        stars["month"] = stars.starred_at.map(_month)
        for repo, g in stars.groupby("repo"):
            monthly = g.groupby("month").size().sort_index()
            # Months with no new stars are real zeros, not missing data, so fill them.
            span = pd.period_range(min(monthly.index), max(monthly.index), freq="M")
            monthly = monthly.reindex([date(p.year, p.month, 1) for p in span], fill_value=0)
            for month, new, cum in zip(monthly.index, monthly.values, monthly.cumsum().values):
                rows.append(SignalRow("github", "gh_stars", repo, month, "month", "new_stars", float(new), "stars", fetched))
                rows.append(SignalRow("github", "gh_stars", repo, month, "month", "cumulative_stars", float(cum), "stars", fetched))

    issues = pd.DataFrame([i.raw for i in items if i.kind == "repo_issue"])
    if not issues.empty:
        for repo, g in issues.groupby("repo"):
            # The API filters on updated_at, so months before `since` are incomplete and are dropped.
            floor = _month(g["since"].iloc[0])
            opened = g.created_at.map(_month).value_counts()
            closed = g.closed_at.dropna().map(_month).value_counts()
            for metric, series in (("issues_opened", opened), ("issues_closed", closed)):
                for month, n in series.sort_index().items():
                    if month >= floor:
                        rows.append(SignalRow("github", "gh_issue_velocity", repo, month, "month", metric, float(n), "issues", fetched))
    return rows


# --- vendor mentions -----------------------------------------------------------

_ALIASES = {e: [re.compile(p, re.IGNORECASE) for p in pats] for e, pats in config.MENTION_ALIASES.items()}
_AMBIGUOUS = [
    {**t, "term_re": re.compile(t["term"], re.IGNORECASE), "context_re": [re.compile(c, re.IGNORECASE) for c in t["context"]]}
    for t in config.AMBIGUOUS_TERMS
]
_EXCLUDED = [{**x, "re": re.compile(x["pattern"], re.IGNORECASE)} for x in config.EXCLUDED_PATTERNS]


@dataclass(frozen=True)
class RejectedMention:
    entity: str
    term: str  # the pattern that matched
    reason: str  # no_context | excluded
    snippet: str


def _match_text(text: str) -> tuple[dict[str, list[int]], list[RejectedMention]]:
    """Offsets of accepted matches per entity, plus every rejected candidate."""
    accepted: dict[str, list[int]] = {}
    spans: list[tuple[int, int]] = []
    for entity, patterns in _ALIASES.items():
        for p in patterns:
            for m in p.finditer(text):
                accepted.setdefault(entity, []).append(m.start())
                spans.append(m.span())

    def covered(start: int) -> bool:
        return any(s <= start < e for s, e in spans)

    # Excluded phrases must not serve as context: "snowflake schema" is not evidence that a
    # nearby "redshift" is the AWS product. Blank them out of the text used for context checks.
    context_text = text
    for x in _EXCLUDED:
        context_text = x["re"].sub(lambda m: m.group(0) if covered(m.start()) else " " * len(m.group(0)), context_text)

    rejected: list[RejectedMention] = []
    for t in _AMBIGUOUS:
        for m in t["term_re"].finditer(text):
            if covered(m.start()):
                continue  # already counted by an unambiguous phrase such as "azure synapse"
            window = context_text[max(0, m.start() - t["window"]): m.end() + t["window"]]
            if any(c.search(window) for c in t["context_re"]):
                accepted.setdefault(t["entity"], []).append(m.start())
            else:
                rejected.append(RejectedMention(t["entity"], t["term"], "no_context", _snippet(text, m.start(), m.end())))
    for x in _EXCLUDED:
        for m in x["re"].finditer(text):
            if not covered(m.start()):
                rejected.append(RejectedMention(x["entity"], x["pattern"], "excluded", _snippet(text, m.start(), m.end())))
    return {e: sorted(set(v)) for e, v in accepted.items()}, rejected


def _snippet(text: str, start: int, end: int, pad: int = 60) -> str:
    return re.sub(r"\s+", " ", text[max(0, start - pad): end + pad]).strip()


def find_mentions_with_rejections(body: str, title: str | None = None) -> tuple[list[MentionRow], list[RejectedMention]]:
    """Count accepted matches per entity across title and body, and return rejected candidates.

    first_char_offset indexes into `body` so it can slice the stored text directly;
    it is None when the entity appears only in the title.
    """
    body_hits, rejected = _match_text(body)
    title_hits: dict[str, list[int]] = {}
    if title and title != body:
        title_hits, title_rejected = _match_text(title)
        rejected += title_rejected
    out = []
    for entity in list(_ALIASES) + [t["entity"] for t in _AMBIGUOUS if t["entity"] not in _ALIASES]:
        b, t = body_hits.get(entity, []), title_hits.get(entity, [])
        if b or t:
            out.append(MentionRow(entity, len(b) + len(t), b[0] if b else None))
    return out, rejected


def find_mentions(body: str, title: str | None = None) -> list[MentionRow]:
    return find_mentions_with_rejections(body, title)[0]


# Word boundaries matter: a bare substring test makes "POC" match "epoch" and "pocket".
_SWITCHING_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(p) for p in config.SWITCHING_PHRASES) + r")\b", re.IGNORECASE
)


def has_switching_language(text: str) -> bool:
    return bool(_SWITCHING_RE.search(text))
