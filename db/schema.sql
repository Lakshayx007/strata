-- Strata Phase 1 schema (Postgres 14+ / Supabase).
-- Columns follow the Phase 1 spec exactly. Enumerations are CHECK constraints
-- rather than Postgres ENUM types so that adding a value later is a one-line
-- migration instead of an ALTER TYPE dance.
-- Safe to re-run: every statement is IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS sources (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name         TEXT NOT NULL,
    kind         TEXT NOT NULL CHECK (kind IN ('api', 'docs')),
    base_url     TEXT NOT NULL,
    terms_note   TEXT NOT NULL,
    last_run_at  TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS documents (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id     BIGINT NOT NULL REFERENCES sources (id),
    external_id   TEXT NOT NULL,
    url           TEXT NOT NULL,
    title         TEXT,
    body          TEXT NOT NULL,
    author_hash   TEXT,
    posted_at     TIMESTAMPTZ,
    score         INTEGER,
    n_comments    INTEGER,
    fetched_at    TIMESTAMPTZ NOT NULL,
    content_hash  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS documents_source_posted_idx ON documents (source_id, posted_at);
CREATE UNIQUE INDEX IF NOT EXISTS documents_content_hash_uq ON documents (content_hash);

CREATE TABLE IF NOT EXISTS mentions (
    id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id        BIGINT NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    vendor             TEXT NOT NULL,
    mention_count      INTEGER NOT NULL CHECK (mention_count > 0),
    first_char_offset  INTEGER
);
CREATE INDEX IF NOT EXISTS mentions_vendor_document_idx ON mentions (vendor, document_id);

CREATE TABLE IF NOT EXISTS switch_events (
    id                   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id          BIGINT NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    from_vendor          TEXT,
    to_vendor            TEXT,
    direction            TEXT NOT NULL CHECK (direction IN ('adopt', 'leave', 'evaluate')),
    stated_reason_label  TEXT,
    confidence           REAL,
    -- Phase 3 rule: never store an event without the sentence that produced it.
    evidence_span        TEXT NOT NULL CHECK (length(evidence_span) > 0),
    labeled_by           TEXT NOT NULL CHECK (labeled_by IN ('human', 'model'))
);

CREATE TABLE IF NOT EXISTS labels (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id    BIGINT NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    taxonomy_code  TEXT NOT NULL,
    confidence     REAL,
    labeled_by     TEXT NOT NULL CHECK (labeled_by IN ('human', 'model')),
    labeled_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS vendor_features (
    vendor        TEXT NOT NULL,
    capability    TEXT NOT NULL,
    score         REAL,
    evidence_url  TEXT,
    note          TEXT,
    as_of         DATE NOT NULL,
    PRIMARY KEY (vendor, capability, as_of)
);

CREATE TABLE IF NOT EXISTS market_inputs (
    key     TEXT NOT NULL,
    value   DOUBLE PRECISION,
    unit    TEXT,
    source  TEXT,
    note    TEXT,
    as_of   DATE NOT NULL,
    PRIMARY KEY (key, as_of)
);

-- Time-series signals (Stack Overflow tag counts, GitHub ecosystem metrics).
-- Deliberately separate from `documents`: a tag count is an adoption proxy, a
-- discussion is stated reasoning, and the two must never be summed into one
-- metric. See docs/methodology.md.
CREATE TABLE IF NOT EXISTS signals (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id     BIGINT NOT NULL REFERENCES sources (id),
    signal_type   TEXT NOT NULL CHECK (signal_type IN ('so_tag_count', 'gh_stars', 'gh_contributors', 'gh_issue_velocity')),
    entity        TEXT NOT NULL,  -- vendor slug, or repo as owner/name
    period_start  DATE NOT NULL,
    granularity   TEXT NOT NULL CHECK (granularity IN ('month', 'quarter')),
    metric        TEXT NOT NULL,
    value         DOUBLE PRECISION NOT NULL,
    unit          TEXT NOT NULL,
    fetched_at    TIMESTAMPTZ NOT NULL,
    UNIQUE (source_id, signal_type, entity, period_start, metric)
);

-- Dedupe audit: every document removed as a duplicate before loading, so the duplicate
-- rate can be reported from the database (Actions runners keep no local files).
-- Unique per source item, so re-running an ingestion does not inflate the count.
CREATE TABLE IF NOT EXISTS dedupe_drops (
    id                   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id            BIGINT NOT NULL REFERENCES sources (id),
    dropped_external_id  TEXT NOT NULL,
    kept_key             TEXT NOT NULL,  -- external_id of the kept document, or db:<content_hash>
    reason               TEXT NOT NULL CHECK (reason IN ('exact', 'near')),
    similarity           REAL NOT NULL,
    dropped_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_id, dropped_external_id)
);
