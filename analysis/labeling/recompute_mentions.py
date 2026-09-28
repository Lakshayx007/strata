"""Rebuild the mentions table after a matcher change and report what moved.

    python -m analysis.labeling.recompute_mentions

Prints, per vendor and source, the documents that gained or lost the vendor, and up to AUDIT_ROWS removed
"snowflake" documents with the matcher's rejection snippet, so the change can be audited from the run log.
Writes data/processed/labeling/mention_changes.csv (document_id, source, vendor, change).
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from analysis.labeling.sample import EXPORT_DIR
from ingestion.normalize import find_mentions_with_rejections

AUDIT_ROWS = 40


def _pairs(engine) -> pd.DataFrame:
    return pd.read_sql(text("""SELECT m.document_id, s.name AS source, m.vendor FROM mentions m
                               JOIN documents d ON d.id = m.document_id JOIN sources s ON s.id = d.source_id"""), engine)


def diff(before: pd.DataFrame, after: pd.DataFrame) -> pd.DataFrame:
    keys = ["document_id", "source", "vendor"]
    m = before[keys].merge(after[keys], how="outer", indicator=True)
    m = m[m._merge != "both"].copy()
    m["change"] = m._merge.map({"left_only": "removed", "right_only": "added"}).astype(str)
    return m.drop(columns="_merge").sort_values(keys).reset_index(drop=True)


def main() -> None:
    from ingestion.load_to_db import get_engine, recompute_all_mentions

    engine = get_engine()
    before = _pairs(engine)
    n = recompute_all_mentions(engine)
    after = _pairs(engine)
    changes = diff(before, after)
    print(f"Rebuilt {n:,} mention rows; {len(changes):,} document-vendor pairs changed.\n")
    if len(changes):
        print(changes.groupby(["vendor", "source", "change"]).size().unstack(fill_value=0).to_string(), "\n")
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    changes.to_csv(EXPORT_DIR / "mention_changes.csv", index=False)

    removed = changes[(changes.vendor == "snowflake") & (changes.change == "removed")].document_id.tolist()
    if removed:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT id, title, body FROM documents WHERE id = ANY(:ids) ORDER BY id"),
                                {"ids": removed[:AUDIT_ROWS]}).all()
        print(f"Audit: first {len(rows)} of {len(removed)} documents that lost 'snowflake' (matcher's snippet):")
        for i, title, body in rows:
            snips = [r for r in find_mentions_with_rejections(body, title)[1] if r.entity == "snowflake"]
            print(f"  {i} [{snips[0].reason if snips else '-'}] {snips[0].snippet[:160] if snips else ''}")


if __name__ == "__main__":
    main()
