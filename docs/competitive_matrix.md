# Competitive feature-parity and positioning matrix

## Rubric

Every cell is scored on a three-point scale:

| Score | Meaning |
|---|---|
| 0 | Not offered |
| 1 | Partial, preview, or via partner/marketplace |
| 2 | Generally available and native |

Every cell has an `evidence_url` pointing to official vendor documentation, an `as_of` date, and a short note. If a cell cannot be verified, it is scored `null` with an explanation.

## Vendors

Snowflake, Databricks, Cloudera, AWS, Microsoft, Google.

## Capability groups (24 capabilities in 6 groups)

### Open table formats (3)
Iceberg read/write, Delta support, REST catalog / Polaris / Unity OSS interoperability.

### Governed catalog (6)
Fine-grained row/column access, tag/attribute-based policies, column-level lineage, cross-system lineage, data quality monitoring, semantic layer / business glossary.

### Deployment (5)
Self-managed on-prem, private cloud, multi-cloud, sovereign/air-gapped, single control plane across on-prem and cloud.

### GenAI (5)
Model serving, private LLM hosting, vector search, NL-to-SQL assistant, AI agent / MCP support.

### Data movement (2)
Streaming ingest and processing, federated query across external sources.

### Commercial (2)
Consumption pricing, committed-use/subscription options.

## Top 3 capability gaps per vendor

### Snowflake
1. **No on-prem deployment** (deployment: 0) — cloud-only, no self-managed option
2. **No cross-system lineage** (governed_catalog: 0) — lineage limited to Snowflake
3. **Limited streaming** (data_movement: 1) — Snowpipe Streaming is micro-batch

### Databricks
1. **No on-prem deployment** (deployment: 0) — cloud-only managed service
2. **No single control plane** (deployment: 0) — separate workspaces per cloud
3. **No native semantic layer** (governed_catalog: 1) — relies on partners like dbt

### Cloudera
1. **No consumption pricing** (commercial: 0) — subscription-only model
2. **No vector search** (genai: 0) — no native vector search capability
3. **No AI agent/MCP support** (genai: 0) — no agent framework

### AWS
1. **No cross-system lineage** (governed_catalog: 0) — lineage limited to AWS services
2. **No multi-cloud** (deployment: 0) — AWS-only
3. **No semantic layer** (governed_catalog: 0) — no native semantic layer

### Microsoft
1. **No on-prem for Fabric** (deployment: 0) — Fabric is cloud-only
2. **Iceberg support still in preview** (open_table_formats: 1)
3. **Data Quality in preview** (governed_catalog: 1) — Purview DQ not yet GA

### Google
1. **No on-prem deployment** (deployment: 0) — cloud-only services
2. **No single control plane** (deployment: 0) — no unified on-prem + cloud
3. **Delta support read-only** (open_table_formats: 1) — via BigLake only

## Cloudera's defensible moats and weak spots

**Moats:**
- **Deployment flexibility** (scores: on-prem 2, private cloud 2, sovereign/air-gapped 2, single control plane 2). No other vendor matches this breadth.
- **Cross-system lineage** (score: 2). Apache Atlas tracks lineage across Hive, Spark, NiFi — spanning the full data pipeline.
- **Streaming** (score: 2). Native NiFi + Kafka + Flink stack.

**Weak spots:**
- **No consumption pricing** (score: 0). Every cloud-native competitor offers pay-per-use.
- **GenAI gaps** (vector search: 0, AI agents: 0). Behind all cloud vendors.
- **No Delta Lake support** (score: 0). Limits interoperability with Databricks-originated tables.
- **Share of voice: 0.9%** of vendor-naming documents (phase-1 finding). Near-absent from public developer discussion.

## Three trends: where each vendor stands

### GenAI and AI agents
- **Leaders:** Databricks (agent framework + MCP GA), AWS (Bedrock Agents), Microsoft (Azure AI Agent Service), Google (Agent Builder)
- **Competitive:** Snowflake (Cortex Agent in preview)
- **Trailing:** Cloudera (no agent/MCP, no vector search)

### Open table formats
- **Leaders:** Databricks (Delta native + UniForm for Iceberg), Snowflake (native Iceberg + Polaris catalog), AWS (Glue + Athena Iceberg)
- **Competitive:** Cloudera (Iceberg GA), Google (BigQuery Iceberg)
- **Trailing:** Microsoft (Iceberg in preview)

### Governed catalogs
- **Leaders:** Databricks (Unity Catalog OSS), Microsoft (Purview cross-system lineage), Cloudera (Atlas cross-system lineage)
- **Competitive:** Snowflake (column lineage + DQ), Google (Dataplex DQ), AWS (Lake Formation + Glue DQ)

## Positioning map

Axes:
- **X (Deployment flexibility):** mean score of self_managed_onprem, private_cloud, multi_cloud, sovereign_airgapped, single_control_plane
- **Y (Openness / interoperability):** mean score of iceberg_read_write, delta_support, rest_catalog_interop, cross_system_lineage

Cloudera sits in the upper-right quadrant (most flexible deployment + strong openness). Cloud-native vendors (Snowflake, Databricks, AWS, Google, Microsoft) cluster in the left half (flexible on cloud, inflexible on-prem).

See `docs/img/competitive_positioning.png`.

## Outputs

- `data/competitive/vendor_features.csv` — 144 rows (24 caps × 6 vendors)
- `docs/img/competitive_heatmap.png`
- `docs/img/competitive_positioning.png`
- `analysis/export/competitive.json`
