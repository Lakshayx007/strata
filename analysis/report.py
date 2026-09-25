"""Corpus readiness report: is there enough labellable text to start Phase 2?

Reads only the database, so it can be re-run at any time without re-ingesting:
    python -m analysis.report

It answers four questions, each by source:
  1. How many documents contain switching language (config.SWITCHING_PHRASES, body only)?
  2. How many compare vendors (two or more distinct vendors mentioned), and which pairs?
  3. Are documents substantive, or thin one-liners (median length, share under 20 words)?
  4. How much was thrown away as duplicate (dedupe audit)?
Signals are reported last and on their own; they are never added to document counts.
"""

from __future__ import annotations

from collections import Counter
from itertools import combinations

import pandas as pd
from sqlalchemy import text

from ingestion import config
from ingestion.load_to_db import get_engine
from ingestion.normalize import has_switching_language

DISCUSSION_SOURCES = ["hackernews", "stackexchange", "devto", "github_threads", "reddit"]  # vendor pages are reference text, not seed material
THIN_WORDS = 20  # below this a document rarely carries a reason that can be labelled


def _table(df: pd.DataFrame) -> str:
    return "  (none)" if df.empty else "\n".join("  " + line for line in df.to_string(index=False).splitlines())


def build(engine) -> dict[str, pd.DataFrame | int]:
    docs = pd.read_sql(text("SELECT d.id, s.name AS source, d.body FROM documents d JOIN sources s ON s.id = d.source_id"), engine)
    mentions = pd.read_sql(text("SELECT document_id, vendor FROM mentions"), engine)
    drops = pd.read_sql(text("SELECT s.name AS source, x.reason FROM dedupe_drops x JOIN sources s ON s.id = x.source_id"), engine)
    signals = pd.read_sql(text('''
        SELECT signal_type, COUNT(DISTINCT entity) AS entities, COUNT(*) AS signal_rows,
               MIN(period_start) AS first_period, MAX(period_start) AS last_period
        FROM signals GROUP BY signal_type ORDER BY signal_type'''), engine)
    return compute(docs, mentions, drops, signals)


def compute(docs: pd.DataFrame, mentions: pd.DataFrame, drops: pd.DataFrame, signals: pd.DataFrame) -> dict:
    """Pure function over the four frames, so the arithmetic is unit-tested without a database."""
    docs = docs.copy()
    out: dict[str, pd.DataFrame | int] = {"documents": len(docs), "mention_rows": len(mentions), "signals": signals}

    # Explicit dtypes: on an empty frame pandas would otherwise infer object columns.
    docs["words"] = docs.body.str.split().str.len().astype("int64")
    docs["chars"] = docs.body.str.len().astype("int64")
    docs["switching"] = docs.body.map(has_switching_language).astype(bool)

    # Vendors only: tech:* entities (Delta Lake, Spark) are not vendors and must not create "comparisons".
    vend = mentions[mentions.vendor.isin(config.VENDORS)].drop_duplicates()
    per_doc = vend.groupby("document_id").vendor.apply(lambda v: tuple(sorted(v)))
    multi_ids = per_doc[per_doc.map(len) >= 2]
    docs["multi_vendor"] = docs.id.isin(multi_ids.index)
    pairs = Counter(p for vs in multi_ids for p in combinations(vs, 2))
    out["top_pairs"] = pd.DataFrame([{"vendor_a": a, "vendor_b": b, "documents": n} for (a, b), n in pairs.most_common(10)])

    g = docs.groupby("source")
    by_source = pd.DataFrame({
        "documents": g.size(),
        "switching": g.switching.sum(),
        "multi_vendor": g.multi_vendor.sum(),
        "median_words": g.words.median(),
        "median_chars": g.chars.median(),
        f"share_under_{THIN_WORDS}_words": g.words.apply(lambda w: (w < THIN_WORDS).mean()),
    }) if not docs.empty else pd.DataFrame()
    if not by_source.empty:
        by_source["switching_share"] = by_source.switching / by_source.documents
        by_source["multi_vendor_share"] = by_source.multi_vendor / by_source.documents
    out["by_source"] = by_source.reset_index()
    # Headline numbers cover discussion sources only; the by-source table shows everything.
    disc = docs[docs.source.isin(DISCUSSION_SOURCES)]
    out["discussion_documents"] = len(disc)
    out["switching"] = int(disc.switching.sum())
    out["multi_vendor"] = int(disc.multi_vendor.sum())
    out["median_words"] = float(disc.words.median()) if len(disc) else 0.0
    out["median_chars"] = float(disc.chars.median()) if len(disc) else 0.0

    # Duplicate rate = dropped / (dropped + kept). Drops are unique per source item, so re-runs don't inflate it.
    d = drops.groupby(["source", "reason"]).size().unstack(fill_value=0) if not drops.empty else pd.DataFrame()
    dup = pd.DataFrame({"kept": docs.groupby("source").size()}).join(d, how="outer").fillna(0).astype(int)
    for col in ("exact", "near"):
        if col not in dup:
            dup[col] = 0
    dup["duplicate_rate"] = ((dup.exact + dup.near) / (dup.kept + dup.exact + dup.near)).fillna(0)
    out["dupes"] = dup.reset_index().rename(columns={"index": "source"})
    total_dropped = int(dup.exact.sum() + dup.near.sum())
    out["duplicate_rate"] = total_dropped / (total_dropped + len(docs)) if (total_dropped + len(docs)) else 0.0
    return out


def render(r: dict) -> str:
    n = r["discussion_documents"] or 1
    lines = [
        "=" * 78,
        "STRATA CORPUS REPORT",
        "=" * 78,
        f"Documents, all sources         {r['documents']:>8,}",
        f"Discussion documents           {r['discussion_documents']:>8,}  ({', '.join(DISCUSSION_SOURCES)}; headline below)",
        f"  with switching language      {r['switching']:>8,}  ({r['switching'] / n:.1%})",
        f"  mentioning 2+ vendors        {r['multi_vendor']:>8,}  ({r['multi_vendor'] / n:.1%})",
        f"  median body length           {r['median_words']:>8,.0f} words / {r['median_chars']:,.0f} chars",
        f"Duplicate rate, all sources    {r['duplicate_rate']:>8.1%}",
        f"Mention rows                   {r['mention_rows']:>8,}",
        "",
        f"Switching phrases (body, case-insensitive, whole words): {' | '.join(config.SWITCHING_PHRASES)}",
        "",
        "By source:",
        _table(r["by_source"].round(3)),
        "",
        "Top vendor pairs (documents mentioning both):",
        _table(r["top_pairs"]),
        "",
        "Duplicates removed before loading:",
        _table(r["dupes"].round(3)),
        "",
        "Signals (separate evidence; never added to document counts):",
        _table(r["signals"]),
    ]
    return "\n".join(lines)


def main() -> None:
    print(render(build(get_engine())))


if __name__ == "__main__":
    main()
