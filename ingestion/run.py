"""End-to-end ingestion: fetch -> raw JSONL -> normalize -> dedupe -> load.

Usage:
    python -m ingestion.run --sources hackernews,stackexchange --since 2023-01-01 --limit 500
    python -m ingestion.run --from-raw data/raw/hackernews/20260925T160000.jsonl   # re-load without re-fetching

Required environment variables for every requested source are checked before
anything is fetched; if any are missing the run stops with the list, rather than
quietly skipping a source. A query that fails at runtime (network, API error) is
logged, the rest continue, and the run exits non-zero. Nothing is ever back-filled.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import pandas as pd

from ingestion import config, dedupe, load_to_db, normalize
from ingestion.models import FetchedItem
from ingestion.sources import github_ecosystem, hackernews, reddit, stackexchange, vendor_docs

log = logging.getLogger("strata.run")
PLACEHOLDER_MARKERS = ("YOUR_", "REPLACE_WITH")
ALL_SOURCES = ["reddit", "hackernews", "stackexchange", "github", "vendor_docs"]


def _queries(source: str) -> list[str]:
    if source in ("reddit", "hackernews"):
        return [q for _, q in config.search_queries()]
    if source == "stackexchange":
        return list(config.SE_TAGS)
    if source == "github":
        return list(config.GITHUB_REPOS)
    return list(config.VENDOR_DOC_URLS)


FETCHERS = {
    "reddit": reddit.fetch,
    "hackernews": hackernews.fetch,
    "stackexchange": stackexchange.fetch,
    "github": github_ecosystem.fetch,
    "vendor_docs": vendor_docs.fetch,
}


FLUSH_EVERY_QUERIES = 20  # load in batches so a long run that is cut off keeps what it already fetched


def fetch_source(source: str, since: datetime, limit: int) -> Iterator[tuple[list[FetchedItem], list[str]]]:
    """Yield (items, errors) every FLUSH_EVERY_QUERIES queries, and once more at the end."""
    items: list[FetchedItem] = []
    errors: list[str] = []
    fetched_any = False
    queries = _queries(source)
    for n, q in enumerate(queries, 1):
        try:
            got = FETCHERS[source](q, since, limit)
            items.extend(got)
            fetched_any = fetched_any or bool(got)
        except Exception as exc:  # keep going: one failing query should not discard the rest
            errors.append(f"{source} query {q!r} failed: {type(exc).__name__}: {exc}")
            log.warning(errors[-1])
            if len(errors) >= 3 and not fetched_any:
                errors.append(f"abandoned {source} after 3 failures with no data")
                break
        if n % FLUSH_EVERY_QUERIES == 0 and items:
            yield items, errors
            items, errors = [], []
    yield items, errors


def save_raw(source: str, items: list[FetchedItem]) -> Path | None:
    if not items:
        return None
    path = config.RAW_DIR / source / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for it in items:
            f.write(json.dumps(it.to_json(), default=str) + "\n")
    return path


def read_raw(path: Path) -> list[FetchedItem]:
    return [FetchedItem.from_json(json.loads(line)) for line in path.read_text().splitlines() if line.strip()]


def process(items: list[FetchedItem], engine=None, tag: str = "run") -> dict[str, int]:
    signals = normalize.to_signals(items)
    docs = normalize.to_documents(items)
    existing = load_to_db.existing_bodies(engine) if engine is not None else []
    kept, drops = dedupe.run(docs, existing)
    if drops:
        report = config.PROCESSED_DIR / f"dedupe_report_{tag}.csv"
        report.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame([d.__dict__ for d in drops]).to_csv(report, index=False)
    loaded = load_to_db.upsert_documents(engine, kept) if engine is not None else 0
    if engine is not None:
        load_to_db.record_drops(engine, drops)
    n_signals = load_to_db.upsert_signals(engine, signals) if engine is not None else 0
    return {"fetched": len(items), "documents": len(docs), "dropped_dupes": len(drops), "loaded": loaded, "signals": n_signals}


def missing_env(sources: list[str], use_db: bool) -> list[str]:
    needed = list(config.REQUIRED_ENV_ALWAYS) + (config.REQUIRED_ENV_DB if use_db else [])
    for s in sources:
        needed += config.REQUIRED_ENV_BY_SOURCE[s]
    # A value still holding the .env.example placeholder counts as missing, not as a credential.
    return [v for v in dict.fromkeys(needed) if not os.getenv(v) or any(t in os.getenv(v, "") for t in PLACEHOLDER_MARKERS)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", default=",".join(ALL_SOURCES))
    ap.add_argument("--since", default=config.DEFAULT_SINCE.date().isoformat())
    ap.add_argument("--limit", type=int, default=config.DEFAULT_LIMIT)
    ap.add_argument("--from-raw", type=Path, help="re-process a saved raw JSONL instead of fetching")
    ap.add_argument("--no-db", action="store_true", help="fetch and save raw only")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    sources = [x.strip() for x in args.sources.split(",") if x.strip()]
    unknown = [x for x in sources if x not in FETCHERS]
    if unknown:
        sys.exit(f"Unknown source(s): {', '.join(unknown)}. Choose from: {', '.join(ALL_SOURCES)}")
    missing = missing_env([] if args.from_raw else sources, not args.no_db)
    if missing:
        sys.exit(
            "Missing required environment variable(s): " + ", ".join(missing)
            + f"\nSet them in {config.PROJECT_ROOT / '.env'} (see .env.example for where to get each one),"
            + " or drop the source that needs them from --sources."
        )

    engine = None if args.no_db else load_to_db.get_engine()
    if engine is not None:
        load_to_db.apply_schema(engine)

    if args.from_raw:
        items = read_raw(args.from_raw)
        print(json.dumps(process(items, engine, args.from_raw.stem)))
        return

    since = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc)
    summary: dict[str, dict] = {}
    for source in sources:
        totals: dict[str, int] = {}
        all_errors: list[str] = []
        for batch_no, (items, errors) in enumerate(fetch_source(source, since, args.limit)):
            all_errors += errors
            if not items:
                continue
            save_raw(source, items)
            for k, v in process(items, engine, f"{source}_{batch_no}").items():
                totals[k] = totals.get(k, 0) + v
        if engine is not None:
            # Recorded even when nothing came back: "ran and got 0" is different from "never ran".
            load_to_db.mark_run(engine, load_to_db.ensure_source(engine, source))
        summary[source] = {**totals, "errors": all_errors}
        log.info("%s: %s", source, summary[source])
    print(json.dumps(summary, indent=2))
    failed = {k: v["errors"] for k, v in summary.items() if v["errors"]}
    if failed:
        sys.exit(f"Finished with errors in: {', '.join(failed)}. See the log above; loaded data is kept.")


if __name__ == "__main__":
    main()
