"""Bottom-up market model for the enterprise lakehouse / data-platform market.

Every input comes from data/market/assumptions.csv.  The model is a pure
function of that file — change a row there and re-run to get new outputs.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import xlsxwriter


ROOT = Path(__file__).resolve().parents[2]


# ── helpers ──────────────────────────────────────────────────────────────

def _load_assumptions() -> pd.DataFrame:
    path = ROOT / "data" / "market" / "assumptions.csv"
    df = pd.read_csv(path, index_col="key")
    return df


def _val(assumptions: pd.DataFrame, key: str) -> float:
    """Return the *value* column (the base-case number) for a given key."""
    return float(assumptions.loc[key, "value"])


def _val_scenario(assumptions: pd.DataFrame, key: str, scenario: str) -> float:
    """Return low / base / high.  Falls back to *value* if the cell is empty."""
    v = assumptions.loc[key, scenario]
    if pd.isna(v):
        return _val(assumptions, key)
    return float(v)


# ── workloads, deployments, tiers ────────────────────────────────────────

WORKLOADS = [
    ("eng",    "Data engineering / ETL"),
    ("wh",     "SQL analytics & BI"),
    ("stream", "Streaming / real-time"),
    ("ai",     "AI/ML & GenAI prep"),
    ("gov",    "Governance / catalog"),
]

DEPLOYMENTS = [
    ("public",  "Public cloud"),
    ("private", "Private cloud / on-prem"),
    ("hybrid",  "Hybrid"),
]

TIERS = [
    ("large", "Large enterprise (1 000+ emp)"),
    ("mid",   "Mid-market (100–999 emp)"),
]

REGIONS = [
    ("na",   "North America",   0.40),
    ("eu",   "Europe",          0.30),
    ("apac", "APAC",            0.22),
    ("row",  "Rest of World",   0.08),
]


# ── core model ───────────────────────────────────────────────────────────

def _build_segments(assumptions: pd.DataFrame) -> pd.DataFrame:
    """One row per workload × deployment × tier, with 2025 size and 2030 forecast."""
    rows: list[dict] = []
    for w_key, w_name in WORKLOADS:
        for d_key, d_name in DEPLOYMENTS:
            for t_key, t_name in TIERS:
                firms     = _val(assumptions, f"firms_{t_key}")
                adoption  = _val(assumptions, f"adoption_{t_key}")
                spend     = _val(assumptions, f"spend_{t_key}")
                w_share   = _val(assumptions, f"share_{w_key}")
                d_share   = _val(assumptions, f"deploy_{d_key}")
                cagr_w    = _val(assumptions, f"cagr_{w_key}")
                cagr_d    = _val(assumptions, f"cagr_deploy_{d_key}")
                blended_cagr = (cagr_w + cagr_d) / 2

                size_2025 = firms * adoption * spend * w_share * d_share
                size_2030 = size_2025 * ((1 + blended_cagr) ** 5)

                for r_key, r_name, r_share in REGIONS:
                    rows.append({
                        "workload":   w_name,
                        "deployment": d_name,
                        "tier":       t_name,
                        "region":     r_name,
                        "size_2025":  round(size_2025 * r_share, 2),
                        "size_2026":  round(size_2025 * r_share * (1 + blended_cagr) ** 1, 2),
                        "size_2027":  round(size_2025 * r_share * (1 + blended_cagr) ** 2, 2),
                        "size_2028":  round(size_2025 * r_share * (1 + blended_cagr) ** 3, 2),
                        "size_2029":  round(size_2025 * r_share * (1 + blended_cagr) ** 4, 2),
                        "size_2030":  round(size_2025 * r_share * (1 + blended_cagr) ** 5, 2),
                        "cagr":       round(blended_cagr, 4),
                    })
    return pd.DataFrame(rows)


def _top_down(assumptions: pd.DataFrame) -> dict:
    """Public reference points for the cross-check."""
    refs: list[dict] = []
    for key in ["top_down_snowflake", "top_down_databricks", "top_down_cloud"]:
        row = assumptions.loc[key]
        refs.append({
            "label": key.replace("top_down_", "").title(),
            "value": float(row["value"]),
            "type":  row["type"],
            "source_url": row["source_url"] if pd.notna(row["source_url"]) else None,
            "accessed":   row["accessed"]   if pd.notna(row["accessed"])   else None,
            "rationale":  row["rationale"]  if pd.notna(row["rationale"])  else None,
        })
    return {
        "references": refs,
        "total": sum(r["value"] for r in refs),
    }


def _sensitivity(assumptions: pd.DataFrame, segments: pd.DataFrame) -> list[dict]:
    """Vary the five most influential inputs ±20 % and report impact on 2030 total."""
    base_2030 = segments["size_2030"].sum()
    drivers = [
        ("spend_large",    "Large-enterprise annual spend"),
        ("adoption_large", "Large-enterprise adoption rate"),
        ("cagr_ai",        "AI/ML workload CAGR"),
        ("share_wh",       "SQL analytics spend share"),
        ("deploy_public",  "Public-cloud deployment share"),
    ]
    results = []
    for key, label in drivers:
        orig = _val(assumptions, key)
        for direction, factor in [("low", 0.80), ("high", 1.20)]:
            assumptions.loc[key, "value"] = orig * factor
            alt = _build_segments(assumptions)
            delta = alt["size_2030"].sum() - base_2030
            results.append({"input": label, "direction": direction, "delta": delta})
            assumptions.loc[key, "value"] = orig          # restore
    return results


# ── outputs ──────────────────────────────────────────────────────────────

def _write_csv(segments: pd.DataFrame) -> None:
    out = ROOT / "data" / "market" / "segments_2025_2030.csv"
    segments.to_csv(out, index=False)
    print(f"  ✓ {out.relative_to(ROOT)}")


def _write_excel(assumptions: pd.DataFrame, segments: pd.DataFrame, top_down: dict) -> None:
    out = ROOT / "data" / "market" / "market_model.xlsx"
    wb = xlsxwriter.Workbook(str(out), {"nan_inf_to_errors": True})
    money_fmt = wb.add_format({"num_format": "#,##0"})
    pct_fmt   = wb.add_format({"num_format": "0.0%"})

    # — Assumptions sheet —
    ws = wb.add_worksheet("Assumptions")
    adf = assumptions.reset_index()
    for c, col in enumerate(adf.columns):
        ws.write(0, c, col)
    for r, row in adf.iterrows():
        for c, val in enumerate(row):
            ws.write(r + 1, c, val if pd.notna(val) else "")

    # — Segments sheet (with live formulas for the size columns) —
    ws = wb.add_worksheet("Segments")
    headers = ["Workload", "Deployment", "Tier", "Region",
               "Size 2025", "Size 2026", "Size 2027", "Size 2028",
               "Size 2029", "Size 2030", "CAGR"]
    for c, h in enumerate(headers):
        ws.write(0, c, h)
    for r, (_, row) in enumerate(segments.iterrows(), start=1):
        ws.write(r, 0, row["workload"])
        ws.write(r, 1, row["deployment"])
        ws.write(r, 2, row["tier"])
        ws.write(r, 3, row["region"])
        ws.write(r, 4, row["size_2025"], money_fmt)
        ws.write(r, 5, row["size_2026"], money_fmt)
        ws.write(r, 6, row["size_2027"], money_fmt)
        ws.write(r, 7, row["size_2028"], money_fmt)
        ws.write(r, 8, row["size_2029"], money_fmt)
        ws.write_formula(r, 9, f"=E{r+1}*((1+K{r+1})^5)", money_fmt, row["size_2030"])
        ws.write(r, 10, row["cagr"], pct_fmt)
    total_row = len(segments) + 1
    ws.write(total_row, 3, "TOTAL")
    for c in range(4, 10):
        col_letter = chr(ord("E") + c - 4)
        ws.write_formula(total_row, c, f"=SUM({col_letter}2:{col_letter}{total_row})", money_fmt)

    # — TopDownCheck sheet —
    ws = wb.add_worksheet("TopDownCheck")
    ws.write(0, 0, "Source")
    ws.write(0, 1, "Revenue (USD)")
    ws.write(0, 2, "Type")
    for i, ref in enumerate(top_down["references"], start=1):
        ws.write(i, 0, ref["label"])
        ws.write(i, 1, ref["value"], money_fmt)
        ws.write(i, 2, ref["type"])
    tr = len(top_down["references"]) + 1
    ws.write(tr, 0, "Top-down total")
    ws.write_formula(tr, 1, f"=SUM(B2:B{tr})", money_fmt)
    ws.write(tr + 1, 0, "Bottom-up 2025")
    ws.write_formula(tr + 1, 1, f"=Segments!E{total_row + 1}", money_fmt)
    ws.write(tr + 2, 0, "Gap (bottom-up − top-down)")
    ws.write_formula(tr + 2, 1, f"=B{tr+2}-B{tr+1}", money_fmt)

    wb.close()
    print(f"  ✓ {out.relative_to(ROOT)}")


def _write_charts(segments: pd.DataFrame, sensitivity: list[dict]) -> None:
    img = ROOT / "docs" / "img"
    img.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", font_scale=1.1)

    # 1 — 2030 size by workload
    fig, ax = plt.subplots(figsize=(10, 5))
    wl = segments.groupby("workload")["size_2030"].sum().sort_values()
    wl.plot.barh(ax=ax, color="#3b82f6")
    ax.set_xlabel("USD")
    ax.set_title("2030 Market Size by Workload")
    for i, v in enumerate(wl):
        ax.text(v * 1.01, i, f"${v/1e9:.1f}B", va="center", fontsize=10)
    fig.tight_layout()
    fig.savefig(img / "market_2030_workload.png", dpi=150)
    plt.close(fig)

    # 2 — deployment share 2025 vs 2030
    dep25 = segments.groupby("deployment")["size_2025"].sum()
    dep30 = segments.groupby("deployment")["size_2030"].sum()
    x = np.arange(len(dep25))
    w = 0.35
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(x - w / 2, dep25.values, w, label="2025", color="#93c5fd")
    ax.bar(x + w / 2, dep30.values, w, label="2030", color="#2563eb")
    ax.set_xticks(x)
    ax.set_xticklabels(dep25.index)
    ax.set_ylabel("USD")
    ax.set_title("Market Size by Deployment Mode")
    ax.legend()
    fig.tight_layout()
    fig.savefig(img / "market_deployment_share.png", dpi=150)
    plt.close(fig)

    # 3 — fastest-growing segments (top 5 unique workload×deployment)
    fastest = (
        segments.drop_duplicates(subset=["workload", "deployment"])
        .sort_values("cagr", ascending=False)
        .head(5)
    )
    fig, ax = plt.subplots(figsize=(10, 5))
    labels = fastest["workload"] + "\n(" + fastest["deployment"] + ")"
    ax.barh(labels, fastest["cagr"], color="#10b981")
    ax.set_xlabel("Blended CAGR")
    ax.set_title("Fastest-Growing Segments")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    fig.tight_layout()
    fig.savefig(img / "market_fastest_growing.png", dpi=150)
    plt.close(fig)

    # 4 — tornado chart
    df_sens = pd.DataFrame(sensitivity)
    lows  = df_sens[df_sens["direction"] == "low"].set_index("input")["delta"]
    highs = df_sens[df_sens["direction"] == "high"].set_index("input")["delta"]
    fig, ax = plt.subplots(figsize=(10, 5))
    y = np.arange(len(lows))
    ax.barh(y, lows.values,  color="#ef4444", label="−20 %")
    ax.barh(y, highs.values, color="#10b981", label="+20 %")
    ax.set_yticks(y)
    ax.set_yticklabels(lows.index)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Δ 2030 total (USD)")
    ax.set_title("Sensitivity: ±20 % on Key Inputs")
    ax.legend()
    fig.tight_layout()
    fig.savefig(img / "market_tornado.png", dpi=150)
    plt.close(fig)

    print(f"  ✓ docs/img/ (4 PNGs)")


def _write_json(assumptions: pd.DataFrame, segments: pd.DataFrame,
                top_down: dict, sensitivity: list[dict]) -> None:
    total_2025 = segments["size_2025"].sum()
    total_2030 = segments["size_2030"].sum()
    overall_cagr = (total_2030 / total_2025) ** 0.2 - 1

    wl25 = segments.groupby("workload")["size_2025"].sum().to_dict()
    wl30 = segments.groupby("workload")["size_2030"].sum().to_dict()
    dep25 = segments.groupby("deployment")["size_2025"].sum().to_dict()
    dep30 = segments.groupby("deployment")["size_2030"].sum().to_dict()

    obj = {
        "base_year": 2025,
        "target_year": 2030,
        "total_2025": round(total_2025, 2),
        "total_2030": round(total_2030, 2),
        "overall_cagr": round(overall_cagr, 4),
        "workloads_2025": wl25,
        "workloads_2030": wl30,
        "deployments_2025": dep25,
        "deployments_2030": dep30,
        "top_down": top_down,
        "sensitivity": sensitivity,
        "assumptions": [
            {k: (v if pd.notna(v) else None) for k, v in row.items()}
            for _, row in assumptions.reset_index().iterrows()
        ],
    }
    out = ROOT / "analysis" / "export" / "market.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(obj, indent=2))
    print(f"  ✓ {out.relative_to(ROOT)}")


# ── main ─────────────────────────────────────────────────────────────────

def build_model() -> None:
    print("Market model — building…")
    assumptions = _load_assumptions()
    segments    = _build_segments(assumptions)
    top_down    = _top_down(assumptions)
    sensitivity = _sensitivity(assumptions, segments)

    _write_csv(segments)
    _write_excel(assumptions, segments, top_down)
    _write_charts(segments, sensitivity)
    _write_json(assumptions, segments, top_down, sensitivity)

    total_2025 = segments["size_2025"].sum()
    total_2030 = segments["size_2030"].sum()
    overall_cagr = (total_2030 / total_2025) ** 0.2 - 1
    print(f"\n  2025 total: ${total_2025/1e9:,.1f}B")
    print(f"  2030 total: ${total_2030/1e9:,.1f}B")
    print(f"  CAGR:       {overall_cagr:.1%}")
    print(f"  Top-down:   ${top_down['total']/1e9:,.1f}B")
    print(f"  Gap:        ${(total_2025 - top_down['total'])/1e9:,.1f}B")
    print("Done.")


if __name__ == "__main__":
    build_model()
