"""Read a returned review workbook and measure agreement with the model draft.

    python -m analysis.labeling.review --sample seed_v1 --workbook analysis/labeling/seed_review_claude_review.xlsx \
        --labeled-by claude_review

Writes `<labeled_by>_labels_<sample>.csv` (one final row per document) and `agreement_<sample>.md`.

A blank reviewer cell means the draft value stands. Taxonomy decisions on the workbook's taxonomy sheet
(merge-into / rename) are applied to both the draft and the reviewer's codes before comparing, so a merge is
never counted as a disagreement.

Who filled the reviewer columns is recorded in `labeled_by`: 'human' only when a person did the review.
The seed_v1 review was done by a second Claude session reading excerpts, so it is 'claude_review', and every
agreement number here is model-vs-model, not model-vs-human.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from sklearn.metrics import cohen_kappa_score

HERE = Path(__file__).resolve().parent
FIELDS = {"taxonomy_code": ("draft_label", "my_label"), "from_vendor": ("draft_from", "my_from"),
          "to_vendor": ("draft_to", "my_to"), "direction": ("draft_direction", "my_direction")}


def _sheet(wb, name: str) -> pd.DataFrame:
    rows = list(wb[name].iter_rows(values_only=True))
    return pd.DataFrame(rows[1:], columns=rows[0])


def _blank(v) -> bool:
    return v is None or (isinstance(v, float) and pd.isna(v)) or (isinstance(v, str) and not v.strip())


def code_map(taxonomy_sheet: pd.DataFrame) -> dict[str, str]:
    """Old code -> new code from the taxonomy sheet's merge-into / rename decisions."""
    out = {}
    for r in taxonomy_sheet.itertuples():
        decision = "" if _blank(r.my_decision) else str(r.my_decision).strip().lower()
        if decision in ("merge-into", "rename") and not _blank(r.my_new_name):
            out[r.code] = str(r.my_new_name).strip()
    return out


def final_labels(labels_sheet: pd.DataFrame, codes: dict[str, str]) -> pd.DataFrame:
    """One row per document with the draft and the reviewer's final value for each field."""
    rows = []
    for r in labels_sheet.to_dict(orient="records"):
        row = {"document_id": int(r["doc_id"]), "notes": "" if _blank(r.get("notes")) else str(r["notes"]).strip(),
               "evidence_span": r["draft_evidence"]}
        for field, (draft_col, my_col) in FIELDS.items():
            draft = str(r[draft_col]).strip()
            final = draft if _blank(r[my_col]) else str(r[my_col]).strip()
            if field == "taxonomy_code":
                draft, final = codes.get(draft, draft), codes.get(final, final)
            row[f"draft_{field}"], row[field] = draft, final
        rows.append(row)
    return pd.DataFrame(rows).sort_values("document_id").reset_index(drop=True)


def _agree(a: pd.Series, b: pd.Series) -> dict:
    n = len(a)
    pct = float((a.values == b.values).mean()) if n else float("nan")
    # Kappa is undefined when either rater used a single category (e.g. every draft is 'none').
    kappa = float(cohen_kappa_score(a, b)) if n and a.nunique() > 1 and b.nunique() > 1 else float("nan")
    return {"n": n, "agree": int((a.values == b.values).sum()), "pct": pct, "kappa": kappa}


def agreement(final: pd.DataFrame) -> dict:
    subsets = {"all rows": final,
               "draft = none": final[final.draft_taxonomy_code == "none"],
               "draft = a reason": final[final.draft_taxonomy_code != "none"]}
    out = {name: {f: _agree(df[f"draft_{f}"], df[f]) for f in FIELDS} for name, df in subsets.items()}
    out["confusion"] = pd.crosstab(final.draft_taxonomy_code, final.taxonomy_code,
                                   rownames=["model_draft"], colnames=["reviewer"])
    per_cat = []
    for code, g in final.groupby("draft_taxonomy_code"):
        rev = final[final.taxonomy_code == code]
        per_cat.append({"category": code, "draft_rows": len(g), "kept_by_reviewer": int((g.taxonomy_code == code).sum()),
                        "reviewer_rows": len(rev), "draft_share_kept": (g.taxonomy_code == code).mean()})
    out["per_category"] = pd.DataFrame(per_cat).sort_values("draft_rows", ascending=False)
    return out


def _fmt(x: float, pct: bool = False) -> str:
    if pd.isna(x):
        return "n/a"
    return f"{x:.1%}" if pct else f"{x:.2f}"


def render(sample: str, labeled_by: str, a: dict) -> str:
    lines = [f"### {sample}: model_draft vs {labeled_by} (model-vs-model agreement)", "",
             "| Rows | Field | n | Agree | % agree | Cohen's kappa |", "|---|---|---|---|---|---|"]
    for name in ("all rows", "draft = none", "draft = a reason"):
        for f, v in a[name].items():
            lines.append(f"| {name} | {f} | {v['n']} | {v['agree']} | {_fmt(v['pct'], True)} | {_fmt(v['kappa'])} |")
    lines += ["", "Kappa is n/a where one rater used a single value in that subset (every draft row in "
              "'draft = none' is none, so kappa cannot be computed there).", "",
              "Per draft category (taxonomy_code):", "",
              "| Category | Draft rows | Kept by reviewer | % kept | Reviewer rows |", "|---|---|---|---|---|"]
    for r in a["per_category"].itertuples():
        lines.append(f"| {r.category} | {r.draft_rows} | {r.kept_by_reviewer} | {_fmt(r.draft_share_kept, True)} | {r.reviewer_rows} |")
    conf = a["confusion"]
    lines += ["", "Confusion table (rows: model_draft, columns: reviewer):", "",
              "| model_draft \\ reviewer | " + " | ".join(conf.columns) + " |",
              "|---|" + "---|" * len(conf.columns)]
    for idx, r in conf.iterrows():
        lines.append(f"| {idx} | " + " | ".join(str(int(v)) for v in r.values) + " |")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sample", required=True)
    ap.add_argument("--workbook", type=Path, required=True)
    ap.add_argument("--labeled-by", required=True, choices=["human", "claude_review"])
    args = ap.parse_args()
    wb = load_workbook(args.workbook, read_only=True)
    codes = code_map(_sheet(wb, "taxonomy"))
    final = final_labels(_sheet(wb, "labels"), codes)
    cols = ["document_id", "taxonomy_code", "from_vendor", "to_vendor", "direction", "evidence_span", "notes"]
    final[cols].to_csv(HERE / f"{args.labeled_by}_labels_{args.sample}.csv", index=False)
    text = render(args.sample, args.labeled_by, agreement(final))
    (HERE / f"agreement_{args.sample}.md").write_text(text + "\n")
    print(f"taxonomy decisions applied: {codes}\n")
    print(text)


if __name__ == "__main__":
    main()
