"""Pool reason counts across labelled seed samples, by category and by source.

    python -m analysis.labeling.pool

For each sample the most-reviewed label set available is used: claude_review if that file exists, otherwise
model_draft. There is no human review in this project, so no set is 'human'. The table says which set each
sample contributed. Sources come from each sample's documents export. Writes pooled_reasons.md next to this file.

The samples over-sample switching and reason-bearing documents (seed_v1 by the v1 phrase list, seed_v2 by
detector v2), so these counts describe the labelled documents, not the corpus.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from analysis.labeling.build_review import HERE

EXPORTS = Path("data/processed/labeling")
PREFERENCE = ["claude_review", "model_draft"]


def load_sample(sample: str, exports: Path = EXPORTS) -> tuple[pd.DataFrame, str]:
    for labeled_by in PREFERENCE:
        path = HERE / (f"draft_labels_{sample}.csv" if labeled_by == "model_draft" else f"{labeled_by}_labels_{sample}.csv")
        if path.exists():
            labels = pd.read_csv(path, keep_default_na=False)
            break
    else:
        raise FileNotFoundError(f"no labels for {sample}")
    docs = json.loads((exports / f"{sample}_documents.json").read_text())
    labels["source"] = labels.document_id.map({int(d["id"]): d["source"] for d in docs})
    if labels.source.isna().any():
        raise SystemExit(f"{sample}: labels for documents missing from the export")
    return labels.assign(sample=sample, labeled_by=labeled_by), labeled_by


def pooled_tables(frames: list[pd.DataFrame]) -> dict[str, pd.DataFrame]:
    df = pd.concat(frames, ignore_index=True)
    reasons = df[df.taxonomy_code != "none"]
    by_source = pd.crosstab(reasons.taxonomy_code, reasons.source, margins=True, margins_name="total")
    by_sample = pd.crosstab(reasons.taxonomy_code, reasons["sample"], margins=True, margins_name="total")
    docs = df.groupby("source").agg(documents=("document_id", "size"),
                                    with_reason=("taxonomy_code", lambda s: int((s != "none").sum())),
                                    with_move=("direction", lambda s: int((s != "none").sum())))
    docs["reason_share"] = docs.with_reason / docs.documents
    return {"by_source": by_source, "by_sample": by_sample, "documents": docs}


def _md(df: pd.DataFrame, pct_cols: tuple[str, ...] = ()) -> str:
    cols = [df.index.name or ""] + [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for idx in df.index:
        vals = [f"{df.at[idx, c]:.0%}" if c in pct_cols else str(int(df.at[idx, c])) for c in df.columns]
        lines.append(f"| {idx} | " + " | ".join(vals) + " |")
    return "\n".join(lines)


def main() -> None:
    samples = sorted(p.stem.removeprefix("draft_labels_") for p in HERE.glob("draft_labels_*.csv"))
    frames, used = [], {}
    for s in samples:
        f, used[s] = load_sample(s)
        frames.append(f)
    t = pooled_tables(frames)
    text = "\n\n".join([
        "Label sets used: " + ", ".join(f"{s} = {b}" for s, b in used.items()) + ". No label in any sample is human.",
        "Documents, reasons and moves by source:", _md(t["documents"], pct_cols=("reason_share",)),
        "Reason categories by source:", _md(t["by_source"]),
        "Reason categories by sample:", _md(t["by_sample"])])
    (HERE / "pooled_reasons.md").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
