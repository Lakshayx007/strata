"""Draw the Phase 2 seed sample for human labelling, and report vendor share of voice.

    python -m analysis.labeling.sample            # draw (or re-export an existing draw) and write the export
    python -m analysis.labeling.sample --redraw   # replace an existing draw of the same sample name

The draw is deterministic (fixed seed) and recorded in `sample_members`, so a re-run returns the same
documents even after the corpus grows. Rules, in the order they are applied:

  1. Pool: discussion documents from the quota sources, at least MIN_WORDS words, naming at least one vendor
     (tech:* entities do not count). A one-line comment rarely states a reason, and a document naming no
     vendor cannot carry a from/to label.
  2. Vendor floors: for the scarcest vendor first, add documents mentioning it until the floor is met,
     switching-language documents first, spread round-robin across sources, within each source's quota.
  3. Fill each source to its quota: switching documents up to the source's switching target, then others.
  4. If a source runs short, the remaining places go to other sources, switching documents first.

Every count below is printed as achieved, including any floor or target that was missed.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

from ingestion import config
from ingestion.normalize import has_switching_language

SAMPLE = "seed_v1"
SEED = 20260925
TOTAL = 150
SWITCHING_MIN = 110
QUOTAS = {"hackernews": 60, "stackexchange": 45, "devto": 45}
VENDOR_FLOORS = {"cloudera": 12, "microsoft": 10, "aws": 10, "google": 10}
MIN_WORDS = 20
DISCUSSION_SOURCES = ["hackernews", "stackexchange", "devto", "github_threads"]
EXPORT_DIR = config.PROJECT_ROOT / "data" / "processed" / "labeling"


def prepare(docs: pd.DataFrame, mentions: pd.DataFrame) -> pd.DataFrame:
    """Add words, switching flag and the sorted vendor tuple to each document."""
    docs = docs.copy()
    docs["words"] = docs.body.str.split().str.len().fillna(0).astype("int64")
    docs["switching"] = docs.body.map(has_switching_language).astype(bool)
    vend = mentions[mentions.vendor.isin(config.VENDORS)]
    per_doc = vend.groupby("document_id").vendor.apply(lambda v: tuple(sorted(set(v))))
    docs["vendors"] = docs.id.map(per_doc).apply(lambda v: v if isinstance(v, tuple) else ())
    return docs


def draw(docs: pd.DataFrame, seed: int = SEED, quotas: dict[str, int] = QUOTAS, total: int = TOTAL,
         switching_min: int = SWITCHING_MIN, floors: dict[str, int] = VENDOR_FLOORS, min_words: int = MIN_WORDS) -> pd.DataFrame:
    """Pure sampling over a prepared frame. Returns the selected rows with `picked_for` and `stratum`."""
    rng = np.random.default_rng(seed)
    pool = docs[docs.source.isin(quotas) & (docs.words >= min_words) & (docs.vendors.map(len) > 0)].copy()
    pool["r"] = rng.random(len(pool))
    pool = pool.sort_values(["r", "id"]).reset_index(drop=True)
    quotas = dict(quotas)
    # Per-source switching target, scaled so the targets add up to at least switching_min. A source with
    # too few switching documents passes its deficit to sources that have spare ones; only if their quotas
    # cannot absorb it does a place move from the short source to another (reported via the achieved counts).
    avail = {s: int((pool.switching & (pool.source == s)).sum()) for s in quotas}
    sw_target = {s: min(math.ceil(q * switching_min / total), avail[s]) for s, q in quotas.items()}
    while sum(sw_target.values()) < switching_min:
        spare = [s for s in quotas if sw_target[s] < min(avail[s], quotas[s])]
        if spare:
            sw_target[max(spare, key=lambda s: avail[s] - sw_target[s])] += 1
            continue
        donors = [s for s in quotas if quotas[s] > sw_target[s]]
        takers = [s for s in quotas if avail[s] > quotas[s]]
        if not donors or not takers:
            break  # the pool cannot supply switching_min; the shortfall shows in the achieved counts
        quotas[min(donors, key=lambda s: avail[s] - sw_target[s])] -= 1
        quotas[max(takers, key=lambda s: avail[s] - quotas[s])] += 1

    chosen: dict[int, str] = {}  # document id -> picked_for
    src_of = dict(zip(pool.id, pool.source))
    sw_of = dict(zip(pool.id, pool.switching))

    def n_src(s: str, switching: bool | None = None) -> int:
        return sum(1 for i in chosen if src_of[i] == s and (switching is None or sw_of[i] == switching))

    def room(s: str, switching: bool) -> bool:
        if n_src(s) >= quotas[s]:
            return False
        # A non-switching pick must leave room for the source's switching target.
        return switching or n_src(s, False) < quotas[s] - sw_target[s]

    # 2. Vendor floors, scarcest vendor first.
    availability = {v: int(pool.vendors.map(lambda t: v in t).sum()) for v in floors}
    for v in sorted(floors, key=lambda v: (availability[v], v)):
        have = sum(1 for i in chosen if v in pool.loc[pool.id == i, "vendors"].iloc[0])
        cand = pool[pool.vendors.map(lambda t: v in t) & ~pool.id.isin(chosen)].copy()
        cand["rank"] = cand.groupby("source").cumcount()
        cand = cand.sort_values(["switching", "rank", "source"], ascending=[False, True, True])
        for row in cand.itertuples():
            if have >= floors[v]:
                break
            if room(row.source, row.switching):
                chosen[row.id] = f"vendor_floor:{v}"
                have += 1

    # 3. Fill each source: switching up to target, then the rest.
    for s, q in quotas.items():
        src_pool = pool[(pool.source == s) & ~pool.id.isin(chosen)]
        for row in src_pool[src_pool.switching].itertuples():
            if n_src(s, True) >= sw_target[s] or n_src(s) >= q:
                break
            chosen[row.id] = "quota"
        for row in src_pool[~src_pool.switching].itertuples():
            if n_src(s) >= q:
                break
            if row.id not in chosen:
                chosen[row.id] = "quota"
        for row in src_pool[src_pool.switching].itertuples():  # source short of non-switching docs
            if n_src(s) >= q:
                break
            if row.id not in chosen:
                chosen[row.id] = "quota"

    # 4. Shortfall in one source goes to the others, switching first.
    rest = pool[~pool.id.isin(chosen)].sort_values(["switching", "r"], ascending=[False, True])
    for row in rest.itertuples():
        if len(chosen) >= total:
            break
        chosen[row.id] = "shortfall_fill"

    out = pool[pool.id.isin(chosen)].copy()
    out["picked_for"] = out.id.map(chosen)
    out["stratum"] = out.source + "/" + np.where(out.switching, "switching", "other")
    return out.drop(columns=["r"]).sort_values(["source", "id"]).reset_index(drop=True)


def coverage(sample: pd.DataFrame, quotas: dict[str, int] = QUOTAS) -> dict:
    return {
        "total": len(sample),
        "switching": int(sample.switching.sum()),
        "by_source": {s: {"target": quotas.get(s), "achieved": int((sample.source == s).sum()),
                          "switching": int(((sample.source == s) & sample.switching).sum())}
                      for s in sorted(set(quotas) | set(sample.source))},
        "by_vendor": {v: int(sample.vendors.map(lambda t: v in t).sum()) for v in config.VENDORS},
        "multi_vendor": int((sample.vendors.map(len) >= 2).sum()),
        "picked_for": dict(Counter(sample.picked_for)),
    }


def share_of_voice(docs: pd.DataFrame, mentions: pd.DataFrame) -> pd.DataFrame:
    """Per vendor, over discussion sources: documents naming it, its share of vendor-naming documents,
    raw mention count, and the same among switching-language documents."""
    disc = docs[docs.source.isin(DISCUSSION_SOURCES)]
    m = mentions[mentions.vendor.isin(config.VENDORS) & mentions.document_id.isin(disc.id)]
    any_vendor = m.document_id.nunique() or 1
    sw_ids = set(disc.id[disc.switching])
    sw_any = m[m.document_id.isin(sw_ids)].document_id.nunique() or 1
    rows = []
    for v in config.VENDORS:
        mv = m[m.vendor == v]
        ids = set(mv.document_id)
        rows.append({
            "vendor": v, "documents": len(ids), "share_of_vendor_docs": len(ids) / any_vendor,
            "mentions": int(mv.mention_count.sum()),
            "switching_documents": len(ids & sw_ids), "share_of_switching_vendor_docs": len(ids & sw_ids) / sw_any,
            **{f"docs_{s}": int(disc.id[disc.source == s].isin(ids).sum()) for s in DISCUSSION_SOURCES},
        })
    out = pd.DataFrame(rows).sort_values("documents", ascending=False).reset_index(drop=True)
    out.attrs.update(vendor_docs=any_vendor, switching_vendor_docs=sw_any, discussion_docs=len(disc))
    return out


def render(cov: dict, sov: pd.DataFrame, quotas=QUOTAS, floors=VENDOR_FLOORS) -> str:
    lines = [f"SEED SAMPLE {SAMPLE} (seed {SEED})", "",
             f"Total {cov['total']} (target {TOTAL});  switching language {cov['switching']} (min {SWITCHING_MIN});"
             f"  multi-vendor {cov['multi_vendor']}", "", "By source (achieved / target, of which switching):"]
    for s, c in cov["by_source"].items():
        lines.append(f"  {s:<15} {c['achieved']:>4} / {c['target'] or '-':>3}   switching {c['switching']}")
    lines += ["", "Documents mentioning each vendor (a document can name several):"]
    for v, n in cov["by_vendor"].items():
        f = floors.get(v)
        lines.append(f"  {v:<12} {n:>4}" + (f"   floor {f}: {'met' if n >= f else 'MISSED'}" if f else ""))
    lines += ["", f"Picked for: {cov['picked_for']}", "",
              f"SHARE OF VOICE, discussion sources ({sov.attrs['discussion_docs']:,} documents; "
              f"{sov.attrs['vendor_docs']:,} name a vendor; {sov.attrs['switching_vendor_docs']:,} of those use switching language)",
              "\n".join("  " + l for l in sov.round(3).to_string(index=False).splitlines())]
    return "\n".join(lines)


def load_frames(engine) -> tuple[pd.DataFrame, pd.DataFrame]:
    docs = pd.read_sql(text("""SELECT d.id, s.name AS source, d.external_id, d.url, d.title, d.body, d.posted_at, d.score
                               FROM documents d JOIN sources s ON s.id = d.source_id"""), engine)
    mentions = pd.read_sql(text("SELECT document_id, vendor, mention_count, first_char_offset FROM mentions"), engine)
    return docs, mentions


def main() -> None:
    from ingestion.load_to_db import apply_schema, get_engine

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--redraw", action="store_true", help="replace an existing draw of this sample")
    args = ap.parse_args()

    engine = get_engine()
    apply_schema(engine)
    docs, mentions = load_frames(engine)
    docs = prepare(docs, mentions)

    with engine.connect() as conn:
        existing = pd.read_sql(text("SELECT document_id, stratum, picked_for FROM sample_members WHERE sample = :s"),
                               conn, params={"s": SAMPLE})
    if len(existing) and not args.redraw:
        print(f"{SAMPLE} already drawn ({len(existing)} documents); re-exporting it. Use --redraw to replace it.")
        sample = docs.merge(existing.rename(columns={"document_id": "id"}), on="id")
    else:
        sample = draw(docs)
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM sample_members WHERE sample = :s"), {"s": SAMPLE})
            conn.execute(text("""INSERT INTO sample_members (sample, document_id, stratum, picked_for, seed)
                                 VALUES (:sample, :id, :stratum, :picked_for, :seed)"""),
                         [{"sample": SAMPLE, "id": int(r.id), "stratum": r.stratum, "picked_for": r.picked_for, "seed": SEED}
                          for r in sample.itertuples()])

    cov = coverage(sample)
    sov = share_of_voice(docs, mentions)
    report = render(cov, sov)
    print(report)

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    (EXPORT_DIR / f"{SAMPLE}_report.txt").write_text(report + "\n")
    (EXPORT_DIR / f"{SAMPLE}_coverage.json").write_text(json.dumps(cov, indent=2))
    sov.to_csv(EXPORT_DIR / "share_of_voice.csv", index=False)
    records = sample.assign(posted_at=sample.posted_at.astype(str), vendors=sample.vendors.map(list))
    cols = ["id", "source", "external_id", "url", "title", "body", "posted_at", "score", "words", "switching",
            "vendors", "stratum", "picked_for"]
    (EXPORT_DIR / f"{SAMPLE}_documents.json").write_text(
        json.dumps(records[cols].to_dict(orient="records"), ensure_ascii=False, indent=1, default=str))
    print(f"\nWrote {len(sample)} documents to {EXPORT_DIR}")


if __name__ == "__main__":
    main()
