"""Idempotent loading into Postgres.

Re-running any ingestion must converge to the same database, so:
- sources are looked up by name and created once;
- documents upsert on content_hash, refreshing only the fields that change
  over time (score, n_comments, fetched_at) and never the text;
- mentions for every touched document are replaced wholesale, so changing an
  alias regex and re-running corrects old counts instead of adding to them;
- signals upsert on their natural key (source, type, entity, period, metric).
Labels and switch_events are never touched here.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from typing import Iterable

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import MetaData, Table

from ingestion import config
from ingestion.dedupe import DropRecord
from ingestion.normalize import DocumentRow, RejectedMention, SignalRow, find_mentions_with_rejections

log = logging.getLogger("strata.load")
SCHEMA_SQL = config.PROJECT_ROOT / "db" / "schema.sql"
BATCH = 500


def get_engine(url: str | None = None) -> Engine:
    url = url or config.DATABASE_URL
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return create_engine(normalise_db_url(url), pool_pre_ping=True, future=True)


def normalise_db_url(url: str) -> str:
    """Supabase hands out postgresql:// (or postgres://) URIs. SQLAlchemy 2.1 maps a bare
    postgresql:// to psycopg 3, which we do not install, so pin the psycopg2 driver explicitly."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg2://" + url[len(prefix):]
    return url


def apply_schema(engine: Engine, path: Path = SCHEMA_SQL) -> None:
    with engine.begin() as conn:
        conn.exec_driver_sql(path.read_text())


def ensure_source(engine: Engine, name: str) -> int:
    meta = config.SOURCE_REGISTRY[name]
    with engine.begin() as conn:
        row = conn.execute(text("SELECT id FROM sources WHERE name = :n"), {"n": name}).first()
        if row:
            # terms_note is refreshed so the table always reflects the current config's reading of the terms.
            conn.execute(text("UPDATE sources SET kind=:k, base_url=:b, terms_note=:t WHERE id=:id"),
                         {"k": meta["kind"], "b": meta["base_url"], "t": meta["terms_note"], "id": row[0]})
            return int(row[0])
        return int(conn.execute(
            text("INSERT INTO sources (name, kind, base_url, terms_note) VALUES (:n, :k, :b, :t) RETURNING id"),
            {"n": name, "k": meta["kind"], "b": meta["base_url"], "t": meta["terms_note"]},
        ).scalar_one())


def mark_run(engine: Engine, source_id: int, at: datetime | None = None) -> None:
    with engine.begin() as conn:
        conn.execute(text("UPDATE sources SET last_run_at=:t WHERE id=:id"), {"t": at or datetime.now(timezone.utc), "id": source_id})


def existing_bodies(engine: Engine) -> list[tuple[str, str]]:
    with engine.connect() as conn:
        return [(r[0], r[1]) for r in conn.execute(text("SELECT content_hash, body FROM documents"))]


def upsert_documents(engine: Engine, docs: Iterable[DocumentRow]) -> int:
    # ON CONFLICT cannot touch the same row twice in one statement, so collapse repeats defensively.
    docs = list({d.content_hash: d for d in docs}.values())
    if not docs:
        return 0
    md = MetaData()
    documents = Table("documents", md, autoload_with=engine)
    mentions = Table("mentions", md, autoload_with=engine)
    source_ids = {name: ensure_source(engine, name) for name in {d.source for d in docs}}

    written = 0
    rejections: list[tuple[int, RejectedMention]] = []
    for start in range(0, len(docs), BATCH):
        chunk = docs[start:start + BATCH]
        values = [
            {
                "source_id": source_ids[d.source], "external_id": d.external_id, "url": d.url, "title": d.title,
                "body": d.body, "author_hash": d.author_hash, "posted_at": d.posted_at, "score": d.score,
                "n_comments": d.n_comments, "fetched_at": d.fetched_at, "content_hash": d.content_hash,
            }
            for d in chunk
        ]
        stmt = pg_insert(documents).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["content_hash"],
            set_={"score": stmt.excluded.score, "n_comments": stmt.excluded.n_comments, "fetched_at": stmt.excluded.fetched_at},
        ).returning(documents.c.id, documents.c.content_hash)
        with engine.begin() as conn:
            ids = {h: i for i, h in conn.execute(stmt)}
            conn.execute(mentions.delete().where(mentions.c.document_id.in_(list(ids.values()))))
            mention_rows = []
            for d in chunk:
                found, rejected = find_mentions_with_rejections(d.body, d.title)
                mention_rows += [{"document_id": ids[d.content_hash], "vendor": m.vendor, "mention_count": m.mention_count,
                                  "first_char_offset": m.first_char_offset} for m in found]
                rejections += [(ids[d.content_hash], r) for r in rejected]
            if mention_rows:
                conn.execute(mentions.insert(), mention_rows)
        written += len(ids)
    log.info("upserted %d documents", written)
    report_rejections(rejections)
    return written


