"""Central configuration for Strata ingestion.

Search terms, vendor aliases and source settings live here so that the corpus
definition is one reviewable file. If the analysis is challenged ("why did you
miss X?"), this is the file that answers it, so adapters must never hardcode
their own terms.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
STATE_DIR = PROJECT_ROOT / "data" / "state"

# --- Identity -------------------------------------------------------------
# One User-Agent for every request (HTTP and praw) so site operators see a single,
# consistent identity with a URL that explains the project.
USER_AGENT = "strata-research/0.1 (+https://github.com/Lakshayx007/strata; portfolio research project)"

DATABASE_URL = os.getenv("DATABASE_URL", "")
AUTHOR_HASH_SALT = os.getenv("AUTHOR_HASH_SALT", "")

DEFAULT_SINCE = datetime.fromisoformat(os.getenv("STRATA_SINCE", "2023-01-01")).replace(tzinfo=timezone.utc)
DEFAULT_LIMIT = int(os.getenv("STRATA_LIMIT_PER_QUERY", "500"))

# --- Vendors --------------------------------------------------------------
# Canonical vendor key -> base search queries (recall) used by the APIs.
VENDOR_QUERIES: dict[str, list[str]] = {
    "databricks": ["databricks"],
    "snowflake": ["snowflake"],
    "cloudera": ["cloudera"],
    "aws": ["redshift", "aws glue"],
    "microsoft": ["microsoft fabric", "synapse"],
    "google": ["bigquery"],
}

VENDORS: list[str] = list(VENDOR_QUERIES)

# --- Mention matching -------------------------------------------------------
# Three tiers, applied by normalize.find_mentions:
#   1. MENTION_ALIASES: unambiguous phrases, always counted.
#   2. AMBIGUOUS_TERMS: a bare word that is also ordinary English or another field's
#      jargon. Counted only when a context pattern appears within `window` characters;
#      otherwise rejected, and the rejection is counted so precision can be audited.
#   3. EXCLUDED_PATTERNS: never counted; matches are logged as rejections.
# Keys starting "tech:" are open-source technologies, not vendors. They are counted so
# the corpus can be explored, but are never attributed to a vendor (Delta Lake is not
# Databricks, Spark is not Databricks) and are excluded from vendor charts.
MENTION_ALIASES: dict[str, list[str]] = {
    "databricks": [r"\bdatabricks\b", r"\bunity catalog\b"],
    "snowflake": [r"\bsnowflake\b(?!\s+schemas?\b)", r"\bsnowpark\b", r"\bsnowpipe\b"],
    "cloudera": [r"\bcloudera\b", r"\bhortonworks\b"],
    "aws": [r"\b(?:amazon|aws) redshift\b", r"\bredshift (?:serverless|spectrum)\b", r"\baws glue\b",
            r"\bglue (?:catalog|jobs?|etl|crawlers?|data catalog)\b"],
    "microsoft": [r"\bmicrosoft fabric\b", r"\bms fabric\b", r"\bfabric (?:lakehouse|warehouse|capacity|notebooks?)\b",
                  r"\bonelake\b", r"\bazure synapse\b", r"\bsynapse analytics\b"],
    "google": [r"\bbigquery\b", r"\bbig query\b"],
    "tech:delta_lake": [r"\bdelta lake\b", r"\bdelta(?:-io| tables?| format| live tables| sharing)\b"],
    "tech:apache_spark": [r"\bapache spark\b", r"\bpyspark\b", r"\bspark ?sql\b", r"\bspark (?:streaming|structured streaming)\b"],
}

AMBIGUOUS_TERMS: list[dict] = [
    {   # Astronomy: "the redshift of distant galaxies"; also a GPU renderer.
        "entity": "aws", "term": r"\bredshift\b", "window": 200,
        "context": [r"\baws\b", r"\bamazon\b", r"warehouse", r"\bclusters?\b", r"\bsql\b", r"\bquer(?:y|ies)\b",
                    r"\betl\b", r"\bs3\b", r"snowflake", r"bigquery", r"databricks", r"\bdbt\b"],
    },
    {   # Neuroscience: synapses between neurons.
        "entity": "microsoft", "term": r"\bsynapse\b", "window": 200,
        "context": [r"\bazure\b", r"microsoft", r"\bfabric\b", r"\bsql pools?\b", r"\bspark pools?\b", r"dedicated pool",
                    r"serverless", r"warehouse", r"pipelines?", r"power ?bi", r"data factory", r"databricks", r"snowflake"],
    },
    {   # Generic change or difference: "the delta between runs", "delta load".
        "entity": "tech:delta_lake", "term": r"\bdelta\b", "window": 120,
        "context": [r"\blake(?:house)?\b", r"iceberg", r"\bhudi\b", r"parquet", r"table format", r"databricks",
                    r"\bspark\b", r"time travel", r"\bmerge into\b", r"unity catalog"],
    },
    {   # Generic verb/noun: "spark a debate", "spark joy".
        "entity": "tech:apache_spark", "term": r"\bspark\b", "window": 120,
        "context": [r"\bclusters?\b", r"executors?", r"dataframes?", r"\bjobs?\b", r"hadoop", r"\bemr\b", r"\bscala\b",
                    r"\brdds?\b", r"databricks", r"\bhive\b", r"\bkafka\b", r"shuffle", r"\bdriver\b",
                    r"parquet", r"iceberg", r"\bdelta (?:lake|tables?)\b"],
    },
]

EXCLUDED_PATTERNS: list[dict] = [
    # Kimball dimensional-modelling term, not the vendor.
    {"entity": "snowflake", "pattern": r"\bsnowflake\s+schemas?\b"},
    # Ordinary English ("the fabric of", "fabric softener") unless a product phrase above matched.
    {"entity": "microsoft", "pattern": r"\bfabric\b"},
    # Ordinary English and "glue code" unless an AWS Glue phrase above matched.
    {"entity": "aws", "pattern": r"\bglue\b"},
]

# --- Switching language ---------------------------------------------------
# SWITCHING_PHRASES defines "contains switching language" for the corpus report and for
# Phase 2 stratification. It is Lakshay's list, matched case-insensitively on word
# boundaries against the document body. Change it only deliberately: every switching
# count Strata reports depends on it.
SWITCHING_PHRASES: list[str] = [
    "migrated from", "moved off", "switched to", "moving from", "instead of",
    "evaluated", "bake-off", "bakeoff", "POC", "proof of concept", "ripped out",
    "replaced with", "consolidated onto",
]

# Phrases combined with vendor queries at search time to over-sample switching discussion.
# A superset of SWITCHING_PHRASES (recall at collection time is cheap; the report uses the
# stricter list above).
SWITCHING_SEARCH_PHRASES: list[str] = list(dict.fromkeys(SWITCHING_PHRASES + [
    "migrating from", "migration from", "moving off", "moved away from", "switching to",
    "switched from", "evaluating", "cost blowup", "bill shock", "replaced", "ditched",
]))


def search_queries() -> list[tuple[str, str]]:
    """(vendor, query) pairs: every base query alone, then each paired with each switching phrase.

    The bare queries give a recall baseline; the combined ones over-sample switching
    discussion, which is otherwise a small fraction of vendor chatter.
    """
    pairs: list[tuple[str, str]] = []
    for vendor, queries in VENDOR_QUERIES.items():
        for q in queries:
            pairs.append((vendor, q))
            pairs.extend((vendor, f'{q} "{p}"') for p in SWITCHING_SEARCH_PHRASES)
    return pairs


# --- Required environment -------------------------------------------------
# run.py checks these before any fetch and exits with the list of what is missing,
# so a source is never silently skipped for want of a credential.
REQUIRED_ENV_ALWAYS = ["AUTHOR_HASH_SALT"]
REQUIRED_ENV_DB = ["DATABASE_URL"]
REQUIRED_ENV_BY_SOURCE: dict[str, list[str]] = {
    "reddit": ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET"],
    "hackernews": [],
    "stackexchange": [],  # STACKEXCHANGE_KEY is optional
    "github": ["STRATA_GITHUB_TOKEN"],
    "vendor_docs": [],
}

# --- Reddit ---------------------------------------------------------------
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_SUBREDDITS = ["dataengineering", "databricks", "snowflake", "BusinessIntelligence", "analytics", "dataisbeautiful"]
# replace_more expands "load more comments" stubs; each expansion is an API call.
REDDIT_REPLACE_MORE_LIMIT = int(os.getenv("REDDIT_REPLACE_MORE_LIMIT", "8"))

# --- Hacker News (Algolia) ------------------------------------------------
HN_BASE_URL = "https://hn.algolia.com/api/v1"
HN_MIN_INTERVAL_S = 0.5  # Algolia allows 10k req/hour/IP; we stay far below.

# --- Stack Exchange -------------------------------------------------------
SE_BASE_URL = "https://api.stackexchange.com/2.3"
SE_SITE = "stackoverflow"
SE_KEY = os.getenv("STACKEXCHANGE_KEY", "")
# Unkeyed quota is 300/day per IP; the spec caps us under it with a margin.
SE_DAILY_BUDGET = int(os.getenv("SE_DAILY_BUDGET", "290"))
SE_TAGS: dict[str, list[str]] = {
    "databricks": ["databricks"],
    "snowflake": ["snowflake-cloud-data-platform"],
    "cloudera": ["cloudera"],
    "aws": ["amazon-redshift", "aws-glue"],
    "microsoft": ["microsoft-fabric", "azure-synapse"],
    "google": ["google-bigquery"],
}
SE_TAG_COUNT_MONTHS = int(os.getenv("SE_TAG_COUNT_MONTHS", "24"))

# --- GitHub ---------------------------------------------------------------
GITHUB_TOKEN = os.getenv("STRATA_GITHUB_TOKEN", "")
GITHUB_API = "https://api.github.com"
GITHUB_REPOS = ["apache/iceberg", "delta-io/delta", "apache/hudi", "apache/polaris"]

# --- Vendor docs ----------------------------------------------------------
# Public pricing/docs pages. Each is robots-checked before every fetch.
VENDOR_DOC_URLS: dict[str, list[str]] = {
    "databricks": ["https://www.databricks.com/product/pricing", "https://www.databricks.com/product/pricing/databricks-sql"],
    "snowflake": ["https://www.snowflake.com/en/pricing-options/", "https://docs.snowflake.com/en/user-guide/cost-understanding-overall"],
    "cloudera": ["https://www.cloudera.com/products/pricing.html"],
    "aws": ["https://aws.amazon.com/redshift/pricing/", "https://aws.amazon.com/glue/pricing/"],
    "microsoft": [
        "https://azure.microsoft.com/en-us/pricing/details/microsoft-fabric/",
        "https://azure.microsoft.com/en-us/pricing/details/synapse-analytics/",
    ],
    "google": ["https://cloud.google.com/bigquery/pricing"],
}
DOCS_MIN_INTERVAL_S = 3.0
DOCS_USE_PLAYWRIGHT = os.getenv("DOCS_USE_PLAYWRIGHT", "0") == "1"

# --- What each source's terms permit (written to sources.terms_note) ------
SOURCE_REGISTRY: dict[str, dict[str, str]] = {
    "reddit": {
        "kind": "api",
        "base_url": "https://oauth.reddit.com",
        "terms_note": "Reddit Data API via app-only read-only OAuth (praw, no user login). Data API Terms permit non-commercial research use; "
        "commercial use needs a separate agreement. 100 QPM per OAuth client. No bulk redistribution of content.",
    },
    "hackernews": {
        "kind": "api",
        "base_url": HN_BASE_URL,
        "terms_note": "HN Search API by Algolia, public and unauthenticated. Documented limit 10,000 requests/hour/IP. "
        "Content remains authors'; store for analysis with links back.",
    },
    "stackexchange": {
        "kind": "api",
        "base_url": SE_BASE_URL,
        "terms_note": "Stack Exchange API v2.3. 300 requests/day unkeyed (10k with key); must honour 'backoff'. "
        "Content CC BY-SA; attribution via question URL required.",
    },
    "github": {
        "kind": "api",
        "base_url": GITHUB_API,
        "terms_note": "GitHub REST API with a classic token with no scopes (public data only), 5,000 requests/hour. Public repository metadata only; "
        "GitHub Acceptable Use permits research use of public data via the API.",
    },
    "vendor_docs": {
        "kind": "docs",
        "base_url": "multiple vendor sites",
        "terms_note": "Public pricing/docs pages; robots.txt checked and honoured before each fetch. One request per "
        f"{DOCS_MIN_INTERVAL_S:.0f}s per host. Vendor ToS reviewed per site before adding a URL.",
    },
}
