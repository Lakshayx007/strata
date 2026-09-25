"""Generates analysis/notebooks/01_corpus_eda.ipynb so the notebook's code stays reviewable as plain Python."""

import nbformat as nbf
from pathlib import Path

cells = []
md = lambda s: cells.append(nbf.v4.new_markdown_cell(s))
code = lambda s: cells.append(nbf.v4.new_code_cell(s))

md("""# 01 · Corpus EDA

What was actually collected, straight from the database. Nothing here is estimated or filled in:
an empty section means the source returned nothing (or was not run), and the coverage table says which.

Vendor-docs pages are reference material, not practitioner voice, so they are counted in coverage
but excluded from the discussion charts and the reading sample. Signals (tag counts, GitHub metrics)
have their own section and are never combined with document counts (see docs/methodology.md).""")
code("""import os, sys, json, textwrap
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
from sqlalchemy import create_engine, text

ROOT = Path.cwd().resolve().parents[1] if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(ROOT))
from ingestion import config
from ingestion.normalize import has_switching_language

engine = create_engine(os.environ.get("DATABASE_URL") or config.DATABASE_URL, pool_pre_ping=True)
BLUE = "#2a78d6"  # one hue: every chart here is a single series
plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                     "grid.color": "#e6e6e3", "axes.axisbelow": True, "figure.dpi": 110})
DISCUSSION = ["reddit", "hackernews", "stackexchange"]
SAMPLE_SEED = 20260925  # fixed so the 20 printed documents are reproducible""")

md("## 1. Coverage: which sources produced anything")
code("""docs = pd.read_sql(text('''
    SELECT d.id, s.name AS source, d.external_id, d.url, d.title, d.body, d.posted_at, d.score, d.n_comments, d.fetched_at
    FROM documents d JOIN sources s ON s.id = d.source_id'''), engine)
sources = pd.read_sql(text("SELECT name, kind, last_run_at, terms_note FROM sources"), engine)
registry = pd.DataFrame([{"name": k, **v} for k, v in config.SOURCE_REGISTRY.items()])[["name", "kind"]]
coverage = registry.merge(sources[["name", "last_run_at"]], on="name", how="left")
coverage["documents"] = coverage["name"].map(docs["source"].value_counts()).fillna(0).astype(int)
processed = ROOT / "data" / "processed"
sig_counts = pd.read_sql(text("SELECT s.name, COUNT(*) AS n FROM signals g JOIN sources s ON s.id = g.source_id GROUP BY 1"), engine)
coverage["signal_rows"] = coverage["name"].map(sig_counts.set_index("name")["n"]).fillna(0).astype(int)
coverage["status"] = coverage.apply(
    lambda r: "never run" if pd.isna(r.last_run_at) else ("ran, 0 rows" if r.documents + r.signal_rows == 0 else "ok"), axis=1)
coverage""")

md("## 2. Volume by source and month (discussion sources)")
code("""disc = docs[docs.source.isin(DISCUSSION)].copy()
print(f"{len(disc):,} discussion documents; {disc.posted_at.isna().sum()} without a posted date")
if disc.empty:
    print("No discussion documents collected yet. Nothing to chart.")
else:
    disc["month"] = pd.to_datetime(disc.posted_at, utc=True).dt.tz_localize(None).dt.to_period("M").dt.to_timestamp()
    vol = disc.groupby(["source", "month"]).size().rename("docs").reset_index()
    srcs = sorted(vol.source.unique())
    fig, axes = plt.subplots(len(srcs), 1, figsize=(10, 2.4 * len(srcs)), sharex=True, squeeze=False)
    for ax, s in zip(axes[:, 0], srcs):  # small multiples: one source per panel, same hue, own y-scale
        v = vol[vol.source == s]
        ax.bar(v.month, v.docs, width=20, color=BLUE)
        ax.set_title(s, loc="left", fontsize=10)
        ax.set_ylabel("docs / month")
    plt.tight_layout(); plt.show()
    display(vol.pivot(index="month", columns="source", values="docs").fillna(0).astype(int).tail(24))""")

md("## 3. Vendor mention counts\n\nFrom the `mentions` table. Rules are in `ingestion/config.py`: *snowflake schema* and bare *fabric*/*glue* are excluded; "
   "*redshift*, *synapse*, *delta* and *spark* need nearby context. `tech:` rows (Delta Lake, Spark) are open-source technologies, "
   "shown in the table but never in the vendor chart.")
