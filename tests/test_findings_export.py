import pandas as pd

from analysis.export.findings import promotional_sensitivity, reason_tables


def _rev():
    return pd.DataFrame({
        "document_id": [1, 2, 3, 4, 5],
        "sample": ["seed_v1", "seed_v1", "seed_v2", "seed_v2", "seed_v2"],
        "source": ["hackernews", "devto", "hackernews", "stackexchange", "devto"],
        "taxonomy_code": ["cost", "cost", "right_sizing", "none", "lock_in_openness"],
        "direction": ["adopt", "none", "none", "evaluate", "none"],
    })


def test_reason_tables_counts_by_category_source_and_sample():
    t = reason_tables(_rev())
    assert t["documents_labelled"] == 5 and t["reasons_total"] == 4
    cost = t["by_category"][0]
    assert cost["category"] == "cost" and cost["reasons"] == 2
    assert cost["by_source"] == {"devto": 1, "hackernews": 1, "stackexchange": 0}
    assert cost["by_sample"] == {"seed_v1": 2, "seed_v2": 0}
    se = next(r for r in t["by_source"] if r["source"] == "stackexchange")
    assert se == {"source": "stackexchange", "documents": 1, "with_reason": 0, "with_move": 1, "reason_share": 0.0}


def test_promotional_sensitivity_drops_flagged_documents():
    s = promotional_sensitivity(_rev(), [2, 4])
    assert s["reasons_with"] == 4 and s["reasons_without"] == 3
    assert s["flagged_with_reason"] == 1
    assert {"category": "cost", "with": 2, "without": 1} in s["by_category"]
