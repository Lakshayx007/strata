import pandas as pd

from analysis.report import compute, render

DOCS = pd.DataFrame([
    {"id": 1, "source": "hackernews", "body": "We migrated from Redshift to Snowflake after a bake-off, mostly on cost."},
    {"id": 2, "source": "hackernews", "body": "+1"},
    {"id": 3, "source": "reddit", "body": "Compared BigQuery and Snowflake and Databricks for our team of five."},
    {"id": 4, "source": "reddit", "body": "Our POC on Fabric ran for two weeks."},
])
MENTIONS = pd.DataFrame([
    {"document_id": 1, "vendor": "aws"}, {"document_id": 1, "vendor": "snowflake"},
    {"document_id": 3, "vendor": "google"}, {"document_id": 3, "vendor": "snowflake"}, {"document_id": 3, "vendor": "databricks"},
    {"document_id": 4, "vendor": "microsoft"}, {"document_id": 4, "vendor": "tech:apache_spark"},
])
DROPS = pd.DataFrame([{"source": "hackernews", "reason": "exact"}, {"source": "reddit", "reason": "near"}])
SIGNALS = pd.DataFrame(columns=["signal_type", "entities", "signal_rows", "first_period", "last_period"])


def test_counts():
    r = compute(DOCS, MENTIONS, DROPS, SIGNALS)
    assert r["documents"] == 4 and r["discussion_documents"] == 4
    assert r["switching"] == 2  # "migrated from"/"bake-off" and "POC"; "Compared" is not on the list
    assert r["multi_vendor"] == 2  # tech: entities never make a document multi-vendor
    assert r["duplicate_rate"] == 2 / 6
    pairs = {(p.vendor_a, p.vendor_b): p.documents for p in r["top_pairs"].itertuples()}
    assert pairs[("aws", "snowflake")] == 1 and pairs[("google", "snowflake")] == 1 and len(pairs) == 4


def test_empty_database_renders():
    empty = compute(DOCS.iloc[0:0], MENTIONS.iloc[0:0], DROPS.iloc[0:0], SIGNALS)
    text = render(empty)
    assert "Documents" in text and "(none)" in text


def test_vendor_pages_are_excluded_from_headline():
    docs = pd.concat([DOCS, pd.DataFrame([{"id": 9, "source": "vendor_docs", "body": "Use us instead of the rest."}])])
    r = compute(docs, MENTIONS, DROPS, SIGNALS)
    assert r["documents"] == 5 and r["discussion_documents"] == 4 and r["switching"] == 2
