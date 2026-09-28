"""Measure how often a proposed reason category could occur across the whole discussion corpus.

    python -m analysis.labeling.category_probe

Proposed category `deployment_control`: where the platform runs and who controls it drives the choice
(self-hosted or on-premises versus SaaS, bring-your-own-cloud / in-VPC deployment, data residency or sovereignty,
air-gapped environments).

For the candidate and, as a yardstick, for every existing category's cue words (config.REASON_CUES), it counts
discussion documents with at least one "strict" sentence: the cue plus a data platform (config.PLATFORM_TERMS)
plus a move or comparison (config.MOVE_PHRASES), the same shape detector v2 uses. It prints counts by source and
vendor and up to AUDIT_ROWS strict sentences for the candidate, so its precision can be read by hand from the
log (public post text, no author data). Cue matches are an upper bound on the category, not a label count.
"""

from __future__ import annotations

import re

import pandas as pd
from sqlalchemy import text

from analysis.labeling.sample import DISCUSSION_SOURCES, EXPORT_DIR
from ingestion import config
from ingestion.normalize import _MOVE_RE, _PLATFORM_RE, _SENTENCE_SPLIT

CANDIDATE = "deployment_control"
CANDIDATE_CUES = [r"byoc", r"bring your own cloud", r"self[- ]?host(?:ed|ing)?", r"self[- ]managed", r"on[- ]?prem(?:ise|ises)?",
                  r"(?:in|into) (?:our|your|their|the customer's) own (?:cloud|vpc|account|data ?cent(?:er|re)|infrastructure)",
                  r"air[- ]?gapped", r"data residency", r"(?:data )?sovereign(?:ty)?", r"private cloud", r"customer[- ]managed",
                  r"run (?:it )?ourselves", r"our own (?:hardware|servers|racks)", r"cloud exit", r"repatriat\w*"]
AUDIT_ROWS = 60


def _re(words: list[str]) -> re.Pattern:
    return re.compile(r"\b(?:" + "|".join(words) + r")\b", re.IGNORECASE)


def strict_sentences(body: str, cue: re.Pattern) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(body or "")
            if cue.search(s) and _PLATFORM_RE.search(s) and _MOVE_RE.search(s)]


def probe(docs: pd.DataFrame, cues: dict[str, re.Pattern]) -> pd.DataFrame:
    rows = []
    for name, cue in cues.items():
        any_hit = docs.body.fillna("").map(lambda b: bool(cue.search(b)))
        strict = docs.body.map(lambda b: strict_sentences(b, cue))
        rows.append({"category": name, "documents_with_cue": int(any_hit.sum()),
                     "documents_strict": int((strict.map(len) > 0).sum()),
                     **{f"strict_{s}": int(((strict.map(len) > 0) & (docs.source == s)).sum()) for s in DISCUSSION_SOURCES}})
    return pd.DataFrame(rows).sort_values("documents_strict", ascending=False).reset_index(drop=True)


def main() -> None:
    from ingestion.load_to_db import get_engine

    engine = get_engine()
    docs = pd.read_sql(text("""SELECT d.id, s.name AS source, d.body FROM documents d JOIN sources s ON s.id = d.source_id
                               WHERE s.name = ANY(:s)"""), engine, params={"s": DISCUSSION_SOURCES})
    mentions = pd.read_sql(text("SELECT document_id, vendor FROM mentions"), engine)
    cues = {CANDIDATE: _re(CANDIDATE_CUES), **{k: _re(v) for k, v in config.REASON_CUES.items()}}
    table = probe(docs, cues)
    print(f"{len(docs):,} discussion documents\n")
    print(table.to_string(index=False), "\n")

    cand = docs.assign(strict=docs.body.map(lambda b: strict_sentences(b, cues[CANDIDATE])))
    cand = cand[cand.strict.map(len) > 0]
    vend = mentions[mentions.vendor.isin(config.VENDORS) & mentions.document_id.isin(cand.id)]
    print(f"{CANDIDATE}: strict documents naming each vendor")
    print(vend.groupby("vendor").document_id.nunique().sort_values(ascending=False).to_string(), "\n")
    print(f"Audit: {min(AUDIT_ROWS, len(cand))} of {len(cand)} strict {CANDIDATE} documents (every {max(1, len(cand) // AUDIT_ROWS)}th)")
    step = max(1, len(cand) // AUDIT_ROWS)
    for r in cand.sort_values("id").iloc[::step].head(AUDIT_ROWS).itertuples():
        sentence = re.sub(r"\s+", " ", r.strict[0])[:260]
        print(f"  {r.id} {r.source[:2]} | {sentence}")
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    table.to_csv(EXPORT_DIR / f"probe_{CANDIDATE}.csv", index=False)


if __name__ == "__main__":
    main()