REJECTIONS_CSV = config.PROCESSED_DIR / "rejected_mentions.csv"


def report_rejections(rejections: list[tuple[int, RejectedMention]]) -> None:
    """Log rejected candidate mentions per term and keep them, with snippets, for precision review.

    The CSV is rewritten per document id, so re-running does not accumulate duplicates.
    """
    counts = Counter((r.entity, r.term, r.reason) for _, r in rejections)
    for (entity, term, reason), n in counts.most_common():
        log.info("rejected mention candidates entity=%s term=%s reason=%s count=%d", entity, term, reason, n)
    if not rejections:
        return
    new = pd.DataFrame([{"document_id": i, **r.__dict__} for i, r in rejections])
    if REJECTIONS_CSV.exists():
        old = pd.read_csv(REJECTIONS_CSV)
        new = pd.concat([old[~old.document_id.isin(new.document_id)], new])
    REJECTIONS_CSV.parent.mkdir(parents=True, exist_ok=True)
    new.to_csv(REJECTIONS_CSV, index=False)


def upsert_signals(engine: Engine, rows: Iterable[SignalRow]) -> int:
    rows = list({(r.source, r.signal_type, r.entity, r.period_start, r.metric): r for r in rows}.values())
    if not rows:
        return 0
    signals = Table("signals", MetaData(), autoload_with=engine)
    source_ids = {name: ensure_source(engine, name) for name in {r.source for r in rows}}
    for start in range(0, len(rows), BATCH):
        values = [{"source_id": source_ids[r.source], "signal_type": r.signal_type, "entity": r.entity,
                   "period_start": r.period_start, "granularity": r.granularity, "metric": r.metric,
                   "value": r.value, "unit": r.unit, "fetched_at": r.fetched_at} for r in rows[start:start + BATCH]]
        stmt = pg_insert(signals).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["source_id", "signal_type", "entity", "period_start", "metric"],
            set_={"value": stmt.excluded.value, "unit": stmt.excluded.unit, "granularity": stmt.excluded.granularity,
                  "fetched_at": stmt.excluded.fetched_at},
        )
        with engine.begin() as conn:
            conn.execute(stmt)
    log.info("upserted %d signal rows", len(rows))
    return len(rows)


def recompute_all_mentions(engine: Engine) -> int:
    """Rebuild mentions from stored text, e.g. after editing the alias rules in config. Safe to re-run."""
    md = MetaData()
    mentions = Table("mentions", md, autoload_with=engine)
    with engine.begin() as conn:
        rows = conn.execute(text("SELECT id, title, body FROM documents")).all()
        conn.execute(mentions.delete())
        new, rejections = [], []
        for i, t, b in rows:
            found, rejected = find_mentions_with_rejections(b, t)
            new += [{"document_id": i, "vendor": m.vendor, "mention_count": m.mention_count,
                     "first_char_offset": m.first_char_offset} for m in found]
            rejections += [(i, r) for r in rejected]
        if new:
            conn.execute(mentions.insert(), new)
    report_rejections(rejections)
    return len(new)


def record_drops(engine: Engine, drops: Iterable[DropRecord]) -> int:
    """Persist the dedupe audit. Idempotent on (source, dropped_external_id)."""
    drops = list({(d.dropped_source, d.dropped_external_id): d for d in drops}.values())
    if not drops:
        return 0
    table = Table("dedupe_drops", MetaData(), autoload_with=engine)
    source_ids = {name: ensure_source(engine, name) for name in {d.dropped_source for d in drops}}
    values = [{"source_id": source_ids[d.dropped_source], "dropped_external_id": d.dropped_external_id,
               "kept_key": d.kept_key, "reason": d.reason, "similarity": d.similarity} for d in drops]
    for start in range(0, len(values), BATCH):
        stmt = pg_insert(table).values(values[start:start + BATCH])
        stmt = stmt.on_conflict_do_update(
            index_elements=["source_id", "dropped_external_id"],
            set_={"kept_key": stmt.excluded.kept_key, "reason": stmt.excluded.reason, "similarity": stmt.excluded.similarity},
        )
        with engine.begin() as conn:
            conn.execute(stmt)
    return len(values)
