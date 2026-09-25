"""Hand-written payloads in each API's documented shape. They are test fixtures, not corpus data."""

from datetime import datetime, timezone

from ingestion import normalize
from ingestion.models import FetchedItem

NOW = datetime(2026, 9, 25, tzinfo=timezone.utc)


def item(source, kind, raw, ext="1"):
    return FetchedItem(source, kind, ext, NOW, "q", raw)


def test_hn_comment_html_is_stripped_and_url_built():
    raw = {"objectID": "42", "comment_text": "<p>We moved off Redshift.<p>Cost &amp; ops.", "author": "a", "created_at_i": 1700000000, "points": None}
    [doc] = normalize.to_documents([item("hackernews", "comment", raw)])
    assert doc.url == "https://news.ycombinator.com/item?id=42"
    assert "<p>" not in doc.body and "Cost & ops." in doc.body
    assert doc.posted_at == datetime.fromtimestamp(1700000000, tz=timezone.utc)


def test_link_only_story_uses_title_as_body():
    raw = {"objectID": "7", "title": "Why we left Snowflake", "story_text": None, "author": "a", "created_at_i": 1, "points": 10, "num_comments": 3}
    [doc] = normalize.to_documents([item("hackernews", "story", raw)])
    assert doc.body == "Why we left Snowflake" and doc.n_comments == 3


def test_reddit_deleted_comment_is_not_a_document():
    raw = {"id": "c1", "body": "[deleted]", "permalink": "https://www.reddit.com/r/x/c1", "author": None, "created_utc": 1.0, "score": 1}
    assert normalize.to_documents([item("reddit", "comment", raw)]) == []


def test_stackexchange_question_maps_fields():
    raw = {"question_id": 9, "link": "https://stackoverflow.com/q/9", "title": "BigQuery &amp; dbt", "body": "<p>How do I...</p>",
           "owner": {"display_name": "dev"}, "creation_date": 1700000000, "score": 2, "answer_count": 1}
    [doc] = normalize.to_documents([item("stackexchange", "question", raw)])
    assert doc.title == "BigQuery & dbt" and doc.body == "How do I..." and doc.n_comments == 1


def test_metric_items_never_become_documents():
    raw = {"vendor": "google", "tag": "google-bigquery", "month": "2026-01-01", "total": 100}
    assert normalize.to_documents([item("stackexchange", "tag_count", raw)]) == []
    [sig] = normalize.to_signals([item("stackexchange", "tag_count", raw)])
    assert (sig.signal_type, sig.entity, sig.metric, sig.value) == ("so_tag_count", "google", "questions:google-bigquery", 100.0)


def test_stars_roll_up_to_months_with_zero_fill():
    raws = [{"repo": "apache/iceberg", "starred_at": t} for t in ("2026-01-05T00:00:00Z", "2026-01-20T00:00:00Z", "2026-03-02T00:00:00Z")]
    sigs = normalize.to_signals([item("github", "repo_stars", r, ext=str(i)) for i, r in enumerate(raws)])
    new = {s.period_start.isoformat(): s.value for s in sigs if s.metric == "new_stars"}
    cum = {s.period_start.isoformat(): s.value for s in sigs if s.metric == "cumulative_stars"}
    assert new == {"2026-01-01": 2, "2026-02-01": 0, "2026-03-01": 1}
    assert cum["2026-03-01"] == 3


def test_issue_velocity_drops_months_before_since():
    raws = [
        {"repo": "r/x", "since": "2026-02-01T00:00:00+00:00", "number": 1, "created_at": "2025-12-01T00:00:00Z", "closed_at": "2026-02-10T00:00:00Z", "state": "closed"},
        {"repo": "r/x", "since": "2026-02-01T00:00:00+00:00", "number": 2, "created_at": "2026-02-03T00:00:00Z", "closed_at": None, "state": "open"},
    ]
    sigs = normalize.to_signals([item("github", "repo_issue", r, ext=str(i)) for i, r in enumerate(raws)])
    got = {(s.metric, s.period_start.isoformat()): s.value for s in sigs}
    assert got == {("issues_opened", "2026-02-01"): 1, ("issues_closed", "2026-02-01"): 1}


