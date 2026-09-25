# Strata

Market and competitive intelligence for the enterprise lakehouse market. Phase 1: schema and ingestion.

## Setup
    pip install -r requirements.txt
    cp .env.example .env        # fill in DATABASE_URL, AUTHOR_HASH_SALT and the source credentials

## Run
    python -m ingestion.run --sources hackernews,stackexchange,vendor_docs   # no credentials needed
    python -m ingestion.run --sources reddit,github                          # need Reddit app + no-scope GitHub token
    python -m ingestion.run --from-raw data/raw/<source>/<file>.jsonl       # re-load without re-fetching
    python analysis/tools/build_eda_notebook.py && jupyter nbconvert --execute --inplace analysis/notebooks/01_corpus_eda.ipynb
    pytest

## Layout
- `db/schema.sql` Postgres schema (idempotent; applied automatically by `ingestion.run`)
- `ingestion/config.py` every search term, vendor alias, subreddit, tag, repo and URL
- `ingestion/sources/*.py` one adapter per source, each `fetch(query, since, limit) -> list[FetchedItem]`
- `ingestion/normalize.py` native payloads -> `documents` rows, vendor mention matching
- `ingestion/dedupe.py` exact (content_hash) then near-duplicate (3-shingle cosine >= 0.90) removal, with a report
- `ingestion/load_to_db.py` idempotent upsert on content_hash; mentions rebuilt per touched document
- `data/raw/` untouched API payloads (JSONL, git-ignored); `data/processed/` dedupe and rejected-mention reports

## Signals vs documents
Stack Overflow tag counts and GitHub star, contributor and issue data are time series. They go in the `signals`
table and are never combined with `documents`. See `docs/methodology.md` for this rule and every other counting decision.

A missing credential for any requested source stops the run before anything is fetched, and lists what to set.
