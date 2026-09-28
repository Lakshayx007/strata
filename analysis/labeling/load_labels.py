"""Load the seed sample's labels into the `labels` table.

    python -m analysis.labeling.load_labels

For every sample with a committed draft_labels_<sample>.csv, loads it as labeled_by='model_draft', and loads
any claude_review_labels_<sample>.csv / human_labels_<sample>.csv under that labeled_by. Re-running replaces a
sample's rows for each labeled_by, so the table always matches the committed files. Every evidence sentence is re-checked against the stored document
body, and the load stops if one is not verbatim.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from analysis.labeling.build_review import HERE, locate

DRAFT = "model_draft"
REVIEWERS = ["claude_review", "human"]  # <labeled_by>_labels_<sample>.csv, written by analysis.labeling.review


def _rows(drafts: pd.DataFrame, labeled_by: str, sample: str) -> list[dict]:
    return [{"document_id": int(r.document_id), "taxonomy_code": r.taxonomy_code, "labeled_by": labeled_by,
             "sample": sample, "from_vendor": r.from_vendor, "to_vendor": r.to_vendor, "direction": r.direction,
             "evidence_span": r.evidence_span} for r in drafts.itertuples()]


def replace_labels(engine, rows: list[dict], labeled_by: str, sample: str) -> int:
    ids = [r["document_id"] for r in rows]
    with engine.begin() as conn:
        bodies = dict(conn.execute(text("SELECT id, body FROM documents WHERE id = ANY(:ids)"), {"ids": ids}).all())
        members = {i for (i,) in conn.execute(text("SELECT document_id FROM sample_members WHERE sample = :s"), {"s": sample})}
        bad = [r["document_id"] for r in rows if r["document_id"] not in members]
        if bad:
            raise SystemExit(f"Labels for documents outside {sample}: {bad}")
        for r in rows:
            locate(bodies[r["document_id"]], r["evidence_span"])  # raises if not verbatim
        conn.execute(text("DELETE FROM labels WHERE sample = :s AND labeled_by = :b"), {"s": sample, "b": labeled_by})
        conn.execute(text("""INSERT INTO labels (document_id, taxonomy_code, labeled_by, sample, from_vendor, to_vendor,
                                                 direction, evidence_span)
                             VALUES (:document_id, :taxonomy_code, :labeled_by, :sample, :from_vendor, :to_vendor,
                                     :direction, :evidence_span)"""), rows)
    return len(rows)


def main() -> None:
    from ingestion.load_to_db import apply_schema, get_engine

    engine = get_engine()
    apply_schema(engine)
    for draft_file in sorted(HERE.glob("draft_labels_*.csv")):
        sample = draft_file.stem.removeprefix("draft_labels_")
        files = {DRAFT: draft_file, **{b: HERE / f"{b}_labels_{sample}.csv" for b in REVIEWERS}}
        for labeled_by, path in files.items():
            if path.exists():
                n = replace_labels(engine, _rows(pd.read_csv(path, keep_default_na=False), labeled_by, sample), labeled_by, sample)
                print(f"Loaded {n} {labeled_by} labels for {sample}")
    with engine.connect() as conn:
        for row in conn.execute(text("""SELECT sample, labeled_by, taxonomy_code, COUNT(*) FROM labels
                                        GROUP BY 1, 2, 3 ORDER BY 1, 2, 4 DESC""")):
            print("  ", *row)


if __name__ == "__main__":
    main()
