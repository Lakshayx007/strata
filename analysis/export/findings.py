"""Export the frozen Phase 2 findings as one JSON file for the frontend.

    python -m analysis.export.findings            # reads the database; writes analysis/export/findings.json

Every number comes from the database (documents, mentions, labels) or from a committed audit file
(claude_review_labels_seed_v2.csv for the promotional notes, probe_deployment_control_audit.csv). Nothing is typed
in by hand except the choice of which quotes to show, and each quote is checked to be verbatim in its stored
document. The label counts use labeled_by='claude_review' (a second Claude pass; there is no human review in this
project) and must match the committed claude_review_labels_<sample>.csv files, or the export stops.
The schema is documented in docs/data_contract.md.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sklearn.metrics import cohen_kappa_score

from analysis.labeling.build_review import HERE as LABELING, locate
from analysis.labeling.sample import DISCUSSION_SOURCES, prepare, share_of_voice
from ingestion import config

SCHEMA_VERSION = 1
OUT = Path(__file__).resolve().parent / "findings.json"
SAMPLES = ["seed_v1", "seed_v2"]
LABEL_SET = "claude_review"

# Quotes shown in findings.md and the frontend. Chosen by reading the claude_review reason rows; at least one per
# top category. The text must appear verbatim in the stored document (checked below).
QUOTES = [
    (1611, "cost", "We switched to Snowflake, saved money, got better performance, and had a simpler setup."),
    (274, "cost", "The quickest way to 10x your costs is to move a Vertica workload to Snowflake (last I heard my old job is now up to 40x)."),
    (649, "operational_simplicity", "Trying to just run a simple Spark query using an S3 Table Bucket was enough to remind me why Snowflake and Databricks are printing money by making it a more user friendly experience."),
    (11002, "lock_in_openness", "Snowflake's optimizations lived inside a proprietary storage layout nothing else could read."),
    (1272, "performance_scale", "But at the larger org, we started having performance issues. We migrated from Redshift to Snowflake"),
    (1268, "right_sizing", "In fact, I just advised someone recently to simply use Postgres instead of BigQuery since they had <1TB and their queries weren't super intensive."),
    (1750, "governance_security", "The best thing I've built in a long time is replacing a complex (and scary) permissions system built on top of Snowflake with single role duckdb databases"),
    (10963, "ecosystem_fit", "Fabric wins on Microsoft-shop fit because the identity, licensing, and Power BI story compound"),
]

# Cloudera cases recorded in docs/methodology.md, quoted in the authors' words only.
CLOUDERA_CASES = [
    (7279, "stranded_on_free_edition", [
        "We are running a mini DWH platform with Cloudera Enterprise community version.",
        "not able to find any upgraded version of Cloudera Enterprise which supports RHEL 8",
        "We want to stay on Community edition of Cloudera.",
    ]),
    (220, "exit_to_open_source", [
        "I know a company who had 2PBs+ of data in Cloudera. But instead of moving to the cloud (and Databricks), they saved 5X costs by building their own analytics platform with Iceberg, Trino and Superset.",
    ]),
    (2153, "legacy_reference", [
        "old and expensive cloudera clusters",
    ]),
]


def _iso(ts) -> str | None:
    return None if pd.isna(ts) else pd.Timestamp(ts).isoformat()


def check_labels_match_files(labels: pd.DataFrame, label_dir: Path = LABELING) -> None:
    """The database must hold exactly the committed claude_review files."""
    for s in SAMPLES:
        f = pd.read_csv(label_dir / f"{LABEL_SET}_labels_{s}.csv", keep_default_na=False)
        db = labels[(labels["sample"] == s) & (labels.labeled_by == LABEL_SET)]
        a = f.set_index("document_id").taxonomy_code.sort_index()
        b = db.set_index("document_id").taxonomy_code.sort_index()
        if len(a) != len(b) or not a.equals(b):
            raise SystemExit(f"{s}: database {LABEL_SET} labels differ from {LABEL_SET}_labels_{s}.csv; run load_labels")


def reason_tables(rev: pd.DataFrame) -> dict:
    reasons = rev[rev.taxonomy_code != "none"]
    cats = reasons.taxonomy_code.value_counts()
    by_cat = [{
        "category": c, "reasons": int(n),
        "by_source": {s: int(((reasons.taxonomy_code == c) & (reasons.source == s)).sum()) for s in sorted(rev.source.unique())},
        "by_sample": {s: int(((reasons.taxonomy_code == c) & (reasons["sample"] == s)).sum()) for s in SAMPLES},
    } for c, n in sorted(cats.items(), key=lambda kv: (-kv[1], kv[0]))]
    by_src = [{
        "source": s, "documents": int((rev.source == s).sum()),
        "with_reason": int(((rev.source == s) & (rev.taxonomy_code != "none")).sum()),
        "with_move": int(((rev.source == s) & (rev.direction != "none")).sum()),
    } for s in sorted(rev.source.unique())]
    for r in by_src:
        r["reason_share"] = round(r["with_reason"] / r["documents"], 4) if r["documents"] else None
    return {"documents_labelled": int(len(rev)), "reasons_total": int(len(reasons)),
            "by_category": by_cat, "by_source": by_src}


def promotional_sensitivity(rev: pd.DataFrame, flagged: list[int]) -> dict:
    kept = rev[~rev.document_id.isin(flagged)]
    with_ = rev[rev.taxonomy_code != "none"].taxonomy_code.value_counts()
    without = kept[kept.taxonomy_code != "none"].taxonomy_code.value_counts()
    cats = sorted(with_.index, key=lambda c: (-with_[c], c))
    flagged_rows = rev[rev.document_id.isin(flagged)]
    return {
        "flagged_document_ids": sorted(int(i) for i in flagged),
        "flagged_with_reason": int((flagged_rows.taxonomy_code != "none").sum()),
        "reasons_with": int(with_.sum()), "reasons_without": int(without.sum()),
        "by_category": [{"category": c, "with": int(with_[c]), "without": int(without.get(c, 0))} for c in cats],
        "rank_order_with": cats,
        "rank_order_without": sorted(without.index, key=lambda c: (-without[c], c)),
    }


def agreement(labels: pd.DataFrame) -> list[dict]:
    out = []
    for s in SAMPLES:
        d = labels[(labels["sample"] == s) & (labels.labeled_by == "model_draft")].set_index("document_id")
        r = labels[(labels["sample"] == s) & (labels.labeled_by == LABEL_SET)].set_index("document_id")
        ids = d.index.intersection(r.index)
        for field in ["taxonomy_code", "direction"]:
            a, b = d.loc[ids, field].astype(str), r.loc[ids, field].astype(str)
            out.append({"sample": s, "field": field, "n": int(len(ids)), "agree": int((a == b).sum()),
                        "pct_agree": round(float((a == b).mean()), 4), "cohen_kappa": round(float(cohen_kappa_score(a, b)), 2),
                        "raters": ["model_draft", LABEL_SET]})
    return out


def build(docs: pd.DataFrame, mentions: pd.DataFrame, labels: pd.DataFrame, promo_flagged: dict[str, list[int]],
          audit: pd.DataFrame, generated_at: str | None = None) -> dict:
    """`docs` must already carry the detector columns from sample.prepare."""
    check_labels_match_files(labels)
    by_id = docs.set_index("id")
    disc = docs[docs.source.isin(DISCUSSION_SOURCES)]

    sov = share_of_voice(docs.assign(switching=docs.switching_v1), mentions)
    share = [{
        "vendor": r.vendor, "documents": int(r.documents), "share_of_vendor_documents": round(float(r.share_of_vendor_docs), 4),
        "mentions": int(r.mentions), "switching_documents": int(r.switching_documents),
        "reason_v2_documents": int(r.reason_v2_documents),
        "documents_by_source": {s: int(getattr(r, f"docs_{s}")) for s in DISCUSSION_SOURCES},
    } for r in sov.itertuples()]

    rev = labels[labels.labeled_by == LABEL_SET].copy()
    rev["source"] = rev.document_id.map(by_id.source)

    quotes = []
    for doc_id, cat, quote in QUOTES:
        d, lab = by_id.loc[doc_id], rev.set_index("document_id").loc[doc_id]
        locate(d.body, quote)
        if lab.taxonomy_code != cat:
            raise SystemExit(f"quote {doc_id}: labelled {lab.taxonomy_code}, not {cat}")
        quotes.append({"document_id": int(doc_id), "category": cat, "quote": quote, "source": d.source, "url": d.url,
                       "posted_at": _iso(d.posted_at), "sample": lab["sample"], "from_vendor": lab.from_vendor,
                       "to_vendor": lab.to_vendor, "direction": lab.direction})

    cl_ids = set(mentions.document_id[(mentions.vendor == "cloudera") & mentions.document_id.isin(disc.id)])
    cl = disc[disc.id.isin(cl_ids)].sort_values("posted_at")
    cl_labels = rev.set_index("document_id")
    cl_list = [{
        "document_id": int(r.id), "source": r.source, "url": r.url, "title": r.title if isinstance(r.title, str) else None,
        "posted_at": _iso(r.posted_at), "other_vendors": [v for v in r.vendors if v != "cloudera"],
        "switching_v1": bool(r.switching_v1),
        "sample": cl_labels.at[r.id, "sample"] if r.id in cl_labels.index else None,
        "taxonomy_code": cl_labels.at[r.id, "taxonomy_code"] if r.id in cl_labels.index else None,
        "direction": cl_labels.at[r.id, "direction"] if r.id in cl_labels.index else None,
        "from_vendor": cl_labels.at[r.id, "from_vendor"] if r.id in cl_labels.index else None,
    } for r in cl.itertuples()]
    cases = []
    for doc_id, kind, qs in CLOUDERA_CASES:
        d = by_id.loc[doc_id]
        for q in qs:
            locate(d.body, q)
        cases.append({"document_id": int(doc_id), "kind": kind, "source": d.source, "url": d.url,
                      "title": d.title if isinstance(d.title, str) else None, "posted_at": _iso(d.posted_at), "quotes": qs})
    labelled_cl = [c for c in cl_list if c["sample"]]
    cloudera = {
        "documents": len(cl_list),
        "by_source": {s: int((cl.source == s).sum()) for s in DISCUSSION_SOURCES},
        "by_year": {str(y): int(n) for y, n in pd.to_datetime(cl.posted_at, utc=True).dt.year.value_counts().sort_index().items()},
        "labelled": len(labelled_cl),
        "labelled_with_reason": sum(c["taxonomy_code"] != "none" for c in labelled_cl),
        "labelled_leaving_cloudera": sum(c["from_vendor"] == "cloudera" for c in labelled_cl),
        "cases": cases, "document_list": cl_list,
    }

    verdicts = audit.verdict.value_counts()
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "label_set": LABEL_SET, "human_reviewed_labels": int((labels.labeled_by == "human").sum()),
        "corpus": {
            "discussion_documents": int(len(disc)),
            "discussion_documents_by_source": {s: int((disc.source == s).sum()) for s in DISCUSSION_SOURCES},
            "vendor_documents": int(sov.attrs["vendor_docs"]),
            "switching_vendor_documents": int(sov.attrs["switching_vendor_docs"]),
        },
        "share_of_voice": share,
        "reasons": reason_tables(rev),
        "agreement": agreement(labels),
        # seed_v2: the five documents the seed_v2 review notes flag; all_samples adds the seed_v1 notes' flags.
        "promotional_sensitivity": {
            "seed_v2": promotional_sensitivity(rev, promo_flagged.get("seed_v2", [])),
            "all_samples": promotional_sensitivity(rev, sorted({i for v in promo_flagged.values() for i in v})),
        },
        "quotes": quotes,
        "cloudera": cloudera,
        "deployment_control_probe": {
            "strict_documents_audited": int(len(audit)),
            "deployment_control_reason": int(verdicts.get("yes", 0)),
            "overlaps_other_category": int(verdicts.get("overlap", 0)),
            "not_a_reason": int(verdicts.get("no", 0)),
            "decision": "not_added",
        },
    }


def promo_flagged_from_notes(label_dir: Path = LABELING) -> dict[str, list[int]]:
    """Per sample, the documents whose claude_review notes call them vendor or self-promotional content."""
    out = {}
    for s in SAMPLES:
        f = pd.read_csv(label_dir / f"{LABEL_SET}_labels_{s}.csv", keep_default_na=False)
        out[s] = sorted(int(i) for i in f.document_id[f.notes.str.contains("promotional", case=False)]) if "notes" in f else []
    return out


def main() -> None:
    from sqlalchemy import text

    from analysis.labeling.sample import load_frames
    from ingestion.load_to_db import apply_schema, get_engine

    engine = get_engine()
    apply_schema(engine)
    docs, mentions = load_frames(engine)
    docs = prepare(docs, mentions, "v2")
    labels = pd.read_sql(text("""SELECT document_id, sample, labeled_by, taxonomy_code, from_vendor, to_vendor, direction,
                                        evidence_span FROM labels WHERE sample IS NOT NULL"""), engine)
    audit = pd.read_csv(LABELING / "probe_deployment_control_audit.csv")
    out = build(docs, mentions, labels, promo_flagged_from_notes(), audit)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({k: out[k] for k in ["corpus", "promotional_sensitivity", "deployment_control_probe"]}, indent=1))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
