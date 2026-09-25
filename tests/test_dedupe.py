from datetime import datetime, timedelta, timezone

from ingestion import dedupe
from ingestion.normalize import DocumentRow, content_hash

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
LONG = ("we migrated our warehouse from redshift to snowflake last year mostly because concurrency scaling "
        "kept costing more than expected and the ops burden of vacuum and sort keys was eating a full engineer "
        "every sprint so the move paid for itself within two quarters")


def doc(ext, body, days=0, source="hackernews"):
    return DocumentRow(source, ext, f"u/{ext}", None, body, None, T0 + timedelta(days=days), None, None, T0, content_hash(body))


def test_exact_keeps_earliest():
    kept, drops = dedupe.exact([doc("b", "same text", 2), doc("a", "Same  text", 1)])
    assert [d.external_id for d in kept] == ["a"]
    assert drops[0].dropped_external_id == "b" and drops[0].reason == "exact"


def test_exact_keeps_rows_already_in_db_for_refresh():
    d = doc("a", "x")
    kept, drops = dedupe.exact([d], {d.content_hash})
    assert kept == [d] and drops == []


def test_near_duplicate_dropped_and_reported():
    kept, drops = dedupe.near([doc("orig", LONG, 0), doc("repost", LONG + " edit: typo", 1)])
    assert [d.external_id for d in kept] == ["orig"]
    assert drops[0].kept_key == "orig" and drops[0].similarity >= dedupe.NEAR_DUP_THRESHOLD


def test_near_duplicate_of_existing_db_row():
    existing = [("h1", LONG)]
    kept, drops = dedupe.near([doc("new", LONG + " thanks", 0)], existing)
    assert kept == [] and drops[0].kept_key == "db:h1"


def test_short_texts_are_never_near_dups():
    kept, _ = dedupe.near([doc("a", "moved to snowflake, happy"), doc("b", "moved to snowflake, very happy")])
    assert len(kept) == 2


def test_distinct_long_texts_survive():
    other = " ".join(reversed(LONG.split())) + " bigquery slots were the real issue for us"
    kept, drops = dedupe.run([doc("a", LONG), doc("b", other)])
    assert len(kept) == 2 and drops == []