code("""ment = pd.read_sql(text('''
    SELECT m.vendor, s.name AS source, COUNT(DISTINCT m.document_id) AS documents, SUM(m.mention_count) AS mentions
    FROM mentions m JOIN documents d ON d.id = m.document_id JOIN sources s ON s.id = d.source_id
    GROUP BY 1, 2 ORDER BY 1, 2'''), engine)
if ment.empty:
    print("No vendor mentions yet.")
else:
    display(ment.pivot_table(index="vendor", columns="source", values="documents", fill_value=0, margins=True, aggfunc="sum"))
    d = ment[ment.source.isin(DISCUSSION)].groupby("vendor").documents.sum().reindex(config.VENDORS, fill_value=0).sort_values()
    if d.sum():
        ax = d.plot.barh(color=BLUE, figsize=(8, 3.2)); ax.set_xlabel("discussion documents mentioning vendor"); ax.set_ylabel("")
        for i, v in enumerate(d): ax.text(v, i, f" {v:,}", va="center", fontsize=9)
        plt.tight_layout(); plt.show()
    else:
        print("No vendor mentions in discussion sources yet (vendor_docs mentions shown in the table only).")""")

md("## 4. Document length distribution")
code("""docs["words"] = docs.body.str.split().str.len()
display(docs.groupby("source").words.describe(percentiles=[.1, .25, .5, .75, .9]).round(0))
if not disc.empty:
    disc["words"] = disc.body.str.split().str.len()
    srcs = sorted(disc.source.unique())
    fig, axes = plt.subplots(1, len(srcs), figsize=(4 * len(srcs), 3), squeeze=False)
    for ax, s in zip(axes[0], srcs):
        w = disc.loc[disc.source == s, "words"].clip(upper=disc.words.quantile(.99))
        ax.hist(w, bins=40, color=BLUE, edgecolor="white", linewidth=1)
        ax.set_title(s, loc="left", fontsize=10); ax.set_xlabel("words (clipped at p99)")
    plt.tight_layout(); plt.show()""")

md("## 5. Switching language share\n\nHow much of the corpus body text contains any phrase from `config.SWITCHING_PHRASES` (same rule as `python -m analysis.report`). A coarse filter for stratification, not a label.")
code("""if disc.empty:
    print("No discussion documents yet.")
else:
    disc["switching"] = disc.body.map(has_switching_language)  # body only, same rule as analysis.report
    display(disc.groupby("source").switching.agg(["sum", "mean", "size"]).rename(columns={"sum": "with_switching", "mean": "share", "size": "docs"}).round(3))""")

md("## 6. Rejected mention candidates\n\nCandidates discarded by the ambiguity rules, for precision review. Snippets are in `data/processed/rejected_mentions.csv`.")
code("""rej_path = processed / "rejected_mentions.csv"
if rej_path.exists():
    rej = pd.read_csv(rej_path)
    display(rej.groupby(["entity", "term", "reason"]).size().rename("rejected").sort_values(ascending=False))
    display(rej.sample(n=min(10, len(rej)), random_state=SAMPLE_SEED)[["entity", "reason", "snippet"]])
else:
    print("No rejected candidates recorded.")""")

md("## 7. Duplicates removed before loading")
code("""reports = sorted(processed.glob("dedupe_report_*.csv"))
if reports:
    dr = pd.concat([pd.read_csv(p).assign(report=p.name) for p in reports])
    display(dr.groupby(["dropped_source", "reason"]).size().rename("dropped"))
else:
    print("No dedupe reports: no duplicates have been dropped so far.")""")

md("## 8. Signals (kept separate from documents)\n\nAdoption and activity proxies: a different unit answering a different question. Never added to or divided by document counts.")
code("""sig = pd.read_sql(text('''
    SELECT g.signal_type, g.entity, g.metric, g.unit, g.granularity, COUNT(*) AS periods,
           MIN(g.period_start) AS first_period, MAX(g.period_start) AS last_period
    FROM signals g GROUP BY 1, 2, 3, 4, 5 ORDER BY 1, 2, 3'''), engine)
if sig.empty:
    print("No signals collected yet (Stack Exchange and GitHub have not produced rows).")
else:
    display(sig)""")

md("## 9. Twenty random documents, in full\n\nDrawn uniformly from discussion sources with a fixed seed. Read these before trusting any chart above.")
code("""if disc.empty:
    print("No discussion documents to sample.")
else:
    sample = disc.sample(n=min(20, len(disc)), random_state=SAMPLE_SEED)
    for i, r in enumerate(sample.itertuples(), 1):
        print("=" * 100)
        print(f"[{i}] doc {r.id} | {r.source} | {r.posted_at} | score={r.score} | {r.url}")
        if r.title: print(f"TITLE: {r.title}")
        print("-" * 100)
        print(r.body)
    print("=" * 100)""")

nb = nbf.v4.new_notebook(cells=cells, metadata={"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}})
out = Path(__file__).resolve().parents[1] / "notebooks" / "01_corpus_eda.ipynb"
nbf.write(nb, out)
print(out)
