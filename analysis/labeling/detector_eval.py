"""Precision and recall of the switching detectors against a reviewed sample.

    python -m analysis.labeling.detector_eval --sample seed_v1 --labeled-by claude_review

A document is positive when the reviewer's label gives a reason (taxonomy_code != none) or reports a move
(direction != none). Needs the sample's documents export for the text. The numbers describe this sample only:
seed_v1 was drawn to be 110/150 flagged by the v1 phrase list, and v2 was tuned on it, so neither is a corpus
estimate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from analysis.labeling.build_review import HERE
from ingestion.normalize import has_reason_language, has_switching_language

DETECTORS = {"v1 phrase list (SWITCHING_PHRASES)": has_switching_language,
             "v2 platform + move/reason sentence": has_reason_language}


def evaluate(bodies: dict[int, str], labels: pd.DataFrame) -> pd.DataFrame:
    positive = {int(r.document_id) for r in labels.itertuples() if r.taxonomy_code != "none" or r.direction != "none"}
    rows = []
    for name, f in DETECTORS.items():
        flagged = {i for i, b in bodies.items() if f(b)}
        tp = len(flagged & positive)
        rows.append({"detector": name, "documents": len(bodies), "positives": len(positive), "flagged": len(flagged),
                     "true_positives": tp, "precision": tp / len(flagged) if flagged else float("nan"),
                     "recall": tp / len(positive) if positive else float("nan"),
                     "missed": " ".join(str(i) for i in sorted(positive - flagged))})
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sample", default="seed_v1")
    ap.add_argument("--labeled-by", default="claude_review")
    ap.add_argument("--documents", type=Path)
    args = ap.parse_args()
    docs_path = args.documents or Path("data/processed/labeling") / f"{args.sample}_documents.json"
    bodies = {int(d["id"]): d["body"] for d in json.loads(docs_path.read_text())}
    labels = pd.read_csv(HERE / f"{args.labeled_by}_labels_{args.sample}.csv", keep_default_na=False)
    out = evaluate(bodies, labels)
    print(out.to_string(index=False))
    out.to_csv(HERE / f"detector_eval_{args.sample}.csv", index=False)


if __name__ == "__main__":
    main()
