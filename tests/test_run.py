from ingestion import run


def test_missing_credentials_are_listed(monkeypatch):
    for v in ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "STRATA_GITHUB_TOKEN", "DATABASE_URL"):
        monkeypatch.delenv(v, raising=False)
    assert run.missing_env(["reddit", "github", "hackernews"], use_db=True) == [
        "DATABASE_URL", "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "STRATA_GITHUB_TOKEN"]


def test_placeholder_values_count_as_missing(monkeypatch):
    monkeypatch.setenv("STRATA_GITHUB_TOKEN", "ghp_YOUR_TOKEN_WITH_NO_SCOPES")
    assert run.missing_env(["github"], use_db=False) == ["STRATA_GITHUB_TOKEN"]


def test_sources_without_credentials_need_nothing_extra(monkeypatch):
    assert run.missing_env(["hackernews", "stackexchange", "vendor_docs"], use_db=False) == []
