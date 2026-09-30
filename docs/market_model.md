# Market model: enterprise lakehouse and data-platform market

## Method

Bottom-up sizing: number of firms × adoption rate × average annual platform spend × workload share × deployment-mode split, computed per segment (workload × deployment × tier × region) for base year 2025, then forecast to 2030 with workload- and deployment-specific CAGRs. Every input is in `data/market/assumptions.csv` with its type (SOURCED or ASSUMPTION), source URL, access date and rationale.

The model is a pure function of that CSV: `python analysis/market/model.py` reads it and writes all outputs.

## Segment definitions

**Workloads** (5): Data engineering/ETL, SQL analytics & BI, Streaming/real-time, AI/ML & GenAI prep, Governance/catalog.

**Deployment modes** (3): Public cloud, Private cloud/on-prem, Hybrid.

**Enterprise tiers** (2): Large enterprise (1,000+ employees), Mid-market (100–999 employees).

**Regions** (4): North America (40%), Europe (30%), APAC (22%), Rest of World (8%).

Total segments: 5 × 3 × 2 × 4 = 120.

## Top 10 assumptions and why

| # | Input | Base value | Type | Rationale |
|---|---|---|---|---|
| 1 | Large-enterprise firms globally | 50,000 | SOURCED | US Census SUSB + extrapolation |
| 2 | Mid-market firms globally | 250,000 | ASSUMPTION | Broad estimate of 100–999 emp firms |
| 3 | Large-enterprise adoption rate | 60% | ASSUMPTION | Larger firms more likely to have a modern data platform |
| 4 | Mid-market adoption rate | 25% | ASSUMPTION | Growing but trails large enterprise |
| 5 | Large-enterprise avg annual spend | $1.5M | ASSUMPTION | Covers compute, storage, licensing |
| 6 | Mid-market avg annual spend | $150K | ASSUMPTION | Order-of-magnitude smaller |
| 7 | SQL analytics spend share | 35% | ASSUMPTION | Core warehouse use case dominates |
| 8 | AI/ML CAGR | 35% | ASSUMPTION | Fastest-growing segment due to GenAI |
| 9 | Public cloud share | 65% | ASSUMPTION | Dominant deployment mode |
| 10 | Streaming CAGR | 25% | ASSUMPTION | High growth in real-time use cases |

## Headline results

| Metric | Value |
|---|---|
| 2025 base total | ~$54B |
| 2030 total | ~$121B |
| Overall CAGR (2025–2030) | ~17% |
| Largest segment (2030) | SQL analytics & BI |
| Fastest-growing segment | AI/ML & GenAI prep (public cloud) |
| Hybrid share of 2030 total | Growing from 20% of deployments |

## Top-down cross-check

| Source | Value | Type |
|---|---|---|
| Snowflake reported product revenue | $3.5B | SOURCED (investors.snowflake.com) |
| Databricks announced revenue run-rate | $2.4B | SOURCED (databricks.com/newsroom) |
| Cloud providers estimated data platform revenue | $15B | ASSUMPTION |
| **Top-down total** | **$20.9B** | |
| **Bottom-up 2025** | **~$54B** | |
| **Gap** | **~$33B** | |

The bottom-up exceeds the top-down reference by about $33B. This is expected: the top-down total only captures a few public reference points (two pure-play vendors plus an estimate for the cloud hyperscalers' data platform slices), while the bottom-up includes the full addressable market across all tiers, regions and workloads — including spend that goes to smaller vendors, on-prem tools, and internal engineering. The top-down references are revenue, not market size.

## Limitations

- Firm counts and adoption rates are rough. The model is illustrative, not a forecast.
- Workload shares are assumptions; real spend allocation varies by industry.
- CAGRs are based on general industry trends, not econometric models.
- The model does not account for vendor-specific dynamics (e.g. pricing wars).
- Regional splits are simplified and do not capture country-level variation.

## Outputs

- `data/market/assumptions.csv` — every input with type, source, rationale
- `data/market/segments_2025_2030.csv` — 120 segment rows
- `data/market/market_model.xlsx` — Excel with live formulas
- `docs/img/market_*.png` — 4 charts
- `analysis/export/market.json` — JSON for the website