def test_content_hash_ignores_case_and_whitespace():
    assert normalize.content_hash("Moved  to\nSnowflake") == normalize.content_hash("moved to snowflake")


def test_author_hash_is_salted_and_source_scoped():
    a = normalize.author_hash("reddit", "bob")
    assert a and a != normalize.author_hash("hackernews", "bob") and "bob" not in a
    assert normalize.author_hash("reddit", None) is None


def test_snowflake_schema_is_not_a_vendor_mention():
    assert normalize.find_mentions("Use a snowflake schema for the dims.") == []
    [m] = normalize.find_mentions("We left Snowflake for BigQuery", None)[:1]
    assert m.vendor == "snowflake" and m.first_char_offset == 8


def test_title_only_mention_has_null_offset():
    ms = {m.vendor: m for m in normalize.find_mentions("body text about costs", "Leaving Databricks")}
    assert ms["databricks"].mention_count == 1 and ms["databricks"].first_char_offset is None


def test_ambiguous_words_do_not_count():
    assert normalize.find_mentions("the fabric of our glue code") == []


def test_ambiguous_terms_need_context():
    cases = {
        "The redshift of distant galaxies": set(),
        "We moved off Redshift to Snowflake": {"aws", "snowflake"},
        "synapse plasticity in cortical neurons": set(),
        "our Synapse dedicated pool keeps timing out": {"microsoft"},
        "the delta between the two runs": set(),
        "we write delta tables from our spark cluster": {"tech:delta_lake", "tech:apache_spark"},
        "this should spark a discussion": set(),
    }
    for text, expected in cases.items():
        assert {m.vendor for m in normalize.find_mentions(text)} == expected, text


def test_rejections_are_reported_with_reason():
    found, rejected = normalize.find_mentions_with_rejections("snowflake schema and the redshift of galaxies")
    assert found == []
    assert {(r.entity, r.reason) for r in rejected} == {("snowflake", "excluded"), ("aws", "no_context")}


def test_unambiguous_phrase_is_not_also_rejected():
    found, rejected = normalize.find_mentions_with_rejections("Azure Synapse and a Fabric lakehouse")
    assert {m.vendor for m in found} == {"microsoft"} and rejected == []


def test_switching_language_uses_word_boundaries():
    assert normalize.has_switching_language("We ran a POC last quarter")
    assert not normalize.has_switching_language("unix epoch in my pocket")


def test_devto_article_maps_markdown_body():
    raw = {"id": 5, "title": "Why we left Redshift", "body_markdown": "We moved off Redshift to BigQuery.", "url": "https://dev.to/a/b",
           "author": "writer", "published_at": "2025-03-01T10:00:00Z", "reactions": 12, "comments_count": 3, "tags": ["redshift"]}
    [doc] = normalize.to_documents([item("devto", "article", raw)])
    assert doc.url == "https://dev.to/a/b" and doc.body.startswith("We moved off") and doc.posted_at.year == 2025


def test_github_title_only_issue_uses_title():
    raw = {"number": 7, "title": "Migrating from Hudi to Iceberg", "body": "", "url": "https://github.com/apache/iceberg/issues/7",
           "author": "dev", "created_at": "2025-01-02T00:00:00Z", "comments": 4, "reactions": 1}
    [doc] = normalize.to_documents([item("github_threads", "issue", raw)])
    assert doc.body == "Migrating from Hudi to Iceberg" and doc.n_comments == 4


def test_nul_bytes_are_removed():
    raw = {"number": 8, "title": "t\x00", "body": "stack trace \x00\x00 here", "url": "https://github.com/a/b/issues/8",
           "author": None, "created_at": "2025-01-02T00:00:00Z", "comments": 0, "reactions": 0}
    [doc] = normalize.to_documents([item("github_threads", "issue", raw)])
    assert "\x00" not in doc.body and "\x00" not in doc.title
