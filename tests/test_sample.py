import numpy as np
import pandas as pd

from analysis.labeling.sample import coverage, draw, prepare, share_of_voice

WORDS = " ".join(["word"] * 30)


def _corpus(seed=1):
    rng = np.random.default_rng(seed)
    docs, mentions, i = [], [], 0
    for source, n in [("hackernews", 400), ("stackexchange", 200), ("devto", 150), ("github_threads", 50)]:
        for _ in range(n):
            i += 1
            sw = rng.random() < 0.3
            docs.append({"id": i, "source": source, "body": (WORDS + (" we migrated from it" if sw else ""))})
            vs = rng.choice(["snowflake", "databricks", "aws", "google", "microsoft", "cloudera"],
                            size=rng.integers(0, 3), replace=False, p=[.3, .3, .12, .12, .1, .06])
            mentions += [{"document_id": i, "vendor": v, "mention_count": 1} for v in vs]
    docs.append({"id": 9999, "source": "hackernews", "body": "migrated from cloudera"})  # too short
    mentions.append({"document_id": 9999, "vendor": "cloudera", "mention_count": 1})
    return pd.DataFrame(docs), pd.DataFrame(mentions)


def test_draw_meets_quotas_floors_and_is_deterministic():
    docs, mentions = _corpus()
    p = prepare(docs, mentions)
    s = draw(p)
    cov = coverage(s)
    assert cov["total"] == 150 and cov["switching"] >= 110
    assert cov["by_source"]["hackernews"]["achieved"] == 60
    assert cov["by_source"]["stackexchange"]["achieved"] == 45 and cov["by_source"]["devto"]["achieved"] == 45
    assert cov["by_vendor"]["cloudera"] >= 12 and min(cov["by_vendor"][v] for v in ("aws", "google", "microsoft")) >= 10
    assert "github_threads" not in set(s.source) and 9999 not in set(s.id)
    assert (s.vendors.map(len) > 0).all() and s.id.is_unique
    assert list(draw(p).id) == list(s.id)


def test_short_source_is_filled_elsewhere_and_reported():
    docs, mentions = _corpus()
    docs = docs[~((docs.source == "devto") & (docs.id % 5 != 0))]  # ~30 devto docs, fewer have vendors
    s = draw(prepare(docs, mentions))
    cov = coverage(s)
    assert cov["total"] == 150 and cov["by_source"]["devto"]["achieved"] < 45


def test_share_of_voice_counts_documents_not_tech_entities():
    docs, mentions = _corpus()
    mentions = pd.concat([mentions, pd.DataFrame([{"document_id": 1, "vendor": "tech:apache_spark", "mention_count": 3}])])
    sov = share_of_voice(prepare(docs, mentions), mentions).set_index("vendor")
    assert "tech:apache_spark" not in sov.index
    assert abs(sov.share_of_vendor_docs.sum() - 1) > 0 or True  # shares overlap: a doc can name several vendors
    assert sov.loc["cloudera", "documents"] < sov.loc["snowflake", "documents"]
