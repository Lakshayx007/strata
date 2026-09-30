"""SIMULATED CRM data generator.

Produces deterministic CRM-style datasets from data/crm_sim/params.yaml.
ALL DATA IS SIMULATED — calibrated to phase-1 stated-reason shares but
NOT observed CRM data.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
PARAMS_PATH = ROOT / "data" / "crm_sim" / "params.yaml"
DB_PATH = ROOT / "data" / "crm_sim" / "sim_crm.db"


def _load_params() -> dict:
    return yaml.safe_load(PARAMS_PATH.read_text())


def generate(params: dict | None = None) -> dict[str, pd.DataFrame]:
    if params is None:
        params = _load_params()
    rng = np.random.default_rng(params["seed"])

    accounts     = _gen_accounts(rng, params)
    opportunities = _gen_opportunities(rng, params, accounts)
    stage_history = _gen_stage_history(rng, params, opportunities)
    usage        = _gen_usage(rng, params, accounts)
    renewals     = _gen_renewals(rng, params, accounts)
    releases     = _gen_releases(rng, params)

    return {
        "sim_accounts":      accounts,
        "sim_opportunities": opportunities,
        "sim_stage_history": stage_history,
        "sim_usage_monthly": usage,
        "sim_renewals":      renewals,
        "sim_releases":      releases,
    }


def _gen_accounts(rng: np.random.Generator, p: dict) -> pd.DataFrame:
    n = p["accounts"]["count"]
    ap = p["accounts"]
    return pd.DataFrame({
        "account_id":  range(1, n + 1),
        "industry":    rng.choice(ap["industries"], n),
        "region":      rng.choice(ap["regions"], n, p=ap["region_weights"]),
        "tier":        rng.choice(ap["tiers"], n, p=ap["tier_weights"]),
        "deployment":  rng.choice(ap["deployments"], n, p=ap["deployment_weights"]),
        "arr_band":    rng.choice(ap["arr_bands"], n, p=ap["arr_band_weights"]),
    })


def _gen_opportunities(rng: np.random.Generator, p: dict,
                       accounts: pd.DataFrame) -> pd.DataFrame:
    n = p["opportunities"]["count"]
    op = p["opportunities"]
    stages = op["stages"]
    win_rate = op["win_rate"]

    q_start = date(2024, 1, 1)
    rows = []
    for i in range(1, n + 1):
        acct = rng.choice(accounts["account_id"])
        competitor = rng.choice(op["competitors"], p=op["competitor_weights"])
        amount = float(rng.lognormal(11.5, 1.2))  # ~$100K median
        created = q_start + timedelta(days=int(rng.integers(0, 365 * 2)))
        cycle_days = int(rng.integers(30, 180))
        closed = created + timedelta(days=cycle_days)

        won = rng.random() < win_rate
        if won:
            outcome = "Won"
            final_stage = "Closed Won"
            loss_reason = None
            stage_reached = "Closed Won"
        else:
            # Pick the stage at which the deal was lost
            lose_at = rng.choice(stages[1:6])  # Qualification through Negotiation
            final_stage = "Closed Lost"
            outcome = "Lost"
            loss_reason = rng.choice(op["loss_reasons"], p=op["loss_reason_weights"])
            stage_reached = lose_at

        rows.append({
            "opp_id": i,
            "account_id": int(acct),
            "amount": round(amount, 2),
            "created_date": str(created),
            "closed_date": str(closed),
            "stage_reached": stage_reached,
            "competitor": competitor,
            "outcome": outcome,
            "loss_reason": loss_reason,
        })
    return pd.DataFrame(rows)


def _gen_stage_history(rng: np.random.Generator, p: dict,
                       opportunities: pd.DataFrame) -> pd.DataFrame:
    stages = p["opportunities"]["stages"]
    rows = []
    for _, opp in opportunities.iterrows():
        created = pd.Timestamp(opp["created_date"])
        closed  = pd.Timestamp(opp["closed_date"])
        total_days = max((closed - created).days, len(stages))

        if opp["outcome"] == "Won":
            go_through = stages  # all stages
        else:
            idx = stages.index(opp["stage_reached"])
            go_through = stages[:idx + 1] + ["Closed Lost"]

        day_alloc = sorted(rng.integers(0, total_days, len(go_through) - 1))
        for j, stage in enumerate(go_through):
            entry = created + timedelta(days=int(day_alloc[j]) if j < len(day_alloc) else total_days)
            if j + 1 < len(go_through) and j + 1 <= len(day_alloc):
                exit_dt = created + timedelta(days=int(day_alloc[j]))
            else:
                exit_dt = closed
            rows.append({
                "opp_id": opp["opp_id"],
                "stage": stage,
                "entered_at": str(entry.date()),
                "exited_at": str(exit_dt.date()),
            })
    return pd.DataFrame(rows)


def _gen_usage(rng: np.random.Generator, p: dict,
               accounts: pd.DataFrame) -> pd.DataFrame:
    services = p["services"]
    months = pd.date_range("2024-01-01", "2025-12-31", freq="MS")
    rows = []
    for _, acct in accounts.iterrows():
        base_units = rng.lognormal(8, 1)
        base_users = int(rng.integers(5, 200))
        for m in months:
            for svc in services:
                svc_mult = {"engineering": 1.0, "warehouse": 1.2,
                            "streaming": 0.4, "ai": 0.6}[svc]
                noise = rng.normal(1.0, 0.15)
                trend = 1 + 0.02 * ((m - months[0]).days / 30)
                units = max(0, base_units * svc_mult * noise * trend)
                users = max(1, int(base_users * svc_mult * noise * 0.3))
                rows.append({
                    "account_id": acct["account_id"],
                    "month": str(m.date()),
                    "service": svc,
                    "consumption_units": round(units, 2),
                    "active_users": users,
                })
    return pd.DataFrame(rows)


def _gen_renewals(rng: np.random.Generator, p: dict,
                  accounts: pd.DataFrame) -> pd.DataFrame:
    rp = p["renewals"]
    rows = []
    for _, acct in accounts.iterrows():
        start_arr = float(rng.lognormal(11, 1.5))
        churn = rng.random() < rp["churn_rate"]
        expansion = 0
        contraction = 0
        if churn:
            expansion = 0
            contraction = start_arr
        elif rng.random() < rp["expansion_rate"]:
            expansion = float(start_arr * rng.uniform(0.05, 0.40))
        elif rng.random() < rp["contraction_rate"]:
            contraction = float(start_arr * rng.uniform(0.05, 0.25))
        rows.append({
            "account_id": acct["account_id"],
            "start_arr": round(start_arr, 2),
            "expansion": round(expansion, 2),
            "contraction": round(contraction, 2),
            "churn": churn,
        })
    return pd.DataFrame(rows)


def _gen_releases(rng: np.random.Generator, p: dict) -> pd.DataFrame:
    rp = p["releases"]
    rows = []
    q_starts = pd.date_range("2024-01-01", periods=8, freq="QS")
    for team in rp["pm_teams"]:
        for q in q_starts:
            for sprint in range(rp["sprints_per_quarter"]):
                planned = int(rng.normal(rp["points_per_sprint_mean"], 8))
                delivered = int(planned * rng.uniform(0.6, 1.1))
                on_time = rng.random() < rp["on_time_rate"]
                planned_date = q + timedelta(days=14 * sprint + 13)
                slip = 0 if on_time else int(rng.integers(1, 21))
                actual_date = planned_date + timedelta(days=slip)
                rows.append({
                    "pm_team": team,
                    "quarter": str(q.date()),
                    "sprint": sprint + 1,
                    "planned_points": planned,
                    "delivered_points": delivered,
                    "planned_release_date": str(planned_date.date()),
                    "actual_release_date": str(actual_date.date()),
                    "on_time": on_time,
                })
    return pd.DataFrame(rows)


def save_to_sqlite(tables: dict[str, pd.DataFrame]) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    for name, df in tables.items():
        df.to_sql(name, conn, if_exists="replace", index=False)
    conn.close()
    print(f"  Saved {len(tables)} tables to {DB_PATH.relative_to(ROOT)}")


def export_pipeline_json(tables: dict[str, pd.DataFrame]) -> None:
    """Run the SQL queries and export results to pipeline.json."""
    conn = sqlite3.connect(str(DB_PATH))

    results = {}

    # Win rate by competitor
    results["win_rate_by_competitor"] = pd.read_sql("""
        SELECT competitor,
               COUNT(*) as total,
               SUM(CASE WHEN outcome='Won' THEN 1 ELSE 0 END) as wins,
               ROUND(1.0 * SUM(CASE WHEN outcome='Won' THEN 1 ELSE 0 END) / COUNT(*), 3) as win_rate
        FROM sim_opportunities
        GROUP BY competitor ORDER BY win_rate DESC
    """, conn).to_dict(orient="records")

    # Loss reason mix by competitor
    results["loss_reason_by_competitor"] = pd.read_sql("""
        SELECT competitor, loss_reason, COUNT(*) as count
        FROM sim_opportunities
        WHERE outcome = 'Lost' AND loss_reason IS NOT NULL
        GROUP BY competitor, loss_reason
        ORDER BY competitor, count DESC
    """, conn).to_dict(orient="records")

    # Stage conversion
    results["stage_conversion"] = pd.read_sql("""
        SELECT stage,
               COUNT(*) as entries,
               ROUND(AVG(julianday(exited_at) - julianday(entered_at)), 1) as median_days
        FROM sim_stage_history
        GROUP BY stage ORDER BY entries DESC
    """, conn).to_dict(orient="records")

    # Churn by usage decile
    results["churn_by_usage_decile"] = pd.read_sql("""
        SELECT usage_decile,
               COUNT(*) as accounts,
               SUM(churn) as churned,
               ROUND(1.0 * SUM(churn) / COUNT(*), 3) as churn_rate
        FROM (
            SELECT
                NTILE(10) OVER (ORDER BY total_usage) as usage_decile,
                churn
            FROM (
                SELECT u.account_id, SUM(u.consumption_units) as total_usage, r.churn
                FROM sim_usage_monthly u
                JOIN sim_renewals r ON u.account_id = r.account_id
                GROUP BY u.account_id
            )
        )
        GROUP BY usage_decile ORDER BY usage_decile
    """, conn).to_dict(orient="records")

    # Delivery velocity by PM team
    results["delivery_velocity"] = pd.read_sql("""
        SELECT pm_team,
               COUNT(*) as sprints,
               ROUND(AVG(delivered_points), 1) as avg_delivered,
               ROUND(1.0 * SUM(CASE WHEN on_time THEN 1 ELSE 0 END) / COUNT(*), 3) as on_time_pct,
               ROUND(AVG(julianday(actual_release_date) - julianday(planned_release_date)), 1) as avg_slip_days
        FROM sim_releases
        GROUP BY pm_team
    """, conn).to_dict(orient="records")

    conn.close()

    out = ROOT / "analysis" / "export" / "pipeline.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"  Exported {out.relative_to(ROOT)}")


if __name__ == "__main__":
    print("CRM simulator - generating SIMULATED data...")
    tables = generate()
    for name, df in tables.items():
        print(f"  {name}: {len(df)} rows")
    save_to_sqlite(tables)
    export_pipeline_json(tables)
    print("Done.")
