"""Competitive feature-parity analysis.

Reads data/competitive/vendor_features.csv (the source of truth) and
produces a heatmap, group-level scores, and a positioning map.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

ROOT = Path(__file__).resolve().parents[2]
IMG  = ROOT / "docs" / "img"


def build_matrix() -> None:
    print("Competitive matrix - building...")
    IMG.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="white", font_scale=0.9)

    df = pd.read_csv(ROOT / "data" / "competitive" / "vendor_features.csv")

    vendors = ["snowflake", "databricks", "cloudera", "aws", "microsoft", "google"]
    groups  = df["group"].unique().tolist()
    capabilities = df["capability"].unique().tolist()

    # --- Pivot for heatmap ---
    pivot = df.pivot_table(index="capability", columns="vendor", values="score")
    pivot = pivot.reindex(columns=vendors, index=capabilities)

    fig, ax = plt.subplots(figsize=(12, 14))
    cmap = sns.color_palette(["#fef2f2", "#fde68a", "#86efac"], as_cmap=True)
    sns.heatmap(
        pivot, annot=True, fmt=".0f", cmap=cmap,
        vmin=0, vmax=2, linewidths=0.5, linecolor="white",
        cbar_kws={"label": "0 = not offered  1 = partial/preview  2 = GA native",
                  "shrink": 0.5},
        ax=ax,
    )
    ax.set_title("Competitive Feature Matrix", fontsize=14, fontweight="bold")
    ax.set_xlabel("")
    ax.set_ylabel("")
    # Add group separators
    cap_groups = df.drop_duplicates("capability")[["capability", "group"]]
    group_boundaries = []
    prev = None
    for i, (_, row) in enumerate(cap_groups.iterrows()):
        if row["group"] != prev:
            group_boundaries.append((i, row["group"]))
            prev = row["group"]
    for idx, name in group_boundaries:
        ax.axhline(y=idx, color="gray", linewidth=1.5)

    fig.tight_layout()
    fig.savefig(IMG / "competitive_heatmap.png", dpi=150)
    plt.close(fig)

    # --- Group-level scores ---
    group_scores = (
        df.groupby(["vendor", "group"])["score"]
        .mean()
        .unstack("vendor")
        .reindex(columns=vendors)
    )
    group_scores_dict = {}
    for v in vendors:
        group_scores_dict[v] = {g: round(group_scores.loc[g, v], 2) for g in groups}

    # --- Positioning map ---
    # x-axis: deployment flexibility = mean of deployment group
    # y-axis: openness/interop = mean of open_table_formats + cross_system_lineage
    openness_caps = ["iceberg_read_write", "delta_support", "rest_catalog_interop",
                     "cross_system_lineage"]
    deploy_caps   = ["self_managed_onprem", "private_cloud", "multi_cloud",
                     "sovereign_airgapped", "single_control_plane"]

    positions = []
    for v in vendors:
        vdf = df[df["vendor"] == v]
        x = vdf[vdf["capability"].isin(deploy_caps)]["score"].mean()
        y = vdf[vdf["capability"].isin(openness_caps)]["score"].mean()
        positions.append({"vendor": v, "deploy_flex": round(x, 2), "openness": round(y, 2)})

    pos_df = pd.DataFrame(positions)

    fig, ax = plt.subplots(figsize=(8, 8))
    vendor_colors = {
        "snowflake": "#29b5e8", "databricks": "#ff3621", "cloudera": "#f59e0b",
        "aws": "#ff9900", "microsoft": "#00a4ef", "google": "#4285f4",
    }
    for _, row in pos_df.iterrows():
        ax.scatter(row["deploy_flex"], row["openness"], s=200,
                   color=vendor_colors.get(row["vendor"], "gray"), zorder=5)
        ax.annotate(row["vendor"].title(), (row["deploy_flex"], row["openness"]),
                    textcoords="offset points", xytext=(10, 5), fontsize=11)
    ax.set_xlabel("Deployment Flexibility (mean score)", fontsize=12)
    ax.set_ylabel("Openness / Interoperability (mean score)", fontsize=12)
    ax.set_title("Positioning Map", fontsize=14, fontweight="bold")
    ax.set_xlim(-0.2, 2.2)
    ax.set_ylim(-0.2, 2.2)
    ax.axhline(1.0, color="lightgray", linestyle="--", linewidth=0.8)
    ax.axvline(1.0, color="lightgray", linestyle="--", linewidth=0.8)
    ax.text(0.3, 2.1, "Open but inflexible\ndeployment", fontsize=8, color="gray", ha="center")
    ax.text(1.7, 2.1, "Open AND flexible", fontsize=8, color="gray", ha="center")
    ax.text(0.3, -0.1, "Closed AND inflexible", fontsize=8, color="gray", ha="center")
    ax.text(1.7, -0.1, "Flexible but closed", fontsize=8, color="gray", ha="center")
    fig.tight_layout()
    fig.savefig(IMG / "competitive_positioning.png", dpi=150)
    plt.close(fig)

    # --- Export JSON ---
    scores_dict = df[["vendor", "capability", "group", "score", "evidence_url", "note"]].replace({np.nan: None}).to_dict(orient="records")
    competitive_json = {
        "vendors": vendors,
        "capabilities": capabilities,
        "groups": groups,
        "scores": scores_dict,
        "group_scores": group_scores_dict,
        "positioning": positions,
        "positioning_axes": {
            "x": {"label": "Deployment Flexibility", "capabilities": deploy_caps},
            "y": {"label": "Openness / Interoperability", "capabilities": openness_caps},
        },
    }
    out = ROOT / "analysis" / "export" / "competitive.json"
    out.write_text(json.dumps(competitive_json, indent=2))
    print(f"  Done: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    build_matrix()
