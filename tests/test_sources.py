"""Adapter logic exercised with fake clients returning each API's documented shape (fixtures, not data)."""

from datetime import datetime, timezone

from ingestion import config
from ingestion.sources import devto

SINCE = datetime(2024, 1, 1, tzinfo=timezone.utc)


class FakeDevto:
    def __init__(self):
        self.article_calls = 0

    def get_json(self, url, params=None):
        if url.endswith("/articles"):
            if params["page"] > 1:
                return []
            return [
                {"id": 1, "title": "Snowflake vs BigQuery", "description": "", "tag_list": ["dataengineering"], "published_at": "2025-01-01T00:00:00Z"},
                {"id": 2, "title": "My dbt tips", "description": "", "tag_list": ["dataengineering"], "published_at": "2025-01-01T00:00:00Z"},
                {"id": 3, "title": "Old lakehouse post", "description": "", "tag_list": ["lakehouse"], "published_at": "2020-01-01T00:00:00Z"},
            ]
        self.article_calls += 1
        aid = int(url.rsplit("/", 1)[1])
        return {"id": aid, "title": "t", "body_markdown": "body", "url": f"https://dev.to/x/{aid}", "user": {"username": "u"},
                "published_at": "2025-01-01T00:00:00Z", "tags": ["dataengineering"]}

    def close(self):
        pass


def test_devto_broad_tag_prefilters_and_respects_since():
    devto._SEEN.clear()
    fake = FakeDevto()
    items = devto.fetch("dataengineering", SINCE, 100, client=fake)
    assert [i.external_id for i in items] == ["1"]  # unrelated post skipped, pre-`since` post dropped
    assert fake.article_calls == 1


def test_devto_does_not_refetch_an_article_seen_under_another_tag():
    devto._SEEN.clear()
    fake = FakeDevto()
    devto.fetch("snowflake", SINCE, 100, client=fake)
    devto.fetch("bigquery", SINCE, 100, client=fake)
    assert fake.article_calls == 2  # ids 1 and 2 once each (vendor tags are not pre-filtered)


def test_reddit_is_excluded_and_not_in_all_sources():
    from ingestion import run

    assert "reddit" in config.EXCLUDED_SOURCES and "reddit" not in run.ALL_SOURCES
    assert config.SOURCE_REGISTRY["reddit"]["terms_note"].startswith("excluded: API access requires approval")
