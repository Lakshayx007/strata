"""Remove exact and near-duplicate documents before loading.

Duplicates inflate exactly the counts Strata reports ("N people cite cost"),
so each dropped document is written to a report with the document it
duplicated and the similarity, making the removal auditable rather than silent.

Near-duplicates are found with word 3-shingles and cosine similarity. Short
texts are exempt: two "Same here, moved to Snowflake" comments by different
people are separate voices, and shingle overlap on a dozen words is noise.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.neighbors import NearestNeighbors

from ingestion.normalize import DocumentRow, normalise_for_hash

log = logging.getLogger("strata.dedupe")

NEAR_DUP_THRESHOLD = 0.90
MIN_TOKENS_FOR_NEAR_DUP = 30
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


@dataclass(frozen=True)
class DropRecord:
    dropped_external_id: str
    dropped_source: str
    kept_key: str  # external_id of the kept doc, or "db:<content_hash>" if it was already loaded
    reason: str  # exact | near
    similarity: float


def _order_key(d: DocumentRow) -> tuple:
    # Keep the earliest post: the original is more likely to be the author's own words than a repost.
    return (d.posted_at or d.fetched_at or _EPOCH, d.source, d.external_id)


def exact(docs: list[DocumentRow], existing_hashes: set[str] | None = None) -> tuple[list[DocumentRow], list[DropRecord]]:
    existing_hashes = existing_hashes or set()
    kept: dict[str, DocumentRow] = {}
    drops: list[DropRecord] = []
    for d in sorted(docs, key=_order_key):
        if d.content_hash in existing_hashes:
            # Already in the DB: the loader's upsert refreshes score/n_comments, so keep it for loading.
            kept.setdefault(d.content_hash, d)
            continue
        if d.content_hash in kept:
            drops.append(DropRecord(d.external_id, d.source, kept[d.content_hash].external_id, "exact", 1.0))
            continue
        kept[d.content_hash] = d
    return list(kept.values()), drops


def near(
    docs: list[DocumentRow],
    existing: list[tuple[str, str]] | None = None,
    threshold: float = NEAR_DUP_THRESHOLD,
) -> tuple[list[DocumentRow], list[DropRecord]]:
    """Drop docs that are >= threshold similar to an earlier doc or to an already-loaded one.

    `existing` is [(content_hash, body)] from the database, so near-duplicates
    are caught across runs as well as within one.
    """
    existing = existing or []
    existing_hashes = {h for h, _ in existing}
    docs = sorted(docs, key=_order_key)
    long_idx = [i for i, d in enumerate(docs) if len(d.body.split()) >= MIN_TOKENS_FOR_NEAR_DUP]
    long_existing = [(h, b) for h, b in existing if len(b.split()) >= MIN_TOKENS_FOR_NEAR_DUP]
    if not long_idx:
        return docs, []

    texts = [normalise_for_hash(b) for _, b in long_existing] + [normalise_for_hash(docs[i].body) for i in long_idx]
    vec = HashingVectorizer(analyzer="word", ngram_range=(3, 3), n_features=2**20, alternate_sign=False, norm="l2")
    X = vec.transform(texts)
    n_exist = len(long_existing)
    nn = NearestNeighbors(metric="cosine", algorithm="brute").fit(X)
    # Query only the new documents (against everything): cost grows with batch x corpus,
    # not corpus x corpus, which matters once the database holds tens of thousands of rows.
    dist_new, ind_new = nn.radius_neighbors(X[n_exist:], radius=1 - threshold, sort_results=True)
    dist = [None] * n_exist + list(dist_new)
    ind = [None] * n_exist + list(ind_new)

    dropped: set[int] = set()  # positions in `texts`
    drops: list[DropRecord] = []
    for pos in range(n_exist, len(texts)):
        doc = docs[long_idx[pos - n_exist]]
        if doc.content_hash in existing_hashes:
            continue  # this is an existing row being refreshed, not a new near-dup
        for d, other in zip(dist[pos], ind[pos]):
            # Only compare against things that come first: loaded rows, or earlier new docs that survived.
            if other == pos or other > pos or other in dropped:
                continue
            kept_key = f"db:{long_existing[other][0]}" if other < n_exist else docs[long_idx[other - n_exist]].external_id
            drops.append(DropRecord(doc.external_id, doc.source, kept_key, "near", float(np.round(1 - d, 4))))
            dropped.add(pos)
            break

    dropped_ids = {id(docs[long_idx[p - n_exist]]) for p in dropped}
    kept = [d for d in docs if id(d) not in dropped_ids]
    log.info("near-dup: %d of %d long docs dropped at threshold %.2f", len(dropped), len(long_idx), threshold)
    return kept, drops


def run(docs: list[DocumentRow], existing: list[tuple[str, str]] | None = None) -> tuple[list[DocumentRow], list[DropRecord]]:
    existing = existing or []
    kept, drops_exact = exact(docs, {h for h, _ in existing})
    kept, drops_near = near(kept, existing)
    log.info("dedupe: %d in, %d exact dropped, %d near dropped, %d out", len(docs), len(drops_exact), len(drops_near), len(kept))
    return kept, drops_exact + drops_near
