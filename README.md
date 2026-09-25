# Strata

Market and competitive intelligence for the enterprise lakehouse market. Phase 1: schema and ingestion.

## Sources
| source | what | access |
|---|---|---|
| hackernews | stories and comments | Algolia HN Search API, no key |
| stackexchange | Stack Overflow questions and monthly tag counts; dba, datascience, softwareengineering questions | Stack Exchange API, unkeyed |
| devto | long-form articles tagged databricks, snowflake, dataengineering, lakehouse, bigquery, redshift | Forem public API, no key |
| github_threads | issues and discussions on delta-io/delta, apache/iceberg, apache/hudi, dbt-labs/dbt-core that match migration or comparison phrases | GitHub search APIs, Actions token |
| github | stars, contributors and issue velocity for the open table formats (signals, not documents) | GitHub REST API, Actions token |
| vendor_docs | pricing and docs pages for the six vendors | plain HTTP, robots.txt checked |
| reddit | **excluded: API access requires approval** (Reddit Responsible Builder Policy). Not collected, with no unauthenticated or scraped fallback. The adapter stays in the repo in case access is granted. | |

## Setup
    pip install -r requirements.txt
    cp .env.example .env        # fill in DATABASE_URL, AUTHOR_HASH_SALT and the source credentials

## Run
    python -m ingestion.run --sources hackernews,stackexchange,devto,vendor_docs   # no credentials needed
    python -m ingestion.run --sources github_threads,github                        # need a no-scope GitHub token
    python -m ingestion.run --from-raw data/raw/<source>/<file>.jsonl       # re-load without re-fetching
    python analysis/tools/build_eda_notebook.py && jupyter nbconvert --execute --inplace analysis/notebooks/01_corpus_eda.ipynb
    python -m analysis.report                                                # corpus readiness numbers, from the DB only
    pytest

## Run in GitHub Actions
Add the repository secrets `DATABASE_URL` (any Postgres, e.g. Supabase session pooler or Neon) and `AUTHOR_HASH_SALT`.
Then go to Actions > ingest > Run workflow and pick a source (default: all).
The job log and run summary end with document, mention and signal counts from the database.
Raw JSONL is not kept between Actions runs; the database is the record.

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
