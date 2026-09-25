"""Load the seed sample's labels into the `labels` table.

    python -m analysis.labeling.load_labels

Loads draft_labels.csv as labeled_by='model_draft'. Re-running replaces that sample's draft rows, so the
table always matches the committed file. Every evidence sentence is re-checked against the stored document
body, and the load stops if one is not verbatim.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from analysis.labeling.build_review import DRAFT_CSV, locate
from analysis.labeling.sample import SAMPLE

DRAFT = "model_draft"


def _rows(drafts: pd.DataFrame, labeled_by: str) -> list[dict]:
    return [{"document_id": int(r.document_id), "taxonomy_code": r.taxonomy_code, "labeled_by": labeled_by,
             "sample": SAMPLE, "from_vendor": r.from_vendor, "to_vendor": r.to_vendor, "direction": r.direction,
             "evidence_span": r.evidence_span} for r in drafts.itertuples()]


def replace_labels(engine, rows: list[dict], labeled_by: str) -> int:
    ids = [r["document_id"] for r in rows]
    with engine.begin() as conn:
        bodies = dict(conn.execute(text("SELECT id, body FROM documents WHERE id = ANY(:ids)"), {"ids": ids}).all())
        members = {i for (i,) in conn.execute(text("SELECT document_id FROM sample_members WHERE sample = :s"), {"s": SAMPLE})}
        bad = [r["document_id"] for r in rows if r["document_id"] not in members]
        if bad:
            raise SystemExit(f"Labels for documents outside {SAMPLE}: {bad}")
        for r in rows:
            locate(bodies[r["document_id"]], r["evidence_span"])  # raises if not verbatim
        conn.execute(text("DELETE FROM labels WHERE sample = :s AND labeled_by = :b"), {"s": SAMPLE, "b": labeled_by})
        conn.execute(text("""INSERT INTO labels (document_id, taxonomy_code, labeled_by, sample, from_vendor, to_vendor,
                                                 direction, evidence_span)
                             VALUES (:document_id, :taxonomy_code, :labeled_by, :sample, :from_vendor, :to_vendor,
                                     :direction, :evidence_span)"""), rows)
    return len(rows)


def main() -> None:
    from ingestion.load_to_db import apply_schema, get_engine

    engine = get_engine()
    apply_schema(engine)
    drafts = pd.read_csv(DRAFT_CSV, keep_default_na=False)
    n = replace_labels(engine, _rows(drafts, DRAFT), DRAFT)
    print(f"Loaded {n} {DRAFT} labels for {SAMPLE}")
    with engine.connect() as conn:
        for row in conn.execute(text("""SELECT labeled_by, taxonomy_code, COUNT(*) FROM labels WHERE sample = :s
                                        GROUP BY 1, 2 ORDER BY 1, 3 DESC"""), {"s": SAMPLE}):
            print("  ", *row)


if __name__ == "__main__":
    main()
