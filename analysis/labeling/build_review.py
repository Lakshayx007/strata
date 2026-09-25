"""Build analysis/labeling/seed_review.xlsx, the review workbook for the seed sample.

    python -m analysis.labeling.build_review --documents data/processed/labeling/seed_v1_documents.json

Inputs (committed next to this file):
  taxonomy_draft.csv   the DRAFT categories, each with two quotes and their document IDs
  draft_labels.csv     one model_draft label per sampled document, with its evidence sentence
The documents export (from `python -m analysis.labeling.sample`) supplies the text. It is not committed.

Every quote and evidence sentence is checked to be verbatim text of its document before the workbook is
written; the build fails otherwise, so nothing paraphrased or invented can reach the review file.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from ingestion import config

HERE = Path(__file__).resolve().parent
TAXONOMY_CSV = HERE / "taxonomy_draft.csv"
DRAFT_CSV = HERE / "draft_labels.csv"
OUT = HERE / "seed_review.xlsx"
DIRECTIONS = ["adopt", "leave", "evaluate", "none"]
VENDOR_CHOICES = config.VENDORS + ["other", "none"]
DECISIONS = ["keep", "rename", "merge-into"]
EXCERPT_WORDS = 60


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def locate(body: str, span: str) -> tuple[int, int]:
    """Character span of `span` in the whitespace-normalised body; raises if it is not verbatim."""
    b, s = _norm(body), _norm(span)
    i = b.find(s)
    if not s or i < 0:
        raise ValueError(f"not verbatim in document: {span[:80]!r}")
    return i, i + len(s)


def excerpt(body: str, span: str, n_words: int = EXCERPT_WORDS) -> str:
    """About n_words words of the body, centred on the evidence sentence, which is always kept whole
    unless it alone is longer than n_words."""
    b = _norm(body)
    i, j = locate(body, span)
    before, mid, after = b[:i].split(), b[i:j].split(), b[j:].split()
    if len(mid) >= n_words:
        words, pre, post = mid[:n_words], False, True
    else:
        room = n_words - len(mid)
        take_before = min(len(before), room // 2)
        take_after = min(len(after), room - take_before)
        take_before = min(len(before), room - take_after)
        words = before[len(before) - take_before:] + mid + after[:take_after]
        pre, post = take_before < len(before), take_after < len(after)
    return ("… " if pre else "") + " ".join(words) + (" …" if post else "")


def validate(docs: dict[int, dict], taxonomy: pd.DataFrame, drafts: pd.DataFrame) -> None:
    codes = set(taxonomy.code)
    problems = []
    for t in taxonomy.itertuples():
        for k in (1, 2):
            doc_id, quote = int(getattr(t, f"example_{k}_doc_id")), getattr(t, f"example_{k}_quote")
            try:
                locate(docs[doc_id]["body"], quote)
            except (KeyError, ValueError) as e:
                problems.append(f"taxonomy {t.code} example {k} (doc {doc_id}): {e}")
    missing = set(docs) - set(drafts.document_id)
    extra = set(drafts.document_id) - set(docs)
    if missing or extra:
        problems.append(f"draft labels must cover the sample exactly: missing {sorted(missing)}, extra {sorted(extra)}")
    for r in drafts.itertuples():
        if r.taxonomy_code not in codes:
            problems.append(f"doc {r.document_id}: unknown taxonomy_code {r.taxonomy_code}")
        if r.direction not in DIRECTIONS:
            problems.append(f"doc {r.document_id}: bad direction {r.direction}")
        for v in (r.from_vendor, r.to_vendor):
            if v not in VENDOR_CHOICES:
                problems.append(f"doc {r.document_id}: bad vendor {v}")
        try:
            locate(docs[r.document_id]["body"], r.evidence_span)
        except (KeyError, ValueError) as e:
            problems.append(f"doc {r.document_id} evidence: {e}")
    if problems:
        raise SystemExit("Review file not built:\n  " + "\n  ".join(problems))


HEADER_FILL = PatternFill("solid", fgColor="DDE4EE")
INPUT_FILL = PatternFill("solid", fgColor="FFF7D6")


def _sheet(ws, header: list[str], rows: list[list], widths: dict[str, int], input_cols: list[str]) -> None:
    ws.append(header)
    for r in rows:
        ws.append(r)
    for c, name in enumerate(header, 1):
        cell = ws.cell(row=1, column=c)
        cell.font, cell.fill = Font(bold=True), (INPUT_FILL if name in input_cols else HEADER_FILL)
        ws.column_dimensions[get_column_letter(c)].width = widths.get(name, 14)
        for r in range(2, len(rows) + 2):
            ws.cell(row=r, column=c).alignment = Alignment(wrap_text=True, vertical="top")
            if name in input_cols:
                ws.cell(row=r, column=c).fill = INPUT_FILL
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = ws.dimensions


def _dropdown(ws, header: list[str], col: str, choices_ref: str, n_rows: int) -> None:
    letter = get_column_letter(header.index(col) + 1)
    dv = DataValidation(type="list", formula1=choices_ref, allow_blank=True, showDropDown=False)
    dv.error, dv.errorTitle, dv.showErrorMessage = "Pick a value from the list", "Not in list", True
    ws.add_data_validation(dv)
    dv.add(f"{letter}2:{letter}{n_rows + 1}")


def build(docs: dict[int, dict], taxonomy: pd.DataFrame, drafts: pd.DataFrame, out: Path = OUT) -> Path:
    validate(docs, taxonomy, drafts)
    wb = Workbook()

    # Sheet 1: taxonomy
    ws = wb.active
    ws.title = "taxonomy"
    th = ["code", "name", "definition", "example_1_doc_id", "example_1_quote", "example_2_doc_id", "example_2_quote",
          "draft_count", "status", "my_decision", "my_new_name"]
    counts = drafts.taxonomy_code.value_counts()
    trows = [[t.code, t.name, t.definition, int(t.example_1_doc_id), t.example_1_quote, int(t.example_2_doc_id),
              t.example_2_quote, int(counts.get(t.code, 0)), "DRAFT", None, None] for t in taxonomy.itertuples()]
    _sheet(ws, th, trows, {"code": 14, "name": 22, "definition": 48, "example_1_quote": 60, "example_2_quote": 60,
                           "my_decision": 14, "my_new_name": 22}, ["my_decision", "my_new_name"])

    # Sheet 3 (hidden-ish lists) first, so the dropdowns can reference it.
    lists = wb.create_sheet("lists")
    cols = {"taxonomy_code": list(taxonomy.code), "vendor": VENDOR_CHOICES, "direction": DIRECTIONS, "decision": DECISIONS}
    for c, (name, values) in enumerate(cols.items(), 1):
        lists.cell(row=1, column=c, value=name).font = Font(bold=True)
        for r, v in enumerate(values, 2):
            lists.cell(row=r, column=c, value=v)
    ref = {name: f"lists!${get_column_letter(c)}$2:${get_column_letter(c)}${len(v) + 1}"
           for c, (name, v) in enumerate(cols.items(), 1)}
    _dropdown(ws, th, "my_decision", ref["decision"], len(trows))

    # Sheet 2: labels
    wl = wb.create_sheet("labels", 1)
    lh = ["doc_id", "source", "link", "title", "excerpt", "draft_label", "draft_from", "draft_to", "draft_direction",
          "draft_evidence", "my_label", "my_from", "my_to", "my_direction", "notes"]
    lrows = []
    for r in drafts.sort_values(["document_id"]).itertuples():
        d = docs[r.document_id]
        lrows.append([r.document_id, d["source"], d["url"], d.get("title") or "", excerpt(d["body"], r.evidence_span),
                      r.taxonomy_code, r.from_vendor, r.to_vendor, r.direction, _norm(r.evidence_span),
                      None, None, None, None, None])
    _sheet(wl, lh, lrows, {"doc_id": 9, "source": 13, "link": 30, "title": 28, "excerpt": 70, "draft_evidence": 45,
                           "notes": 30}, ["my_label", "my_from", "my_to", "my_direction", "notes"])
    for i in range(len(lrows)):
        c = wl.cell(row=i + 2, column=lh.index("link") + 1)
        c.hyperlink, c.style = c.value, "Hyperlink"
        c.alignment = Alignment(wrap_text=True, vertical="top")
    _dropdown(wl, lh, "my_label", ref["taxonomy_code"], len(lrows))
    _dropdown(wl, lh, "my_from", ref["vendor"], len(lrows))
    _dropdown(wl, lh, "my_to", ref["vendor"], len(lrows))
    _dropdown(wl, lh, "my_direction", ref["direction"], len(lrows))

    readme = wb.create_sheet("how_to_review", 0)
    for line in [
        "Seed sample review (sample seed_v1, 150 documents). Everything in this file is a DRAFT by the model (labeled_by='model_draft').",
        "",
        "taxonomy sheet: set my_decision to keep, rename or merge-into. For rename, put the new name in my_new_name;",
        "for merge-into, put the code of the category it merges into in my_new_name.",
        "",
        "labels sheet: fill a my_ cell only when you disagree with the draft next to it. A blank my_ cell means the draft stands.",
        "my_label, my_from, my_to and my_direction have dropdowns (Data > Data validation in Sheets if they do not show).",
        "Codes: 'none' = no stated switching reason in the document; 'other' in from/to = a vendor outside the six.",
        "",
        "Excerpts are about 60 words centred on draft_evidence; follow the link for the full text.",
        "Every quote and evidence sentence was checked to be verbatim text of its document before this file was built.",
    ]:
        readme.append([line])
    readme.column_dimensions["A"].width = 120
    wb.active = 1
    wb.save(out)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--documents", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    docs = {int(d["id"]): d for d in json.loads(args.documents.read_text())}
    taxonomy = pd.read_csv(TAXONOMY_CSV)
    drafts = pd.read_csv(DRAFT_CSV, keep_default_na=False)
    print(f"Wrote {build(docs, taxonomy, drafts, args.out)}")


if __name__ == "__main__":
    main()
